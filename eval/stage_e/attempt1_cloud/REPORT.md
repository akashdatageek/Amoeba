# D117 Stage E report

Folder: `eval/stage_e/attempt1_cloud`

## Per run

| Task | Seed | Arm | Outcome | Steps not done (why) | Stuck steps (cause) | Recovered (rung) | Work-arounds | Rubric | Tokens | Adapt tokens | Wall (min) | Searches + fetches | Problems |
|---|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| probe-h1-freight | 0 | off | done with limitation | {'attached unused': 1} | 0  | - | 0 | - | 160,716 | 0 | 24.3 | 0 + 0 | - |
| probe-h1-freight | 0 | on | done with limitation | {'mislabelled citation': 3} | 0  | - | 0 | - | 141,856 | 0 | 22.8 | 0 + 0 | - |

## Per arm

| | off | on |
|---|---|---|
| runs | 1 | 1 |
| outcomes | {'done with limitation': 1} | {'done with limitation': 1} |
| stuck_steps | 0 | 0 |
| stuck_by_cause | {} | {} |
| recovered | {} | {} |
| workarounds | 0 | 0 |
| tokens | 160716 | 141856 |
| adapt_tokens | 0 | 0 |
| wall_min | 24.3 | 22.8 |
| searches | 0 | 0 |
| fetches | 0 | 0 |
| rubric | [] | [] |

## Recovered steps, picked at random (on arm)

The off arm makes no fixes, so it has no recovered steps.
No step was recovered.
