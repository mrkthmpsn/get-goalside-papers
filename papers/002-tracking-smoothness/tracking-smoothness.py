"""Analysis script: how smooth SkillCorner's tracking positions and body pose are from one frame to the next.

Terms, as in the paper beside this file. Over every tracking player-frame of every
match with tracking, by match and across all of them:

- whether `x` and `y` lie on whole centimetres;
- the second-difference acceleration of each player's positions over one and two
  frames either side, for detected and extrapolated positions and at the frames
  where `is_detected` switches;
- what rounding positions to 1 cm alone would produce, simulated.

And over every pose player-frame of the two matches with full body pose:

- whether each joint's `x`, `y` and `z` lie on whole millimetres;
- the horizontal second-difference acceleration of `midHip` over one and five pose
  frames either side (0.04 s and 0.2 s);
- the second-difference acceleration of each joint relative to `midHip`, in 3D,
  over the same two windows, by body part;
- what rounding to 1 mm alone would produce, simulated;
- in open play, the same over one pose frame either side by running speed, and for
  players standing (under 0.5 m/s);
- the median of SkillCorner's error radius, `p90_mae_cm`, by body part.
- how often each knee angle zigzags, reversing direction between frames, and by how much,
  over one pose frame either side, and in open play by running speed.

Results are printed and written to `outputs/tracking_smoothness.json` beside this file.
The tables are read from `goalside.data_dir()`, and need all 20 matches' tracking,
and the full body pose of matches 1925299 and 1996435, converted with goalside.

    uv run python papers/002-tracking-smoothness/tracking-smoothness.py
"""

import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import polars as pl

from goalside import data_dir
from goalside.skillcorner.constants import POSE_FPS, TRACKING_FPS
from goalside.skillcorner.event_types import PhaseType
from goalside.skillcorner.facing import JOINT_INDEX, joint_arrays
from goalside.skillcorner.frames import tracking_frame
from goalside.skillcorner.phases_of_play import scan_phases_of_play
from goalside.skillcorner.pose import scan_pose
from goalside.skillcorner.tracking import scan_tracking

# the two matches with full body pose
POSE_MATCH_IDS = (1925299, 1996435)
QUANTILES = (0.5, 0.75, 0.9, 0.95, 0.99)
# Pose windows, in pose frames either side: one frame (0.04 s), and five (0.2 s), tracking's two frames.
POSE_STEPS = (1, 5)
MID_HIP = JOINT_INDEX["midHip"]
# Running speed bands, in m/s, as in the tracking and pose coverage paper.
SPEED_BANDS = {"0-2": (0, 2), "2-4": (2, 4), "4-6": (4, 6), "6+": (6, np.inf)}
# below this running speed, in m/s, a player counts as standing, with the least real movement of the limbs
STANDING_M_S = 0.5
# each knee's angle is taken at the knee between the thigh (to the hip) and the shin (to the ankle)
KNEES = (("lHip", "lKnee", "lAnkle"), ("rHip", "rKnee", "rAnkle"))
# a knee zigzag counts when both of its moves, out and back, exceed each of these sizes in degrees
ZIGZAG_DEGREES = (0, 5, 10, 15)
# a knee angle is left out where the pose is collapsed, with all 29 joints within this many metres
# of each other (the engagement pose checks paper's rule), or where its thigh or shin is shorter than
# the second, less than half the shortest 0.1% of uncollapsed thighs and shins
COLLAPSED_M = 0.3
SHORTEST_KNEE_BONE_M = 0.1
BODY_PARTS = {
    "head": ("nose", "lEye", "rEye", "lEar", "rEar"),
    "trunk": ("neck", "lShoulder", "rShoulder", "lHip", "rHip"),
    "knees and elbows": ("lKnee", "rKnee", "lElbow", "rElbow"),
    "ankles and wrists": ("lAnkle", "rAnkle", "lWrist", "rWrist"),
    "feet and hands": ("lHeel", "rHeel", "lBigToe", "rBigToe", "lSmallToe", "rSmallToe",
                       "lThumb", "rThumb", "lPinky", "rPinky"),
}


def quantiles(series: pl.Series) -> dict[str, float]:
    return {f"p{int(q * 100)}": round(float(series.quantile(q)), 3) for q in QUANTILES}


