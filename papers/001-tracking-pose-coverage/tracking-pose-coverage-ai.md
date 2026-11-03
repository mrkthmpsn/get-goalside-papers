---
goalside: 0.1.0
history:
- date: 2026-11-03
  event: published
---

# Lights, camera, action: SkillCorner open data camera coverage

**Why study this?:** To find out if there's measurement error between the tracking data and the body pose data, and, if so, how large it is.

---

## Abstract

This blog-paper measures four basic properties of SkillCorner's tracking and body pose data made publicly available for two A-League matches, Match A (Brisbane Roar v Perth Glory, ID 1925299, 2024-12-21) and Match B (Sydney FC v Adelaide United, ID 1996435, 2025-02-01). 

The areas covered in the study are: how much of the tracking is covered from the broadcast camera, how much of the broadcast tracking has pose data, and how far apart the two sources place the same player. 

It has four findings:
- **Frame pairing.** Each match has several instances of two pose frames with the same timestamp, one of which sits outside the end of a period, interfering with easy joining of pose and tracking data on timestamps alone. However, pairing by frame rates is possible.
- **Direct detection level.** In the two matches, 57.9% (Match A) and 65.8% (Match B) of tracking data frames were noted as detected directly from the broadcast footage; the rest of the tracking data extrapolated by SkillCorner's model. In 21.8% of frames (Match A) and 24.4% (Match B), the tracking lists no players. 
   - _These frames are stoppages that the broadcast does not show as a view of the pitch: they have no ball and almost never a camera view, 95–96% of them fall outside every phase of play from SkillCorner's Dynamic Events data, and 48/53 instances (Match A) and 67/71 (Match B) start after an on-ball event that ends in a goal kick, free kick, throw-in, corner or goal._
- **Pose coverage.** Of the player-frames the camera detected (_not_ the extrapolated tracking data), 98.0% have pose in Match A and 98.6% in Match B. Out of _all_ tracking player-frames, off-camera extrapolated data included, that's 57.8% (Match A) and 65.4% (Match B) with pose data.
- **Tracking against pose.** Where the camera detects a player, the tracking position lies this far from the pose `midHip`:

  | Match ID | Median | 75th percentile | 90th | 95th |
  | --- | --- | --- | --- | --- |
  | Match A | 0.22m | 0.35m | 0.53m | 0.69m |
  | Match B | 0.20m | 0.30m | 0.43m | 0.54m |

  However, the distance does not grow with a player's speed, which would be a type of measurement error that could interfere with analysis.

## 1. Introduction

SkillCorner's open data has three types:
- **tracking**, which places every player on the pitch at 10 frames per second, extrapolating the position of players not visible on the camera footage that the main tracking data is drawn from;
- **body pose**, which gives 29 joints for players at 25 frames per second;
- **Dynamic Events data**, which record possessions, passing options, off-ball runs and on-ball engagements, each with its player's position at the start.

Analyses will tend to combine data sources, for example to see player pose shapes when moving or turning at different speeds and angles. That requires us to know how much the data sources agree with each other, and the extent that pose data exists in relation to tracking data. 

