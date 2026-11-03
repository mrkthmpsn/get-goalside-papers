---
goalside: 0.1.0
history:
  - date: 2026-11-03
    event: published
---

# Smooth sailing or choppy waters: How smooth is SkillCorner's open tracking and body pose data from one frame to the next

**Why study this?:** To check the smoothness of the SkillCorner open tracking and body pose data, to see whether they need post-processing for smoothing purposes.

---

## Abstract

This blog-paper measures how smooth SkillCorner's open tracking positions and body pose are from one frame to the next: tracking over all 20 A-League matches in SkillCorner's open data, and body pose over the two matches with full body pose, Match A (Brisbane Roar v Perth Glory, ID 1925299, 2024-12-21) and Match B (Sydney FC v Adelaide United, ID 1996435, 2025-02-01).

The main takeaway is that tracking data appears pre-smoothed, while body pose data needs some treatment. Tracking positions are rounded to the nearest centimetre but otherwise appear smooth. Body pose varies from frame to frame far more than its rounding to the nearest millimetre.

It has five findings:

- **Tracking is quite smooth apart from its rounding to 1cm.** Its one-frame 'second difference' has a median of 1.41m/s² in every match, little more than the simulated value of 0.89m/s² that the data's rounding to centimetres can be attributed with; extrapolated positions are smoother still.
- **Pose varies far more than its rounding to 1mm.** The one-frame 'second difference' of `midHip` has a median of about 15m/s² in both matches, against a simulated rounding value of 0.55m/s².
- **The feet and hands vary most, mainly because they are placed less precisely.** They vary about three times as much as the trunk, and 2.3–2.4 times as much even when a player stands still, in line with SkillCorner's own error estimates for those joints.
- **Pose varies more the faster the player runs.** From the slowest speed band to the fastest, the median variation, measured as the one-frame 'second difference', rises about 1.4 times for `midHip` and 2.4–2.6 times for the feet and hands.
- **The knee angle zigzags in about a third of frames, mostly by under 2°.** Zigzags (where the movement is in one direction then the opposite across subsequent frames) of more than 15° each way happen in about 1% of frames.

## 1. Introduction

Speed, acceleration and turning are measured from the change in a player's tracking position between frames, and body pose adds a whole set of additional movements that can be studied between a range of joints. Therefore the reliability of the data is important to consider for potential studies.

In addition, acceleration and turning are computed from the change in velocity between frames, which is itself computed from the change in position, so a positional error can amplify when applied to these 'change' metrics. How much error a position carries from one frame to the next therefore has a particularly significant impact on how these measures may need to be processed.

The blog-paper asks five questions:

1. How smooth are tracking positions from one frame to the next, and how much of what is measured comes from how the positions are published?
2. Is that different where the camera did not detect the player, or where detection switches on or off?
3. How smooth is body pose from one frame to the next, for the player's position (`midHip`) and for each joint relative to it, and how does it compare with tracking over the same window?
4. How does that change with the player's running speed, in open play?
5. How often does the knee angle zigzag (change direction from one frame to the next) and by how much?

## 2. Definitions

**Tracking frame.** One of SkillCorner's tracking time steps, 100ms apart (10 frames per second).

**Pose frame.** One of SkillCorner's body-pose time steps, 40ms apart (25 frames per second).

**Player-frame.** One player in one frame. A **tracking player-frame** is a player's position in one tracking frame; a **pose player-frame** is a player's 29 joints in one pose frame.

