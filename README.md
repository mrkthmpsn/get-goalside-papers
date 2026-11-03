# get-goalside-papers

Blog-papers on football providers' open data. Each paper answers a question by measuring the data, and keeps the code that measured it in its own folder under `papers/`, so its numbers can be reproduced from the same open data with the version of [`goalside`](https://github.com/mrkthmpsn/get-goalside-code) it names.

| | Paper | Question | goalside | Tables |
| --- | --- | --- | --- | --- |
| 001 | [Tracking and pose coverage](papers/001-tracking-pose-coverage/tracking-pose-coverage-ai.md) | How SkillCorner's tracking and body pose line up: frame pairing, camera and pose coverage, and the distance between the two | 0.1.0 | `skillcorner.tracking`, `tracking_frames`, `pose`, `pose_frames`, `dynamic_events`, `phases_of_play`, `match_periods`, each v1 |
| 002 | [Tracking and pose smoothness](papers/002-tracking-smoothness/tracking-smoothness-ai.md) | How smooth SkillCorner's tracking positions and body pose are from one frame to the next, and how much of that is their rounding | 0.1.0 | `skillcorner.tracking`, `pose`, `phases_of_play`, each v1 |
| 003 | [Pose checks and smoothing on engagements](papers/003-engagement-pose-checks/pose-checks-and-smoothing-on-engagements-ai.md) | How often a defender's body pose is inconsistent around on-ball engagements at the last line in open play, which checks find it, and how far smoothing goes | 0.1.0 | `skillcorner.pose`, `pose_frames`, `dynamic_events`, `phases_of_play`, each v1 |
| 004 | [Event moments](papers/004-event-moments/event-moments-ai.md) | Where the start and end frames of SkillCorner's player possessions fall against the ball and the player, in time and on the pitch, and which frame to take as the moment of a pass | 0.1.0 | `skillcorner.dynamic_events`, `phases_of_play`, `tracking`, `tracking_frames`, `pose`, `pose_frames`, each v1 |

## Reproducing a paper

The papers need Python 3.12, [uv](https://docs.astral.sh/uv/), and a clone of `get-goalside-code`, the repository of the `goalside` package, in the same parent folder as this repository, since `pyproject.toml` installs `goalside` from `../get-goalside-code`. Clone both, with `goalside` at the version the papers name:

```bash
git clone --branch v0.1.0 https://github.com/mrkthmpsn/get-goalside-code.git
git clone https://github.com/mrkthmpsn/get-goalside-papers.git
cd get-goalside-papers
uv sync
```

The papers use SkillCorner's two matches with full body pose, 1925299 and 1996435, and paper 002 also uses the tracking of all 20 matches in SkillCorner's open data. Load the two matches' tables into goalside's data directory, which is `data/` under the working directory unless `GOALSIDE_DATA_DIR` names another:

```python
from goalside.skillcorner.dynamic_events import convert_dynamic_events, download_dynamic_events
from goalside.skillcorner.match import convert_match, download_match
from goalside.skillcorner.phases_of_play import convert_phases_of_play, download_phases_of_play
from goalside.skillcorner.pose import convert_pose, download_pose_match
from goalside.skillcorner.tracking import convert_tracking, download_tracking

for match_id in (1925299, 1996435):
    download_match(match_id)
    convert_match(match_id)
    download_dynamic_events(match_id)
    convert_dynamic_events(match_id)
    download_phases_of_play(match_id)
    convert_phases_of_play(match_id)
    download_tracking(match_id)
    convert_tracking(match_id)
    download_pose_match(match_id)
    convert_pose(match_id)
```

The two pose archives are about 600MB each, and converting each takes about 4.5 minutes. Each paper's appendix then gives the command for each of its scripts, which write their results to `outputs/` in the paper's folder.

## Credit and licence

The papers are drawn from [SkillCorner's open data](https://github.com/SkillCorner/opendata), which must be credited in anything published from it. The papers and their code are released under the MIT licence, in [LICENSE](LICENSE).
