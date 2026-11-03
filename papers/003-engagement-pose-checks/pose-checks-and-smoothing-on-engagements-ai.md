---
goalside: 0.1.0
history:
- date: 2026-11-03
  event: published
---

# 'Do my legs look long in this?': Identifying and addressing inconsistencies in SkillCorner open body pose data

**Why study this?:** The quality of SkillCorner open body pose data appears to vary depending on whether players are close to each other. It would be useful to find out the extent of this, to guide post-processing and analysis techniques.

---

## Abstract

This study measures how often SkillCorner's body pose is internally inconsistent in ways that can be detected from the data itself; such as bones that change length, joints that jump out and back between frames, and limbs bent tighter than a joint allows. 

Ten checks and one smoothing method were applied to the pose data of defenders engaging the ball carrier around their team's last line in open play (a subset chosen for a smaller-scale study), from two A-League matches at 25 frames per second.

It has four findings:
- **The pose varies within a standard range in every frame.** In the median frame of ordinary movement, a limb bone is 11% off that player's usual length for it, though a real bone keeps its length, and the largest 'second difference' of a limb joint is 107m/s².
- **SkillCorner's own error estimate misses most frames where a joint changes velocity sharply.** Of the frames whose 'second difference' is above its check's threshold, the error estimate is also above its threshold in only 23.8%, so it can't be the only check.
- **Large inconsistencies concentrate where players are close together.** Each check flagged frames 4 to 12 times as often when the defender was within 1m of the ball carrier as when they were 4m or more away.
- **Smoothing removes the standard variation, not the large inconsistencies.** A seven-frame Savitzky–Golay fit more than halved the typical 'second difference' of the raw pose while moving joints by less than their reported error, but spread the large inconsistencies over neighbouring frames.

The standard variation and the large inconsistencies therefore need different treatment: smoothing for the standard variation, and, perhaps, detection, removal and interpolation for the large inconsistencies.

## 1. Introduction

Measures such as joint angles and foot speeds are computed from pose data that SkillCorner generates from broadcast footage, so an error in a joint's position carries into every measure computed from it. 

Pose data can have errors which are not necessarily apparent when observing single frames in isolation, such as the implicit length of a player's limb changing.

The study asks four questions about the data:
1. How common are detectable inconsistencies, and of which kinds?
2. Does SkillCorner's error estimate flag the same frames as checks based on the geometry and motion of the pose?
3. To what extent are inconsistencies more likely when players are close together?
4. Can smoothing bring the pose to a consistent state without moving joints further than their reported error?

## 2. Definitions

**Pose frame.** One of SkillCorner's body-pose time steps, 40ms apart (25 frames per second). In each, a player with resolved pose has 29 joints in 3D pitch coordinates, in metres.

**Defender frame.** A pose frame of an engaging defender in which all 29 joints are present.

**Engagement.** A record of type `on_ball_engagement` in SkillCorner's Dynamic Events data: a period in which a defender engages the player in possession, the **ball carrier**. It has a start frame and an end frame, and its physical start is the frame at which the defender first exceeds 15km/h on the way to engaging.

**Open play.** The frames inside a phase of play, one of SkillCorner's stretches of one team's possession in `skillcorner.phases_of_play`, whose phase type for the team in possession is not `set_play`. Set plays, and the stoppages between phases, are left out.

**At the last line.** An engagement is at the last line when the defender starts it within 5m of their team's last defensive line, by the Dynamic Events data's `delta_to_last_defensive_line_start` column. The study uses the 292 engagements in the two matches that start in open play at the last line, of 1,961 in all, so that it covers the engagements between the defending team's back line and the opponents it faces.

**Distance to the carrier.** The horizontal distance between the defender's `midHip` joint and the carrier's in the same frame.

**Ordinary movement.** The 25 defender frames before the physical start of each of 267 engagements, when defenders are walking, jogging or running and not yet engaging.

**Close engagement frames.** The defender frames from 1s before the start frame to 1s after the end frame of 24 engagements that ended in a regain, where a defender foot came within 1m of the ball or the two players' hips came within 1m of each other.

