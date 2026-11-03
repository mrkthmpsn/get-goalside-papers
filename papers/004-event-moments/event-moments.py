"""Analysis script: where SkillCorner's on-ball events fall against the ball and the player, in time and on the pitch.

Terms, as in the paper beside this file. For every player possession in open play in the
two matches with full body pose, its start at `frame_start`, and its end at `frame_end`
where it ends in a pass, shot or clearance:

- from tracking (10 fps): the ball's horizontal distance from the player's tracking
  position, and the ball's one-frame 'second difference', on every frame from five
  before the event frame to five after, and the offset of the closest frame and of
  the largest 'second difference';
- from pose (25 fps): the horizontal distance from the ball to the player's nearest foot joint,
  on every pose frame from 12 before to 12 after, and the offset of the closest one;
- the event's logged position (`x_start`, `y_start`; `x_end`, `y_end`), converted to
  tracking's pitch frame, against the player's tracking position at the event frame.

And, for both matches, how the 25 fps ball in `skillcorner.pose_frames` relates to the
10 fps ball in `skillcorner.tracking_frames`, by whether each source detected the ball.

Results are printed and written to `outputs/event_moments.json` beside this file.
The tables are read from `goalside.data_dir()`, and need both matches' dynamic events,
phases of play, tracking and full body pose converted with goalside.

    uv run python papers/004-event-moments/event-moments.py
"""

import json
from pathlib import Path

import numpy as np
import polars as pl

from goalside.skillcorner.constants import POSE_FPS, TRACKING_FPS
from goalside.skillcorner.dynamic_events import scan_dynamic_events
from goalside.skillcorner.event_types import EndType, EventType, PhaseType, StartType
from goalside.skillcorner.frames import DYNAMIC_EVENTS_COORDINATES, pose_frame, to_pitch_frame
from goalside.skillcorner.phases_of_play import scan_phases_of_play
from goalside.skillcorner.pose import scan_pose, scan_pose_frames
from goalside.skillcorner.tracking import scan_tracking, scan_tracking_frames

# the two matches with full body pose
MATCH_IDS = (1925299, 1996435)
ENDS = (EndType.PASS.label, EndType.SHOT.label, EndType.CLEARANCE.label)
# frames either side of the event frame searched for the moment: 0.5 s in tracking, 0.48 s in pose
WINDOW = 5
POSE_WINDOW = 12
FOOT_JOINTS = [f"{side}{joint}" for side in "lr" for joint in ("Ankle", "Heel", "BigToe", "SmallToe")]
QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9)


def quantiles(values) -> dict[str, float]:
    series = pl.Series(values, dtype=pl.Float64).drop_nulls().drop_nans()
    return {f"p{int(q * 100)}": round(float(series.quantile(q)), 3) for q in QUANTILES}


def offset_counts(offsets) -> dict[str, int]:
    counts = pl.Series(offsets).value_counts().sort(pl.first())
    return {str(offset): count for offset, count in counts.iter_rows()}


def moments() -> pl.DataFrame:
    """Each possession start and end, one row per event and kind, with its event frame (`anchor`) and logged position."""
    open_play = (
        scan_phases_of_play()
        .filter(pl.col("match_id").is_in(MATCH_IDS)
                & (pl.col("team_in_possession_phase_type").cast(pl.String) != PhaseType.SET_PLAY.label))
        .select(pl.col("match_id").cast(pl.Int32), "period", pl.col("frame_start").alias("phase_start"),
                pl.col("frame_end").alias("phase_end"))
        .collect()
    )
    possessions = to_pitch_frame(
        scan_dynamic_events()
        .filter(pl.col("match_id").is_in(MATCH_IDS) & (pl.col("event_type") == EventType.PLAYER_POSSESSION.label))
        .select(pl.col("match_id").cast(pl.Int32), "event_id", "period", pl.col("player_id").cast(pl.Int32),
                pl.col("start_type").cast(pl.String), pl.col("end_type").cast(pl.String), "frame_start", "frame_end",
                "attacking_side",
                "x_start", "y_start", "x_end", "y_end")
        .collect(),
        DYNAMIC_EVENTS_COORDINATES,
    )
    in_open_play = possessions.join_where(
        open_play, pl.col("match_id") == pl.col("match_id_right"), pl.col("period") == pl.col("period_right"),
        pl.col("frame_start").is_between(pl.col("phase_start"), pl.col("phase_end")),
    ).select("match_id", "event_id").unique()
    possessions = possessions.join(in_open_play, on=["match_id", "event_id"], how="semi")
    keys = ["match_id", "event_id", "period", "player_id", "start_type", "end_type"]
    start = possessions.select(*keys, pl.lit("start").alias("kind"), pl.col("frame_start").alias("anchor"),
                               pl.col("x_start").alias("logged_x"), pl.col("y_start").alias("logged_y"))
    end = possessions.filter(pl.col("end_type").is_in(ENDS)).select(
        *keys, pl.lit("end").alias("kind"), pl.col("frame_end").alias("anchor"),
        pl.col("x_end").alias("logged_x"), pl.col("y_end").alias("logged_y"))
    return pl.concat([start, end]).with_columns(pl.col("anchor").cast(pl.Int32))