**Detected and extrapolated.** Each tracking player-frame has `is_detected`, true when the broadcast camera saw the player and false when SkillCorner's model placed a player outside the camera's view ([opendata README](https://github.com/SkillCorner/opendata), Tracking Data Description).

**'Second difference'.** The paper's measure of how smoothly a point moves: how much its velocity changes at a frame, which is an estimate of its acceleration. Take the point's position in the frame before, in the frame itself and in the frame after. Its velocity coming into the frame is the change from the first position to the second, and its velocity leaving is the change from the second to the third; the 'second difference' is the change between those two velocities, divided by the time between frames, in m/s². A point moving at a steady speed in a straight line has a 'second difference' of zero.

The one-frame 'second difference' uses the frames one either side. It is undefined where a frame it needs is missing. For tracking, the point is the player's `x` and `y`; for pose, it is `midHip`'s `x` and `y`, or a joint's `x`, `y` and `z` measured from `midHip`.

**Simulated rounding value.** A simulated 'second difference' that rounding alone produces. Rounding to the nearest centimetre moves each coordinate by an amount between −0.5 and +0.5cm. The simulation draws a random rounding amount for each of the three positions of a second difference calculation, works out their 'second difference', and repeats this a million times. The simulated rounding value is the spread of those million values, such as their median. For tracking the step is 1cm; for pose it is 1mm, and a joint measured from `midHip` carries the rounding of both points. It is a size to compare a measurement with, not an amount to subtract from it.

**Running speed.** A player's horizontal speed from the pose: the distance between `midHip`'s positions five pose frames before and five after, divided by 0.4s. Speed bands are 0–2, 2–4, 4–6 and over 6m/s.

**Standing.** A running speed under 0.5m/s, at which the limbs move least.

**Knee angle.** The angle at the knee between the thigh (from the knee to the hip) and the shin (from the knee to the ankle), in degrees: 180° for a straight leg. Both knees of every pose player-frame are measured, so a knee-frame is one knee in one frame. The knee is the joint football analysis uses most, for running, kicking and tackling.

**Zigzag.** A change of direction in opposite directions through subsequent frames: the knee angle moves one way from the frame before and back the other way to the frame after, such as bending by 3° and then straightening by 2°. The **size** of a zigzag is the smaller of these two values, so a 2° zigzag went at least 2° each way.

**Error radius.** SkillCorner's `p90_mae_cm` for a joint in a pose frame: the distance, in centimetres, within which SkillCorner estimates the true joint position lies 90% of the time ([body pose README](https://github.com/SkillCorner/opendata/blob/master/data/bodypose/README.md)).

**Open play.** The frames inside a phase of play, one of SkillCorner's stretches of one team's possession in `skillcorner.phases_of_play`, whose phase type for the team in possession is not `set_play`. Set plays, and the stoppages between phases, are left out.

**Body parts.** The joints relative to `midHip` are grouped as the head (nose, eyes, ears), the trunk (neck, shoulders, hips), knees and elbows, ankles and wrists, and feet and hands (heels, big and small toes, thumbs, pinkies).

**Percentiles.** The nth percentile is the value below which n% of the measurements lie; the median is the 50th.

## 3. Data and methods

### 3.1 Data

The data is loaded with `goalside v0.1.0`, the open-source package these papers use for SkillCorner's open data. `goalside` stores each kind of data as a table whose columns and types are fixed by a named, numbered schema, so naming the schema and its version, such as `skillcorner.tracking` version 1, says exactly which table layout the analysis read. The tracking is `skillcorner.tracking` at schema version 1, as `goalside v0.1.0` converts it from SkillCorner's open data, for all 20 matches: 1874553, 1886347, 1899585, 1925299 (Match A), 1927964, 1953632, 1959846, 1986691, 1996435 (Match B), 1996436, 2006229, 2006363, 2007448, 2007721, 2010085, 2011166, 2013725, 2015213, 2016236 and 2017461. It holds detected and extrapolated positions.

|                               | All 20 matches | Fewest in a match | Most in a match |
| ----------------------------- | -------------- | ----------------- | --------------- |
| Tracking player-frames        | 19,334,986     | 858,330           | 1,067,924       |
| With both neighbouring frames | 19,276,900     | 855,160           | 1,065,152       |
| With both frames two away     | 19,218,814     | 851,990           | 1,062,380       |

The body pose data is `skillcorner.pose` at schema version 1, for Match A (Brisbane Roar v Perth Glory, ID 1925299, 2024-12-21) and Match B (Sydney FC v Adelaide United, ID 1996435, 2025-02-01), the two matches with full body pose. It holds a player-frame only where all 29 joints were resolved. The open-play frames come from `skillcorner.phases_of_play` at schema version 1 for the same two matches.

|                                    | Match A   | Match B   |
| ---------------------------------- | --------- | --------- |
| Pose player-frames                 | 1,540,715 | 1,571,552 |
| With both neighbouring pose frames | 1,529,050 | 1,562,522 |
| With both pose frames five away    | 1,482,521 | 1,526,471 |

### 3.2 Methods

This section summarises what the analysis code does; Appendix B describes the code itself, which is also available in the repo.

The 'second difference' tests smoothness because real movement and measurement error behave differently in it. Real movement would typically be expected to be smoother in velocity change between small timesteps. As the data naturally has no ground truth positions to compare with, this paper compares the 'second difference' with a simulated value that the data's rounding (to the nearest centimetre (tracking) or millimetre (body pose)) would cause, and over two window lengths.

1. Every tracking `x` and `y` in the 20 matches was checked for lying on a whole centimetre, and every player and ball `x` and `y` in SkillCorner's 20 tracking files for its number of decimal places as the file writes it, before `goalside` reads it.
2. The one-frame 'second difference' was computed for every tracking player-frame with both neighbouring frames, within match, period and player, and summarised across the 20 matches and by match:
   - for detected and for extrapolated positions;
   - at the frames where `is_detected` differs from the player's previous frame.
3. The one-frame and two-frame tracking 'second differences' were compared with the simulated rounding value over the same window.
4. Every joint's `x`, `y` and `z` in every 97th pose frame was checked for lying on a whole millimetre, and every joint coordinate on every 50th line of SkillCorner's two pose archives for its number of decimal places. A sample of about 1% keeps the check quick, and 97, a prime number, keeps it from falling in step with any pattern that repeats every few frames, such as pose and tracking coinciding on every fifth pose frame.
5. The one-frame and five-frame 'second differences' were computed for every pose player-frame with both pose frames one away, and with both five away, within period and player:
   - the horizontal 'second difference' of `midHip`;
   - the 'second difference' of each joint relative to `midHip`, pooled by body part.

   Both were compared with the simulated rounding value over the same window.
6. For every pose player-frame in open play with both neighbouring pose frames and a running speed, the one-frame 'second difference' of `midHip`, and of each joint relative to `midHip` by body part, was summarised by speed band, and separately for standing players. Set plays were left out because more measurement error is expected in them.
7. The median error radius was taken over every joint of each body part, in every pose player-frame of each match.
8. Both knee angles were computed for every pose player-frame. For every knee-frame with both neighbouring pose frames, the move into the frame and the move out of it were compared: the frame zigzags when they have opposite signs. Knee-frames were left out where any of the three frames has a collapsed pose, with all 29 joints within 0.3m of each other, or a thigh or shin shorter than 10cm, under half the length of the shortest 0.1% of uncollapsed thighs and shins, whose median is 38cm. That left out 3,764 knee-frames in Match A and 2,478 in Match B. These frames have knee angles that are undefined or meaningless. Paper `003-engagement-pose-checks` checks poses for collapse, and checks each bone's length against that player's usual length for it, which would catch less extreme cases too. The share of knee-frames zigzagging, by sizes of more than 0°, 5°, 10° and 15°, and the median size of a zigzag were summarised over all knee-frames, in open play by running speed and for standing players. The knee joint was chosen for its combination of being largely visible on-camera, while also potentially susceptible to measurement error, and being an area of the body that analysis of pose data may well focus on.

## 4. Results

### 4.1 Tracking positions are rounded to 1cm

Every tracking `x` and `y` in all 20 matches lies on a whole centimetre, as SkillCorner's files publish them: all 40,427,698 player and ball `x` and `y` values in the 20 tracking files have at most two decimal places. Each component of a one-frame 'second difference' is then a whole number of m/s² (1cm divided by (0.1s)²), which is why the percentiles below are lengths such as 1, √2 = 1.41, √5 = 2.24 and 3.

### 4.2 The one-frame tracking 'second difference' has a median 1.6 times the simulated rounding value

One-frame 'second difference', in m/s², across the 19,276,900 tracking player-frames of the 20 matches with both neighbouring frames:

| Tracking positions                         | Median (m/s²) | 75th percentile | 90th percentile | 99th percentile |
| ------------------------------------------ | ------ | ---- | ---- | ---- |
| Detected                                   | 1.41   | 2.24 | 3.16 | 5.39 |
| Extrapolated                               | 1.00   | 1.41 | 2.24 | 4.24 |
| Where detection switches (n = 196,096)     | 1.41   | 2.24 | 3.16 | 5.83 |
| Simulated rounding value                      | 0.89   | 1.20 | 1.48 | 1.90 |

The medians are the same in every one of the 20 matches: 1.41m/s² detected, 1.00m/s² extrapolated and 1.41m/s² where detection switches. Of all tracking player-frames with both neighbouring frames, 0.047% exceed 10m/s², and from 0.022% to 0.087% by match.

### 4.3 The two-frame tracking 'second difference' has a median five times the simulated rounding value

Two-frame 'second difference' (0.2s), in m/s², across the 19,218,814 tracking player-frames of the 20 matches with both frames two away:

| Tracking positions    | Median (m/s²) | 75th percentile | 90th percentile | 99th percentile |
| --------------------- | ------ | ---- | ---- | ---- |
| Detected              | 1.06   | 1.82 | 2.80 | 4.92 |
| Simulated rounding value | 0.22   | 0.30 | 0.37 | 0.47 |

By match, the median for detected positions runs from 1.03m/s² to 1.25m/s²; it is 1.03m/s² in both Match A and Match B.

### 4.4 Pose positions are rounded to 1mm

Every joint's `x`, `y` and `z` in every 97th pose frame of both matches lies on a whole millimetre, as SkillCorner's archives publish them: all 5,388,954 joint coordinates on every 50th line of the two pose archives have at most three decimal places.

### 4.5 The one-frame 'second difference' of `midHip` is far above the simulated rounding value

Horizontal 'second difference' of `midHip`, in m/s², one-frame (0.04s) for the 1,529,050 (Match A) and 1,562,522 (Match B) pose player-frames with both neighbouring pose frames, and five-frame (0.2s) for the 1,482,521 and 1,526,471 with both pose frames five away. Tracking's two-frame 'second difference' spans the same 0.2s:

| `midHip` (or tracking position), by window         | Median (m/s²) | 75th percentile | 90th percentile | 99th percentile |
| -------------------------------------------------- | ------ | ----- | ----- | ------ |
| Match A, one-frame                                 | 15.68  | 29.05 | 49.52 | 114.26 |
| Match B, one-frame                                 | 15.13  | 27.67 | 46.88 | 105.69 |
| Simulated rounding value, one-frame                       | 0.55   | 0.75  | 0.92  | 1.19   |
| Match A, five-frame                                | 2.13   | 3.19  | 4.48  | 8.06   |
| Match B, five-frame                                | 2.06   | 3.11  | 4.38  | 7.87   |
| Simulated rounding value, five-frame                      | 0.02   | 0.03  | 0.04  | 0.05   |
| Match A, tracking, detected, two-frame             | 1.03   | 1.77  | 2.66  | 4.61   |
| Match B, tracking, detected, two-frame             | 1.03   | 1.77  | 2.69  | 4.74   |

### 4.6 Every body part varies far more than its rounding, the extremities most

Median 'second difference' of each joint relative to `midHip`, in m/s², pooled over the joints of each body part, over the same pose player-frames as section 4.5:

| Body part, measured from `midHip` | Match A, one-frame (m/s²) | Match B, one-frame (m/s²) | Match A, five-frame (m/s²) | Match B, five-frame (m/s²) |
| --------------------- | --------------- | --------------- | -------------- | -------------- |
| Head                  | 28.24           | 27.22           | 2.68           | 2.53           |
| Trunk                 | 13.71           | 13.41           | 1.49           | 1.48           |
| Knees and elbows      | 25.36           | 25.11           | 4.76           | 4.68           |
| Ankles and wrists     | 36.50           | 36.30           | 7.79           | 7.74           |
| Feet and hands        | 41.20           | 41.28           | 9.37           | 9.41           |
| Simulated rounding value | 0.98            | 0.98            | 0.04           | 0.04           |

### 4.7 In open play, pose varies more the faster the player runs

Median one-frame 'second difference', in m/s², for pose player-frames in open play, by the player's running speed:

| Match A, running speed | Player-frames | `midHip` (m/s²) | Head (m/s²) | Trunk (m/s²) | Knees and elbows (m/s²) | Ankles and wrists (m/s²) | Feet and hands (m/s²) |
| ---------------- | ------------- | -------- | ----- | ----- | ---------------- | ----------------- | -------------- |
| 0–2m/s          | 504,795       | 15.26    | 26.56 | 12.67 | 21.88            | 31.63             | 34.75          |
| 2–4m/s          | 467,724       | 15.91    | 29.66 | 14.48 | 28.08            | 39.75             | 45.91          |
| 4–6m/s          | 152,685       | 17.37    | 32.44 | 16.49 | 35.24            | 50.80             | 60.65          |
| Over 6m/s       | 22,585        | 20.78    | 37.05 | 19.38 | 45.01            | 67.45             | 81.90          |

| Match B, running speed | Player-frames | `midHip` (m/s²) | Head (m/s²) | Trunk (m/s²) | Knees and elbows (m/s²) | Ankles and wrists (m/s²) | Feet and hands (m/s²) |
| ---------------- | ------------- | -------- | ----- | ----- | ---------------- | ----------------- | -------------- |
| 0–2m/s          | 512,019       | 14.54    | 24.92 | 12.05 | 20.83            | 30.38             | 33.50          |
| 2–4m/s          | 464,334       | 15.10    | 28.18 | 14.06 | 27.63            | 39.40             | 45.85          |
| 4–6m/s          | 166,700       | 16.83    | 31.63 | 16.37 | 35.24            | 50.91             | 61.11          |
| Over 6m/s       | 34,737        | 20.78    | 37.30 | 19.94 | 47.15            | 70.57             | 85.98          |

`midHip` is its horizontal 'second difference'; the body parts are relative to `midHip`, in 3D. From the slowest band to the fastest, the median 'second difference' rises about 1.4 times for `midHip` in both matches, 1.5 (Match A) and 1.7 (Match B) times for the trunk, and 2.4 (Match A) and 2.6 (Match B) times for the feet and hands.

### 4.8 Standing, the feet and hands vary about as much more than the trunk as their in-data error radius is larger

Median one-frame 'second difference' relative to `midHip`, in m/s², for the 53,498 (Match A) and 53,874 (Match B) pose player-frames of standing players in open play, and the median error radius, in centimetres, over every pose player-frame:

| Body part         | 'Second difference' when standing, Match A (m/s²) | 'Second difference' when standing, Match B (m/s²) | SkillCorner's error radius, Match A (cm) | SkillCorner's error radius, Match B (cm) |
| ----------------- | ----------------- | ----------------- | --------------------- | --------------------- |
| Head              | 28.30             | 25.38             | 6.87                  | 6.84                  |
| Trunk             | 13.05             | 11.79             | 6.46                  | 6.43                  |
| Knees and elbows  | 20.71             | 19.17             | 9.43                  | 9.17                  |
| Ankles and wrists | 28.35             | 26.65             | 12.99                 | 12.80                 |
| Feet and hands    | 30.08             | 28.44             | 15.63                 | 15.47                 |

The horizontal one-frame 'second difference' of standing players' `midHip` has a median of 16.21 (Match A) and 14.75 (Match B) m/s². Relative to the trunk, the feet and hands' median is 2.3 (Match A) and 2.4 (Match B) times as large when standing, against 2.4 times for the error radius in both matches. However, the head does not follow this error radius relationship: its error radius is 1.06 times the trunk's in both matches, and its 'second difference' 2.2 times when standing.

### 4.9 The knee angle zigzags in about a third of frames from one pose frame to the next, mostly by under 2°

Share of knee-frames whose angle zigzags from one pose frame to the next, by the size of the zigzag, and the median size of a zigzag:

| Match | Knee-frames | Zigzagging at all | By more than 5° | By more than 10° | By more than 15° | Median size of a zigzag |
| --- | --- | --- | --- | --- | --- | --- |
| Match A | 3,054,336 | 34.6% | 6.7% | 2.3% | 1.2% | 1.9° |
| Match B | 3,122,566 | 34.2% | 6.3% | 2.2% | 1.1% | 1.9° |

One-frame knee zigzags in open play, by running speed, Match A:

| Running speed, Match A | Knee-frames | Zigzagging at all | By more than 5° | By more than 15° | Median size of a zigzag |
| --- | --- | --- | --- | --- | --- |
| Standing (under 0.5m/s) | 106,851 | 44.6% | 5.8% | 0.9% | 1.4° |
| 0–2m/s | 1,008,504 | 36.8% | 5.8% | 1.0% | 1.7° |
| 2–4m/s | 934,219 | 32.6% | 7.5% | 1.2% | 2.4° |
| 4–6m/s | 305,077 | 28.8% | 8.6% | 1.7% | 2.9° |
| Over 6m/s | 45,142 | 25.3% | 10.2% | 2.4% | 3.9° |

One-frame knee zigzags in open play, by running speed, Match B:

| Running speed, Match B | Knee-frames | Zigzagging at all | By more than 5° | By more than 15° | Median size of a zigzag |
| --- | --- | --- | --- | --- | --- |
| Standing (under 0.5m/s) | 107,539 | 44.3% | 4.9% | 0.7% | 1.3° |
| 0–2m/s | 1,023,323 | 36.7% | 5.0% | 0.7% | 1.6° |
| 2–4m/s | 928,246 | 32.2% | 7.1% | 1.1% | 2.3° |
| 4–6m/s | 333,189 | 27.2% | 8.0% | 1.6% | 2.9° |
| Over 6m/s | 69,444 | 24.4% | 10.1% | 2.6% | 4.0° |

As players run faster, fewer frames zigzag, and those that do zigzag by more. The standing rows are a subset of the 0–2m/s rows. Rounding the joints to the nearest millimetre moves a knee angle by about a tenth of a degree, far below the sizes counted here.

## 5. Discussion

### 5.1 Tracking positions are smooth from frame to frame apart from their rounding to 1cm

The one-frame median 'second difference' of 1.41m/s² is little more than the simulated rounding value of 0.89m/s² for a player moving at a steady velocity, so over one frame the measurement sits not far above the noise the rounding creates, and in an ordinary frame a one-frame acceleration from tracking may not be able to be told apart from that noise. 

The two-frame median of 1.06m/s² across the 20 matches is about five times the simulated rounding value of 0.22m/s², so over two frames the figure is mostly the players' own change of velocity.

That leaves very little room for any other error. Positions estimated from broadcast video would normally carry some error that changes from frame to frame, as pose does (section 5.2), and an error of even a few centimetres that jumped about from one frame to the next would push the one-frame 'second difference' far above the 1.41m/s² measured. Most likely, this is evidence that SkillCorner smooths each player's tracking data path before publishing it in this open data. Extrapolated positions, which a model places, are smoother still (median 1.00m/s²), which lends weight to this theory.

### 5.2 Body pose varies from frame to frame far more than its rounding to 1mm

The median horizontal one-frame 'second difference' of `midHip` is 28 (Match A) and 27 (Match B) times the simulated rounding value for rounding to 1mm. Its five-frame median (over 0.2s) is 2.1m/s², and tracking's two-frame median over the same 0.2s in the same two matches is 1.03m/s², so most of the variation comes down when looking at a comparable window in absolute time as is suitable for tracking data.

Over five frames (0.2s), the medians fall to between 1.5m/s² for the trunk and 9.4m/s² for the feet and hands relative to `midHip`.

In open play, the one-frame 'second difference' grows with the player's running speed, and most at the extremities: from the slowest band to the fastest, 2.4 (Match A) and 2.6 (Match B) times for the feet and hands, against about 1.4 times for `midHip` in both. 

Much of the variation at the extremities is present even when a player is standing still and their limbs barely move: standing, the feet and hands vary 2.3 to 2.4 times as much as the trunk, and SkillCorner's own error estimate for those joints is 2.4 times the trunk's. So the extremities vary more mainly because SkillCorner places them less precisely. The head is the exception, varying twice as much as the trunk with about the trunk's error radius.

### 5.3 The knee angle zigzags often, but mostly by a degree or two

A third of one-frame steps reverse the knee angle. Most reversals are small, a median of 1.9°, and they are commonest for a standing player (44.6% and 44.3% of frames), which fits a true knee angle that barely changes, so that a degree or two of error is enough to flip its direction. As players run faster, fewer frames reverse at all, but those that do reverse by more: the median rises from 1.7° (Match A) and 1.6° (Match B) at 0–2m/s to 3.9° and 4.0° above 6m/s, and reversals of more than 15° more than double.

### 5.4 Limitations

- **Smooth is not the same as correct.** A lack of smoothness indicates measurement error, but smooth positions should not necessarily be read as being 'correct': an error that is the same in neighbouring frames, such as a path shifted from where the player was, wouldn't show up in the 'second difference' measure. Paper `001-tracking-pose-coverage` finds tracking and pose about 20cm apart, which smoothness alone could not reveal.
- **Pose rounding on a sample.** The check that pose lies on whole millimetres used every 97th pose frame, about 1% of them.
- **Pose from two matches.** The pose figures come from the two matches with full body pose, so they may not hold for other broadcasts, grounds or camera positions.

## 6. Implications

- **Tracking data needs a wide enough window for acceleration measurement, but no smoothing beyond that.** Speed can be computed from the positions as published. For acceleration and turning, it would be better to use two or more frames either side as a window, given the simulated rounding value at one frame. `goalside`'s `with_movement` function takes acceleration and turn rate over two frames either side for this reason.
- **Acceleration from pose needs a wider window than one frame, or smoothing.** Over one pose frame either side, the frame-to-frame error dominates the acceleration of the player or of a joint. Either of two treatments would reduce it. A wider window, such as five pose frames either side, already brings `midHip` to about twice tracking's figure over the same 0.2s, at the cost of blurring changes shorter than the window. Smoothing the positions first keeps a short window; paper `003-engagement-pose-checks` measures one such smoothing, a seven-frame Savitzky–Golay fit.
- **Pose data measurement error affects joint angles in a way requires careful analysis method.** Researchers should be aware of the measurement error in joint angles, and choose a methodology of analysis, or further data processing, accordingly if joint angles are an area of study.

## Future points for research

- **Whether tracking under-reports sudden changes of direction.** If SkillCorner smooths each tracking path before publishing it (the untested explanation in section 5.1), a sudden stop or cut could be spread over several frames and its peak acceleration lowered. Comparing tracking with pose at moments of sharp turns may shed light on this.
- **Smoothing techniques for the pose data.** Which window or filter removes the frame-to-frame variation without flattening real movement, at each running speed.

## Sources

- SkillCorner, [opendata README](https://github.com/SkillCorner/opendata): broadcast tracking data is "collected through computer vision and machine learning out of the broadcast video", and `is_detected` is a "flag that mentions if the player is detected on the screen or extrapolated" (Tracking Data Description).
- Le, Melnyk, Waldmann, Wadenbäck and Wandt, [QuaMo: Quaternion Motions for Vision-based 3D Human Kinematics Capture](https://arxiv.org/html/2601.19580), on arXiv: "To evaluate the motion jitter, we consider the Accel metric", which "measures the difference between the predicted joint acceleration and the ground truth".
- SkillCorner, [body pose README](https://github.com/SkillCorner/opendata/blob/master/data/bodypose/README.md): the per-joint error "is defined so that 90% of estimated key points are sitting within this error radius".
- SkillCorner's open tracking (`<id>_tracking_extrapolated.jsonl`) for the 20 matches listed in section 3.1, and full body pose for matches 1925299 and 1996435, converted with `goalside v0.1.0` into `skillcorner.tracking` v1 and `skillcorner.pose` v1.

## Appendices

### Appendix A: versions

The paper's results come from `goalside v0.1.0`, reading these tables at these schema versions:

| Table                  | Schema version |
| ---------------------- | -------------- |
| `skillcorner.tracking` | 1              |
| `skillcorner.pose`     | 1              |
| `skillcorner.phases_of_play` | 1        |

`goalside v0.1.0` converted them from this data:

| Data                  | Version                                                                                                                         | Checked                                                                                                                          |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| SkillCorner open data | [`opendata` commit 4340d27](https://github.com/SkillCorner/opendata/tree/4340d274572876239c154c90bc507a9b3250a656) (2026-09-14) | The 20 tracking files match the commit by their Git LFS SHA256, and the pose matches' `match.json` and phases of play CSVs by git hash                                        |
| Full body pose        | SkillCorner's [opendata-bodypose](https://huggingface.co/datasets/SkillCorner/opendata-bodypose) dataset on Hugging Face         | Each archive matches the size and SHA256 in `data/bodypose/MANIFEST.json` at the same commit, which `goalside` checks when it downloads it |

`goalside` downloads SkillCorner's files from the `opendata` repository's `master` branch. Reproducing the paper after a later SkillCorner commit would mean taking the files from commit 4340d27, for example from a clone of `opendata` at that commit, and passing each to `goalside`'s converter functions as `source`.

### Appendix B: the smoothness analysis script

**File.** `tracking-smoothness.py` in this folder. The results above come from `goalside v0.1.0`.

**Run.**

```
uv run python papers/002-tracking-smoothness/tracking-smoothness.py
```

- **Needs:** all 20 matches' tracking, and the full body pose of matches 1925299 and 1996435, in `goalside`'s data directory (the `goalside.data_dir()` function), loaded with `goalside`'s `download_tracking` and `convert_tracking`, then `download_match`, `convert_match`, `download_pose_match` and `convert_pose` functions.
- **Takes:** a few minutes, most of it reading the pose.
- **Writes:** `outputs/tracking_smoothness.json` in this folder, with a `raw_precision` section, a `tracking` section, across the 20 matches and `by_match`, and a `pose` section for each of the two pose matches.

**Structure.**

```
main()
  raw_precision()                                  # sections 4.1 and 4.4, from SkillCorner's files
  tracking = skillcorner.tracking rows for all 20 matches
  tracking_smoothness(tracking)                    # sections 4.1–4.3
    second_difference(1), second_difference(2)
    rounding_acceleration(1), rounding_acceleration(2)
  for each pose match:
    pose_smoothness(match)                         # sections 4.4–4.6
      pose_rounding_acceleration(step, relative) for steps 1 and 5
      open play by running speed                   # section 4.7
      open play, standing; error radius by body part   # section 4.8
      knee zigzags: each window, by speed band, standing  # section 4.9
  write JSON
```

**`tracking_smoothness`: 'second differences' and rounding.**

```
rows = tracking for all 20 matches, sorted by (match_id, period, player_id, frame)
for each row, within (match_id, period, player_id), for step in (1, 2):
    a_step = |position(row + step) − 2 × position(row) + position(row − step)| / (step × 0.1 s)²
    keep a_step only if frame(row + step) − frame(row − step) == 2 × step     # no gap
switch   = is_detected ≠ is_detected of the previous row
on_cm    = |100x − round(100x)| < 0.001 and the same for y
summaries, across the 20 matches: share on_cm; percentiles of a_1 for detected, extrapolated,
           switch rows and all; share of a_1 over 10 m/s²; percentiles of a_2 for detected rows
by match: player-frames, share on_cm, medians of a_1 (detected, extrapolated, switches),
          share of a_1 over 10 m/s², percentiles of a_2 for detected rows

rounding_acceleration(step):                                  # seed 0, one million samples
    error = uniform(−0.5 cm, +0.5 cm) for x and y at row − step, row, row + step
    percentiles of |error(+step) − 2 × error(0) + error(−step)| / (step × 0.1 s)²
```

**`raw_precision`: decimal places as SkillCorner's files write them.**

```
for every line of every <id>_tracking_extrapolated.jsonl:
    count the decimal places of each "x" and "y" value, as text
for every 50th line of each <id>.jsonl.zip pose archive:
    count the decimal places of each value in each joint's "xyz", as text
```

**`pose_smoothness`: pose 'second differences' and rounding.**

```
on_mm = |1000v − round(1000v)| < 0.01 for v in x, y, z, over every 97th pose frame   # float32 values
for each period:
    points = joint_arrays(pose for the match and period)   # n × 29 joints × (x, y, z)
    sort by (player_id, frame)
    for step in (1, 5):
        keep a row only if the rows step before and after are the same player, 2 × step frames apart
        second   = (points(+step) − 2 × points + points(−step)) / (step × 0.04 s)²
        mid_hip  = |second[midHip] in x and y|
        relative = |second[joint] − second[midHip]| in x, y and z, for each joint
summaries: percentiles of mid_hip, and of relative pooled by body part, for each step
speed     = |midHip(+5) − midHip(−5)| in x and y / 0.4 s, where both exist for the same player
open play = frames whose tracking frame lies between frame_start and frame_end of a phases_of_play
            row whose team_in_possession_phase_type is not set_play
for frames in open play with step 1 and a speed: medians of mid_hip and of relative by body part,
            by speed band (0–2, 2–4, 4–6, over 6 m/s), and for speed under 0.5 m/s
error radius = median p90_mae_cm over the joints of each body part, over every pose row of the match
knee angle   = angle at lKnee (and rKnee) between the vectors to lHip and lAnkle, in degrees;
               none where all 29 joints lie within 0.3 m, or the thigh or shin is under 0.1 m
within period and player, where frames f − 1 and f + 1 exist and all three have a knee angle:
    move_in  = angle(f) − angle(f − 1); move_out = angle(f + 1) − angle(f)
    zigzag   = move_in × move_out < 0; size = min(|move_in|, |move_out|)
summaries: share of knee-frames zigzagging by more than 0°, 5°, 10° and 15°, and the median size,
           over all knee-frames, in open play by speed band and standing

pose_rounding_acceleration(step, relative):                  # seed 0, one million samples
    error = uniform(−0.5 mm, +0.5 mm) in 2 (midHip) or 3 (relative) dimensions,
            minus a second such error for a joint relative to midHip
    percentiles of |error(+step) − 2 × error(0) + error(−step)| / (step × 0.04 s)²
```

**Reuse.** The `with_movement` function in `goalside.skillcorner.movement` computes speed, direction, acceleration and turn rate from tracking, with acceleration over two frames either side. The `joint_arrays` function in `goalside.skillcorner.facing` builds the pose arrays.

## Revisions

None since publication.