**Error radius.** SkillCorner's `p90_mae_cm` for a joint in a frame: the distance, in centimetres, within which SkillCorner estimates the true joint position lies 90% of the time ([body pose README](https://github.com/SkillCorner/opendata/blob/master/data/bodypose/README.md)). Over every pose player-frame of the two matches, its median is 6.4–6.5cm for the trunk, 6.8–6.9cm for the head, 9.2–9.4cm for knees and elbows, 12.8–13.0cm for ankles and wrists, and 15.5–15.6cm for feet and hands (paper `002-tracking-smoothness`, section 4.8).

**Limb joints.** Both knees, ankles, elbows, wrists, big toes and heels: the twelve joints the second-difference and jump checks examine.

**Limb bones.** Both thighs (hip to knee), shins (knee to ankle), upper arms (shoulder to elbow) and forearms (elbow to wrist).

**Knee angle.** The angle at the knee between the thigh and the shin; a straight leg is 180°. The angle checks look at the knees only, the joint football analysis uses for running, kicking and tackling.

**'Second difference'.** As in paper `002-tracking-smoothness`, a measure of how smoothly a point moves: how much its velocity changes at a frame, which is an estimate of its acceleration. Take the point's position in the frame before, in the frame itself and in the frame after. Its velocity coming into the frame is the change from the first position to the second, and its velocity leaving is the change from the second to the third; the 'second difference' is the change between those two velocities, divided by the time between frames (0.04s), in m/s². A point moving at a steady speed in a straight line has a 'second difference' of zero. For a knee angle, the paper gives the 'second difference' before the division by time, in degrees: how much more or less the knee bent going into the frame than coming out of it, so a knee bending by 3° into a frame and then by 1° out of it has a 'second difference' of 2°. In these units it can be compared directly with the angle zigzag check's 15° and the out-of-range check's 40°.

**Zigzag.** As in paper `002-tracking-smoothness`, a change of direction in opposite directions through subsequent frames: a knee angle or a joint's position moves one way from the frame before and back the other way to the frame after, such as a knee bending by 3° and then straightening by 2°. For a position, the move back is one that points more than 90° away from the move before. The **size** of a zigzag is the smaller of its two moves, so a 2° zigzag went at least 2° each way. Two checks look for zigzags: the angle zigzag check flags a knee angle that zigzags by more than 15°, and the position zigzag check measures the largest zigzag of a limb joint relative to `midHip`. A large 'second difference' is not always a zigzag, since a sharp change of speed in one direction makes one too.

**Raw pose.** The joint positions as SkillCorner publishes them, with no smoothing of ours. Section 4.5 and Appendix B.3 compare it with the smoothed and fitted pose.

**Inconsistency.** A property of a pose that the data shows cannot be true of a real body, or is very unlikely to be: a bone whose length changes, a joint that accelerates faster than a limb can, a limb bent beyond its range, all joints at one point. Detecting an inconsistency needs no external reference, unlike measuring accuracy.

**Check.** A rule that gives each defender frame a value, such as how far a bone is from its usual length, or a yes or no, such as whether the pose has collapsed.

**Flag.** A frame is flagged by a check when its value is above the check's threshold, or when a yes/no check says yes.

**Threshold.** For checks that give a value, the 99th percentile of that value across ordinary movement. Ordinary movement contains inconsistencies too, so a threshold marks the most extreme 1% of ordinary frames, not a physical limit. By construction, about 1% of ordinary frames are flagged by each such check.

**Spearman correlation.** The correlation between the ranks of two measures across frames: 0 means no relationship, 1 means one always rises with the other.

## 3. Data and methods

This section summarises what the analysis code does; Appendix B describes the code itself.

### 3.1 Data

SkillCorner's open body pose for two matches, Match A (Brisbane Roar v Perth Glory, ID 1925299, 2024-12-21) and Match B (Sydney FC v Adelaide United, ID 1996435, 2025-02-01), with the matches' Dynamic Events data and phases of play, as `goalside v0.1.0` converts them into the `skillcorner.pose`, `skillcorner.pose_frames`, `skillcorner.dynamic_events` and `skillcorner.phases_of_play` tables, each at schema version 1. 

The study uses 6,415 defender frames of ordinary movement from 267 engagements and 2,746 close engagement frames from 24 engagements, all at the last line in open play. Only the defender is checked; the carrier's pose is used only for the distance between the two.

Collapsed frames (when the body pose joints are in tight proximity to each other) are excluded from every check except the collapsed check itself, because their joints have no meaningful lengths or angles.

### 3.2 Checks

