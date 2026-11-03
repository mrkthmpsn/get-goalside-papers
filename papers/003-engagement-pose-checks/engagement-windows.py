"""Analysis script, stage 1 of 3: defender and carrier pose around every on-ball engagement, and the close engagements.

For `pose-checks-and-smoothing-on-engagements-ai.md`.

0. The engagements kept are the `on_ball_engagement`s in both matches that start in
   open play, inside a phase of play whose type for the team in possession is not
   `set_play`, and at the defending team's last line: the engaging player starts
   within 5 m of their team's last defender along the pitch
   (`delta_to_last_defensive_line_start`).
1. Every kept engagement gets a window of pose frames from
   25 before its physical start to 24 after its end frame, and the defender's and
   the ball carrier's pose is loaded for every frame of it.
2. An engagement *has pose* when both players have complete pose at its end frame
   or within two frames of it.
3. For regains (`end_type` `direct_regain` or `indirect_regain`) with pose, where the
   defender has complete pose on every frame from the start frame to the end frame,
   two series are computed on each of those frames: the distance from the nearest
   defender foot joint to the ball (3D), and the horizontal distance between the
   two players' `midHip` joints. Collapsed poses (all joints within 0.3 m) count
   as missing.
4. The *close engagements* are those where either series comes under 1 m.
5. Each defender's usual bone lengths: the median length of each of the 28 bones in
   the skeleton tree, over their *ordinary-movement* frames only (the 25 pose frames
   before the physical start of each engagement with pose, complete and uncollapsed),
   when bone lengths are expected to be most stable. Stages 2 and 3 both read these.

Writes to `outputs/` beside this file:
- `poses.npz`: `P`, joint positions (n x 29 x 3, float32), and `E`, `p90_mae_cm`
  (n x 29, float32), one row per loaded player-frame;
- `pose_index.parquet`: `k` (row in the arrays), `row`, `role` ("def"/"car"), `frame`;
- `engagements.parquet`: one row per engagement with its frames (`s`, `e`, `ps`)
  and `has_pose`;
- `regain_series.parquet` and `close_engagements.parquet`;
- `bone_medians.parquet`: `player_id`, `bone` ("parent-child"), `median_m`, and
  `frames`, the number of ordinary-movement frames behind it.

The tables are read from `goalside.data_dir()`, and need both matches' full body pose
and dynamic events converted with goalside.

    uv run python papers/003-engagement-pose-checks/engagement-windows.py
"""

from pathlib import Path

import numpy as np
import polars as pl


from goalside.skillcorner.dynamic_events import scan_dynamic_events
from goalside.skillcorner.event_types import EventType, PhaseType
from goalside.skillcorner.facing import JOINT_INDEX as J
from goalside.skillcorner.frames import pose_frame
from goalside.skillcorner.phases_of_play import scan_phases_of_play
from goalside.skillcorner.pose import scan_pose, scan_pose_frames
from goalside.skillcorner.skeleton import JOINTS

OUT = Path(__file__).parent / "outputs"
MATCH_IDS = (1925299, 1996435)  # the two matches with full body pose
# an engagement is at the last line when the engaging player starts this close to their last defender, along the pitch
LAST_LINE_M = 5.0
BEFORE, AFTER = 25, 24  # pose frames loaded before the physical start and after the end frame
FOOT_JOINTS = [J[f"{s}{j}"] for s in "lr" for j in ("Ankle", "Heel", "BigToe", "SmallToe")]
COLLAPSED_M = 0.3
CLOSE_M = 1.0
REGAINS = ("direct_regain", "indirect_regain")
ORDINARY = 25  # pose frames before the physical start that count as ordinary movement

# the skeleton from the hips outward, as (parent, child)
TREE = [("midHip", "neck"), ("neck", "nose"), ("nose", "lEye"), ("nose", "rEye"), ("lEye", "lEar"), ("rEye", "rEar"),
        ("neck", "lShoulder"), ("neck", "rShoulder"), ("lShoulder", "lElbow"), ("rShoulder", "rElbow"), ("lElbow", "lWrist"),
        ("rElbow", "rWrist"), ("lWrist", "lThumb"), ("rWrist", "rThumb"), ("lWrist", "lPinky"), ("rWrist", "rPinky"),
        ("midHip", "lHip"), ("midHip", "rHip"), ("lHip", "lKnee"), ("rHip", "rKnee"), ("lKnee", "lAnkle"), ("rKnee", "rAnkle"),
        ("lAnkle", "lHeel"), ("rAnkle", "rHeel"), ("lAnkle", "lBigToe"), ("rAnkle", "rBigToe"), ("lAnkle", "lSmallToe"),
        ("rAnkle", "rSmallToe")]