def tracking_windows(events: pl.DataFrame) -> pl.DataFrame:
    """Ball and player on every tracking frame from `WINDOW + 1` before each event frame to `WINDOW + 1` after."""
    frames = events.select(
        "match_id", "event_id", "kind", "start_type", "end_type", "player_id", "anchor",
        frame=pl.int_ranges(pl.col("anchor") - WINDOW - 1, pl.col("anchor") + WINDOW + 2, dtype=pl.Int32),
    ).explode("frame")
    player = (
        scan_tracking().filter(pl.col("match_id").is_in(MATCH_IDS))
        .select("match_id", "frame", "player_id", "x", "y", "is_detected")
        .join(frames.lazy(), on=["match_id", "frame", "player_id"], how="right")
        .collect()
    )
    ball = (
        scan_tracking_frames().filter(pl.col("match_id").is_in(MATCH_IDS))
        .select("match_id", "frame", "ball_data_x", "ball_data_y", "ball_data_z")
        .collect()
    )
    keys = ["match_id", "event_id", "kind"]
    return (
        player.join(ball, on=["match_id", "frame"], how="left")
        .sort(*keys, "frame")
        .with_columns(
            offset=pl.col("frame") - pl.col("anchor"),
            ball_player=((pl.col("x") - pl.col("ball_data_x")) ** 2 + (pl.col("y") - pl.col("ball_data_y")) ** 2).sqrt(),
            # one-frame 'second difference' of the ball in 3D, in m/s²
            ball_second_difference=pl.sum_horizontal(
                [((pl.col(c).shift(-1) - 2 * pl.col(c) + pl.col(c).shift(1)) * TRACKING_FPS**2).over(keys) ** 2
                 for c in ("ball_data_x", "ball_data_y", "ball_data_z")]
            ).sqrt(),
        )
        .filter(pl.col("offset").abs() <= WINDOW)
    )


def tracking_moments(windows: pl.DataFrame) -> pl.DataFrame:
    """Per event, the offsets of the ball's closest approach to the player and of its largest 'second difference'.

    Only events whose player is detected and whose ball has a position on every frame
    of the window, with the ball on both frames beyond it.
    """
    keys = ["match_id", "event_id", "kind"]
    complete = windows.group_by(keys).agg(
        ok=(pl.col("is_detected").fill_null(False).all() & pl.col("ball_second_difference").is_not_null().all()
            & (pl.len() == 2 * WINDOW + 1)),
    ).filter("ok")
    rows = windows.join(complete, on=keys, how="semi")
    closest = rows.sort("ball_player").group_by(keys).first().select(
        *keys, closest_offset="offset", closest_distance="ball_player")
    sharpest = rows.sort("ball_second_difference", descending=True).group_by(keys).first().select(
        *keys, sharpest_offset="offset", sharpest_value="ball_second_difference")
    at_anchor = rows.filter(pl.col("offset") == 0).select(*keys, "start_type", "end_type", anchor_distance="ball_player")
    return at_anchor.join(closest, on=keys).join(sharpest, on=keys)


