# Phase 2, week 1: the hand-edit check on Gemma (stream_m1, family calc)

> **History.** This describes the offline learning loop (task streams, the Experimenter, the Gate, recipes) that D117 removed on Oct 6, 2026 (spec/BUILD_SPEC_PHASE1.md row D117; spec/BUILD_SPEC_PHASE2.md §17). The results are kept as they were; the scripts and files it names may no longer exist.

*Run 2–3 October 2026 on Gemma 4 31B (`gemma-api`), run clock America/Chicago. Amoeba's plan runner only.*

**Setup.**
- Recipe v1 is the empty seed recipe.
- Every run had the same settings: d24 prompts, step contract on, interpretation on, pool off, re-plan on, self-refine on-issues, collab critique, and the D79 quality gate.
- Held-out slice of `tasks/stream_m1.jsonl`, frozen before any run: 5 post tasks and 3 pre tasks, 3 repeats each.
- Two hand-written hypotheses (`eval/loop/m1/hypotheses/`) went through `scripts/run_experiment.py`, so Box 7 ran the experiment and Box 8 decided. The useless one ran first, so a reject would not move recipe v1 and one calibration could serve both.

## The ledger (`eval/loop/m1/ledger.jsonl`)

| event | hypothesis | decision | observed d | noise | p (test) | N | cost ratio | honesty A → B | retention d | reasons |
|---|---|---|---|---|---|---|---|---|---|---|
| calibration | — | — | 0.000 (A′ − A) | **0.000** | — | — | — | — | — | 15 pairs; mean score 0.733 in both arms |
| hypothesis | h1-revoke-calc | — | — | — | — | — | — | — | — | revoke `calc` from all roles; predicted +0.05 |
| decision | h1-revoke-calc | **reject** | +0.000 | 0.000 | 1.0 (Wilcoxon) | 1 | 0.91 | 1.13 → 0.80 | 0.000 | 2 no real gain (0.000 ≤ 0.05); 3 prediction failed |
| hypothesis | h2-assumptions-rule | — | — | — | — | — | — | — | — | planner rule "end with a section headed '## Assumptions' …"; predicted +0.20 |
| decision | h2-assumptions-rule | **reject** | **+0.267** | 0.000 | 3.1e-5 (Wilcoxon), p×N = 6.1e-5 | 2 | 1.12 | **1.13 → 2.67** | 0.000 | 5 honesty regression (2.67 > 1.13 + 0.2) |

**What was expected.** One accept (h2) and one reject (h1). The result is two rejects:
- **h1, the useless edit, was rejected as expected.** Without `calc`, Gemma still computed every number correctly. All 24 pairs were identical, so there was no gain and the prediction failed.
- **h2, the helpful edit, met the requirement, but the Gate rejected it on honesty.**
  - With the lesson, every one of the 15 held-out post runs had an Assumptions section and scored 1.0, against 0.733 for arm A.
  - It passed rules 1–4 and 6: the gain is real, it was predicted, the cost ratio is 1.12, and it lost nothing on the pre tasks.
  - It failed rule 5. The honesty flags rose from 1.13 to 2.67 per run, past the +0.2 margin.

## Why h2 failed rule 5

The flags are almost all D33 "hallucinated citations": an `[S#]` tag naming no source the step could see. These calc tasks have no web or pool sources, but Gemma's helpers tag computed figures with `[S1]` / `[S2]`. For example, `0.055 / 4 = 0.01375 [S1]` comes from an arm-A step. The tags seem to mean "step 1" or "the calc result".

| Arm | `[S#]` tags in step outputs | counted as hallucinated | run errors | flags per run |
|---|---|---|---|---|
| A | 29 | 17 | 0 | 1.13 |
| B | 62 | 38 | 2 ("incomplete": the answer step failed the inputs-referenced check) | 2.67 |

Under the rule, the plan has a final assembly step (a Summariser, as the lesson needs). That step restates every figure with `[S1]`, so B doubles the mis-tags. So the Gate did exactly what spec §9.2.5 says. But the signal it caught is a mis-tag of step references, not an invented source. Two views:
1. **The reject stands.** The edit really does raise a flag the spec counts, and a better edit would avoid it. For example, add to the rule "refer to earlier steps as 'step N', never as [S#]". That would be hypothesis h3, decided at N = 3.
2. **The measure is too blunt for a family with no sources.** An `[S#]` in a run whose source list is empty cannot be a citation of anything. One could count it as an untagged figure rather than a hallucinated citation, or set the honesty margin relative to the baseline (1.13 per run already) rather than as an absolute +0.2. That is a change to D33 or to the Gate's thresholds, so it is yours to decide.

I have not run h3 or changed any threshold.

## Fixes made during the check (each a spec row)
- **D80a, the rubric's number reader.** It read the "m" of "32.4 m²" or "3.5 m³" as million. It now counts as million only after a currency sign. The Experimenter re-scores every run from its saved answer, so both arms use the fixed scorer.
- **D84a, the section parser.** It split the Planner's reply at a `##` in the middle of a line. The h2 lesson quoted "'## Assumptions'", so the Summariser role was cut out of the roles JSON and lost. The quality gate then failed three times on the missing summariser.
  - Now only a `##` that starts a line, or follows a closing tag, is a section break.
  - Re-parsing the earlier m1 runs changed no section the code reads, so the calibration, the arm-A cache and the h1 decision stand.
  - The first h2 runs were stopped. They are kept under `eval/loop/m1/discarded/h2-before-D84a/`, and h2 was run again from the start.
- **Harness.**
  - `run_experiment.py` drops the environment's `AMOEBA_*` model overrides, which had sent a smoke run to flash-lite.
  - A resumed hand check writes its hypothesis row once.
  - The runs went 4 at a time, because 8 hit Gemma's per-minute quota (one 429 crash, re-run once).
  - One container restart was resumed from finished run folders and the LLM cache.

## Runs and cost

| Part | Runs | Calls | Cost (high price estimate) |
|---|---|---|---|
| Calibration A and A′ + arm A on pre tasks | 40 (one A′ run crashed on 429 and was re-run) | 661 | $2.31 |
| h1 arm B | 24 | 236 | $1.17 |
| h2 arm B (after D84a) | 24 | 419 | $1.64 |
| discarded h2 attempt | 1 finished | 18 | $0.06 |
| **Total** | **89** | **1,334** | **$5.19** |

**Evidence.**
- `eval/loop/m1/armA/<recipe hash>/` holds the arm-A and A′ runs and their index.
- `eval/loop/m1/experiments/<id>/` holds `experiment.json`, `pairs.jsonl` and the arm-B runs.
- `eval/loop/m1/experiments/calibration-calc-v1/` holds the calibration pairs.
- The key scan of all 1,367 files under `eval/loop/m1/` found 0 hits.