def engagements() -> pl.DataFrame:
    """The on-ball engagements in open play at the last line, with pose frames for their start (`s`), end (`e`) and physical start (`ps`)."""
    open_play = (
        scan_phases_of_play()
        .filter(pl.col("match_id").is_in(MATCH_IDS)
                & (pl.col("team_in_possession_phase_type").cast(pl.String) != PhaseType.SET_PLAY.label))
        .select(pl.col("match_id").cast(pl.Int32), "period", pl.col("frame_start").alias("phase_start"),
                pl.col("frame_end").alias("phase_end"))
        .collect()
    )
    events = (
        scan_dynamic_events()
        .filter(pl.col("match_id").is_in(MATCH_IDS) & (pl.col("event_type") == EventType.ON_BALL_ENGAGEMENT.label)
                & (pl.col("delta_to_last_defensive_line_start") <= LAST_LINE_M))
        .select(pl.col("match_id").cast(pl.Int32), "event_id", "period", "player_id",
                pl.col("player_in_possession_id").alias("carrier_id"), pl.col("end_type").cast(pl.String),
                "frame_start", "frame_end", "frame_physical_start")
        .collect()
    )
    in_open_play = events.join_where(
        open_play, pl.col("match_id") == pl.col("match_id_right"), pl.col("period") == pl.col("period_right"),
        pl.col("frame_start").is_between(pl.col("phase_start"), pl.col("phase_end")),
    ).select("match_id", "event_id").unique()
    return (
        events.join(in_open_play, on=["match_id", "event_id"], how="semi")
        .sort("match_id", "frame_start", "event_id")
        .with_columns(
            s=pose_frame(pl.col("frame_start")).cast(pl.Int32),
            e=pose_frame(pl.col("frame_end")).cast(pl.Int32),
            ps=pose_frame(pl.col("frame_physical_start").fill_null(pl.col("frame_start"))).cast(pl.Int32),
        )
        .with_row_index("row")
        .with_columns(pl.col("row").cast(pl.Int32))
    )