SkillCorner states that tracking and pose are generated separately ([body pose README](https://github.com/SkillCorner/opendata/blob/master/data/bodypose/README.md)), so some disagreement between them is expected.

The blog-paper asks four questions:
1. How to match tracking data and pose data?
2. How much of the tracking did the camera detect, and how much is extrapolated or missing?
3. What share of detected player-frames have pose?
4. How far is a player's tracking position from their pose data, and does the distance increase with the speed they're moving?

## 2. Definitions

**Tracking frame.** One of SkillCorner's tracking time steps, 100ms apart (10 frames per second), numbered from 0 at the start of the file.

**Pose frame.** One of SkillCorner's body-pose time steps, 40ms apart (25 frames per second), numbered from 0 at the same instant as tracking frame 0.

**Timestamp.** The match clock each source records with every frame, in the `skillcorner.tracking_frames` and `skillcorner.pose_frames` tables: time since the start of the period, to 100ms in tracking and 40ms in pose.

**Pose-tracking frame.** An instant that is both a pose frame and a tracking frame. The two coincide every 200ms, at tracking frames 0, 2, 4, … and pose frames 0, 5, 10, …, so tracking frame f is pose frame 5f/2 when f is even. The step of 2 tracking frames and 5 pose frames follows from the frame rates (10 and 25 frames per second, whose greatest common divisor is 5), and section 4.1 confirms it against the timestamps. Comparisons between pose and tracking use pose-tracking frames only, so that the two sources describe the same instant.

**Player-frame.** One player in one frame. A **tracking player-frame** is a player's row in one tracking frame, with a position; a **pose player-frame** is a player's joints in one pose frame.

**Detected and extrapolated.** Each tracking player-frame has an `is_detected` flag, `true` when the data is generated from the broadcast footage and `false` when SkillCorner's model extrapolated a player's position outside the camera's view ([opendata README](https://github.com/SkillCorner/opendata), Tracking Data Description). Every tracking frame that lists players lists all 22 players on the pitch, detected or extrapolated, in both matches.

**Frame without players.** A tracking frame inside a period that lists no players. A **gap** is a sequence of consecutive frames without players.

**Camera view.** The four corners of the broadcast image projected onto the pitch, in the `tracking_frames` file's `image_corners_projection_*` columns. They are null when the image cannot be placed on the pitch.

**Phase of play.** One of SkillCorner's stretches of one team's possession, from `skillcorner.phases_of_play`, with a start and an end frame.

**Stoppage.** The interruption SkillCorner records after a player possession or an on-ball engagement, in the Dynamic Events data's `game_interruption_after` column: a goal kick, free kick, throw-in, corner, penalty or goal. A possession and an engagement often record the same stoppage, so the stoppage events that end before the same next possession or engagement count as one stoppage.

**Has pose.** A player-frame has pose when the `pose` table holds its joints. The table holds a player-frame only when all 29 joints were resolved, so the player-frame's `midHip` row marks it.

**Pose coverage.** The share of detected tracking player-frames, at pose-tracking frames, that have pose.

**Tracking–pose distance.** For a player-frame with a tracking position at a pose-tracking frame with pose data, the distance in metres between the tracking `x`/`y` and the pose `midHip` joint's `x`/`y`. Both are pitch coordinates.

**Speed.** A player's speed from tracking data: the distance between their positions one tracking frame before and one after, divided by 0.2s. It is undefined where either neighbouring frame is missing. It is the shortest window centred on a frame, so each speed describes the player's movement at that frame, the same instant as the tracking–pose distance it is compared with. A speed from the frame before and the frame itself would describe the movement between them, centred 0.05s before the frame. The data is recorded, so the frame after is available.

**Error radius.** SkillCorner's `p90_mae_cm` for a pose joint in a frame: the distance, in centimetres, within which SkillCorner estimates the true joint position lies 90% of the time ([body pose README](https://github.com/SkillCorner/opendata/blob/master/data/bodypose/README.md)).

**Percentiles.** The nth percentile is the value below which n% of the measurements lie; the median is the 50th.

## 3. Data and methods

### 3.1 Data

| Count | Match A | Match B |
| --- | --- | --- |
| Tracking frames inside a period | 61,282 | 57,602 |
| Pose-tracking frames | 30,642 | 28,802 |
| Tracking player-frames | 1,054,724 | 957,682 |
| Tracking player-frames at pose-tracking frames | 527,318 | 478,918 |
| Pose player-frames at pose-tracking frames | 306,569 | 313,024 |

The data is SkillCorner's open data for Match A (Brisbane Roar v Perth Glory, ID 1925299, 2024-12-21) and Match B (Sydney FC v Adelaide United, ID 1996435, 2025-02-01). `goalside v0.1.0`, the open-source package these papers use for SkillCorner's open data, converts SkillCorner's files into tables, each with a named schema whose numbered version fixes its columns and types, so naming a schema and its version, such as `skillcorner.tracking` version 1, says exactly which table layout an analysis read. The paper uses seven of them, each at version 1:
- `skillcorner.tracking`: one row per player per tracking frame, with `x`, `y` and `is_detected`;
- `skillcorner.tracking_frames`: one row per tracking frame, with its period, timestamp, ball position and camera view;
- `skillcorner.pose`: one row per joint per player per pose frame, with `x`, `y`, `z` and the error radius;
- `skillcorner.pose_frames`: one row per pose frame, with its period and timestamp;
- `skillcorner.dynamic_events`: one row per Dynamic Events record, with its frames and the stoppage after it;
- `skillcorner.phases_of_play`: one row per phase of play, with its start and end frames;
- `skillcorner.match_periods`: one row per period, with its start and end frames.

SkillCorner's tracking file holds one record per frame. In each match, 19 of those records have no period: they are frames before kick-off and between the periods, with no players or ball, and `goalside` leaves them out of the tables. The `skillcorner.pose` table holds only the players on the pitch, so it leaves out the joints SkillCorner gives two substitutes in Match B at the touchline in the five seconds before they come on, 54 player-frames at pose-tracking frames.

### 3.2 Methods

This section summarises what the analysis code does; Appendix B describes the code itself.

0. **Frame pairing.**
   - Each tracking frame at a pose-tracking frame is paired with its pose frame by arithmetic, and the two sources' timestamps are compared.
   - A join on period and timestamp is run as an alternative, and compared with the arithmetic pairs.
   - Pose frames whose timestamp repeats another's within the period are listed, with whether they lie past the period's end in `match.json`.
1. **Detection and gaps.**
   - The share of tracking player-frames with `is_detected` true, by match and period.
   - Frames without players are the frames in `tracking_frames` with no rows in `tracking`; gaps are counted within each period.
   - For frames without players and for frames with players: the share with a null ball, the share with a null camera view, and the share inside a phase of play.
   - For each gap, the last player possession or on-ball engagement to end at or before its first frame, and whether it records a stoppage.
   - For each stoppage, whether a gap starts before the next possession or engagement.
2. **Pose coverage.**
   - Tracking player-frames at pose-tracking frames are joined to pose `midHip` rows on period, pose frame and player.
   - Coverage is computed over the detected ones, and over all of them.
   - Every pose player-frame at a pose-tracking frame is then classed by the tracking it meets: detected, extrapolated, or no tracking row.
   - Those meeting extrapolated tracking are measured in tracking frames to the player's nearest detected frame, and those with no tracking row to the nearest edge of their gap.
3. **Tracking–pose distance.** Computed for every joined player-frame with pose, and summarised:
   - for all of them;
   - for detected positions only;
   - as the share within 0.5m and over 1m;
   - by speed band: 0–2, 2–4, 4–6 and over 6m/s.

## 4. Results

### 4.1 Pose and tracking frames pair exactly by frame rate, but not by timestamp

Every pairing made from the frame rates, 30,642 in Match A and 28,802 in Match B, lands on a pose frame with the same timestamp as the tracking frame.

Joining the two sources on period and timestamp instead finds the same 30,642 (Match A) and 28,802 (Match B) tracking frames, and no tracking frame between pose-tracking frames. But it returns one extra row in each match, pairing one tracking frame with two pose frames. That is because some pose frames repeat a timestamp:

| Match | Period | Pose frame | Timestamp | Past the period's end |
| --- | --- | --- | --- | --- |
| Match A | 1 | 69,554 | 46:21.16 | no |
| Match A | 1 | 72,577 | 48:22.08 | no |
| Match A | 1 | 75,601 | 48:22.08 | yes |
| Match A | 1 | 75,602 | 46:21.16 | yes |
| Match A | 2 | 153,250 | 96:45.00 | no |
| Match A | 2 | 153,251 | 96:45.00 | yes |
| Match B | 1 | 64,448 | 42:56.92 | no |
| Match B | 1 | 67,249 | 44:48.96 | no |
| Match B | 1 | 70,051 | 44:48.96 | yes |
| Match B | 1 | 70,052 | 42:56.92 | yes |
| Match B | 2 | 144,050 | 94:19.00 | no |
| Match B | 2 | 144,051 | 94:19.00 | yes |

In each match, the three pose frames that lie past a period's end (calculated by taking `match.json`'s end frame and multiplying by 2.5) carry the timestamp of an earlier frame:
- at the end of the first period, from 2 and 4 minutes earlier;
- at the end of the second, from the frame before.

`match.json` gives each period's end as a tracking frame, its `end_frame` (30,240 for Match A's first period, so pose frame 75,600), and each pose frame carries its own timestamp, recorded in `skillcorner.pose_frames`. The repeats at the two period ends differ:
- **First period.** The ball's position continues steadily from the frame before, as it does from frame to frame in play (in Match A, x moves from −33.22m at pose frame 75,600 to −31.89m and −30.55m), so these frames follow on from the period's last frame and only their timestamps are wrong.
- **Second period.** The extra frame repeats both the timestamp and the ball position of the frame before.