| Check | Value per defender frame | Flag |
| --- | --- | --- |
| Bone length | The largest relative difference of a limb bone's length from that player's usual length for the same bone, the median over their ordinary-movement frames | Above threshold |
| Joint jump | The largest speed of a limb joint relative to `midHip` between the previous frame and this one | Above threshold |
| Limb position second difference | The largest 'second difference' of a limb joint's position relative to `midHip`, in m/s² | Above threshold |
| Knee angle second difference | The largest 'second difference' of a knee angle, in degrees | Above threshold |
| Limb position zigzag | The size of the largest zigzag of a limb joint relative to `midHip`, in metres | Above threshold |
| Knee angle zigzag | Whether a knee angle changes by more than 15° from the previous frame and then by more than 15° in the opposite direction to the next | Yes |
| Out of range | Whether a knee angle is below 40°, tighter than a knee bends | Yes |
| Left/right swap | Whether the knees and ankles, compared with the previous frame, each lie much nearer where the opposite-side joint was than where they were themselves: the summed cross-side displacement is under half the same-side displacement, which is over 0.4m | Yes |
| Error estimate | The mean error radius over the 29 joints, divided by that player's median of the same | Above threshold |
| Collapsed | Whether all 29 joints lie within 0.3m of each other | Yes |

The checks cover four kinds of inconsistency: those measured in one frame alone (out of range, collapsed); bone length, which compares a frame's bones with the player's usual lengths, the medians over their ordinary-movement frames; those measured between consecutive frames (joint jump, 'second differences', zigzags, swap); and the model's own report of uncertainty (error estimate).

The code for every step is described in Appendix B: B.1 (frames and selection), B.2 (checks and results) and B.3 (smoothing).

### 3.3 Comparisons

1. The typical size of each inconsistency in ordinary movement, and the share of frames each check flags in ordinary movement and in close engagement frames.
2. Whether SkillCorner's error estimate is high in the frames where the other checks find inconsistencies, measured in two ways:
   - the Spearman correlation between the error estimate's value and each other check's value across all frames, which says whether frames ranked high by one tend to be ranked high by the other;
   - of the frames flagged by either 'second difference' check, the share the error estimate also flags, and of the frames the error estimate flags, the share either 'second difference' check also flags.
3. The share of frames flagged at four bands of distance to the carrier: under 1m, 1–2m, 2–4m, and 4m or more.

### 3.4 Smoothing

Each joint coordinate in a defender frame was replaced by a Savitzky–Golay fit: a quadratic fitted by least squares to that coordinate on the frame and the three frames either side, evaluated at the centre frame.

A second, optional step fitted the skeleton to fixed bone lengths. Working outward from `midHip` along the skeleton, each joint was moved along the line from its parent joint so that the bone between them took that player's median length.

Both steps were applied to the 6,838 defender frames, from both sets, that had all seven frames of the fitting window. They were compared with the raw frames on four measures:
- the 'second difference' of limb joint positions;
- the 'second difference' of knee angles;
- the largest relative bone-length difference;
- the distance each joint moved from its raw position, by body part and distance to the carrier.

## 4. Results

### 4.1 The pose varies within a standard range in every frame

| Measure | Median, ordinary movement | Median, close engagement frames | 99th percentile, ordinary movement (the threshold) |
| --- | --- | --- | --- |
| Worst limb bone off its median length | 10.6% | 14.3% | 50.7% |
| Largest limb-joint 'second difference' | 107m/s² | 168m/s² | 660m/s² |
| Largest knee angle 'second difference' | 10.6° | 15.3° | 67° |
| Largest limb-joint zigzag | 5.1cm | 8.8cm | 44cm |
| Fastest limb joint relative to `midHip` | 4.2m/s | 5.7m/s | 16.5m/s |
| Mean error radius relative to the player's median | 0.97 | 1.11 | 1.71 |

Each threshold is the 99th percentile of ordinary movement, so that every check that gives a value flags the same 1% of ordinary-movement frames, whatever its units. The thresholds are therefore set from the data rather than at physical limits. The bone-length threshold shows how far apart the two can be: in 1% of ordinary-movement frames a limb bone is more than half off its usual length, which no real bone is, and a threshold at a physical limit, such as a bone 20% off its usual length, would flag many more frames, since the median frame is already 10.6% off. The checks therefore find the most extreme inconsistencies in the data, not every one.

