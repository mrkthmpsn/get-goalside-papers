"""Analysis script: camera coverage, pose coverage, and the distance between tracking and pose.

Terms, as in the paper beside this file:
- a *pose frame* is one of the pose's 25-per-second time steps, a *tracking frame*
  one of the tracking's 10-per-second time steps;
- a *pose-tracking frame* is an instant with both: every 200 ms, at tracking frame
  f = 0, 2, 4, ... and pose frame 5f/2 = 0, 5, 10, ....

For each match:

T. Timestamps: whether pose-tracking frames paired by frame arithmetic
   (`goalside.skillcorner.frames.pose_tracking_rows`) have identical timestamps in
   `skillcorner.tracking_frames` and `skillcorner.pose_frames`, what a join on timestamps instead would find, and which pose frames
   repeat a timestamp.
0. Tracking: the share of tracking player-frames the camera detected, by period, and
   the frames that list no players (count, gaps of consecutive such frames, longest and
   median gap), with the share of them that have a ball, a camera view and a phase of
   play, how many gaps start after an on-ball event that ends in a stoppage, and how
   many distinct stoppages are followed by a gap before play restarts.
1. Pose coverage: of the detected player-frames at pose-tracking frames, and of all
   tracking player-frames there, the share with pose (a `midHip` row in the `pose` table),
   and where the pose player-frames with extrapolated or no tracking fall.
2. Tracking-pose distance: for player-frames at pose-tracking frames with both, the
   horizontal distance between tracking `x`/`y` and pose `midHip`, overall, for
   detected positions, and by the player's tracking speed, with `midHip`'s error radius.

Results are printed and written to `outputs/tracking_pose_coverage.json` beside this file.
The tables are read from `goalside.data_dir()`, and need both matches' tracking,
full body pose, dynamic events, phases of play and `match.json` converted with goalside.

    uv run python papers/001-tracking-pose-coverage/tracking-pose-coverage.py
"""

import json
from pathlib import Path

import polars as pl

from goalside.skillcorner.constants import POSE_FPS, TRACKING_FPS
from goalside.skillcorner.dynamic_events import scan_dynamic_events
from goalside.skillcorner.frames import pose_tracking_rows
from goalside.skillcorner.match import scan_match_periods
from goalside.skillcorner.phases_of_play import scan_phases_of_play
from goalside.skillcorner.pose import scan_pose, scan_pose_frames
from goalside.skillcorner.tracking import scan_tracking, scan_tracking_frames

MATCH_IDS = (1925299, 1996435)
QUANTILES = (0.5, 0.75, 0.9, 0.95, 0.99)


def quantiles(series: pl.Series) -> dict[str, float]:
    return {f"p{int(q * 100)}": round(float(series.quantile(q)), 3) for q in QUANTILES}


def tracking_with_speed(match_id: int) -> pl.DataFrame:
    """Tracking rows for one match, with each player's speed over the frames either side."""
    return (
        scan_tracking().filter(pl.col("match_id") == match_id)
        .select("period", "frame", "player_id", "x", "y", "is_detected")
        .collect()
        .sort("period", "player_id", "frame")
        .with_columns(
            speed=(
                ((pl.col("x").shift(-1) - pl.col("x").shift(1)) ** 2
                 + (pl.col("y").shift(-1) - pl.col("y").shift(1)) ** 2).sqrt()
                * TRACKING_FPS / 2
            ).over("period", "player_id"),
            gap=(pl.col("frame").shift(-1) - pl.col("frame").shift(1)).over("period", "player_id"),
        )
        # speed only where both neighbouring frames exist
        .with_columns(speed=pl.when(pl.col("gap") == 2).then(pl.col("speed")))
        .drop("gap")
    )