def second_difference(step: int) -> pl.Expr:
    """Length of the x and y second difference over `step` frames either side, in m/s², within (match_id, period, player_id)."""
    dt = step / TRACKING_FPS
    keys = ["match_id", "period", "player_id"]
    components = [
        ((pl.col(c).shift(-step) - 2 * pl.col(c) + pl.col(c).shift(step)) / dt**2).over(keys)
        for c in ("x", "y")
    ]
    return (components[0] ** 2 + components[1] ** 2).sqrt()


def rounding_acceleration(step: int, samples: int = 1_000_000) -> dict[str, float]:
    """Second-difference acceleration that rounding positions to 1 cm alone would produce, simulated."""
    dt = step / TRACKING_FPS
    rng = np.random.default_rng(0)
    error = rng.uniform(-0.005, 0.005, size=(3, 2, samples))  # before, at and after, for x and y
    components = (error[2] - 2 * error[1] + error[0]) / dt**2
    return quantiles(pl.Series(np.hypot(components[0], components[1])))


def tracking_smoothness(tracking: pl.DataFrame) -> dict:
    """Second-difference acceleration of each player's positions, across all matches and by match."""
    keys = ["match_id", "period", "player_id"]
    rows = (
        tracking.sort("match_id", "period", "player_id", "frame")
        .with_columns(
            acceleration=second_difference(1),
            acceleration_step_2=second_difference(2),
            gap=(pl.col("frame").shift(-1) - pl.col("frame").shift(1)).over(keys),
            gap_2=(pl.col("frame").shift(-2) - pl.col("frame").shift(2)).over(keys),
            switch=(pl.col("is_detected") != pl.col("is_detected").shift(1)).over(keys),
            on_cm=((pl.col("x") * 100 - (pl.col("x") * 100).round()).abs() < 1e-3)
            & ((pl.col("y") * 100 - (pl.col("y") * 100).round()).abs() < 1e-3),
        )
    )
    # only where both neighbouring frames exist
    step_1 = rows.filter(pl.col("gap") == 2)
    step_2 = rows.filter(pl.col("gap_2") == 4)
    by_match = (
        rows.group_by("match_id").agg(player_frames=pl.len(), on_cm=pl.col("on_cm").mean())
        .join(step_1.group_by("match_id").agg(
            with_both_neighbours=pl.len(),
            detected_median=pl.col("acceleration").filter("is_detected").median(),
            extrapolated_median=pl.col("acceleration").filter(~pl.col("is_detected")).median(),
            switches_median=pl.col("acceleration").filter("switch").median(),
            share_over_10=(pl.col("acceleration") > 10).mean(),
        ), on="match_id")
        .join(step_2.group_by("match_id").agg(
            with_both_two_away=pl.len(),
            step_2_detected_median=pl.col("acceleration_step_2").filter("is_detected").median(),
            step_2_detected_p75=pl.col("acceleration_step_2").filter("is_detected").quantile(0.75),
            step_2_detected_p90=pl.col("acceleration_step_2").filter("is_detected").quantile(0.9),
            step_2_detected_p99=pl.col("acceleration_step_2").filter("is_detected").quantile(0.99),
        ), on="match_id")
        .sort("match_id")
    )
    return {
        "matches": by_match.height,
        "player_frames": rows.height,
        "share_of_positions_on_a_whole_cm": round(float(rows["on_cm"].mean()), 5),
        "player_frames_with_both_neighbours": step_1.height,
        "acceleration_m_s2_detected": quantiles(step_1.filter("is_detected")["acceleration"]),
        "acceleration_m_s2_extrapolated": quantiles(step_1.filter(~pl.col("is_detected"))["acceleration"]),
        "acceleration_m_s2_all": quantiles(step_1["acceleration"]),
        "share_over_10_m_s2": round(float((step_1["acceleration"] > 10).mean()), 5),
        "detection_switches": int(step_1["switch"].sum()),
        "acceleration_m_s2_at_switches": quantiles(step_1.filter("switch")["acceleration"]),
        "acceleration_m_s2_from_rounding_alone": rounding_acceleration(1),
        "player_frames_with_both_neighbours_step_2": step_2.height,
        "acceleration_m_s2_step_2_detected": quantiles(step_2.filter("is_detected")["acceleration_step_2"]),
        "acceleration_m_s2_step_2_from_rounding_alone": rounding_acceleration(2),
        "by_match": {str(row["match_id"]): {k: (round(v, 5) if isinstance(v, float) else v) for k, v in row.items() if k != "match_id"}
                     for row in by_match.iter_rows(named=True)},
    }


