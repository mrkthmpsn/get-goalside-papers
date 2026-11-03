"""Analysis script, stage 2 of 3: ten pose checks on the defender, and every results table in the paper.

For `pose-checks-and-smoothing-on-engagements-ai.md`. Needs stage 1
(`engagement-windows.py`) to have run.

Each defender's usual bone lengths come from stage 1, which takes them from
ordinary-movement frames only. Two sets of defender frames are checked:
- *close engagement frames*: for each of stage 1's 24 close engagements
  (`close_engagements.parquet`), the pose frames from 25 before the start frame to
  24 after the end frame;
- *ordinary movement*: for every engagement with pose, the 25 pose frames before
  its physical start.

A frame in both sets (an engagement whose physical start is within 25 frames of
its start) is counted in each.

Writes `outputs/quality_frames.parquet` (one row per
checked frame) and `pose_checks.json` (every table in sections 4.1 to 4.4).

    uv run python papers/003-engagement-pose-checks/engagement-pose-checks.py
"""

import json
from pathlib import Path

import numpy as np
import polars as pl

from goalside.skillcorner.constants import POSE_FPS
from goalside.skillcorner.facing import JOINT_INDEX as J

OUT = Path(__file__).parent / "outputs"
COLLAPSED_M = 0.3

BONES = [(f"{s}{a}", f"{s}{b}") for s in "lr" for a, b in (("Hip", "Knee"), ("Knee", "Ankle"), ("Shoulder", "Elbow"), ("Elbow", "Wrist"))]
# knee angles only: the joint football analysis uses
ANGLES = [(f"{s}Hip", f"{s}Knee", f"{s}Ankle") for s in "lr"]
LIMB_JOINTS = [J[f"{s}{j}"] for s in "lr" for j in ("Knee", "Ankle", "Elbow", "Wrist", "BigToe", "Heel")]
# second_difference_pos measures the size of a change of velocity, in m/s² as in the tracking smoothness paper;
# second_difference_ang is the knee angle's second difference per frame step, in degrees, before dividing by time;
# the zigzags require a change of direction
CONTINUOUS = ["bone_dev", "jump", "second_difference_pos", "second_difference_ang", "position_zigzag", "err_rel"]
YES_NO = ["angle_zigzag", "out_of_range", "swap", "collapsed"]


def angle(q: np.ndarray, a: str, b: str, c: str) -> float:
    """The angle at joint `b` between the bones to `a` and `c`, in degrees (180 = straight)."""
    u, v = q[J[a]] - q[J[b]], q[J[c]] - q[J[b]]
    return float(np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9), -1, 1))))