These figures are for the raw pose, as SkillCorner publishes it. Bone lengths varying by around 10% in ordinary movement show that SkillCorner's model does not hold a player's bone lengths fixed from frame to frame. The largest limb-joint 'second difference' in the median frame, 107m/s², is the largest of twelve joints, so it is above the medians of single joints over every frame of the two matches in paper `002-tracking-smoothness`, 25–41m/s² for the knees and elbows, ankles and wrists, and feet and hands.

### 4.2 Large inconsistencies by kind

Share of defender frames flagged:

| Check | Share of ordinary-movement frames flagged | Share of close engagement frames flagged |
| --- | --- | --- |
| Bone length | 1.00% | 4.62% |
| Joint jump | 0.95% | 5.94% |
| Position second difference | 0.92% | 5.61% |
| Angle second difference | 0.92% | 4.81% |
| Position zigzag | 0.92% | 4.92% |
| Error estimate | 1.00% | 6.23% |
| Angle zigzag | 2.43% | 9.72% |
| Out of range | 0.02% | 0.18% |
| Left/right swap | 0.09% | 0.29% |
| Collapsed | 0.00% | 0.11% |
| Any check | 4.82% | 19.26% |

The threshold-based checks flag about 1% of ordinary frames by construction and five to six times that in close engagement frames. The angle zigzag check flags 2.4% of ordinary frames and 9.7% of close engagement frames, so a knee angle that moves more than 15° one way and then back between consecutive frames is uncommon in this data but not rare. Knees bent beyond their range and collapsed poses are rare, and the swap check flags almost nothing anywhere.

### 4.3 The error estimate flags a quarter of the frames the second-difference checks flag

Of the 332 frames flagged by either second-difference check, the error estimate also flagged 23.8%. Of the 235 frames the error estimate flagged, either second-difference check also flagged 36.6%. Of the 194 frames the position zigzag check flagged, the error estimate also flagged 28.4%.

| Check | Spearman correlation with the error estimate |
| --- | --- |
| Bone length | 0.51 |
| Position second difference | 0.42 |
| Angle second difference | 0.30 |
| Position zigzag | 0.40 |
| Joint jump | 0.28 |

The error estimate and the motion-based checks pick out largely different frames. A frame the model reports as confident can still contain a joint that jumps out and back, and the error estimate agrees best with bone-length inconsistency, which compares each frame with the player's usual bone lengths, and least with joint jumps, which compare consecutive frames.

### 4.4 Inconsistencies rise with closeness to the carrier

Share of frames flagged, by distance to the carrier, over all frames in which both players have pose:

| Distance to carrier | Frames | Flagged by either second-difference check | Flagged by the position zigzag check | Flagged by the error estimate | Flagged by bone length | Flagged by the angle zigzag check |
| --- | --- | --- | --- | --- | --- | --- |
| Under 1m | 453 | 13.0% | 7.3% | 10.4% | 10.6% | 10.4% |
| 1–2m | 1,140 | 9.9% | 6.1% | 7.1% | 4.7% | 11.5% |
| 2–4m | 1,761 | 3.4% | 1.6% | 3.1% | 1.9% | 5.1% |
| 4m or more | 5,677 | 2.1% | 1.1% | 0.9% | 0.9% | 2.7% |

Under 1m, each check flags 4-12 times as many frames as at 4m or more, with bone length and the error estimate rising most (about 12 times) and the angle zigzag check least (4 times). The rise is steady across the bands for most checks, not a jump at contact; the angle zigzag check flags as many frames at 1–2m as under 1m.

### 4.5 Smoothing

Each of the 6,838 defender frames was compared in three versions: the raw pose, as SkillCorner publishes it; the smoothed pose (section 3.4); and the smoothed pose fitted to the player's usual bone lengths. Three measures of inconsistency for each version, as medians across the frames, with 99th percentiles in brackets:

| Pose | Largest limb-joint 'second difference', median (99th percentile) | Largest knee angle 'second difference', median (99th percentile) | Worst limb bone off its usual length, median (99th percentile) |
| --- | --- | --- | --- |
| Raw | 125m/s² (911m/s²) | 12.0° (93°) | 11.7% (68.9%) |
| Smoothed | 53m/s² (200m/s²) | 5.6° (27°) | 12.2% (56.0%) |
| Smoothed, then fitted to bone lengths | 54m/s² (228m/s²) | 5.6° (27°) | 0% (0%) |