def load_poses(ev: pl.DataFrame) -> tuple[np.ndarray, np.ndarray, pl.DataFrame]:
    """Defender and carrier pose for every frame from `ps - BEFORE` to `e + AFTER` of each engagement."""
    frames = ev.select(
        "row", "match_id", "period", "player_id", "carrier_id",
        frame=pl.int_ranges(pl.col("ps") - BEFORE, pl.col("e") + AFTER + 1),
    ).explode("frame")
    targets = pl.concat([
        frames.select("row", "match_id", "period", "frame", pl.col("player_id").cast(pl.Int32), pl.lit("def").alias("role")),
        frames.select("row", "match_id", "period", "frame", pl.col("carrier_id").cast(pl.Int32).alias("player_id"),
                      pl.lit("car").alias("role")),
    ]).drop_nulls("player_id")
    parts = []
    for (match_id, period), group in targets.group_by(["match_id", "period"]):
        parts.append(
            scan_pose()
            .filter((pl.col("match_id") == match_id) & (pl.col("period") == period)
                    & pl.col("frame").is_in(group["frame"].unique().implode()))
            .select("frame", "player_id", pl.col("joint").cast(pl.String), "x", "y", "z", "p90_mae_cm")
            .collect()
            .join(group.select("row", "role", "player_id", "frame"), on=["player_id", "frame"])
        )
    long = pl.concat(parts).with_columns(
        j=pl.col("joint").replace_strict({name: i for i, name in enumerate(JOINTS)}, return_dtype=pl.Int32)
    )
    index = long.select("row", "role", "frame").unique().sort("row", "role", "frame").with_row_index("k")
    long = long.join(index, on=["row", "role", "frame"])
    P = np.full((index.height, 29, 3), np.nan, dtype=np.float32)
    E = np.full((index.height, 29), np.nan, dtype=np.float32)
    P[long["k"].to_numpy(), long["j"].to_numpy()] = long.select("x", "y", "z").to_numpy()
    E[long["k"].to_numpy(), long["j"].to_numpy()] = long["p90_mae_cm"].to_numpy()
    return P, E, index.with_columns(pl.col("k").cast(pl.Int64))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ev = engagements()
    P, E, index = load_poses(ev)
    complete = ~np.isnan(P).any(axis=(1, 2))
    idx = {(r, role, f): k for k, r, role, f in index.select("k", "row", "role", "frame").iter_rows()}

    def ok(row: int, role: str, f: int) -> bool:
        k = idx.get((row, role, f))
        return k is not None and bool(complete[k])

    # has pose: both players complete at the end frame or within two frames of it
    ev = ev.with_columns(has_pose=pl.Series([
        any(ok(r, "def", f) and ok(r, "car", f) for f in (e, e - 1, e + 1, e - 2, e + 2))
        for r, e in ev.select("row", "e").iter_rows()
    ]))

    def pose(row: int, role: str, f: int) -> np.ndarray | None:
        k = idx.get((row, role, f))
        if k is None or not complete[k]:
            return None
        q = P[k].astype(np.float64)
        return None if np.ptp(q, axis=0).max() < COLLAPSED_M else q

    regains = [row for row in ev.filter(pl.col("has_pose") & pl.col("end_type").is_in(REGAINS)).iter_rows(named=True)
               if all(ok(row["row"], "def", f) for f in range(row["s"], row["e"] + 1))]
    need = pl.DataFrame([(row["match_id"], row["period"], f) for row in regains for f in range(row["s"], row["e"] + 1)],
                        schema=["match_id", "period", "frame"], orient="row").unique()
    ball = (scan_pose_frames().select(pl.col("match_id").cast(pl.Int32), pl.col("period").cast(pl.Int32), "frame",
                                      pl.col("ball_data_x").alias("ball_x"), pl.col("ball_data_y").alias("ball_y"),
                                      pl.col("ball_data_z").alias("ball_z"))
            .join(need.lazy(), on=["match_id", "period", "frame"]).collect())
    B = {(m, p, f): np.array([x, y, z]) for m, p, f, x, y, z in ball.iter_rows() if x is not None}

    series = []
    for row in regains:
        for f in range(row["s"], row["e"] + 1):
            dq, cq, b = pose(row["row"], "def", f), pose(row["row"], "car", f), B.get((row["match_id"], row["period"], f))
            series.append({
                "row": row["row"], "frame": f,
                "foot_ball": min(float(np.linalg.norm(dq[j] - b)) for j in FOOT_JOINTS) if dq is not None and b is not None else None,
                "hips": float(np.linalg.norm(dq[J["midHip"], :2] - cq[J["midHip"], :2])) if dq is not None and cq is not None else None,
            })
    series = pl.DataFrame(series, schema={"row": pl.Int32, "frame": pl.Int32, "foot_ball": pl.Float64, "hips": pl.Float64})
    close = (
        series.group_by("row").agg(min_foot=pl.col("foot_ball").min(), min_hips=pl.col("hips").min())
        .filter((pl.col("min_foot") < CLOSE_M) | (pl.col("min_hips") < CLOSE_M))
        .join(ev.select("row", "match_id", "event_id", "end_type"), on="row")
        .sort("match_id", "row")
    )

    # each defender's usual bone lengths, from ordinary movement only
    lengths: dict[int, list] = {}
    for r, player_id, ps in ev.filter("has_pose").select("row", "player_id", "ps").iter_rows():
        for f in range(ps - ORDINARY, ps):
            q = pose(r, "def", f)
            if q is not None:
                lengths.setdefault(player_id, []).append([np.linalg.norm(q[J[b]] - q[J[a]]) for a, b in TREE])
    bone_medians = pl.DataFrame(
        [(player_id, f"{a}-{b}", float(m), len(v))
         for player_id, v in lengths.items() for (a, b), m in zip(TREE, np.median(np.array(v), axis=0))],
        schema={"player_id": pl.Int32, "bone": pl.String, "median_m": pl.Float64, "frames": pl.Int32}, orient="row",
    )

    np.savez_compressed(OUT / "poses.npz", P=P, E=E)
    bone_medians.write_parquet(OUT / "bone_medians.parquet")
    index.write_parquet(OUT / "pose_index.parquet")
    ev.write_parquet(OUT / "engagements.parquet")
    series.write_parquet(OUT / "regain_series.parquet")
    close.write_parquet(OUT / "close_engagements.parquet")
    print(f"{ev.height:,} engagements, {int(ev['has_pose'].sum()):,} with pose; {index.height:,} player-frames loaded")
    print(f"{len(regains)} regains with full defender pose from start to end; {close.height} close engagements:")
    print(close.group_by("end_type").len().sort("end_type"))
    frames = bone_medians.unique("player_id")["frames"]
    print(f"bone medians for {frames.len()} defenders from {frames.min()} to {frames.max()} ordinary-movement frames each")


if __name__ == "__main__":
    main()
