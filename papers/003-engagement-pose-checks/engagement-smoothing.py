"""Analysis script, stage 3 of 3: how far smoothing and a bone-length fit go towards a consistent pose.

For `pose-checks-and-smoothing-on-engagements-ai.md`. Needs stage 1
(`engagement-windows.py`) to have run.

On the same two sets of defender frames as stage 2 (close engagement frames and
ordinary movement), each joint coordinate is replaced by a Savitzky-Golay fit: a
quadratic fitted by least squares over the frame and three either side, evaluated
at the centre. A second step then fits the skeleton to fixed bone lengths, walking
out from `midHip` and moving each joint along its bone so the bone takes that
player's usual length, from stage 1 (the median over ordinary-movement frames).
Raw, smoothed and fitted poses are compared, on frames
whose whole seven-frame window has complete, uncollapsed pose, on:
- the largest second difference of a limb joint's position relative to `midHip`;
- the largest second difference of a knee angle;
- the largest relative difference of a limb bone from the player's median;
- how far each joint moves from its raw position, by body part and distance to the carrier.

Writes `outputs/smooth_frames.parquet` and `smoothing.json`.

    uv run python papers/003-engagement-pose-checks/engagement-smoothing.py
"""

import json
from pathlib import Path

import numpy as np
import polars as pl

from goalside.skillcorner.constants import POSE_FPS
from goalside.skillcorner.facing import JOINT_INDEX as J

OUT = Path(__file__).parent / "outputs"
COLLAPSED_M = 0.3
M = 3  # frames either side of the fitted frame
SG = np.linalg.pinv(np.vander(np.arange(-M, M + 1), 3, increasing=True))[0]  # weights for the fitted centre value

# the skeleton from the hips outward, as (parent, child)
TREE = [("midHip", "neck"), ("neck", "nose"), ("nose", "lEye"), ("nose", "rEye"), ("lEye", "lEar"), ("rEye", "rEar"),
        ("neck", "lShoulder"), ("neck", "rShoulder"), ("lShoulder", "lElbow"), ("rShoulder", "rElbow"), ("lElbow", "lWrist"),
        ("rElbow", "rWrist"), ("lWrist", "lThumb"), ("rWrist", "rThumb"), ("lWrist", "lPinky"), ("rWrist", "rPinky"),
        ("midHip", "lHip"), ("midHip", "rHip"), ("lHip", "lKnee"), ("rHip", "rKnee"), ("lKnee", "lAnkle"), ("rKnee", "rAnkle"),
        ("lAnkle", "lHeel"), ("rAnkle", "rHeel"), ("lAnkle", "lBigToe"), ("rAnkle", "rBigToe"), ("lAnkle", "lSmallToe"),
        ("rAnkle", "rSmallToe")]
TI = [(J[a], J[b]) for a, b in TREE]
LIMB = [J[f"{s}{j}"] for s in "lr" for j in ("Knee", "Ankle", "Elbow", "Wrist", "BigToe", "Heel")]
# knee angles only, as in stage 2
ANG = [tuple(J[f"{s}{x}"] for x in ("Hip", "Knee", "Ankle")) for s in "lr"]
CHECK_BONES = [(J[f"{s}{a}"], J[f"{s}{b}"]) for s in "lr" for a, b in (("Hip", "Knee"), ("Knee", "Ankle"), ("Shoulder", "Elbow"), ("Elbow", "Wrist"))]
PART = {**{j: "head" for j in ("nose", "lEye", "rEye", "lEar", "rEar")},
        **{j: "trunk" for j in ("neck", "lShoulder", "rShoulder", "midHip", "lHip", "rHip")},
        **{j: "knees, elbows" for j in ("lKnee", "rKnee", "lElbow", "rElbow")},
        **{j: "ankles, wrists" for j in ("lAnkle", "rAnkle", "lWrist", "rWrist")},
        **{j: "feet, hands" for j in ("lHeel", "rHeel", "lBigToe", "rBigToe", "lSmallToe", "rSmallToe", "lThumb", "rThumb",
                                      "lPinky", "rPinky")}}
PARTS = sorted(set(PART.values()))


def ang(x: np.ndarray, a: int, b: int, c: int) -> float:
    u, v = x[a] - x[b], x[c] - x[b]
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9), -1, 1))))


def measures(seq: list, i: int) -> tuple[float, float]:
    """The largest limb-joint second difference (m/s²) and knee angle second difference (degrees, per frame step) at position i."""
    rel = [x - x[J["midHip"]] for x in seq[i - 1: i + 2]]
    zz = float(np.max(np.linalg.norm(rel[2][LIMB] - 2 * rel[1][LIMB] + rel[0][LIMB], axis=1))) * POSE_FPS**2
    za = max(abs(ang(seq[i + 1], *t) - 2 * ang(seq[i], *t) + ang(seq[i - 1], *t)) for t in ANG)
    return zz, za