def tracking_summary(events: pl.DataFrame, windows: pl.DataFrame, per_event: pl.DataFrame) -> dict:
    result = {}
    for kind in ("start", "end"):
        rows = per_event.filter(pl.col("kind") == kind)
        profile = (
            windows.join(rows.select("match_id", "event_id", "kind"), on=["match_id", "event_id", "kind"], how="semi")
            .group_by("offset").agg(pl.col("ball_player").median().round(3), pl.col("ball_second_difference").median().round(2))
            .sort("offset")
        )
        result[kind] = {
            "events": events.filter(pl.col("kind") == kind).height,
            "with_detected_player_and_ball": rows.height,
            "by_match": {str(m): rows.filter(pl.col("match_id") == m).height for m in MATCH_IDS},
            "median_by_offset": {str(row["offset"]): {"ball_player_m": row["ball_player"],
                                                      "ball_second_difference_m_s2": row["ball_second_difference"]}
                                 for row in profile.iter_rows(named=True)},
            "closest_offset_counts": offset_counts(rows["closest_offset"]),
            "sharpest_offset_counts": offset_counts(rows["sharpest_offset"]),
            "closest_offset_counts_by_match": {str(m): offset_counts(rows.filter(pl.col("match_id") == m)["closest_offset"])
                                               for m in MATCH_IDS},
            "sharpest_offset_counts_by_match": {str(m): offset_counts(rows.filter(pl.col("match_id") == m)["sharpest_offset"])
                                                for m in MATCH_IDS},
            "share_closest_and_sharpest_within_1_frame": round(float(
                ((rows["closest_offset"] - rows["sharpest_offset"]).abs() <= 1).mean()), 4),
            "anchor_distance_m": quantiles(rows["anchor_distance"]),
            "closest_distance_m": quantiles(rows["closest_distance"]),
        }
        if kind == "start":
            received = pl.col("start_type") == StartType.PASS_RECEPTION.label
            result[kind]["by_start_type"] = {
                name: {"events": part.height,
                       "sharpest_offset_counts": offset_counts(part["sharpest_offset"]),
                       "closest_offset_counts": offset_counts(part["closest_offset"])}
                for name, part in (("pass_reception", rows.filter(received)), ("other", rows.filter(~received)))
            }
            result[kind]["start_types"] = dict(
                rows.group_by("start_type").len().sort("len", descending=True).iter_rows())
        if kind == "end":
            result[kind]["by_end_type"] = {
                end_type: {"events": part.height,
                           "closest_offset_counts": offset_counts(part["closest_offset"]),
                           "sharpest_offset_counts": offset_counts(part["sharpest_offset"])}
                for end_type in ENDS if (part := rows.filter(pl.col("end_type") == end_type)).height
            }
    return result