Only the second-period repeat affects a join with tracking. Its timestamp, 96:45.00 (Match A) and 94:19.00 (Match B), is also the timestamp of tracking's last frame in the period, while the first period's repeated timestamps, such as 46:21.16, fall between tracking's 0.1s steps and meet no tracking frame. The extra row in each match's timestamp join is therefore the second-period one.

Because these frames lie past the end of their period, discarding them removes the repeated timestamps.

### 4.2 Four in ten tracking player-frames are extrapolated, and a fifth of frames show no players

| Measure | Match A | Match B |
| --- | --- | --- |
| Player-frames detected | 57.9% | 65.8% |
| First period | 55.1% | 66.9% |
| Second period | 60.7% | 64.7% |
| Frames without players | 13,340 of 61,282 (21.8%) | 14,071 of 57,602 (24.4%) |
| Gaps | 53 | 71 |
| Median gap | 163 frames (16.3s) | 160 frames (16.0s) |
| Longest gap | 1,378 frames (2min 18s) | 848 frames (1min 25s) |

The detected shares are of tracking player-frames, overall and in each period, 1,054,724 (Match A) and 957,682 (Match B) in all; the share of frames without players is of the tracking frames inside a period.

Frames without players have no ball, almost never a camera view, and mostly fall outside the phases of play. Each share below is of the frames in its column: the tracking frames inside a period without players, 13,340 (Match A) and 14,071 (Match B), or with players, 47,942 and 43,531.