Smoothing more than halved the median 'second difference' of both the limb joints and the knee angles, and cut the 99th percentile of the limb joints' from 911m/s² to 200m/s². It barely changed bone lengths, which only the fitting step set to the player's usual lengths.

Smoothing and fitting move the joints, so the next two tables check how far. They give the median distance each joint moved from its raw position, by body part and distance to the carrier, for smoothing alone and for smoothing then fitting, with SkillCorner's median error radius for each body part in the last row:

| Smoothing alone, distance to carrier | Trunk (cm) | Head (cm) | Knees and elbows (cm) | Ankles and wrists (cm) | Feet and hands (cm) |
| --- | --- | --- | --- | --- | --- |
| Under 1m | 2.5 | 2.8 | 3.6 | 5.1 | 5.6 |
| 1–2m | 2.4 | 2.7 | 3.4 | 4.7 | 5.2 |
| 2–4m | 1.9 | 2.0 | 2.6 | 3.5 | 4.0 |
| 4m or more | 1.7 | 1.9 | 2.2 | 2.9 | 3.3 |
| SkillCorner's median error radius | 6.4–6.5 | 6.8–6.9 | 9.2–9.4 | 12.8–13.0 | 15.5–15.6 |

| Smoothing then fitting, distance to carrier | Trunk (cm) | Head (cm) | Knees and elbows (cm) | Ankles and wrists (cm) | Feet and hands (cm) |
| --- | --- | --- | --- | --- | --- |
| Under 1m | 3.4 | 4.6 | 4.6 | 6.8 | 7.5 |
| 1–2m | 3.4 | 4.7 | 4.4 | 6.5 | 7.2 |
| 2–4m | 2.5 | 3.3 | 3.5 | 4.9 | 5.5 |
| 4m or more | 2.2 | 2.9 | 3.0 | 4.1 | 4.6 |
| SkillCorner's median error radius | 6.4–6.5 | 6.8–6.9 | 9.2–9.4 | 12.8–13.0 | 15.5–15.6 |

Every median distance moved is smaller than its body part's median error radius, at every distance to the carrier. The error radius is the distance from the published position within which SkillCorner estimates the true joint position lies 90% of the time, so the smoothed and fitted joints stay, at the median, within the area where SkillCorner's own estimate places the true joint.

The 99th percentile of the smoothed limb-joint 'second difference' is still 200m/s² overall and 250m/s² when the defender is under 1m from the carrier, against 911m/s² and 984m/s² raw. Each smoothed position is a weighted average of seven raw frames, so a large error in one raw frame is not removed: each of the seven smoothed frames around it takes on part of that error, which leaves the large inconsistencies smaller but spread over more frames.

## 5. Discussion

The data contains two kinds of inconsistency, and they need different treatment.

**A standard range of variation in every frame.** In the raw pose, joint positions vary from frame to frame and bone lengths vary by around 10% throughout ordinary movement. Smoothing more than halves the typical 'second difference', and it moves each joint, at the median, by less than SkillCorner's error radius for that joint, the distance from the published position within which SkillCorner estimates the true position lies 90% of the time. So a smoothed joint is still where SkillCorner's own estimate says the true joint could well be. Fitting bone lengths moves the joints about 2cm further at the median and removes the length variation entirely.

**Large inconsistencies in a few frames, concentrated at close range.** These are 'second differences' of several hundred m/s², bones stretched by half their length, and joints moving faster than a limb can. This paper's smoothing does not remove them, because each smoothed frame is a weighted average of seven raw frames, so a large error in one frame is shared out across the seven around it rather than dropped, which is why the 99th percentile of the smoothed limb-joint 'second difference' is still 200m/s². One approach, not tested here, would be to detect them, drop the affected frames and fill short gaps by interpolation before smoothing. Their rise as players come together fits the two players hiding each other from the broadcast camera, and it means the frames around a challenge, which tackle measures need most, are the least reliable.

**No single check covers the others.** The checks find largely different frames: of the frames either 'second difference' check flags, SkillCorner's error estimate also flags only 23.8%, and the error estimate's Spearman correlation with each of the other value-based checks is between 0.28 and 0.51 (section 4.3), where 1 would mean the two always rank frames in the same order. Finding the large inconsistencies would therefore take the error estimate, the 'second difference' checks and the jump check together.

### 5.1 Limitations