def window_frames(P, E, idx, complete, bone_med, row, player, frames, which):
    """One record per defender frame in `frames` with a complete pose."""
    out = []
    ks = [idx.get((row, "def", f)) for f in frames]
    ks = [k if k is not None and complete[k] else None for k in ks]
    ok = lambda k: k is not None and np.ptp(P[k], axis=0).max() >= COLLAPSED_M
    rel = lambda k: P[k] - P[k][J["midHip"]]
    for i, f in enumerate(frames):
        k = ks[i]
        if k is None:
            continue
        q = P[k]
        rec = {"row": row, "frame": f, "set": which, "player_id": player, "err": float(np.nanmean(E[k]))}
        rec["collapsed"] = bool(np.ptp(q, axis=0).max() < COLLAPSED_M)
        if rec["collapsed"]:
            out.append(rec)
            continue
        lens = np.array([np.linalg.norm(q[J[a]] - q[J[b]]) for a, b in BONES])
        rec["bone_dev"] = float(np.max(np.abs(lens / bone_med[player] - 1)))
        angs = np.array([angle(q, *t) for t in ANGLES])
        rec["out_of_range"] = bool((angs < 40).any())
        kp = ks[i - 1] if i > 0 else None
        kn = ks[i + 1] if i + 1 < len(ks) else None
        if ok(kp):
            rec["jump"] = float(np.max(np.linalg.norm(rel(k)[LIMB_JOINTS] - rel(kp)[LIMB_JOINTS], axis=1)) * POSE_FPS)
            same = cross = 0.0
            for joint in ("Knee", "Ankle"):
                lt, rt, lp, rp = P[k][J["l" + joint]], P[k][J["r" + joint]], P[kp][J["l" + joint]], P[kp][J["r" + joint]]
                same += np.linalg.norm(lt - lp) + np.linalg.norm(rt - rp)
                cross += np.linalg.norm(lt - rp) + np.linalg.norm(rt - lp)
            rec["swap"] = bool(same > 0.4 and cross < 0.5 * same)
        if ok(kp) and ok(kn):
            rec["second_difference_pos"] = float(np.max(np.linalg.norm(rel(kn)[LIMB_JOINTS] - 2 * rel(k)[LIMB_JOINTS] + rel(kp)[LIMB_JOINTS], axis=1)) * POSE_FPS**2)
            # a joint zigzags when its moves into and out of the frame point more than 90 degrees apart;
            # its size is the shorter of the two moves
            move_in = rel(k)[LIMB_JOINTS] - rel(kp)[LIMB_JOINTS]
            move_out = rel(kn)[LIMB_JOINTS] - rel(k)[LIMB_JOINTS]
            turns_back = (move_in * move_out).sum(axis=1) < 0
            shorter = np.minimum(np.linalg.norm(move_in, axis=1), np.linalg.norm(move_out, axis=1))
            rec["position_zigzag"] = float(np.max(np.where(turns_back, shorter, 0.0)))
            before = np.array([angle(P[kp], *t) for t in ANGLES])
            after = np.array([angle(P[kn], *t) for t in ANGLES])
            rec["second_difference_ang"] = float(np.max(np.abs(after - 2 * angs + before)))
            d1, d2 = angs - before, after - angs
            rec["angle_zigzag"] = bool(((np.sign(d1) != np.sign(d2)) & (np.abs(d1) > 15) & (np.abs(d2) > 15)).any())
        out.append(rec)
    return out