| Share of frames | Without players, Match A | Without players, Match B | With players, Match A | With players, Match B |
| --- | --- | --- | --- | --- |
| Null ball | 100% | 100% | 0% | 0% |
| Null camera view | 99.8% | 99.9% | 11.2% | 12.1% |
| Inside a phase of play | 4.8% | 3.8% | 73.4% | 72.9% |

| Gaps after a stoppage | Match A | Match B |
| --- | --- | --- |
| Gaps starting after a stoppage-causing on-ball event | 48 of 53 | 67 of 71 |
| Median time from that event's end to the gap | 10.1s | 8.5s |

The stoppages before the gaps are goal kicks (19 gaps in Match A, 18 in Match B), free kicks (13 and 22), corners (7 and 14), throw-ins (9 and 7) and goals (none and 6). A median gap of about 16 seconds, starting about 10 seconds after a stoppage, is consistent with replays shown after an incident, although this is an assumed possibility.

Most stoppages are not followed by a gap. The Dynamic Events data record 187 stoppage events in Match A and 207 in Match B, which come to 86 and 94 stoppages once a stoppage recorded by both a possession and an engagement is counted once. Goal kicks and corners are mostly followed by a gap before play restarts, and throw-ins mostly are not:

| Stoppage | Followed by a gap, Match A | Followed by a gap, Match B |
| --- | --- | --- |
| Goal kick | 16 of 19 | 17 of 19 |
| Corner | 6 of 6 | 12 of 16 |
| Free kick | 9 of 20 | 18 of 24 |
| Goal | 0 of 1 | 5 of 5 |
| Throw-in | 8 of 40 | 7 of 30 |
| All | 39 of 86 | 59 of 94 |

### 4.3 Pose covers 98% of detected player-frames

| Player-frames | Match A | Match B |
| --- | --- | --- |
| Detected player-frames at pose-tracking frames | 305,207 | 315,070 |
| Of which with pose | 299,042 (98.0%) | 310,571 (98.6%) |
| Of which without pose | 6,165 (2.0%) | 4,499 (1.4%) |
| All tracking player-frames at pose-tracking frames | 527,318 | 478,918 |
| Of which with pose | 304,998 (57.8%) | 313,024 (65.4%) |

When the camera shows a player, pose is missing in 2.0% (Match A) and 1.4% (Match B) of player-frames. Counting extrapolated player-frames too, 57.8% (Match A) and 65.4% (Match B) have pose, because pose exists almost only where the camera shows the player.

Seen from the pose side, almost every pose player-frame meets a detected tracking position:

| Pose player-frames at pose-tracking frames | Match A | Match B |
| --- | --- | --- |
| Tracking position detected | 299,042 (97.5%) | 310,571 (99.2%) |
| Tracking position extrapolated | 5,956 (1.9%) | 2,453 (0.8%) |
| No tracking row for the player | 1,571 (0.5%) | 0 |
| Total | 306,569 | 313,024 |

The second and third rows may suggest that the two sources disagree about whether a player was visible. The third arises when the tracking lists no players in a frame for which the pose has some. The pairing of frames does not produce either row: each pose-tracking frame pairs with a pose frame of identical timestamp (section 4.1), all 1,571 pose player-frames with no tracking row in Match A lie inside a gap, a median of 78 tracking frames from its nearer edge, and the pose player-frames meeting extrapolated tracking lie a median of 27 (Match A) and 28 (Match B) tracking frames from the player's nearest detected frame.

### 4.4 Tracking and pose are about 20cm apart

Tracking–pose distance, in metres:

| Match and positions | Median (m) | 75th percentile (m) | 90th percentile (m) | 95th percentile (m) | 99th percentile (m) | Share within 0.5m | Share over 1m |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Match A, detected positions | 0.218 | 0.348 | 0.528 | 0.689 | 1.587 | 88.5% | 2.1% |
| Match A, all positions with pose | 0.222 | 0.358 | 0.563 | 0.790 | 5.440 | 87.0% | 3.5% |
| Match B, detected positions | 0.198 | 0.302 | 0.433 | 0.543 | 1.008 | 93.5% | 1.0% |
| Match B, all positions with pose | 0.199 | 0.305 | 0.442 | 0.567 | 1.917 | 92.9% | 1.6% |

Including extrapolated positions barely moves the median, because they are only 1.9% (Match A) and 0.8% (Match B) of pose player-frames, but raises the 99th percentile in Match A from 1.6m to 5.4m.

### 4.5 The distance does not grow with speed

Median (90th percentile) tracking–pose distance in metres, by the player's speed. "n" is player-frames with pose and a defined speed.

| Running speed | Match A, median (90th percentile) distance (m) | Match A, player-frames | Match B, median (90th percentile) distance (m) | Match B, player-frames |
| --- | --- | --- | --- | --- |
| 0–2m/s | 0.226 (0.576) | 158,564 | 0.208 (0.465) | 156,794 |
| 2–4m/s | 0.216 (0.541) | 108,508 | 0.193 (0.427) | 110,715 |
| 4–6m/s | 0.215 (0.554) | 33,320 | 0.186 (0.410) | 38,088 |
| Over 6m/s | 0.228 (0.719) | 4,606 | 0.184 (0.401) | 7,425 |

A player moving at 6m/s covers 0.6m in one tracking frame. A delay of even one tracking frame between the sources would therefore make the distance at high speed far larger than at walking pace. The medians are flat across the bands in both matches. The 90th percentile rises above 6m/s in Match A only, from 0.55m to 0.72m.

## 5. Discussion

### 5.1 Pose and tracking frames can be paired by their frame rates, or by timestamp with processing

The pairs made from the frame rates have identical timestamps in the two sources on every pose-tracking frame in both matches, so arithmetic on the frame numbers is a reliable way to pair them. A join on timestamps would give the same pairs only once the pose frames past a period's end were discarded, because they repeat the timestamps of earlier frames and would pair one instant with two pose frames. Once those frames are discarded, every timestamp is unique within its period, and the join on period and timestamp gives exactly the arithmetic pairs.

### 5.2 Tracking lists players in about three frames in four, and pose exists almost only where the broadcast footage shows the player

Tracking lists players in 78.2% (Match A) and 75.6% (Match B) of the frames inside a period, and whenever it lists any, it lists all 22 on the pitch. Of those tracking player-frames, 57.9% (Match A) and 65.8% (Match B) were detected from the broadcast footage, and pose follows that detection closely: it is missing for 2.0% (Match A) and 1.4% (Match B) of detected player-frames, and only 1.9% (Match A) and 0.8% (Match B) of pose player-frames meet an extrapolated tracking position. Whether a player has pose at a given moment therefore depends mainly on whether the broadcast footage was showing them, which tracking's `is_detected` records.

The pose player-frames that meet extrapolated tracking, or no tracking at all, are where the two sources disagree about whether a player was visible. They lie well away from the frames where the player's detection changes (section 4.3), so they are not an effect of pairing the frames.

