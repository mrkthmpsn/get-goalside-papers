---
goalside: 0.1.0
history:
- date: 2026-11-03
  event: published
---

# Studs not quite on the ball: When and where SkillCorner's open data on-ball events happen, relative to ball position and the player pose data

**Why study this?:** To find out how closely SkillCorner's on-ball events line up with the ball and the players' feet and bodies, and whether there is a consistent way to pinpoint the moment of an event.

---

## Abstract

This blog-paper measures where SkillCorner's Dynamic Events data place the start and end of each player possession, in time and on the pitch, against the ball and the player in the tracking and body pose data.

It uses the 2,001 player possessions (the Dynamic Events records of one player's spell on the ball) in open play in the two matches with full body pose, Match A (Brisbane Roar v Perth Glory, ID 1925299, 2024-12-21) and Match B (Sydney FC v Adelaide United, ID 1996435, 2025-02-01). For each player possession, it uses the start frame, and, for the 1,835 that end in a pass, shot or clearance, its end frame. A player possession gives a start and an end frame rather than a single moment, so the paper finds the frame at which the ball's movement changes most sharply near each, and compares the two.

It has five findings:
- **The body pose data's ball changes speed or direction only at the times of tracking frames.** Between them it moves in straight lines at a steady speed, so it can't time a touch more finely than tracking, and it sits 0.20–0.24m from tracking's ball where both detect it.
- **A possession's end frame is the pass, shot or clearance, to within a frame.** The ball's sharpest change falls within 0.1s of it in 90% of these possessions.
- **A possession's start frame marks the ball arriving, slightly less precisely.** The ball's sharpest change falls within 0.1s of it in 64% of possessions.
- **At those frames, the ball sits about a metre from the player's tracking position.** The median distance is 1.2m.
- **Pose feet are rarely beside the ball.** At their closest, the player's nearest foot joint is a median of 0.6m from the ball.

## 1. Introduction

Certain types of analysis may require looking at data at (or around) a specific moment of an event. SkillCorner's Dynamic Events data give each player possession a time range with a start frame and an end frame, rather than a specific event timestamp. 

A player possession is one of the four kinds of record in the Dynamic Events data, beside passing options, off-ball runs and on-ball engagements, and covers one player's spell on the ball, from the frame they gain it to the frame they pass, shoot, clear or lose it.

The blog-paper asks four questions:
1. Where do on-ball events fall in relation to a 'player possession' start and end frames?
2. How consistent is that, between different types of events and between the two matches?
3. How far is the ball from the player's tracking position, and from the player's nearest foot in the pose data, at the moment of a touch?
4. How far are event positions logged from the player's tracking position?

## 2. Definitions

**Tracking frame.** One of SkillCorner's tracking time steps, 100ms apart (10 frames per second).

**Pose frame.** One of SkillCorner's body-pose time steps, 40ms apart (25 frames per second). A tracking frame's pose frame is 2.5 times its number: tracking frame 2000 is pose frame 5000.

**Player possession.** A record of type `player_possession` in SkillCorner's Dynamic Events data: one player's spell on the ball, with a start frame, `frame_start`, an end frame, `frame_end`, a `start_type` saying how it began (such as `pass_reception`, `pass_interception` or `recovery`) and an `end_type` saying how it ended (`pass`, `shot`, `clearance`, `possession_loss`, `foul_suffered` or `unknown`).

**Possession start and end.** A possession's **start** is its `frame_start`. Its **end** is its `frame_end`, for possessions ending in a pass, shot or clearance. Either frame is the **event frame**. A start is not always the receipt of a pass: of the 1,845 starts measured from tracking, 1,357 (74%) have `start_type` `pass_reception`, and the rest are interceptions (173), recoveries (145), the player keeping the ball (91), receptions of a throw-in, goal kick or free kick (69) and unknown (10).

**Open play.** The frames inside a phase of play, one of SkillCorner's stretches of one team's possession in `skillcorner.phases_of_play`, whose phase type for the team in possession is not `set_play`. In these matches, the possessions in open play start in phases of types `build_up`, `create`, `finish`, `direct`, `quick_break`, `transition` and `chaotic`. A possession is in open play when its start frame is.

**Offset.** For a frame near a possession start or end, its number minus the event frame, in tracking frames: −1 is the frame before, +1 the frame after, and offsets −5 to +5 span ±0.5s. A **pose-frame offset** is the same in pose frames, from the event frame's pose frame, `frame_start` or `frame_end` × 2.5.

**Ball's 'second difference'.** As in paper `002-tracking-smoothness`, how much the ball's velocity changes at a tracking frame, which is an estimate of its acceleration. Take the ball's position (`x`, `y` and `z`) in the frame before, in the frame itself and in the frame after. Its velocity coming into the frame is the change from the first position to the second, and its velocity leaving is the change from the second to the third; the 'second difference' is the change between those two velocities, divided by the time between frames (0.1s), in m/s². A ball moving at a steady speed in a straight line has a 'second difference' of zero, and it is largest at the frame where the ball's velocity changes most, such as a kick or a trap.

**Sharpest change.** The frame, from offset −5 to +5, at which the ball's 'second difference' is largest, which is the frame at which the ball's velocity changes most.

**Ball–player distance.** The horizontal distance between the ball and the player's tracking position in the same tracking frame. The **closest frame** is the frame from offset −5 to +5 at which it is smallest.

**Foot–ball distance.** The horizontal distance from the ball to the nearest of the player's eight foot joints in the pose (ankles, heels, big toes and small toes) in the same pose frame. Horizontal means across the pitch surface, from `x` and `y` together, leaving out `z`, because pose height is measured from the player's own centroid: SkillCorner states that "position on the z-axis is accurate relatively to the player's centroid, but not necessarily in the pitch coordinate system" ([body pose README](https://github.com/SkillCorner/opendata/blob/master/data/bodypose/README.md)).

**Logged position.** The player's position stored with the possession in the Dynamic Events data: `x_start` and `y_start` for a start, `x_end` and `y_end` for an end. The Dynamic Events data give positions in the acting team's direction of attack, and `goalside`'s `to_pitch_frame` function converts them to tracking's pitch frame before they are compared.

**Percentiles.** The nth percentile is the value below which n% of the measurements lie; the median is the 50th.

## 3. Data and methods

### 3.1 Data

The data is SkillCorner's open data for Match A (Brisbane Roar v Perth Glory, ID 1925299, 2024-12-21) and Match B (Sydney FC v Adelaide United, ID 1996435, 2025-02-01), as `goalside v0.1.0` converts it into `skillcorner.dynamic_events`, `skillcorner.phases_of_play`, `skillcorner.tracking`, `skillcorner.tracking_frames`, `skillcorner.pose` and `skillcorner.pose_frames`, each at schema version 1.

| Possession starts and ends | Match A | Match B | Both matches |
| ------------------------------------------------------------------- | ------- | ------- | ----- |
| Possession starts: player possessions in open play                  | 1,034   | 967     | 2,001 |
| Possession ends: those ending in a pass, shot or clearance          | 946     | 889     | 1,835 |
| Starts with the player detected and a ball at offsets −6 to +6      | 944     | 901     | 1,845 |
| Ends with the player detected and a ball at offsets −6 to +6        | 885     | 860     | 1,745 |
| Starts with pose at pose-frame offsets −12 to +12                   | 940     | 889     | 1,829 |
| Ends with pose at pose-frame offsets −12 to +12                     | 877     | 848     | 1,725 |

The tracking measures use the possession starts and ends whose player is detected by the camera, with a ball position, at every offset from −6 to +6, one either side of the −5 to +5 measured, so that the ball's 'second difference' exists at each. The foot measures use those whose player has pose at every pose-frame offset from −12 to +12. Of the 1,745 ends measured from tracking, 1,658 are passes, 52 shots and 35 clearances.

### 3.2 Methods

This section summarises what the analysis code does; Appendix B describes the code itself.

1. The pose frames at which the 25fps ball in `skillcorner.pose_frames` changes speed or direction were found, and that ball was compared with the 10fps ball in `skillcorner.tracking_frames` at the pose frames that are also tracking frames, by whether each source detected the ball, and against the tracking frames either side.
2. For each possession start and end, the ball–player distance and the ball's 'second difference' were computed at every offset from −5 to +5, and the offsets of the sharpest change and of the closest frame were counted by start or end, start type, end type and match.
3. For each possession start and end, the foot–ball distance was computed at every pose-frame offset from −12 to +12 (±0.48s), once with the ball from `pose_frames` and once with the tracking ball interpolated in a straight line to pose frames, and the offset and size of the smallest were summarised.
4. Each possession start's and end's logged position was compared with the player's tracking position at the event frame.

## 4. Results

### 4.1 The 25fps ball changes speed or direction only at the pose frames nearest a tracking frame, and is 0.20–0.24m from the tracking ball where both detect it

The `pose_frames` table gives a ball position at every pose frame, 25 frames per second, but the ball's path changes speed or direction only at the times of tracking frames, 10 frames per second, and runs in straight lines at a steady speed between them. This shows in where the path bends. Pose frames and tracking frames line up every 0.2s: tracking frame 2000 is pose frame 5000, and tracking frame 2001 falls halfway between pose frames 5002 and 5003. So in every five pose frames, three are at or next to a tracking frame (such as 5000, 5002 and 5003) and two are not (such as 5001 and 5004). The ball changes speed or direction, by a 'second difference' over one pose frame of more than 2mm in `x`, `y` or `z`, only at the first three: 23,877, 22,874 and 22,799 times in Match A, 21,456, 20,505 and 20,513 in Match B, and never at the other two. At those two, the ball carries on in a straight line at the same speed. That fits a ball placed at 10 frames per second with the frames between filled in by straight lines, though this is inferred from the path and was not confirmed with SkillCorner.

The `pose_frames` ball is not tracking's ball as published, since the two differ by a median of 0.2m or more at the frames they share (table below), and SkillCorner states that "XY Tracking data and Body Pose are generated separately" ([body pose README](https://github.com/SkillCorner/opendata/blob/master/data/bodypose/README.md)). Together with the bends at the times of tracking frames, this fits a pose ball made from the same 10fps ball as tracking but processed separately, which is untested. Horizontal distance between the `pose_frames` ball and the `tracking_frames` ball, at the pose frames that are also tracking frames and have both, by which source flags the ball as detected:

| Ball detected in | Match A, frames compared | Match A, median distance | Match B, frames compared | Match B, median distance |
| ---------------- | -------------- | -------------- | -------------- | -------------- |
| Both sources     | 18,939         | 0.24m         | 17,168         | 0.20m         |
| Pose only        | 901            | 1.81m         | 928            | 1.71m         |
| Tracking only    | 357            | 3.50m         | 172            | 5.63m         |
| Neither          | 3,733          | 1.49m         | 3,469          | 1.15m         |
| All              | 23,969         | 0.30m         | 21,769         | 0.24m         |

Over all of them, 0.09% (Match A) and 0.11% (Match B) are within 1cm, and the 90th percentile is 2.15m and 1.75m. The two paths are not offset in time: against the tracking ball one tracking frame earlier or later, the median distance rises to 0.71–0.72m (Match A) and 0.63–0.67m (Match B).

### 4.2 The ball's sharpest change falls within one frame of a possession's end frame in 90% of possessions ending in a pass, shot or clearance

Share of possession ends whose sharpest change is at each offset from `frame_end`, where a large change of the ball's velocity indicates the player kicking it:

| Matches or end type | Possession ends | Sharpest change at −2 or earlier | At −1 | At 0 | At +1 | At +2 or later |
| ------------ | --------------- | ------------- | ----- | ----- | ----- | ----------- |
| Both matches | 1,745           | 4.3%          | 12.3% | 49.8% | 28.4% | 5.2%        |
| Match A      | 885             | 5.0%          | 11.0% | 50.3% | 28.5% | 5.3%        |
| Match B      | 860             | 3.6%          | 13.7% | 49.3% | 28.3% | 5.1%        |
| Passes       | 1,658           | 4.2%          | 12.5% | 50.8% | 27.7% | 4.8%        |
| Shots        | 52              | 7.7%          | 5.8%  | 30.8% | 36.5% | 19.2%       |
| Clearances   | 35              | 2.9%          | 14.3% | 28.6% | 48.6% | 5.7%        |

Median ball–player distance and ball 'second difference' over the 1,745 possession ends, by offset from `frame_end`:

| Offset                          | −5   | −4   | −3   | −2    | −1    | 0     | +1    | +2    | +3   | +4   | +5    |
| ------------------------------- | ---- | ---- | ---- | ----- | ----- | ----- | ----- | ----- | ---- | ---- | ----- |
| Ball–player distance (m)        | 1.09 | 1.08 | 1.04 | 0.99  | 1.00  | 1.20  | 1.73  | 2.62  | 3.78 | 4.96 | 6.11  |
| Ball 'second difference' (m/s²) | 5.1  | 5.7  | 6.8  | 12.7  | 26.0  | 36.2  | 32.3  | 18.5  | 8.6  | 8.3  | 10.4  |

At the median, the ball stays about 1m from the player up to the frame before `frame_end`, and moves away from it after.

### 4.3 The ball's sharpest change falls within one frame of a possession's start frame in 64% of possessions

Share of possession starts whose sharpest change is at each offset from `frame_start`:

| Matches or start type | Possession starts | Sharpest change at −2 or earlier | At −1 | At 0 | At +1 | At +2 or later |
| ------------------------- | ----------------- | ------------- | ----- | ----- | ----- | ----------- |
| Both matches              | 1,845             | 21.5%         | 21.4% | 25.1% | 17.9% | 14.1%       |
| Match A                   | 944               | 22.5%         | 22.1% | 24.2% | 18.2% | 13.0%       |
| Match B                   | 901               | 20.4%         | 20.5% | 26.1% | 17.6% | 15.3%       |
| Starting with a pass received (`pass_reception`) | 1,357 | 20.5% | 25.0% | 25.6% | 15.2% | 13.7% |
| Every other start         | 488               | 24.2%         | 11.3% | 23.6% | 25.6% | 15.4%       |

Median ball–player distance and ball 'second difference' over the 1,845 possession starts, by offset from `frame_start`:

| Offset                          | −5   | −4   | −3    | −2    | −1    | 0     | +1    | +2    | +3   | +4   | +5   |
| ------------------------------- | ---- | ---- | ----- | ----- | ----- | ----- | ----- | ----- | ---- | ---- | ---- |
| Ball–player distance (m)        | 4.28 | 3.46 | 2.71  | 2.04  | 1.51  | 1.19  | 1.05  | 1.02  | 1.05 | 1.07 | 1.10 |
| Ball 'second difference' (m/s²) | 7.5  | 8.3   | 10.5  | 13.9  | 17.3  | 17.5  | 15.0  | 10.8  | 7.0  | 5.9  | 6.2  |

The median ball–player distance is still falling at `frame_start`, at 1.19m, and is smallest at +2, at 1.02m. Individual possessions spread around those medians: the closest frame of a single possession falls at each offset from 0 to +4 in 7–19% of starts, and at +5, the edge of the window, in 23%. The median 'second difference' peaks at −1 and 0 at about half the height of the peak at a possession's end.

### 4.4 The ball–player distance at a possession's start or end frame spans 0.6m to 2.1–2.4m across the middle 80% of possessions

Ball–player distance, in metres:

| Possession starts or ends | 10th percentile (m) | 25th percentile (m) | Median (m) | 75th percentile (m) | 90th percentile (m) |
| ------------------------------------------ | ---- | ---- | ------ | ---- | ---- |
| Possession starts, at `frame_start` (1,845) | 0.56 | 0.81 | 1.19   | 1.67 | 2.37 |
| Possession starts, closest frame           | 0.26 | 0.50 | 0.83   | 1.28 | 1.92 |
| Possession ends, at `frame_end` (1,745)    | 0.57 | 0.84 | 1.20   | 1.60 | 2.13 |
| Possession ends, closest frame             | 0.28 | 0.52 | 0.84   | 1.24 | 1.82 |

### 4.5 The player's nearest foot is a median of 0.6m from the ball at its closest

Foot–ball distance at the pose frame where it is smallest, within ±0.48s of the event frame, and that frame's offset from the event frame, in seconds:

| Possession starts or ends, and ball | Possessions | Median foot–ball distance | Share within 0.25m | Median offset from the event frame | 25th–75th percentile of the offset |
| --------------------------------------- | ----------- | --------------- | ------------- | ------------- | ---------------- |
| Possession starts, `pose_frames` ball   | 1,829       | 0.58m          | 24.5%         | +0.12s       | +0.04 to +0.32s |
| Possession starts, tracking ball        | 1,829       | 0.62m          | 22.9%         | +0.16s       | +0.04 to +0.32s |
| Possession ends, `pose_frames` ball     | 1,725       | 0.59m          | 21.5%         | −0.12s       | −0.28 to −0.04s |
| Possession ends, tracking ball          | 1,725       | 0.63m          | 22.0%         | −0.12s       | −0.28 to −0.04s |

At the event frame itself, the median foot–ball distance is 0.95m for possession starts and 0.99m for possession ends with the `pose_frames` ball. For possession ends, the median foot–ball distance over all 1,725 is smallest at pose-frame offset −3, 0.80m, and grows from the event frame on.

### 4.6 Positions logged in the Dynamic Events data are 0.15–0.19m from the player's tracking position

Distance from each possession start's and end's logged position in the Dynamic Events data to the player's tracking position at the event frame, over every possession start and end with a tracking position there:

| Match and possession starts or ends | Possessions | Share within 1cm | Median distance | 90th percentile of distance |
| -------------------------- | ----------- | ----------- | ------ | ------ |
| Match A, possession starts | 1,031       | 0.39%       | 0.19m | 0.55m |
| Match A, possession ends   | 946         | 0.42%       | 0.19m | 0.52m |
| Match B, possession starts | 958         | 0.42%       | 0.16m | 0.41m |
| Match B, possession ends   | 888         | 0.56%       | 0.15m | 0.37m |

These distances are about the same as the 0.20–0.22m median distance between the tracking position and the body pose's `midHip` in paper `001-tracking-pose-coverage`. Whether the two offsets share a cause was not tested.

## 5. Discussion

### 5.1 A possession's end frame can stand for the moment of a pass, shot or clearance, and its start frame for the ball's arrival

For a possession ending in a pass, shot or clearance, `frame_end` is the frame at which the ball's movement changes most in half of them, and within one frame of it in 90%, in both matches, and at the median the ball is still with the player until then and leaving after. So `frame_end` would serve as the moment of a pass, to within a tracking frame (0.1s) in nine possessions in ten. Where the sharpest change is not at `frame_end`, it is more often the frame after (28%) than the frame before (12%). Shots and clearances have their sharpest change at +1 more often than at 0, but there are only 52 and 35 of them.

At a possession's start, `frame_start` falls as the ball arrives: at the median, the ball is still nearing the player at `frame_start` and closest 0.1–0.2s later, and the sharpest change is within one frame of `frame_start` in 64% of starts, with 21% two or more frames before it. Possessions that start with a pass received fit `frame_start` about as well as the others (66% and 60% within one frame), so the looser fit is not explained by interceptions and recoveries. A trap changes the ball's velocity less than a kick, about half as much at the median, and a short pass's kick can fall inside the ±0.5s window before the start, which would put the sharpest change before `frame_start`. So `frame_start` marks a possession's start less tightly than `frame_end` marks its end, but both are reasonable moments to use.

### 5.2 The ball, the tracking position and the pose feet do not meet at a touch

At a possession's start or end frame, the ball is a median of 1.2m from the player's tracking position, and 0.8m at its closest frame. The nearest pose foot is closer, but still a median of 0.6m from the ball at its closest, and within 0.25m in fewer than a quarter of possessions, although a foot in contact with the ball is about the ball's radius from its centre. The tracking ball and the `pose_frames` ball give the same result to within 0.04m, so the gap is not a property of one ball path. Paper `001-tracking-pose-coverage` finds tracking and pose place a player about 0.2m apart, and section 4.1 finds the two balls 0.20–0.24m apart where both detect it, so each source's position of the player and of the ball carries an error of that order, and a touch measured across sources inherits all of them.

### 5.3 Pose cannot time a touch more finely than tracking

The `pose_frames` ball has a position at every pose frame, but between the times of tracking frames it moves in a straight line at a steady speed, so those positions show no change in the ball's velocity and cannot show when within the 0.1s the ball was touched. Pose feet are given at 25fps, but the ball they would be timed against changes velocity only at the times of tracking frames, so a touch can only be placed to the 0.1s of a tracking frame. The two ball paths agree to about 0.2m where both sources detect the ball, and differ by metres where either places the ball without detecting it.

### 5.4 Logged positions are close to tracking, but not tracking's

The positions logged with each possession in the Dynamic Events data lie a median of 0.15–0.19m from the player's tracking position at the event frame, and within 1cm in under 1%. Both matches are among the ten of SkillCorner's twenty whose `match.json` has no `sequences`, for which `goalside`'s notes on SkillCorner's data (`docs/skillcorner-data.md`) record the same offset of about 0.14–0.27m between event and tracking positions, so a logged position would be taken as close to, and not equal to, where the tracking places the player.

### 5.5 Limitations

- **Two matches.** Both matches come from the same ten of SkillCorner's twenty, so whether the other ten, whose event positions equal tracking's, also time events differently is not known.
- **The ball's sharpest change is a proxy for the touch.** It is the frame of the largest change in the ball's velocity, which a deflection, a bounce or the previous player's kick can also produce. Any smoothing of the ball's path before publication could spread a kick over neighbouring frames.
- **The nearest foot joint, not the touching foot.** The foot measure takes whichever of the eight foot joints is nearest, which before a kick may potentially sometimes be the standing foot.
- **Open play only.** Set plays are left out, so free kicks, corners and goal kicks are not measured.

## 6. Implications

- **The moment of a pass, shot or clearance** could reasonably be taken as the possession's `frame_end`, which is within one tracking frame of the ball's sharpest change in 90% of these possessions. However, it is worth noting that a snapshot of team shape or the offside line at that frame could be 0.1s off in one possession in ten, which for a player running at 8m/s is 0.8m.
- **The ball's arrival at a player** could reasonably be taken as the possession's `frame_start`, or one to two frames later for when the ball is, at the median, closest to the player.
- **Body pose at a touch** would be taken at the pose frame of the event frame, `frame_end` × 2.5, and analyses of foot contact would not rely on the foot–ball distance, which is 0.6m at the median at its smallest.
- **An analysis that measures from the player in a Dynamic Events record**, such as the distance from a passer to the nearest defender in the tracking, would take the passer's position from the tracking at the event frame, and not the logged `x_start`/`y_start` or `x_end`/`y_end`. The logged position sits 0.15–0.19m from the tracking position at the median in these matches, so a distance mixing the two sources would carry that offset.

## Future points for research

- **Whether the other open matches with Dynamic Events and tracking data agree with this analysis.**
- **Which foot touches the ball.** Separating the two feet, and taking the one that moves fastest at the possession's end, would test whether the nearest foot before a pass is the standing foot.
- **On-ball engagements and set plays.** The same comparison for engagements' start, end and physical-start frames, and for set plays, would extend the rule to the other on-ball moments.

## Sources

- SkillCorner, [body pose README](https://github.com/SkillCorner/opendata/blob/master/data/bodypose/README.md): "XY Tracking data and Body Pose are generated separately", and "Position on the z-axis is accurate relatively to the player's centroid, but not necessarily in the pitch coordinate system."
- SkillCorner's open Dynamic Events, phases of play, tracking (`<id>_tracking_extrapolated.jsonl`) and full body pose for matches 1925299 and 1996435, converted with `goalside v0.1.0` into the tables listed in section 3.1.

## Appendices

### Appendix A: versions

The paper's results come from `goalside v0.1.0`, reading these tables at these schema versions:

| Table                         | Schema version |
| ----------------------------- | -------------- |
| `skillcorner.dynamic_events`  | 1              |
| `skillcorner.phases_of_play`  | 1              |
| `skillcorner.tracking`        | 1              |
| `skillcorner.tracking_frames` | 1              |
| `skillcorner.pose`            | 1              |
| `skillcorner.pose_frames`     | 1              |

`goalside v0.1.0` converted them from this data:

| Data | Version | Checked |
| --- | --- | --- |
| SkillCorner open data | [`opendata` commit 4340d27](https://github.com/SkillCorner/opendata/tree/4340d274572876239c154c90bc507a9b3250a656) (2026-09-14) | The Dynamic Events and phases of play CSVs match the commit by git hash, and the tracking files by their Git LFS SHA256 |
| Full body pose | SkillCorner's [opendata-bodypose](https://huggingface.co/datasets/SkillCorner/opendata-bodypose) dataset on Hugging Face | Each archive matches the size and SHA256 in `data/bodypose/MANIFEST.json` at the same commit, which `goalside` checks when it downloads it |

`goalside` downloads SkillCorner's files from the `opendata` repository's `master` branch. Reproducing the paper after a later SkillCorner commit would mean taking the files from commit 4340d27, for example from a clone of `opendata` at that commit, and passing each to `goalside`'s converter functions as `source`.

### Appendix B: the event moments analysis script

**File.** `event-moments.py` in this folder. The results above come from `goalside v0.1.0`.

**Run.**

```
uv run python papers/004-event-moments/event-moments.py
```

- **Needs:** both matches' tables in `goalside`'s data directory (the `goalside.data_dir()` function), loaded with `goalside`'s `download_dynamic_events` and `convert_dynamic_events`, `download_phases_of_play` and `convert_phases_of_play`, `download_tracking` and `convert_tracking`, `download_match` and `convert_match`, then `download_pose_match` and `convert_pose` functions.
- **Takes:** under a minute.
- **Writes:** `outputs/event_moments.json` in this folder, with `events`, `pose_ball`, `tracking`, `pose` and `logged_positions` sections, each holding a `start` and an `end` entry where it measures possessions.

**Structure.**

```
main()
  moments()                                   # section 3.1: possession starts and ends in open play
  pose_ball()                                 # section 4.1
  tracking_windows(), tracking_moments()      # sections 4.2–4.4
  tracking_summary()
  pose_moments()                              # section 4.5
    tracking_ball_at_pose_frames()
  logged_positions()                          # section 4.6
  write JSON
```

**`moments`: the possession starts and ends.**

```
open_play   = phases_of_play rows whose team_in_possession_phase_type is not set_play
possessions = dynamic_events rows of type player_possession, x and y converted with to_pitch_frame,
              whose frame_start lies between a phase's frame_start and frame_end in the same period
start       = every possession: anchor = frame_start, logged = (x_start, y_start), with its start_type
end         = possessions whose end_type is pass, shot or clearance: anchor = frame_end, logged = (x_end, y_end)
```

**`tracking_windows` and `tracking_moments`: the ball against the event frame.**

```
for each start and end, tracking frames anchor − 6 to anchor + 6:
    player x, y, is_detected from tracking; ball x, y, z from tracking_frames
    ball_player            = |ball xy − player xy|
    ball_second_difference = |ball(f + 1) − 2 × ball(f) + ball(f − 1)| × 10² , in x, y and z
keep offsets −5 to +5, and starts and ends with is_detected and a second difference at all 11
sharpest = offset of the largest ball_second_difference; closest = offset of the smallest ball_player
summaries: counts of each offset, by start or end, start type (pass_reception or other), end type
           and match; medians by offset; distance percentiles
```

**`pose_moments`: the feet against the ball.**

```
centre = pose_frame(anchor)                                   # × 2.5, rounding half up
for each start and end, pose frames centre − 12 to centre + 12:
    foot_ball = min over the 8 foot joints of |joint xy − ball xy|
    for ball in (pose_frames ball, tracking ball interpolated to the pose frame)
keep starts and ends with all 25 pose frames
closest = pose frame with the smallest foot_ball → its offset / 25 fps and its distance

tracking_ball_at_pose_frames:
    before = pose_frame × 2 // 5; weight = (pose_frame × 2 mod 5) / 5
    ball   = (1 − weight) × ball(before) + weight × ball(before + 1)
```

**`pose_ball` and `logged_positions`.**

```
pose_ball: over each period of pose_frames, frames where |ball(f + 1) − 2 × ball(f) + ball(f − 1)|
           exceeds 2 mm in any of x, y and z, counted by frame mod 5;
           each pose frame divisible by 5 against its tracking frame (pose frame 5000 against
           tracking frame 2000): horizontal distance between the two balls, overall and by each
           source's ball_data_is_detected; and against the tracking frames either side (1999 and 2001)
logged_positions: |logged xy − player tracking xy| at the event frame, by match, start and end
```

**Reuse.** The `to_pitch_frame` function in `goalside.skillcorner.frames` converts the logged positions, and the `pose_frame` function the event frames. The ball's 'second difference' around an event frame would belong in `goalside` as a function that returns the frame of a touch near a given event.

## Revisions

None since publication.