def tracking_ball_at_pose_frames() -> pl.LazyFrame:
    """The 10 fps tracking ball at every pose frame, interpolated linearly between the tracking frames either side."""
    ball = scan_tracking_frames().filter(pl.col("match_id").is_in(MATCH_IDS)).select(
        "match_id", "frame", "ball_data_x", "ball_data_y", "ball_data_z")
    pose_frames = scan_pose_frames().filter(pl.col("match_id").is_in(MATCH_IDS)).select("match_id", "frame")
    # pose frame p is tracking frame p / 2.5, which lies `weight` of the way from `before` to `before + 1`
    placed = pose_frames.with_columns(before=(pl.col("frame") * 2 // 5).cast(pl.Int32), weight=(pl.col("frame") * 2 % 5) / 5)
    placed = placed.join(ball.rename({"frame": "before"}), on=["match_id", "before"]).join(
        ball.with_columns(pl.col("frame") - 1).rename({"frame": "before"}), on=["match_id", "before"], suffix="_after")
    return placed.select("match_id", "frame", *[
        ((1 - pl.col("weight")) * pl.col(c) + pl.col("weight") * pl.col(f"{c}_after")).alias(c)
        for c in ("ball_data_x", "ball_data_y", "ball_data_z")])


def pose_moments(events: pl.DataFrame) -> dict:
    """Per event, the horizontal distance from the ball to the nearest foot joint on each pose frame, and where it is smallest.

    For each of the two balls: the 25 fps ball in `pose_frames`, and the tracking ball
    interpolated to pose frames. Only events whose player has pose on every pose frame
    of the window.
    """
    centred = events.with_columns(centre=pose_frame(pl.col("anchor")).cast(pl.Int32))
    frames = centred.select(
        "match_id", "event_id", "kind", "period", "player_id", "centre",
        frame=pl.int_ranges(pl.col("centre") - POSE_WINDOW, pl.col("centre") + POSE_WINDOW + 1, dtype=pl.Int32),
    ).explode("frame")
    feet = (
        scan_pose().filter(pl.col("match_id").is_in(MATCH_IDS) & pl.col("joint").cast(pl.String).is_in(FOOT_JOINTS))
        .select("match_id", "period", "frame", "player_id", "x", "y")
        .join(frames.lazy(), on=["match_id", "period", "frame", "player_id"])
    )
    balls = {
        "pose_ball": scan_pose_frames().select("match_id", "frame", "ball_data_x", "ball_data_y", "ball_data_z"),
        "tracking_ball": tracking_ball_at_pose_frames(),
    }
    keys = ["match_id", "event_id", "kind"]
    result = {}
    for source, ball in balls.items():
        distances = (
            feet.join(ball, on=["match_id", "frame"])
            # horizontal, because pose z is measured from the player's centroid and the ball's from the ground
            .with_columns(foot_ball=((pl.col("x") - pl.col("ball_data_x")) ** 2
                                     + (pl.col("y") - pl.col("ball_data_y")) ** 2).sqrt())
            .group_by(*keys, "centre", "frame")
            .agg(pl.col("foot_ball").min())
            .drop_nulls("foot_ball")
            .collect()
        )
        complete = distances.group_by(keys).agg(n=pl.len()).filter(pl.col("n") == 2 * POSE_WINDOW + 1)
        rows = distances.join(complete, on=keys, how="semi").with_columns(offset=pl.col("frame") - pl.col("centre"))
        closest = rows.sort("foot_ball").group_by(keys).first()
        at_centre = rows.filter(pl.col("offset") == 0)
        result[source] = {}
        for kind in ("start", "end"):
            kind_closest = closest.filter(pl.col("kind") == kind)
            profile = (rows.filter(pl.col("kind") == kind).group_by("offset")
                       .agg(pl.col("foot_ball").median().round(3)).sort("offset"))
            result[source][kind] = {
                "with_pose_on_every_frame": kind_closest.height,
                "with_pose_on_every_frame_by_match": {str(m): kind_closest.filter(pl.col("match_id") == m).height
                                                      for m in MATCH_IDS},
                "median_foot_ball_m_by_pose_offset": {str(o): d for o, d in profile.iter_rows()},
                "closest_pose_offset_counts": offset_counts(kind_closest["offset"]),
                "closest_offset_s": quantiles(kind_closest["offset"] / POSE_FPS),
                "closest_foot_ball_m": quantiles(kind_closest["foot_ball"]),
                "share_closest_under_0_25_m": round(float((kind_closest["foot_ball"] < 0.25).mean()), 4),
                "foot_ball_at_event_frame_m": quantiles(at_centre.filter(pl.col("kind") == kind)["foot_ball"]),
            }
    return result


def logged_positions(events: pl.DataFrame, windows: pl.DataFrame) -> dict:
    """The distance from each event's logged position to the player's tracking position at the event frame."""
    at_anchor = windows.filter(pl.col("offset") == 0).select("match_id", "event_id", "kind", "x", "y", "is_detected")
    rows = events.join(at_anchor, on=["match_id", "event_id", "kind"]).with_columns(
        distance=((pl.col("logged_x") - pl.col("x")) ** 2 + (pl.col("logged_y") - pl.col("y")) ** 2).sqrt()
    ).drop_nulls("distance")
    return {
        str(m): {
            kind: {
                "events": part.height,
                "share_within_1_cm": round(float((part["distance"] < 0.01).mean()), 4),
                "distance_m": quantiles(part["distance"]),
                "detected_distance_m": quantiles(part.filter("is_detected")["distance"]),
            }
            for kind in ("start", "end")
            if (part := rows.filter((pl.col("match_id") == m) & (pl.col("kind") == kind))).height
        }
        for m in MATCH_IDS
    }


def pose_ball() -> dict:
    """How the 25 fps ball in `pose_frames` relates to the 10 fps ball in `tracking_frames`."""
    result = {}
    for match_id in MATCH_IDS:
        pose = (scan_pose_frames().filter(pl.col("match_id") == match_id)
                .select("period", "frame", "ball_data_x", "ball_data_y", "ball_data_z").sort("period", "frame").collect())
        changes = []
        for (period,), part in pose.group_by(["period"]):
            frame = part["frame"].to_numpy()
            ball = part.select("ball_data_x", "ball_data_y", "ball_data_z").to_numpy().astype(np.float64)
            second = np.abs(ball[2:] - 2 * ball[1:-1] + ball[:-2]).max(axis=1)
            consecutive = (frame[2:] - frame[:-2] == 2) & np.isfinite(second)
            # a frame where the path bends, beyond float32 error in a straight line
            changes.append(frame[1:-1][consecutive & (second > 2e-3)] % 5)
        bends = np.concatenate(changes)
        tracking = (scan_tracking_frames().filter(pl.col("match_id") == match_id)
                    .select("period", "frame", "ball_data_x", "ball_data_y", "ball_data_is_detected").collect())
        detected = (scan_pose_frames().filter(pl.col("match_id") == match_id)
                    .select("frame", "ball_data_is_detected").collect())
        paired = (pose.join(detected, on="frame").filter(pl.col("frame") % 5 == 0)
                  .with_columns(frame=(pl.col("frame") // 5 * 2).cast(pl.Int32))
                  .join(tracking, on=["period", "frame"], suffix="_tracking")
                  .drop_nulls(["ball_data_x", "ball_data_x_tracking"]))
        paired = paired.with_columns(distance=((pl.col("ball_data_x") - pl.col("ball_data_x_tracking")) ** 2
                                               + (pl.col("ball_data_y") - pl.col("ball_data_y_tracking")) ** 2).sqrt())
        distance = paired["distance"]
        by_detection = {
            f"pose_{'detected' if in_pose else 'not_detected'}_tracking_{'detected' if in_tracking else 'not_detected'}": {
                "frames": part.height, "median_m": round(float(part["distance"].median()), 3)}
            for in_pose in (True, False) for in_tracking in (True, False)
            if (part := paired.filter((pl.col("ball_data_is_detected") == in_pose)
                                      & (pl.col("ball_data_is_detected_tracking") == in_tracking))).height
        }
        # the pose ball against the tracking ball one tracking frame earlier and later, for a time offset
        shifted = {}
        for lag in (-1, 1):
            moved = (pose.filter(pl.col("frame") % 5 == 0)
                     .with_columns(frame=(pl.col("frame") // 5 * 2 + lag).cast(pl.Int32))
                     .join(tracking, on=["period", "frame"], suffix="_tracking")
                     .drop_nulls(["ball_data_x", "ball_data_x_tracking"]))
            shifted[str(lag)] = round(float(((moved["ball_data_x"] - moved["ball_data_x_tracking"]) ** 2
                                             + (moved["ball_data_y"] - moved["ball_data_y_tracking"]) ** 2)
                                            .sqrt().median()), 3)
        result[str(match_id)] = {
            "pose_frames_with_a_ball": int(pose["ball_data_x"].is_not_null().sum()),
            "bends_by_pose_frame_mod_5": {str(k): int(v) for k, v in zip(*np.unique(bends, return_counts=True))},
            "pose_tracking_frames_compared": paired.height,
            "share_equal_to_1_cm": round(float((distance < 0.01).mean()), 4),
            "horizontal_distance_m": quantiles(distance),
            "by_detection": by_detection,
            "median_m_against_tracking_frame_offset": shifted,
        }
    return result


def main() -> None:
    events = moments()
    windows = tracking_windows(events)
    per_event = tracking_moments(windows)
    result = {
        "events": {kind: {"both": events.filter(pl.col("kind") == kind).height,
                          **{str(m): events.filter((pl.col("kind") == kind) & (pl.col("match_id") == m)).height
                             for m in MATCH_IDS}}
                   for kind in ("start", "end")},
        "pose_ball": pose_ball(),
        "tracking": tracking_summary(events, windows, per_event),
        "pose": pose_moments(events),
        "logged_positions": logged_positions(events, windows),
    }
    print(json.dumps(result, indent=2))
    out = Path(__file__).parent / "outputs" / "event_moments.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("written", out)


if __name__ == "__main__":
    main()