# player x and y in a tracking record, and each joint's xyz in a pose record, as written in the file
TRACKING_COORDINATE = re.compile(r'"[xy]": ?(-?[0-9]+(?:\.[0-9]+)?)')
JOINT_XYZ = re.compile(r'"xyz": ?\[([^\]]+)\]')


def decimal_places(number: str) -> int:
    return len(number.split(".")[1]) if "." in number else 0


def raw_precision() -> dict:
    """Decimal places of the coordinates as SkillCorner's files write them, before goalside reads them.

    Every line of every tracking file, and every 50th line of the two pose archives.
    """
    source = data_dir() / "skillcorner" / "source"
    tracking = Counter()
    for path in sorted((source / "matches").glob("*/*_tracking_extrapolated.jsonl")):
        with open(path, encoding="utf-8") as lines:
            for line in lines:
                tracking.update(decimal_places(number) for number in TRACKING_COORDINATE.findall(line))
    pose = Counter()
    for match_id in POSE_MATCH_IDS:
        with zipfile.ZipFile(source / "bodypose" / f"{match_id}.jsonl.zip") as archive:
            with archive.open(archive.namelist()[0]) as raw:
                for i, line in enumerate(io.TextIOWrapper(raw, encoding="utf-8")):
                    if i % 50 == 0:
                        pose.update(decimal_places(value.strip()) for xyz in JOINT_XYZ.findall(line) for value in xyz.split(","))
    return {
        "tracking_files": len(sorted((source / "matches").glob("*/*_tracking_extrapolated.jsonl"))),
        "tracking_coordinates_by_decimal_places": dict(sorted(tracking.items())),
        "pose_joint_coordinates_by_decimal_places": dict(sorted(pose.items())),
    }


def pose_rounding_acceleration(step: int, relative: bool, samples: int = 1_000_000) -> dict[str, float]:
    """Pose second-difference acceleration that rounding coordinates to 1 mm alone would produce, simulated.

    Horizontal for one joint, or in 3D for a joint relative to `midHip`, whose two rounding errors add.
    """
    dt = step / POSE_FPS
    rng = np.random.default_rng(0)
    dimensions = 3 if relative else 2
    error = rng.uniform(-0.0005, 0.0005, size=(3, dimensions, samples))
    if relative:
        error = error - rng.uniform(-0.0005, 0.0005, size=(3, dimensions, samples))
    components = (error[2] - 2 * error[1] + error[0]) / dt**2
    return quantiles(pl.Series(np.sqrt((components**2).sum(axis=0))))


def knee_angles(points: np.ndarray) -> np.ndarray:
    """Each pose's left and right knee angles in degrees, 180 for a straight leg, shaped ``(n, 2)``.

    NaN where the pose is collapsed or the knee's thigh or shin is shorter than ``SHORTEST_KNEE_BONE_M``.
    """
    collapsed = np.ptp(points, axis=1).max(axis=1) < COLLAPSED_M
    angles = []
    for hip_joint, knee_joint, ankle_joint in KNEES:
        knee = points[:, JOINT_INDEX[knee_joint]]
        thigh = points[:, JOINT_INDEX[hip_joint]] - knee
        shin = points[:, JOINT_INDEX[ankle_joint]] - knee
        thigh_length = np.linalg.norm(thigh, axis=1)
        shin_length = np.linalg.norm(shin, axis=1)
        usable = ~collapsed & (thigh_length >= SHORTEST_KNEE_BONE_M) & (shin_length >= SHORTEST_KNEE_BONE_M)
        cosine = np.full(len(points), np.nan)
        cosine[usable] = (thigh * shin).sum(axis=1)[usable] / (thigh_length * shin_length)[usable]
        angles.append(np.degrees(np.arccos(np.clip(cosine, -1, 1))))
    return np.stack(angles, axis=1)


def zigzags(moves_in: np.ndarray, moves_out: np.ndarray) -> dict:
    """How often a knee angle reverses direction, and by how much, from its moves into and out of each frame.

    A frame zigzags when the two moves have opposite signs; its size is the smaller of the two, in degrees.
    Knee-frames whose angle is NaN in any of the three frames are left out.
    """
    measured = np.isfinite(moves_in) & np.isfinite(moves_out)
    moves_in, moves_out = moves_in[measured], moves_out[measured]
    reverses = moves_in * moves_out < 0
    size = np.where(reverses, np.minimum(np.abs(moves_in), np.abs(moves_out)), 0.0)
    return {
        "knee_frames": int(size.size),
        **{f"share_reversing_over_{degrees}": round(float((reverses & (size > degrees)).mean()), 4) for degrees in ZIGZAG_DEGREES},
        "median_size_of_reversals": round(float(np.median(size[reverses])), 2),
    }