def main() -> None:
    arrays = np.load(OUT / "poses.npz")
    P = arrays["P"].astype(np.float64)
    index = pl.read_parquet(OUT / "pose_index.parquet")
    idx = {(r, role, f): k for k, r, role, f in index.select("k", "row", "role", "frame").iter_rows()}
    complete = ~np.isnan(P).any(axis=(1, 2))
    every = pl.read_parquet(OUT / "engagements.parquet")
    ev = every.filter("has_pose")
    close = set(pl.read_parquet(OUT / "close_engagements.parquet")["row"].to_list())
    ok = lambda k: k is not None and complete[k] and np.ptp(P[k], axis=0).max() >= COLLAPSED_M

    # each defender's usual length for every bone in the tree, from ordinary movement (stage 1)
    medians = pl.read_parquet(OUT / "bone_medians.parquet")
    by_bone = {(p, bone): m for p, bone, m in medians.select("player_id", "bone", "median_m").iter_rows()}
    med_len = {p: np.array([by_bone[(p, f"{a}-{b}")] for a, b in TREE]) for p in medians["player_id"].unique().to_list()}

    def fit_bones(x: np.ndarray, p: int) -> np.ndarray:
        y = x.copy()
        for (a, b), length in zip(TI, med_len[p]):
            v = x[b] - x[a]
            y[b] = y[a] + v / (np.linalg.norm(v) + 1e-9) * length
        return y

    out = []
    for row in ev.iter_rows(named=True):
        r, p = row["row"], row["player_id"]
        windows = [("ordinary", range(row["ps"] - 25, row["ps"]))]
        if r in close:
            windows.append(("close", range(row["s"] - 25, row["e"] + 25)))
        for which, frames in windows:
            frames = list(frames)
            raw = [P[k] if ok(k) else None for k in (idx.get((r, "def", f)) for f in frames)]
            smooth = [None] * len(frames)
            for i in range(M, len(frames) - M):
                block = raw[i - M: i + M + 1]
                if all(b is not None for b in block):
                    smooth[i] = np.tensordot(SG, np.stack(block), axes=1)
            fitted = [fit_bones(x, p) if x is not None else None for x in smooth]
            for i in range(1, len(frames) - 1):
                if smooth[i - 1] is None or smooth[i] is None or smooth[i + 1] is None:
                    continue
                kc = idx.get((r, "car", frames[i]))
                dist = float(np.linalg.norm(raw[i][J["midHip"], :2] - P[kc][J["midHip"], :2])) if ok(kc) else None
                rec = {"set": which, "row": r, "frame": frames[i], "car_dist": dist}
                for name, seq in (("raw", raw), ("smooth", smooth), ("fit", fitted)):
                    zz, za = measures(seq, i)
                    bones = np.array([np.linalg.norm(seq[i][b] - seq[i][a]) for a, b in CHECK_BONES])
                    medians = np.array([med_len[p][TI.index((a, b))] for a, b in CHECK_BONES])
                    rec |= {f"{name}_zz": zz, f"{name}_za": za, f"{name}_bone": float(np.max(np.abs(bones / medians - 1)))}
                for name, seq in (("smooth", smooth), ("fit", fitted)):
                    moved = np.linalg.norm(seq[i] - raw[i], axis=1) * 100
                    for part in PARTS:
                        rec[f"{name}_moved_{part}"] = float(np.median([moved[J[j]] for j, pp in PART.items() if pp == part]))
                out.append(rec)
    df = pl.DataFrame(out, infer_schema_length=None)
    df.write_parquet(OUT / "smooth_frames.parquet")

    band = df.with_columns(band=pl.when(pl.col("car_dist") < 1).then(pl.lit("under 1 m"))
                           .when(pl.col("car_dist") < 2).then(pl.lit("1-2 m"))
                           .when(pl.col("car_dist") < 4).then(pl.lit("2-4 m"))
                           .when(pl.col("car_dist").is_not_null()).then(pl.lit("4 m or more"))
                           .otherwise(pl.lit("no carrier pose")))
    result = {
        "frames": {s: n for s, n in df.group_by("set").len().iter_rows()},
        "second_differences_and_bones": {
            name: {m: {"median": round(float(df[f"{name}_{m}"].median()), 4), "p99": round(float(df[f"{name}_{m}"].quantile(0.99)), 4)}
                   for m in ("zz", "za", "bone")}
            for name in ("raw", "smooth", "fit")
        },
        "moved_cm_by_distance": {
            name: {b: {part: round(v, 1) for part, v in zip(PARTS, vals)} for b, *vals in
                   band.group_by("band").agg(*[pl.col(f"{name}_moved_{part}").median() for part in PARTS]).iter_rows()}
            for name in ("smooth", "fit")
        },
        "second_difference_by_distance": {
            b: {"raw_median": round(a, 3), "smooth_median": round(s, 3), "raw_p99": round(rp, 3), "smooth_p99": round(sp, 3)}
            for b, a, s, rp, sp in band.group_by("band").agg(
                pl.col("raw_zz").median().alias("raw"), pl.col("smooth_zz").median().alias("smooth"),
                pl.col("raw_zz").quantile(0.99).alias("raw_p99"), pl.col("smooth_zz").quantile(0.99).alias("smooth_p99"),
            ).iter_rows()
        },
    }
    (OUT / "smoothing.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