- **Relative thresholds.** Each threshold is the 99th percentile of ordinary movement, which contains inconsistencies itself. The thresholds mark unusual frames, not impossible ones, and a different percentile would change every flag rate.
- **Defenders at the last line only.** Only the defender's pose was checked, and only in and just before engagements at the last line in open play. Other players, engagements further from the last line, and set plays were not.
- **Selected close frames.** The close engagement frames were chosen for close contact, so they over-represent it compared with play in general, and are a fairly small sample size.
- **No ground truth.** Inconsistency is not the same as error: a pose can be consistent and wrong, and a large 'second difference' can occasionally be real, since a very fast change of direction or speed produces one too. Smoothing was judged against the raw data and the reported error radius, not against true joint positions, which the data does not contain.
- **Per-player medians.** Bone-length and error-estimate medians come from each player's defender frames in this study, which is fewer frames for players involved in few engagements: the 34 defenders have between 25 and 723 frames each, so medians for some players may rest on a single engagement. A median that is itself off would shift every flag for that player.
- **The swap check.** It requires both knee and ankle to swap together and flags almost nothing. Whether swaps are simply very rare in this data or the check is too strict is not known.
- **Fast movement.** Smoothing will also lower the peak speed of a real fast movement, such as a kick or a tackle thrust. To what extent was not measured.

## 6. Implications

- **The standard range of variation** would be reduced by smoothing every run of a player's frames, such as with this paper's seven-frame Savitzky–Golay fit.
- **Bone lengths** could be held fixed by fitting each frame to the player's median bone lengths, provided those medians come from enough frames and leave out collapsed ones.
- **Large inconsistencies** would be found with the 'second difference', joint-jump and error-estimate checks together, since each finds frames the others miss. Dropping the flagged frames and interpolating across short gaps before smoothing is one option, not tested here.
- **Close range** is where the inconsistencies concentrate, so analyses of challenges would decide how to treat frames under 1m from another player: dropping flagged frames there removes much of each challenge, while keeping them keeps the inconsistencies. One approach would be to flag quality per joint and frame, let each measure use only the joints it needs, and report how many events each measure kept.
- **Comparable measures.** Any measure derived from pose, and any threshold applied to it, would be computed on data cleaned the same way.

## Future points for research

- How much does seven-frame smoothing lower the peak speed of a real kick or foot thrust? Measuring it needs a movement whose true speed is known, which the data cannot supply on its own.
- Do the same rates hold for players who are not engaging, for engagements further from the last line, and in set plays?
- Are close-range inconsistencies worse when one player stands between the other and the camera? The frames table's image corners would allow the camera's position to be estimated.

## Sources

