# D146 — measurement and verifier independence

Status: **built** (branch claude/audit-fixes). This is the audit prompt's "D143".

## Why
- Box 4's diagnoses could not be measured: events.jsonl kept only the signal names, and there was no way to record
  whether a diagnosis was right.
- "Verifier independence" was only a router policy (`routing.verifier_independence: preferred`). With one model per
  profile, every verify step ran on the producers' own model, and nothing in result.json said so.
- The verifier's "own result first" loop (D90) could still read the producers' fetched pages under `sources/`, so it
  was not blind.
- The evidence hash chain looked like an external anchor, but it is not one.

## What
1. **The diagnosis record.**
   - Every `stuck` row in `<run>/events.jsonl` carries the cause, every signal (`signals_detail`, with evidence and
     refusal categories) and the evidence lines.
   - Each row has `ground_truth: null`, to be filled by hand later.
   - `python -m scripts.grade_episodes <run>` asks, per episode, right / partly / wrong / skip with an optional note,
     and writes `<run>/grades.json` next to the run. The hash-chained log itself is never changed, and earlier grades
     are kept unless re-graded.
2. **Verifier independence.**
   - A profile may name a `verifier` profile. `attach_verifier` routes the reviewers group (verify steps and D51
     critics) and the plan observer (`RoleRouter.by_agent`) to that profile's model, when its key is set.
     Otherwise the run prints that the verify steps keep the team's model.
   - New profile **`claude-sonnet+gemma-verify`**: Claude Sonnet for the team, and Gemma (`gemma-api`, needs
     GEMINI_API_KEY) for verify steps and the plan observer.
   - Each step's meta records the models it used (`models`). result.json records, per verify step,
     `verifier_independence`: independent (a different family), same_family or same_model, with both sides' models.
   - **Clean sources for the own-result loop**: while the verifier works out its own result, `sources/` holds only
     what it fetches itself, and the sources note is left out. The producers' files come back for the comparison
     phase, with the verifier's own fetches added (`clean_sources`, event `verifier_clean_sources`).
3. **The evidence hash chain is self-consistent only.** `events.jsonl` is hash-chained (each row holds the SHA-256
   of the row before it), and `scripts.verify_evidence` checks that the chain is unbroken. Nothing anchors it
   outside the run folder: `make_shipper` (amoeba/adapt/evidence.py) is never called, so the chain shows that rows
   were not edited relative to each other. It does not show that the folder was not rewritten as a whole. This
   decision does not wire up the shipper.

## As built (Oct 16)
- The `verifier` profile applies under `--routing role`. Under the default `--routing routed` (D97), the
  ModelRouter's own `verifier_independence` policy picks the verifier per call, and fixed routing (the baselines)
  drops per-role models. The live commands in the audit report use `--routing role`.
- The reviewers group also covers D51's critique reviewers, not only verify steps. Departure: the prompt named verify
  steps and plan observers.
- Model families are read from model names (`model_family`: claude → anthropic, gemma/gemini → google, ...).

## Tests
tests/test_measurement_d146.py:
- a stuck episode in events.jsonl with signals_detail and ground_truth null;
- grade_episodes records a grade and keeps it when skipped later;
- independent / same_family / same_model per verify step;
- the verifier profile's routing, with and without its key;
- the clean sources folder and its restore.