def main() -> None:
    arrays = np.load(OUT / "poses.npz")
    P, E = arrays["P"].astype(np.float64), arrays["E"].astype(np.float64)
    index = pl.read_parquet(OUT / "pose_index.parquet")
    idx = {(r, role, f): k for k, r, role, f in index.select("k", "row", "role", "frame").iter_rows()}
    complete = ~np.isnan(P).any(axis=(1, 2))
    ev = pl.read_parquet(OUT / "engagements.parquet").filter("has_pose")
    player = dict(zip(ev["row"], ev["player_id"]))

    # each defender's usual limb-bone lengths, from ordinary movement (stage 1)
    medians = pl.read_parquet(OUT / "bone_medians.parquet")
    by_bone = {(p, bone): m for p, bone, m in medians.select("player_id", "bone", "median_m").iter_rows()}
    bone_med = {p: np.array([by_bone[(p, f"{a}-{b}")] for a, b in BONES]) for p in medians["player_id"].unique().to_list()}

    close = set(pl.read_parquet(OUT / "close_engagements.parquet")["row"].to_list())

    recs = []
    for row in ev.iter_rows(named=True):
        r = row["row"]
        if r in close:
            recs += window_frames(P, E, idx, complete, bone_med, r, player[r], list(range(row["s"] - 25, row["e"] + 25)), "close")
        recs += window_frames(P, E, idx, complete, bone_med, r, player[r], list(range(row["ps"] - 25, row["ps"])), "baseline")
    df = pl.DataFrame(recs, infer_schema_length=None)
    df = df.join(df.group_by("player_id").agg(err_med=pl.col("err").median()), on="player_id").with_columns(
        err_rel=pl.col("err") / pl.col("err_med"),
        grp=pl.when(pl.col("set") == "baseline").then(pl.lit("ordinary")).otherwise(pl.lit("close")),
    )

    # distance to the carrier, for frames where both players have complete pose
    dist = []
    for r, f in df.select("row", "frame").iter_rows():
        a, b = idx.get((r, "def", f)), idx.get((r, "car", f))
        ok = a is not None and b is not None and complete[a] and complete[b]
        dist.append(float(np.linalg.norm(P[a][J["midHip"], :2] - P[b][J["midHip"], :2])) if ok else None)
    df = df.with_columns(car_dist=pl.Series(dist, dtype=pl.Float64))
    df.write_parquet(OUT / "quality_frames.parquet")

    result: dict = {"frames": {g: int(n) for g, n in df.group_by("set").len().iter_rows()},
                    "engagements": {g: int(n) for g, n in df.group_by("set").agg(pl.col("row").n_unique()).iter_rows()}}

    # 4.1: medians and thresholds (99th percentile of ordinary movement)
    ordinary = df.filter(pl.col("grp") == "ordinary")
    th = {k: float(ordinary[k].quantile(0.99)) for k in CONTINUOUS}
    result["thresholds"] = th
    result["medians"] = {g: {k: float(df.filter(pl.col("grp") == g)[k].median()) for k in CONTINUOUS} for g in ("ordinary", "close")}

    # 4.2 and 4.6: share of frames flagged
    flags = df.with_columns(
        **{f"f_{k}": (pl.col(k) > th[k]).fill_null(False) for k in CONTINUOUS},
        **{f"f_{k}": pl.col(k).fill_null(False) for k in YES_NO},
    )
    names = [f"f_{k}" for k in CONTINUOUS + YES_NO]
    flags = flags.with_columns(f_any=pl.any_horizontal(names))
    names.append("f_any")
    result["flag_rate_by_grp"] = {
        g: {n[2:]: round(float(s[n].mean()) * 100, 2) for n in names} for (g,), s in flags.group_by("grp")
    }

    # 4.3: the error estimate against the other checks, on uncollapsed frames
    unc = df.filter(~pl.col("collapsed"))
    result["spearman_with_error_estimate"] = {
        k: round(float(unc.select(pl.corr("err_rel", k, method="spearman")).item()), 3)
        for k in ("bone_dev", "second_difference_pos", "second_difference_ang", "position_zigzag", "jump")
    }
    z = unc.with_columns(
        zz=(pl.col("second_difference_ang") > th["second_difference_ang"])
        | (pl.col("second_difference_pos") > th["second_difference_pos"]),
        pz=pl.col("position_zigzag") > th["position_zigzag"],
        ee=pl.col("err_rel") > th["err_rel"],
        bb=pl.col("bone_dev") > th["bone_dev"],
    )
    result["overlap"] = {
        "second_difference_flagged": int(z["zz"].sum()),
        "of_those_error_estimate_flagged": round(float(z.filter("zz")["ee"].mean()), 4),
        "error_estimate_flagged": int(z["ee"].sum()),
        "of_those_second_difference_flagged": round(float(z.filter("ee")["zz"].mean()), 4),
        "position_zigzag_flagged": int(z["pz"].sum()),
        "of_those_position_zigzag_error_estimate_flagged": round(float(z.filter("pz")["ee"].mean()), 4),
    }

    # 4.4: by distance to the carrier
    bands = z.drop_nulls("car_dist").with_columns(
        band=pl.when(pl.col("car_dist") < 1).then(pl.lit("under 1 m")).when(pl.col("car_dist") < 2).then(pl.lit("1-2 m"))
        .when(pl.col("car_dist") < 4).then(pl.lit("2-4 m")).otherwise(pl.lit("4 m or more"))
    )
    result["by_distance_to_carrier"] = {
        b: {"frames": n, "second_difference": round(zz * 100, 1), "position_zigzag": round(pz * 100, 1),
            "error_estimate": round(ee * 100, 1), "bone_length": round(bb * 100, 1), "angle_zigzag": round(az * 100, 1)}
        for b, n, zz, pz, ee, bb, az in bands.group_by("band").agg(
            pl.len(), pl.col("zz").mean(), pl.col("pz").fill_null(False).mean(), pl.col("ee").mean(), pl.col("bb").mean(),
            pl.col("angle_zigzag").fill_null(False).mean(),
        ).iter_rows()
    }

    (OUT / "pose_checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