def pose_smoothness(match_id: int) -> dict:
    """Rounding and second-difference acceleration of every pose player-frame's joints, period by period."""
    in_match = pl.col("match_id") == match_id
    sample = scan_pose().filter(in_match & (pl.col("frame") % 97 == 0)).select("x", "y", "z").collect()
    # values are float32, so a whole millimetre is matched to within 0.01 mm
    on_mm = {axis: round(float(((sample[axis].cast(pl.Float64) * 1000 - (sample[axis].cast(pl.Float64) * 1000).round())
                                 .abs() < 0.01).mean()), 5) for axis in ("x", "y", "z")}
    hip = {step: [] for step in POSE_STEPS}
    parts = {step: {part: [] for part in BODY_PARTS} for step in POSE_STEPS}
    # one pose frame either side, by the player's speed, inside phases of play other than set plays
    hip_by_speed = {band: [] for band in SPEED_BANDS}
    parts_by_speed = {band: {part: [] for part in BODY_PARTS} for band in SPEED_BANDS}
    hip_standing = []
    parts_standing = {part: [] for part in BODY_PARTS}
    # knee angle moves into and out of each frame, one pose frame either side, for the knee zigzag measures
    knee_moves = ([], [])
    knee_moves_by_speed = {band: ([], []) for band in SPEED_BANDS}
    knee_moves_standing = ([], [])
    open_play = (
        scan_phases_of_play()
        .filter(in_match & (pl.col("team_in_possession_phase_type").cast(pl.String) != PhaseType.SET_PLAY.label))
        .select("period", "frame_start", "frame_end")
        .collect()
    )
    player_frames = 0
    for period in (1, 2):
        arrays = joint_arrays(scan_pose().filter(in_match & (pl.col("period") == period)))
        order = arrays.keys.with_row_index("row").sort("player_id", "frame")
        points = arrays.points[order["row"].to_numpy()].astype(np.float64)
        player = order["player_id"].to_numpy()
        frame = order["frame"].to_numpy()
        player_frames += len(frame)
        knees = knee_angles(points)
        for step in POSE_STEPS:
            dt = step / POSE_FPS
            # both frames `step` away exist for the same player
            ok = (player[2 * step:] == player[:-2 * step]) & (frame[2 * step:] - frame[:-2 * step] == 2 * step)
            second = (points[2 * step:] - 2 * points[step:-step] + points[:-2 * step])[ok] / dt**2
            hip[step].append(np.hypot(second[:, MID_HIP, 0], second[:, MID_HIP, 1]))
            relative = np.linalg.norm(second - second[:, MID_HIP:MID_HIP + 1, :], axis=-1)
            for part, joints in BODY_PARTS.items():
                columns = [JOINT_INDEX[joint] for joint in joints]
                parts[step][part].append(relative[:, columns].ravel())
            if step == 1:
                knee_moves[0].append((knees[1:-1] - knees[:-2])[ok].ravel())
                knee_moves[1].append((knees[2:] - knees[1:-1])[ok].ravel())
        # speed: midHip's horizontal displacement from 5 pose frames before to 5 after, over 0.4 s
        speed = np.full(len(frame), np.nan)
        five = (player[10:] == player[:-10]) & (frame[10:] - frame[:-10] == 10)
        displacement = np.hypot(*(points[10:, MID_HIP, :2] - points[:-10, MID_HIP, :2]).T)
        speed[5:-5][five] = displacement[five] / (10 / POSE_FPS)
        # whether each pose frame lies inside a phase of play other than a set play
        phases = open_play.filter(pl.col("period") == period).sort("frame_start")
        starts, ends = phases["frame_start"].to_numpy(), phases["frame_end"].to_numpy()
        frame_tracking = tracking_frame(frame)
        latest = np.searchsorted(starts, frame_tracking, side="right") - 1
        in_open_play = (latest >= 0) & (frame_tracking <= ends[np.clip(latest, 0, None)])
        one = (player[2:] == player[:-2]) & (frame[2:] - frame[:-2] == 2)
        second = (points[2:] - 2 * points[1:-1] + points[:-2]) * POSE_FPS**2
        centre_speed = speed[1:-1]
        keep = one & ~np.isnan(centre_speed) & in_open_play[1:-1]
        second, centre_speed = second[keep], centre_speed[keep]
        knee_in = (knees[1:-1] - knees[:-2])[keep]
        knee_out = (knees[2:] - knees[1:-1])[keep]
        hip_one = np.hypot(second[:, MID_HIP, 0], second[:, MID_HIP, 1])
        relative_one = np.linalg.norm(second - second[:, MID_HIP:MID_HIP + 1, :], axis=-1)
        for band, (low, high) in SPEED_BANDS.items():
            in_band = (centre_speed >= low) & (centre_speed < high)
            hip_by_speed[band].append(hip_one[in_band])
            for part, joints in BODY_PARTS.items():
                columns = [JOINT_INDEX[joint] for joint in joints]
                parts_by_speed[band][part].append(relative_one[in_band][:, columns].ravel())
            knee_moves_by_speed[band][0].append(knee_in[in_band].ravel())
            knee_moves_by_speed[band][1].append(knee_out[in_band].ravel())
        standing = centre_speed < STANDING_M_S
        hip_standing.append(hip_one[standing])
        for part, joints in BODY_PARTS.items():
            columns = [JOINT_INDEX[joint] for joint in joints]
            parts_standing[part].append(relative_one[standing][:, columns].ravel())
        knee_moves_standing[0].append(knee_in[standing].ravel())
        knee_moves_standing[1].append(knee_out[standing].ravel())
    result = {"share_of_coordinates_on_a_whole_mm": on_mm, "pose_player_frames": player_frames}
    for step in POSE_STEPS:
        hip_values = pl.Series(np.concatenate(hip[step]))
        result[f"step_{step}"] = {
            "player_frames": hip_values.len(),
            "mid_hip_horizontal_m_s2": quantiles(hip_values),
            "mid_hip_from_rounding_alone": pose_rounding_acceleration(step, relative=False),
            "relative_to_mid_hip_m_s2": {part: quantiles(pl.Series(np.concatenate(values)))
                                         for part, values in parts[step].items()},
            "relative_from_rounding_alone": pose_rounding_acceleration(step, relative=True),
        }
    result["open_play_by_speed_step_1"] = {
        band: {
            "player_frames": int(sum(len(values) for values in hip_by_speed[band])),
            "mid_hip_horizontal_median": round(float(np.median(np.concatenate(hip_by_speed[band]))), 3),
            "relative_to_mid_hip_median": {part: round(float(np.median(np.concatenate(values))), 3)
                                           for part, values in parts_by_speed[band].items()},
        }
        for band in SPEED_BANDS
    }
    result["open_play_standing_step_1"] = {
        "player_frames": int(sum(len(values) for values in hip_standing)),
        "mid_hip_horizontal_median": round(float(np.median(np.concatenate(hip_standing))), 3),
        "relative_to_mid_hip_median": {part: round(float(np.median(np.concatenate(values))), 3)
                                       for part, values in parts_standing.items()},
    }
    def joined(moves):
        return np.concatenate(moves[0]), np.concatenate(moves[1])

    result["knee_zigzag"] = {
        "step_1": zigzags(*joined(knee_moves)),
        "open_play_by_speed_step_1": {band: zigzags(*joined(knee_moves_by_speed[band])) for band in SPEED_BANDS},
        "open_play_standing_step_1": zigzags(*joined(knee_moves_standing)),
    }
    error_radius = (
        scan_pose()
        .filter(in_match)
        .select([pl.col("p90_mae_cm").filter(pl.col("joint").cast(pl.String).is_in(joints)).median().alias(part)
                 for part, joints in BODY_PARTS.items()])
        .collect()
    )
    result["error_radius_cm_median"] = {part: round(float(error_radius[part][0]), 2) for part in BODY_PARTS}
    return result


def main() -> None:
    # every match with tracking in the data directory: all 20 of SkillCorner's open data
    tracking = scan_tracking().select("match_id", "period", "frame", "player_id", "x", "y", "is_detected").collect()
    result = {"raw_precision": raw_precision(), "tracking": tracking_smoothness(tracking)}
    del tracking
    print(json.dumps(result["tracking"], indent=2))
    result["pose"] = {}
    for match_id in POSE_MATCH_IDS:
        result["pose"][str(match_id)] = pose_smoothness(match_id)
        print(match_id, json.dumps(result["pose"][str(match_id)], indent=2))
    out = Path(__file__).parent / "outputs" / "tracking_smoothness.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("written", out)


if __name__ == "__main__":
    main()