def frames_without_players(match_id: int, tracking: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """The tracking frames with and without players, and the gaps: runs of consecutive frames without players."""
    frames = (scan_tracking_frames().filter(pl.col("match_id") == match_id)
              .select("period", "frame", "ball_data_x", "image_corners_projection_x_top_left").collect())
    with_players = tracking.select("period", "frame").unique()
    full = frames.join(with_players, on=["period", "frame"], how="semi")
    empty = (
        frames.join(with_players, on=["period", "frame"], how="anti").sort("period", "frame")
        # a new gap starts where the previous frame without players is not the frame before
        .with_columns(gap=(pl.col("frame").diff().over("period") != 1).fill_null(True).cum_sum())
    )
    gaps = empty.group_by("gap").agg(start=pl.col("frame").min(), end=pl.col("frame").max(), frames=pl.len()).sort("start")
    return frames, full, empty, gaps


def tracking_summary(match_id: int, tracking: pl.DataFrame) -> dict:
    """Detected share by period, the frames listing no players, and the stoppages before their gaps."""
    by_period = (
        tracking.group_by("period")
        .agg(player_frames=pl.len(), detected=pl.col("is_detected").sum())
        .sort("period")
    )
    frames, full, empty, gaps = frames_without_players(match_id, tracking)
    players_per_frame = tracking.group_by("period", "frame").len()["len"]
    phases = scan_phases_of_play().filter(pl.col("match_id") == match_id).select("frame_start", "frame_end").collect()

    def share_in_a_phase(rows: pl.DataFrame) -> float:
        inside = rows.join_where(phases, pl.col("frame").is_between(pl.col("frame_start"), pl.col("frame_end")))
        return round(inside.select("frame").n_unique() / rows.height, 4)

    on_ball = (
        scan_dynamic_events()
        .filter((pl.col("match_id") == match_id)
                & pl.col("event_type").cast(pl.String).is_in(["player_possession", "on_ball_engagement"]))
        .select("frame_start", "frame_end", pl.col("game_interruption_after").cast(pl.String))
        .collect()
    )
    # the last on-ball event (possession or engagement) to end before each gap, and the stoppage it records
    before = gaps.join_asof(on_ball.sort("frame_end"), left_on="start", right_on="frame_end")
    after_stoppage = before.filter(pl.col("game_interruption_after").is_not_null())
    # one stoppage per restart: the stoppage events that end before the same next on-ball event are one stoppage,
    # which a possession and an engagement can both record
    restarts = on_ball.select(pl.col("frame_start").alias("restart")).sort("restart")
    stoppages = (
        on_ball.filter(pl.col("game_interruption_after").is_not_null()).sort("frame_end")
        .join_asof(restarts, left_on="frame_end", right_on="restart", strategy="forward", allow_exact_matches=False)
        .group_by("restart")
        .agg(end=pl.col("frame_end").max(),
             kind=pl.col("game_interruption_after").first().str.replace("_for|_against", ""))
    )
    followed = stoppages.join_where(
        gaps, pl.col("start") >= pl.col("end"), (pl.col("start") < pl.col("restart")) | pl.col("restart").is_null(),
    ).select("restart").unique()
    stoppages = stoppages.with_columns(followed_by_a_gap=pl.col("restart").is_in(followed["restart"].implode()))
    by_kind = stoppages.group_by("kind").agg(stoppages=pl.len(), followed_by_a_gap=pl.col("followed_by_a_gap").sum())
    return {
        "frames": frames.height,
        "players_per_frame_with_players": sorted(players_per_frame.unique().to_list()),
        "frames_without_players": empty.height,
        "gaps": gaps.height,
        "longest_gap_frames": int(gaps["frames"].max()) if gaps.height else 0,
        "median_gap_frames": float(gaps["frames"].median()) if gaps.height else 0.0,
        "frames_without_players_ball_null_share": round(float(empty["ball_data_x"].is_null().mean()), 4),
        "frames_with_players_ball_null_share": round(float(full["ball_data_x"].is_null().mean()), 4),
        "frames_with_players": full.height,
        "frames_without_players_camera_view_null_share": round(
            float(empty["image_corners_projection_x_top_left"].is_null().mean()), 4),
        "frames_with_players_camera_view_null_share": round(
            float(full["image_corners_projection_x_top_left"].is_null().mean()), 4),
        "frames_without_players_in_a_phase_share": share_in_a_phase(empty),
        "frames_with_players_in_a_phase_share": share_in_a_phase(full),
        "gaps_after_a_stoppage": after_stoppage.height,
        "median_seconds_from_stoppage_to_gap": round(
            float(((after_stoppage["start"] - after_stoppage["frame_end"]) / TRACKING_FPS).median()), 1),
        "gaps_by_stoppage": dict(
            after_stoppage.group_by("game_interruption_after").len().sort("game_interruption_after").iter_rows()),
        "stoppage_events": int(on_ball["game_interruption_after"].is_not_null().sum()),
        "stoppages": stoppages.height,
        "stoppages_followed_by_a_gap": int(stoppages["followed_by_a_gap"].sum()),
        "stoppages_by_kind": {k: {"stoppages": n, "followed_by_a_gap": f}
                              for k, n, f in by_kind.sort("kind").iter_rows()},
        "player_frames": int(by_period["player_frames"].sum()),
        "detected_share": round(float(by_period["detected"].sum() / by_period["player_frames"].sum()), 4),
        "detected_share_by_period": {
            str(p): round(d / n, 4) for p, n, d in by_period.select("period", "player_frames", "detected").iter_rows()
        },
    }


def frame_timestamps(match_id: int) -> dict:
    """Pose-tracking pairs against both sources' timestamps, and repeated pose timestamps."""
    tracking = (scan_tracking_frames().filter(pl.col("match_id") == match_id)
                .select(pl.col("period").cast(pl.Int32), "frame", "timestamp").collect())
    pose = (scan_pose_frames().filter(pl.col("match_id") == match_id)
            .select(pl.col("period").cast(pl.Int32), pl.col("frame").alias("pose_frame"),
                    pl.col("timestamp").alias("pose_timestamp")).collect())
    paired = pose_tracking_rows(tracking).join(pose, on=["period", "pose_frame"], how="left")
    by_clock = tracking.join(pose, left_on=["period", "timestamp"], right_on=["period", "pose_timestamp"], how="inner")
    repeats = pose.filter(pl.col("pose_timestamp").is_duplicated().over("period")).sort("period", "pose_frame")
    periods = scan_match_periods().filter(pl.col("match_id") == match_id).select("period", "end_frame").collect()
    ends = {p: end_frame * POSE_FPS / TRACKING_FPS for p, end_frame in periods.iter_rows()}
    return {
        "pairs": paired.height,
        "pairs_with_pose_frame": int(paired["pose_timestamp"].is_not_null().sum()),
        "pairs_with_equal_timestamps": int((paired["pose_timestamp"] == paired["timestamp"]).sum()),
        "timestamp_join_rows": by_clock.height,
        "timestamp_join_tracking_frames": by_clock.select("period", "frame").n_unique(),
        "timestamp_join_odd_tracking_frames": by_clock.filter(pl.col("frame") % 2 == 1).height,
        "timestamp_join_pairs_differing_from_arithmetic": by_clock.filter(
            pl.col("pose_frame") != pl.col("frame") * POSE_FPS // TRACKING_FPS).height,
        "pose_frames_repeating_a_timestamp": [
            {"period": p, "pose_frame": f, "timestamp_s": ts.total_seconds(), "past_period_end": f > ends[p]}
            for p, f, ts in repeats.iter_rows()
        ],
    }


def coverage_and_distance(match_id: int, tracking: pl.DataFrame) -> dict:
    at_pt = pose_tracking_rows(tracking)
    _, _, empty, gaps = frames_without_players(match_id, tracking)
    mid_hip = (
        scan_pose()
        .filter((pl.col("match_id") == match_id) & (pl.col("joint") == "midHip"))
        .select(pl.col("period").cast(pl.Int32), pl.col("frame").alias("pose_frame"), "player_id",
                pl.col("x").alias("pose_x"), pl.col("y").alias("pose_y"), "p90_mae_cm")
        .collect()
    )
    pose_at_pt = mid_hip.filter(pl.col("pose_frame") % 5 == 0)  # pose player-frames at pose-tracking frames
    keys = ["period", "pose_frame", "player_id"]
    joined = at_pt.join(mid_hip, on=keys, how="left").with_columns(
        has_pose=pl.col("pose_x").is_not_null(),
        distance=((pl.col("x") - pl.col("pose_x")) ** 2 + (pl.col("y") - pl.col("pose_y")) ** 2).sqrt(),
    )
    detected = joined.filter("is_detected")
    posed = joined.filter("has_pose")
    posed_detected = posed.filter("is_detected")
    # pose player-frames with no tracking row: where they fall in the gap of frames without players
    no_row = (
        pose_at_pt.join(at_pt.select(keys), on=keys, how="anti")
        .with_columns(frame=(pl.col("pose_frame") // 5 * 2).cast(pl.Int32))
        .join(empty.select("frame", "gap"), on="frame", how="left")
        .join(gaps, on="gap", how="left")
        .with_columns(frames_to_gap_edge=pl.min_horizontal(pl.col("frame") - pl.col("start"), pl.col("end") - pl.col("frame")))
    )
    # pose player-frames meeting extrapolated tracking: frames to that player's nearest detected tracking frame
    detected_frames = (tracking.filter("is_detected").select("period", "player_id", pl.col("frame").alias("detected_frame"))
                       .sort("detected_frame"))
    extrapolated_with_pose = (
        joined.filter(~pl.col("is_detected") & pl.col("has_pose")).select("period", "player_id", "frame").sort("frame")
        .join_asof(detected_frames, left_on="frame", right_on="detected_frame", by=["period", "player_id"], strategy="nearest")
        .with_columns(frames_to_detected=(pl.col("frame") - pl.col("detected_frame")).abs())
    )
    out = {
        "tracking_player_frames_at_pose_tracking_frames": joined.height,
        "detected": detected.height,
        "detected_with_pose": int(detected["has_pose"].sum()),
        "coverage_of_detected": round(float(detected["has_pose"].mean()), 4),
        "with_pose": int(joined["has_pose"].sum()),
        "coverage_of_all": round(float(joined["has_pose"].mean()), 4),
        "pose_player_frames_at_pose_tracking_frames": pose_at_pt.height,
        "pose_with_extrapolated_tracking": int(joined.filter(~pl.col("is_detected"))["has_pose"].sum()),
        "pose_without_tracking_row": no_row.height,
        "pose_without_tracking_row_inside_a_gap": int(no_row["gap"].is_not_null().sum()),
        "pose_without_tracking_row_median_frames_to_gap_edge": no_row["frames_to_gap_edge"].median(),
        "pose_with_extrapolated_tracking_median_frames_to_detected": extrapolated_with_pose["frames_to_detected"].median(),
        "pose_with_extrapolated_tracking_within_2_frames_of_detected": int(
            (extrapolated_with_pose["frames_to_detected"] <= 2).sum()),
        "mid_hip_error_radius_cm": quantiles(pose_at_pt["p90_mae_cm"]),
        "distance_m": quantiles(posed["distance"]),
        "distance_m_detected": quantiles(posed.filter("is_detected")["distance"]),
        "share_within_0_5m": round(float((posed["distance"] < 0.5).mean()), 4),
        "share_over_1m": round(float((posed["distance"] > 1).mean()), 4),
        "share_within_0_5m_detected": round(float((posed_detected["distance"] < 0.5).mean()), 4),
        "share_over_1m_detected": round(float((posed_detected["distance"] > 1).mean()), 4),
    }
    by_speed = (
        posed.drop_nulls("speed")
        .with_columns(band=pl.col("speed").cut([2, 4, 6], labels=["0-2", "2-4", "4-6", "6+"]))
        .group_by("band")
        .agg(n=pl.len(), median=pl.col("distance").median(), p90=pl.col("distance").quantile(0.9))
        .sort("band")
    )
    out["distance_by_speed_m_s"] = {
        str(b): {"n": n, "median": round(m, 3), "p90": round(p, 3)} for b, n, m, p in by_speed.iter_rows()
    }
    return out


def main() -> None:
    result = {}
    for match_id in MATCH_IDS:
        tracking = tracking_with_speed(match_id)
        result[str(match_id)] = {
            "timestamps": frame_timestamps(match_id),
            "tracking": tracking_summary(match_id, tracking),
            "coverage": coverage_and_distance(match_id, tracking),
        }
        print(match_id, json.dumps(result[str(match_id)], indent=2))
    out = Path(__file__).parent / "outputs" / "tracking_pose_coverage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("written", out)


if __name__ == "__main__":
    main()