- SkillCorner, [body pose README](https://github.com/SkillCorner/opendata/blob/master/data/bodypose/README.md): the per-joint error "is defined so that 90% of estimated key points are sitting within this error radius".
- SkillCorner's open body-pose data, Dynamic Events data and match information for matches 1925299 and 1996435, converted with `goalside v0.1.0` into the tables listed in section 3.1.

## Appendices

### Appendix A: versions

The paper's results come from `goalside v0.1.0`, reading these tables at these schema versions:

| Table | Schema version |
| --- | --- |
| `skillcorner.pose` | 1 |
| `skillcorner.pose_frames` | 1 |
| `skillcorner.dynamic_events` | 1 |
| `skillcorner.phases_of_play` | 1 |

`goalside v0.1.0` converted them from this data:

| Data | Version | Checked |
| --- | --- | --- |
| SkillCorner open data | [`opendata` commit 4340d27](https://github.com/SkillCorner/opendata/tree/4340d274572876239c154c90bc507a9b3250a656) (2026-09-14) | The Dynamic Events and phases of play CSVs and `match.json` match the commit by git hash |
| Full body pose | SkillCorner's [opendata-bodypose](https://huggingface.co/datasets/SkillCorner/opendata-bodypose) dataset on Hugging Face | Each archive matches the size and SHA256 in `data/bodypose/MANIFEST.json` at the same commit, which `goalside` checks when it downloads it |

`goalside` downloads SkillCorner's files from the `opendata` repository's `master` branch. Reproducing the paper after a later SkillCorner commit would mean taking the files from commit 4340d27, for example from a clone of `opendata` at that commit, and passing each to `goalside`'s converter functions as `source`.

### Appendix B: the analysis scripts

The analysis runs in three stages, each a script in this folder.

#### B.1 Engagement frames and the close engagements

**Location.** `engagement-windows.py` in this folder. The results above come from `goalside v0.1.0`.

**How to run it.**

```
uv run python papers/003-engagement-pose-checks/engagement-windows.py
```

It needs both matches' tables in `goalside`'s data directory (the `goalside.data_dir()` function), loaded with `goalside`'s `download_match` and `convert_match`, `download_dynamic_events` and `convert_dynamic_events`, `download_phases_of_play` and `convert_phases_of_play`, then `download_pose_match` and `convert_pose` functions. It writes to `outputs/` in this folder, which B.2 and B.3 read, and takes about a minute.

**Inputs.**
- **`skillcorner.dynamic_events`:** every `on_ball_engagement` in the two matches whose `delta_to_last_defensive_line_start` is at most 5m, with its match, event ID, period, defender (`player_id`), carrier (`player_in_possession_id`), `end_type`, and start, end and physical-start frames.
- **`skillcorner.pose`:** all 29 joints with `p90_mae_cm`, for the two players' frames in each window.
- **`skillcorner.pose_frames`:** the 25fps ball position.
- **`skillcorner.phases_of_play`:** each phase's frames and `team_in_possession_phase_type`.

**How it was executed.**
1. **Engagements and their frames.** Of the 1,961 on-ball engagements in the two matches, 306 start within 5m of the last line, and 292 of those start inside a phase of play whose `team_in_possession_phase_type` is not `set_play`. These 292 are sorted by match, start frame and event ID and numbered (`row`). Each gets three pose frames from the `pose_frame` function in `goalside.skillcorner.frames`, which multiplies a 10fps frame by 2.5 and rounds half up:
   - `s`, from the start frame;
   - `e`, from the end frame;
   - `ps`, from the physical start, or the start frame when there is none.
2. **Pose loading.** For each engagement, every pose frame from `ps − 25` to `e + 24` is requested for both the defender and the carrier. The requests are grouped by match and period, the matching rows are read from `skillcorner.pose`, and they are placed into an array `P` (player-frames × 29 joints × 3 coordinates) and an array `E` of error radii. An index records which row of the arrays holds which engagement, role ("def" or "car") and frame. 60,650 player-frames were loaded. A player-frame is *complete* when all 29 joints are present.
3. **Engagements with pose.** An engagement has pose when both players are complete at `e`, or at `e ± 1` or `e ± 2`: 288 of the 292.
4. **Regain series.** For direct and indirect regains with pose, where the defender is complete on every frame from `s` to `e` (54 engagements), two distances are computed on each of those frames:
   - **foot to ball:** the smallest 3D distance from any of the defender's eight foot joints (ankles, heels, big toes, small toes) to the ball;
   - **hips:** the horizontal distance between the two players' `midHip` joints.

   A collapsed pose, with all joints within 0.3m of each other, counts as missing, as does a frame without a ball.
5. **Selection.** An engagement is a close engagement when either series falls below 1m on any frame:

   ```python
   193	        .filter((pl.col("min_foot") < CLOSE_M) | (pl.col("min_hips") < CLOSE_M))
   ```

   This gives 24: 5 direct regains and 19 indirect regains.
6. **Usual bone lengths.** For each defender, the median length of each of the 28 bones in the skeleton tree, over their ordinary-movement frames only: the 25 pose frames before the physical start of each engagement with pose, complete and uncollapsed, when bone lengths are expected to be most stable. The 34 defenders have between 25 and 723 such frames each; the 13 in the close engagements have at least 50. B.2 and B.3 both use these medians.

**Outputs** in `outputs/` in this folder (gitignored):
- `poses.npz` (arrays `P` and `E`, float32);
- `pose_index.parquet` (`k`, `row`, `role`, `frame`);
- `engagements.parquet` (one row per engagement with `s`, `e`, `ps` and `has_pose`);
- `regain_series.parquet` (`row`, `frame`, `foot_ball`, `hips`);
- `close_engagements.parquet` (`row`, match, event, `end_type`, `min_foot`, `min_hips`);
- `bone_medians.parquet` (`player_id`, `bone`, `median_m`, `frames`).

**Reuse.** Loading two players' pose around a list of events (step 2) is the pattern any event study needs. A function taking a table of (match, period, player, frame range) and returning arrays plus an index would belong in the `goalside.skillcorner.pose` module beside the `pose_window` function.

#### B.2 The checks and the results tables

**Location.** `engagement-pose-checks.py` in this folder.

**How to run it.** `uv run python papers/003-engagement-pose-checks/engagement-pose-checks.py`, after B.1. It takes about two minutes and writes `quality_frames.parquet` (one row per checked frame) and `pose_checks.json`, which holds every table in sections 4.1 to 4.4.

**Inputs.** B.1's outputs, including the 24 close engagements in `close_engagements.parquet`.

**How it was executed.**
1. **Usual bone lengths.** The eight limb-bone medians from B.1, step 6.
2. **Frame sets.** For each engagement with pose:
   - the frames from `ps − 25` to `ps − 1` are checked as ordinary movement;
   - if it is one of the 24 close engagements, the frames from `s − 25` to `e + 24` are also checked as close engagement frames.

   The two windows overlap when an engagement's physical start is less than 25 frames before its start frame, and a frame in both is counted in each set.
3. **Per-frame checks.** For each defender frame with complete pose, the function `window_frames` computes:
   - **collapsed:** whether all joints lie within 0.3m. A collapsed frame gets no other value;
   - **bone length and out of range,** from the frame alone;
   - **joint jump and left/right swap,** only when the previous frame is complete and uncollapsed;
   - **the two 'second differences' and the two zigzags,** only when both neighbouring frames are.

   Joint positions in the jump and second-difference checks are taken relative to `midHip`, so whole-body movement cancels out. Knee angles come from the arccosine of the normalised dot product of the thigh and the shin.
4. **Error estimate.** The mean of the frame's 29 error radii, divided by that defender's median over all checked frames.
5. **Distance to the carrier.** The horizontal distance between the two `midHip` joints, where the carrier is complete in the same frame.
6. **Thresholds and tables.**
   - **Thresholds.** Each value-based check's threshold is its 99th percentile over the ordinary-movement frames, and a frame is flagged above it. A yes/no check flags on yes, and a missing value never flags.
   - **Flag rates** are means of the flags by group.
   - **Correlations and overlaps** (section 4.3) use uncollapsed frames from both sets. The overlaps count frames flagged by either second-difference check against frames flagged by the error estimate.
   - **Distance bands** use the frames with a carrier distance.

**Reuse.** Each check is a few lines of `window_frames` and could become a function taking a pose window and returning a value per frame, with its threshold as a parameter.

#### B.3 Smoothing

**Location.** `engagement-smoothing.py` in this folder.

**How to run it.** `uv run python papers/003-engagement-pose-checks/engagement-smoothing.py`, after B.1. It takes a few minutes and writes `smooth_frames.parquet` and `smoothing.json`.

**How it was executed.**
1. **Frames.** The same two frame sets as B.2, both windows as defined there.
2. **Savitzky–Golay weights.** The seven weights that give a quadratic least-squares fit's value at the centre of seven equally spaced frames are the first row of the pseudo-inverse of the 7 × 3 matrix with rows (1, t, t²) for t = −3 to 3:

   ```python
   37	SG = np.linalg.pinv(np.vander(np.arange(-M, M + 1), 3, increasing=True))[0]  # weights for the fitted centre value
   ```

   A frame is smoothed only when all seven frames of its window are complete and uncollapsed. Every coordinate of every joint is then the weighted sum of its seven values.
3. **Bone-length fit.**
   - **Medians.** The 28 bone medians from B.1, step 6.
   - **The fit.** Walking from `midHip` outward, each child joint is moved along the line from its parent so that the bone between them takes that median length, starting from the smoothed pose.
4. **Measures.**
   - **Compared frames.** Measures are computed on frames whose own window and both neighbours' windows were smoothed, 6,838 frames in all.
   - **'Second differences' and bones.** The two 'second differences' (as in B.2, in m/s² and degrees) and the largest limb-bone difference from its median, for the raw, smoothed and fitted poses.
   - **Movement.** For smoothing and for the fit, the distance each joint moved from its raw position, as the median within each body part, by distance to the carrier.

**Outputs.** `smooth_frames.parquet`, one row per compared frame, and `smoothing.json`, with:
- the medians and 99th percentiles of the three measures for raw, smoothed and fitted poses;
- the movement by body part and distance band;
- the 'second difference' by distance band.

**Reuse.** The smoothing weights and the bone-length fit could each become a function on a pose window.

## Revisions

None since publication.