The remaining frames, those without players, have no ball and almost never a camera view, 95–96% of them fall outside every phase of play, and 48 of 53 gaps (Match A) and 67 of 71 (Match B) start after a stoppage. Most stoppages are not followed by a gap, and the share depends on the kind of stoppage: across the two matches, 33 of 38 goal kicks and 18 of 22 corners are followed by a gap, against 15 of 70 throw-ins. One possible explanation, albeit unverified, is that the broadcast footage shows replays or close-ups after an incident near goal, such as a shot that ends in a goal kick or a corner, but keeps showing the pitch during most throw-in stoppages.

### 5.3 Tracking and pose place a player about 20cm apart

The consistency of the discrepancy across different speeds implies that the difference is _not_ a case of mismatched _timing_ of the two sources. A delay between the sources would result in higher discrepancies at higher speeds, as a player would move a larger distance between timesteps. However, the discrepancy stays flat across speeds (section 4.5), so the gap may result from  a diference in where/how each source places a player. Two possible theories, neither tested:
- **Different reference points.** Tracking may place a player at a point on the ground, such as between the feet, while `midHip` sits above the pelvis, and a leaning or striding player moves the two apart.
- **Independent errors.** The two sources may place the player from the image independently, each with its own error.

SkillCorner's error radius for `midHip` is 10.32cm in at least 90% of the pose player-frames compared, in both matches, about half the median distance, so SkillCorner's estimation of pose error alone does not account for it. SkillCorner's [opendata README](https://github.com/SkillCorner/opendata) gives no error for tracking positions.

The distances over 1m are concentrated where the tracking position is extrapolated, rather than collected from the footage. Including extrapolated positions raises the share over 1m from 2.1% to 3.5% (Match A) and from 1.0% to 1.6% (Match B), and the 99th percentile in Match A from 1.6m to 5.4m. An extrapolated position is the model's estimate of where a player outside the camera's view is, so larger disagreements there are expected. These cases are few, 5,956 pose player-frames in Match A (1.9%) and 2,453 in Match B (0.8%), and about three quarters of them are more than 1m apart, so they change the 99th percentile and the share over 1m but not the median. This indicates that pose player-frames whose tracking is not marked as detected should probably be dropped from analyses that combine the two sources, since they are far more likely to carry a large discrepancy and are so few that dropping them loses little data.

### 5.4 Limitations

- **Pose-tracking frames only.** Coverage and distance were measured at the instants where pose and tracking coincide, every 200ms. Pose frames between them were not used; comparing them would need tracking positions interpolated between frames.
- **One point per player.** The distance compares tracking with `midHip` only. Another reference point, such as the midpoint of the ankles, might give a smaller offset.
- **Speed from tracking.** Each speed comes from tracking positions, so an error in those positions would move some player-frames into the wrong speed band and blur the differences between bands. Tracking is rounded to 1cm and otherwise smooth from frame to frame (paper `002-tracking-smoothness`), and rounding changes a speed by about 0.02m/s, so only player-frames within a few hundredths of a metre per second of a band's edge could change band.
- **Small sample.** The measurement differences in the two matches differ (3.5% against 1.6% of player-frames more than 1m apart), so it's unclear how representative this data is of SkillCorner's data in general.

## 6. Implications

- **Studies of pose around events,** such as on-ball engagements, would report missing pose by its cause. A player's pose is missing either because the camera was not showing them, which tracking's `is_detected` records, or because the camera showed them and their pose was still not resolved, which happens in about 2% of detected player-frames. A single share of an event's frames with pose would not say which of the two causes the missing frames had, though the first depends on where the broadcast was pointing and the second on SkillCorner's pose model.
- **Pose frames past a period's end,** by `skillcorner.match_periods`' end frame × 2.5, should be discarded before any join on timestamps, since they repeat the timestamps of earlier frames.
- **Pose analysis is limited** to moments when a player is detected by the camera footage. This potentially places constraints on the types of studies possible, particularly if looking across a full-match, as some players may be off-camera for significant periods of time.
- **Further processing may be needed** for aligning the tracking and body pose data, depending on the type of study. In general, the discrepancy is small, and consistently small across speed ranges. However, the existence of the discrepancy may have implications for studies focused on fine-grain spatial details. 

## Future points for research

- **Which point tracking places a player at.** Comparing tracking with the midpoint of the pose ankles, as well as with `midHip`, in the same player-frames would show which it is closest to.
- **Whether the offset differs by player,** for example by height or position.
- **Coverage levels for different players or playing positions**, which may have particularly large impacts for defenders and strikers. (And goalkeepers, although goalkeeper analysis is likely to focus on moments when they are on-screen).

## Sources

- SkillCorner, [opendata README](https://github.com/SkillCorner/opendata): broadcast tracking data is "collected through computer vision and machine learning out of the broadcast video", and `is_detected` is a "flag that mentions if the player is detected on the screen or extrapolated" (Tracking Data Description).
- SkillCorner, [body pose README](https://github.com/SkillCorner/opendata/blob/master/data/bodypose/README.md): "XY Tracking data and Body Pose are generated separately", and the per-joint error "is defined so that 90% of estimated key points are sitting within this error radius".
- SkillCorner's open tracking (`<id>_tracking_extrapolated.jsonl`), body pose and Dynamic Events data for matches 1925299 and 1996435, converted with `goalside v0.1.0` into the tables listed in section 3.1.

## Appendices
### Appendix A: versions

The paper's results come from `goalside v0.1.0`, reading these tables at these schema versions:

| Table | Schema version |
| --- | --- |
| `skillcorner.tracking` | 1 |
| `skillcorner.tracking_frames` | 1 |
| `skillcorner.pose` | 1 |
| `skillcorner.pose_frames` | 1 |
| `skillcorner.dynamic_events` | 1 |
| `skillcorner.phases_of_play` | 1 |
| `skillcorner.match_periods` | 1 |

`goalside v0.1.0` converted them from this data:

| Data | Version | Checked |
| --- | --- | --- |
| SkillCorner open data | [`opendata` commit 4340d27](https://github.com/SkillCorner/opendata/tree/4340d274572876239c154c90bc507a9b3250a656) (2026-09-14) | The CSVs and `match.json` match the commit by git hash, and the tracking files by their Git LFS SHA256 |
| Full body pose | SkillCorner's [opendata-bodypose](https://huggingface.co/datasets/SkillCorner/opendata-bodypose) dataset on Hugging Face | Each archive matches the size and SHA256 in `data/bodypose/MANIFEST.json` at the same commit, which `goalside` checks when it downloads it |

`goalside` downloads SkillCorner's files from the `opendata` repository's `master` branch. Reproducing the paper after a later SkillCorner commit would mean taking the files from commit 4340d27, for example from a clone of `opendata` at that commit, and passing each to `goalside`'s converter functions as `source`.

### Appendix B: the coverage analysis script

**File.** `tracking-pose-coverage.py` in this folder, with the frame pairing in the `goalside.skillcorner.frames` module of `goalside`. The results above come from `goalside v0.1.0`.

**Run.**

```
uv run python papers/001-tracking-pose-coverage/tracking-pose-coverage.py
```

- **Needs:** both matches' tables in `goalside`'s data directory (the `goalside.data_dir()` function), loaded with `goalside`'s download and convert functions: `download_match` and `convert_match`, `download_dynamic_events` and `convert_dynamic_events`, `download_phases_of_play` and `convert_phases_of_play`, `download_tracking` and `convert_tracking`, then `download_pose_match` and `convert_pose`.
- **Takes:** under a minute.
- **Writes:** `outputs/tracking_pose_coverage.json` in this folder, with `timestamps`, `tracking` and `coverage` sections for each match.

**Structure.**

```
main()
  for each match:
    frame_timestamps(match)                        # section 4.1
    tracking = tracking_with_speed(match)          # all tracking rows + speed
    tracking_summary(match)                        # section 4.2
    coverage_and_distance(match, tracking)         # sections 4.3–4.5
  write JSON
```

**`goalside.skillcorner.frames.pose_tracking_rows`: the pairing.** The steps come from the frame rates in `goalside.skillcorner.constants`:

```python
TRACKING_STEP = TRACKING_FPS // gcd(POSE_FPS, TRACKING_FPS)
POSE_STEP = POSE_FPS // gcd(POSE_FPS, TRACKING_FPS)
...
    coincides = pl.col(column) % TRACKING_STEP == 0
    paired_pose_frame = (pl.col(column) // TRACKING_STEP * POSE_STEP).cast(pl.Int32)
    return frame.filter(coincides).with_columns(pose_frame=paired_pose_frame)
```

`goalside`'s test file `tests/test_skillcorner_frames.py` checks the function on synthetic frames, and `test_full_pose_and_tracking_frames_pair_at_the_same_timestamps` in `tests/test_skillcorner_open_data.py` checks on both matches that every pair has identical timestamps.

**`frame_timestamps`: the check in section 4.1.**

```
tracking = tracking_frames (period, frame, timestamp)
pose     = pose_frames (period, pose_frame, pose_timestamp)
paired   = pose_tracking_rows(tracking)  LEFT JOIN  pose  ON (period, pose_frame)
→ pairs, pairs with a pose frame, pairs with timestamp == pose_timestamp

by_clock = tracking  INNER JOIN  pose  ON (period, timestamp = pose_timestamp)
→ rows, distinct tracking frames, odd tracking frames, pairs where pose_frame ≠ frame × 25 / 10

repeats  = pose rows whose pose_timestamp appears more than once in the period
past_end = pose_frame > match_periods end_frame × 2.5
```

**`tracking_with_speed`: speed from the frames either side.**

```
rows = tracking for the match, sorted by (period, player_id, frame)
for each row, within (period, player_id):
    speed = |position(next row) − position(previous row)| × 10 fps / 2
    keep speed only if next.frame − previous.frame == 2     # no gap either side
```

**`tracking_summary`: detection and frames without players.**

```
detected_share[period] = mean(is_detected) over tracking rows in the period
empty  = tracking_frames (period, frame)  ANTI-JOIN  distinct tracking (period, frame)
gap_id = cumulative sum of (frame − previous empty frame ≠ 1), within period
gaps   = count of frames per gap_id  →  number, median, longest
for frames without players and frames with players:
    share with ball_data_x null, share with image_corners_projection_x_top_left null,
    share inside a phase of play (frame between frame_start and frame_end of a phases_of_play row)
on_ball = player_possession and on_ball_engagement events, sorted by frame_end
before  = each gap's first frame  ASOF JOIN (backward)  on_ball  ON first frame >= frame_end
→ gaps whose event has game_interruption_after, by value; median (first frame − frame_end) / 10 fps
restarts  = on_ball frame_start, sorted
stoppages = on_ball rows with game_interruption_after  ASOF JOIN (forward, strictly after)  restarts  ON frame_end < restart
            grouped by restart → one stoppage per restart, its kind with _for/_against removed
followed  = stoppages with a gap starting at or after their last frame_end and before the restart
→ stoppages, and those followed by a gap, by kind
```

**`coverage_and_distance`: the pose-tracking join.**

```
at_pt    = pose_tracking_rows(tracking)                       # tracking at pose-tracking frames
mid_hip  = pose rows where joint == "midHip"                  # one row per pose player-frame
joined   = at_pt  LEFT JOIN  mid_hip  ON (period, pose_frame, player_id)
has_pose = mid_hip row found
distance = √((x − pose_x)² + (y − pose_y)²)

coverage                   = mean(has_pose) over joined rows where is_detected
coverage_of_all            = mean(has_pose) over all joined rows
pose_with_extrapolated     = count(has_pose) over joined rows where not is_detected
pose_at_pt                 = mid_hip rows where pose_frame % 5 == 0
pose_without_tracking_row  = pose_at_pt  ANTI-JOIN  at_pt  ON (period, pose_frame, player_id)
    → whether inside a gap, and frames to the gap's nearer edge
pose_with_extrapolated rows ASOF JOIN (nearest, by period and player) the player's detected tracking frames
    → frames to the nearest detected frame
error radius = percentiles of p90_mae_cm over pose_at_pt
distance percentiles (50, 75, 90, 95, 99) over rows with pose: all, and detected only;
    share within 0.5 m and over 1 m, all and detected only
by speed band (cut at 2, 4, 6 m/s): median and 90th percentile
```

**Reuse.**
- The `pose_tracking_rows` function in `goalside.skillcorner.frames` pairs the frames, for any analysis that puts a tracking label on a pose frame.
- The `with_movement` function in `goalside.skillcorner.movement` gives speed from tracking, with direction, acceleration and turn rate.

## Revisions

None since publication.
