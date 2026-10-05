# Amoeba Phase 2 build spec: the adaptation loop (Boxes 4–9)

October 2026. Builds on the Phase 1 code as merged (PR #32: Boxes 1–3, D1–D77). Reuses the designs in
`spec/BUILD_SPEC_FULL_reference_only.md` §3.1, §6, §7 and §8, updated for the step graph that Phase 1 made the real unit
of work. Gate rules follow RRSI (Xia et al., arXiv 2609.24972, Sep 2026): noise floor, cost justification, leakage
screening, a failed-hypothesis record and later pruning. We add rollback and safety checks.

Motto, unchanged: **the LLM proposes, plain code disposes.** In the whole loop only the Architect (Box 6) calls a model.
Every decision about what to keep is made by code.

---

## 0. Plain-language summary

Phase 1 makes a team for each task and runs it (Boxes 1–3). Phase 2 lets Amoeba learn from a stream of tasks:
when results get worse for one kind of task, it finds the failing part, proposes one change to that kind of task's
**team recipe**, tests old against new on tasks it has never trained on, and keeps the change only if the gain is real.

```
Task stream ──► Boxes 1–3 (with the recipe for this task type) ──► run records
                                                                       │
     ┌─────────────────────────────────────────────────────────────────┘
     ▼
 4 Monitor ─► 5 Diagnoser ─► 6 Architect (AI) ─► 7 Experimenter ─► 8 Gate ─► 9 Memory
 score drop   which step,     one typed edit      old vs new on      keep only   recipe per
 alarm        what cause      + a prediction      held-out tasks     real gains  task type
                                                                                    │
            Box 2 and Box 3 start from the stored recipe on the next task ◄────────┘
```

**Scope of Phase 2:** improving the team (the recipe per task type). Improving the boxes themselves (the harness:
prompts, observers, runner code) is out of scope. It comes later and reuses the same gate (§12).

**Build order:** the measuring half first, then the thinking half. In Stage A a hand-written edit goes through
the Experimenter and the Gate. We trust the ruler before Gemma is allowed to propose edits.

---

## 1. Decisions fixed by this spec

| # | Decision | Value |
|---|---|---|
| P1 | Unit of adaptation | a **team recipe** per task family (§3), never a single task's draft |
| P2 | Task families | `calc`, `code`, `lookup` (current facts), `research` (multi-source), `files` (documents and spreadsheets). `Task.family` already exists and is used as-is |
| P3 | Shifts | two kinds: **feedback shift** (the user's acceptance criteria change; the system learns it only from feedback on practice tasks) and **environment shift** (a tool is removed or a source breaks) |
| P4 | First edit menu | 6 typed edits (§3.2). Model swaps and topology flips are left out |
| P5 | Runs per test | 5 held-out tasks × 3 repeats = 15 pairs per hypothesis |
| P6 | Score the loop uses | the D30 rubric fraction (code only), plus code honesty flags as a veto (§7.2). No LLM judge in any decision |
| P7 | Model | Gemma 4 31B (`gemma-api` profile) for all boxes, including the Architect |
| P8 | Who is improved | Amoeba's plan runner only (`--topology plan`). The baselines are not adapted; they are the comparison |
| P9 | Splitting a step | expressed as a planner rule in v1 (a code transform for splitting is later) |

---

## 2. Box 0: the task stream (D80)

### 2.1 Files

`tasks/stream_<name>.jsonl`, one task per line. The existing `Task` fields, plus:

```json
{"id": "s1-calc-07", "prompt": "...", "family": "calc", "rubric": {...},
 "split": "practice" | "heldout", "phase": "pre" | "post", "order": 7}
```

- `order`: the position in the stream (practice tasks only; held-out tasks have none).
- Held-out tasks are never run as stream tasks, never shown to Box 6, and are used only by Box 7.
- Each family's held-out set has `post` tasks (does the change help after the shift?) and `pre` tasks (does it keep
  what worked before? This is the retention check).

`tasks/stream_<name>.shifts.yaml`:

```yaml
shifts:
  - after: 8                      # takes effect from practice task order 9
    family: calc
    kind: feedback                # the post-phase rubrics carry the new item(s); the prompts do not mention them
    items: ["assumptions section"]
  - after: 20
    family: code
    kind: remove_tool             # applied by code to the tool registry for that family's runs
    tool: "local:Bash"
```

### 2.2 Rules

- The stream file and its rubrics are written and committed **before** any loop run, as with bench5. Rubrics must be
  stable over time (no answers that change with the date) so that a score change means the system changed.
- **Feedback channel:** after each practice run, the loop records the names of the rubric items that failed (for
  example "assumptions section"). This is the only rubric information the loop sees: the user telling the system what
  was missing. Item patterns, expected numbers and every held-out rubric stay hidden.
- New flag `run_task --disable-tools a,b` removes tools from the registry and the pool for one run (used by
  `remove_tool` shifts).

### 2.3 Milestone stream (written in Stage A)

`tasks/stream_m1.jsonl`, family `calc`:
- 8 practice tasks before the shift and 8 after;
- 5 held-out `post` tasks and 3 held-out `pre` tasks;
- one feedback shift after task 8.

A second stream with an environment shift (`code` family, `local:Bash` removed) is a stretch goal after Stage B.

---

## 3. The team recipe and the edit menu (D81)

### 3.1 The recipe (`amoeba/adapt/recipe.py`)

A recipe is data. Code applies it at three fixed points that already exist in Phase 1:

```python
class Recipe(BaseModel):
    family: str
    version: int = 1
    parent_version: int | None = None
    planner_rules: list[Rule] = []        # Box 2: shown to the Planner and both Observers ("Lessons for this kind of task")
    transforms: list[Transform] = []      # Box 2→3: applied by code to the final Draft before Box 3 builds the team
    run_options: dict[str, Any] = {}      # Box 3: whitelisted PlanOptions / Limits fields
    created_by: Literal["seed", "human", "architect"] = "seed"
    hypothesis_id: str | None = None      # the hypothesis that made this version

class Rule(BaseModel):
    id: str                                # "L1", "L2", ...
    text: str                              # ≤ 300 characters, task-neutral (§7.1 leakage screen)

class Transform(BaseModel):
    id: str                                # "T1", ...
    op: Literal["add_verify_step", "tighten_done_when", "grant_tool", "revoke_tool", "add_role_rule"]
    select: Selector                       # which steps or roles it applies to
    params: dict                           # op-specific, validated per op

class Selector(BaseModel):                 # matched by code against DraftPlanStep / DraftedRole fields only
    kind: Literal["work", "verify", "any"] = "any"
    roles_with_tool: str | None = None     # roles (or steps whose roles) hold this tool
    last_work_step: bool = False
    all_roles: bool = False
```

The seed recipe for every family is empty (`version 1`, nothing in it). With an empty recipe, a run is the same as a
Phase 1 run. This is tested (§11).

### 3.2 The edit menu: what Box 6 may propose

One edit per hypothesis. Each is a pure function `Recipe -> Recipe` (new version, `parent_version` set):

| Edit | What it does | Where it acts |
|---|---|---|
| `add_planner_rule {text}` / `remove_planner_rule {id}` | adds or removes a lesson the Planner and Observers see; also how a step split is asked for (P9) | Box 2 prompt |
| `add_verify_step {select}` | after each matching step, code adds a `kind: verify` step that depends on it, assigned to the team's checker role (one is added with the D65 check tools if the team has none) | Draft, before Box 3 |
| `tighten_done_when {select, clause}` | appends a clause to `done_when` of the matching steps | Draft |
| `grant_tool {select, tool}` / `revoke_tool {select, tool}` | adds or removes a tool on the matching roles | Draft |
| `add_role_rule {select, text}` | appends a line to the matching roles' `constraints` (shown on the role card, D31) | Draft |
| `set_run_option {name, value}` | sets one whitelisted option: `replan` (on/off), `self_refine` (off/on-issues/always), `collab` (concat/critique), `max_turns` (3–8), `check_retry_turns` (1–3) | Box 3 |

`remove_*` and `revoke_*` count as edits too, so the loop can also simplify a recipe.

### 3.3 Validation (`validate_recipe(recipe, envelope) -> list[Violation]`, code only)

- V1: every tool named is in the registry and the envelope allowlist; no tool that the pool's `side_effect()` screen
  (`amoeba/pool/stock.py`) refuses; no paid endpoints (the same filters as the pool, D56).
- V2: every run option is whitelisted and in range.
- V3: rule text ≤ 300 characters; at most 8 rules and 8 transforms per recipe.
- V4: no rule or transform text tells the team to skip checks, citations, the sandbox or the contract (a short
  denylist in `amoeba/config/adapt.yaml`: "skip", "ignore", "without verif", "no citation", "disable"…). This is
  reviewed by hand when it fires.
- V5: after the transforms are applied to a sample draft, the step graph still passes the Phase 1 plan checks
  (depends_on refers to existing steps, no cycles, every role used exists).

---

## 4. Recipe hook in Boxes 2 and 3 (D82)

- `run_task --recipes DIR`: loads the current recipe for `task.family` from the store (§10). Without the flag, or with
  no recipe for the family, nothing changes.
- **Box 2:** the d24 prompts (`d24_create_team.txt`, `d24_review_team.txt`, `d24_review_plan.txt`) get a `{lessons}`
  slot, empty by default. The Plan Observer gets one check item: "every lesson is followed or the plan says why not".
- **Box 2 → 3:** after the final draft, code applies the transforms in order (`apply_transforms(draft, recipe) ->
  Draft`) and records what each changed.
- **Box 3:** `run_options` overlay the CLI's `PlanOptions` and `Limits` values. The CLI wins only when it is set
  explicitly; this is needed for ablations.
- **Records:** `result.json` gets `recipe: {family, version, rules: [...], transforms_applied: [{id, steps or roles
  changed}], run_options}`; trace events `recipe_loaded` and `recipe_applied`; the Draft gets `recipe_applied`.
- **D45 reuse:** `--drafts-from` plus `--recipes` applies only the transforms and run options to the saved draft.
  Rules need a fresh draft, and the record says so. The Experimenter depends on this (§7).

---

## 5. Box 4: the Monitor (D85, code)

`amoeba/adapt/monitor.py`. It reads the run records of the practice stream, per family:

- **Score alarm:** the mean of the last `W=3` scores is below `μ_ref − max(2σ_ref, 0.10)` for that family, where
  `μ_ref` and `σ_ref` come from the family's practice runs since its last accepted change (at least 4 runs; until
  then, no alarm).
- **Cause alarm:** the rate of any D61 cause (`capability`, `checks`, `max_turns`, `unused_tool`,
  `claimed_file_missing`) or of a failed rubric item over the last W runs is ≥ 0.5 and was ≤ 0.2 before.

Output:

```python
class Alarm(BaseModel):
    family: str
    kind: Literal["score", "cause"]
    window: list[str]            # run ids
    before: float; after: float  # mean score (or rate) before and in the window
    at_order: int
```

No alarm while the family is in a dwell period after an accept, or cooling down after a reject (§8.4).

---

## 6. Box 5: the Diagnoser (D86, code)

`amoeba/adapt/diagnoser.py`, tier 0 only (no model). Phase 1 already records why each step failed, so the
Diagnoser counts the records rather than guessing.

Input: the alarm and the window's run folders (`result.json`, `artifacts/step_*.json`, the feedback names).

It counts, over the window:
- D61 `causes` per step, with the step's `kind`, its roles and those roles' tools;
- `blocked_capabilities`, `contract_missing`, `unused`, `unverified_check`, `claimed_files_missing`;
- honesty signals: `provenance.total.hallucinated_citations`, `mislabelled_citations` per step (D74),
  `summary_check.cited_figures_left_out`;
- failed rubric item names (the feedback channel).

```python
class Diagnosis(BaseModel):
    family: str
    symptom: str                          # e.g. "feedback: assumptions section missing in 3/3 runs"
    cause: Literal["capability", "checks", "max_turns", "unused_tool", "claimed_file_missing", "feedback", "honesty"]
    where: dict                           # {"step_kind": "work", "roles_with_tool": "web_search"} — a Selector-shaped hint
    evidence: list[str]                   # short quotes: step file + field + value, at most 8
    counts: dict[str, int]
    allowed_edits: list[str]              # from the table below
```

Which edits may answer which cause (the table lives in `amoeba/config/adapt.yaml`, so it can be edited):

| Cause | Allowed edits |
|---|---|
| capability | `grant_tool`, `add_planner_rule`, `set_run_option(replan)` |
| checks | `add_verify_step`, `tighten_done_when`, `add_role_rule`, `set_run_option(check_retry_turns)` |
| max_turns | `add_planner_rule` (split), `set_run_option(max_turns)` |
| unused_tool | `revoke_tool`, `add_role_rule` |
| claimed_file_missing | `add_role_rule`, `add_verify_step` |
| feedback | `add_planner_rule`, `tighten_done_when`, `add_role_rule` |
| honesty | `add_verify_step`, `add_role_rule`, `tighten_done_when` |

When several causes are present, the most frequent comes first. Ties go in the table's order.

**Ablation switch:** `--diagnoser none` gives the Architect the alarm only, with all edits allowed. This is the
untargeted baseline for the papers.

---

## 7. Box 6: the Architect (D87, the only AI box)

`amoeba/adapt/architect.py`, prompt in `amoeba/config/prompts/architect.txt`.

Input, all as text:
- the diagnosis;
- the current recipe (YAML);
- the allowed edits with their parameter shapes;
- this family's failed hypotheses (edit + observed result, from the ledger);
- 2 practice examples from the window (task prompt, the failing step's `do`/`output`/`done_when`, the evidence lines).
  Practice tasks only.

Output: one JSON object, parsed with pydantic in strict mode:

```python
class Hypothesis(BaseModel):
    hypothesis_id: str
    family: str
    edit: Edit                 # one of §3.2, with its parameters
    rationale: str             # ≤ 400 characters
    metric: Literal["score"] = "score"
    predicted_delta: float     # signed, e.g. +0.15; falsifiable
    diagnosis_ref: str
```

Code checks after parsing (any failure means one retry with the error shown, then give up and log `no_hypothesis`):
- the edit is in `allowed_edits` and its parameters validate;
- `validate_recipe(apply(recipe, edit))` is clean (§3.3);
- it is not a repeat of a failed hypothesis for this family (same op and same normalised parameters, hashed);
- **leakage screen:** the edit text contains no 8-word sequence from any held-out task prompt, no held-out expected
  number and no held-out task id;
- `predicted_delta` is between −1 and 1.

At most 3 hypotheses per alarm. After 3 rejects, the alarm is logged as `unresolved` and written to
`eval/loop/<stream>/human_queue.jsonl`. The loop goes on with the current recipe.

---

## 8. Box 7: the Experimenter (D83, code)

`amoeba/adapt/experimenter.py`.

```
experiment(recipe_A, hypothesis, heldout_slice, repeats=3) -> ReplayResult
  recipe_B = apply(recipe_A, hypothesis.edit)
  for task in heldout_slice (post tasks of the family, then pre tasks for retention):
      for k in 0..repeats-1:
          if the edit is a transform or run option:
              draft once with recipe_A's rules (seed k), save it, run A and B on that same draft (D45)
              → the only difference between the arms is the edit
          else (a planner rule):
              each arm drafts with its own rules (seed k); draft variance is part of the noise
          run A and B with the same seed, tools, model, timezone and limits
  return pairs [(task, k, score_A, score_B, tokens_A, tokens_B, honesty_A, honesty_B, run_ids)]
```

- **Reuse:** arm A results for `(recipe_A hash, task, k)` are cached for the life of a recipe version. Later
  hypotheses against the same version run only arm B, which halves the cost.
- Runs go through the bench runners' parallel pool (8 at once), with D73 retries and resume.
- **Honesty flags per run:** `hallucinated_citations` + Σ `mislabelled_citations` + `claimed_files_missing` +
  `unverified_check` + `1 if error`.
- Everything is written to `eval/loop/<stream>/experiments/<hypothesis_id>/` (pairs.jsonl and the run folders).

**Stage A acceptance (by hand, before Boxes 4–6 exist):** `scripts/run_experiment.py --stream m1 --family calc
--edit edit.yaml` runs one hand-written hypothesis through Box 7 and Box 8.

---

## 9. Box 8: the Gate (D84, code)

`amoeba/adapt/gate.py`, ledger in `amoeba/adapt/ledger.py`. Thresholds live in `amoeba/config/adapt.yaml`.

### 9.1 The noise floor (once per family and recipe version)

Run recipe A against itself (A vs A′) on the held-out post slice: 5 × 3 pairs, using different seeds for A′.
`noise = 2 × std(d_AA) / √n`. Recorded in the ledger as a `calibration` row. Arm A′ also fills the arm-A cache.

### 9.2 Decision, in order (any failure rejects, and the reason is recorded)

1. **Valid:** the recipe validates, and the leakage screen passed (re-checked here; the Architect's check is not
   trusted).
2. **Real gain:** `d = score_B − score_A` over the post pairs. Accept only if `mean(d) > max(noise, 0.05)` **and**
   a one-sided paired test (Wilcoxon signed-rank; a t-test when every d is distinct and n ≥ 10) has
   `p × N < 0.05`, where N = hypotheses tried for this family since its last accept (Bonferroni).
3. **Prediction held:** the sign of `mean(d)` matches the sign of `predicted_delta`. A gain the Architect did not
   predict is rejected and logged as `unexplained_gain`.
4. **Cost justified:** `cost_ratio = mean(tokens_B) / mean(tokens_A) ≤ 1.25`, or `≤ 2.0` when `mean(d) ≥ 0.15`.
5. **No honesty regression:** `mean(honesty_B) ≤ mean(honesty_A) + 0.2`, and no new sandbox or side-effect refusal
   appears. *(Gate v1, used for h1 and h2 in Stage A. Replaced by rules 5 and 5b of Gate v2 below.)*
6. **Retention:** on the held-out pre tasks, `mean(score_B − score_A) ≥ −noise`.

#### Gate v2 (D84b, from Oct 3; written before any re-decision)

Stage A showed two faults in v1's rule 5. First, it summed tags per run, so a habit that shows up once per figure
(Gemma tagging its own computed figures `[S1]` in runs with no sources) was counted once per figure, and an edit that
makes the answer restate every figure doubled the count without making any run less honest. Second, it counted a run
error ("incomplete" etc.) as dishonesty. Gate v2 changes rule 5 and adds rule 5b; rules 1–4 and 6 are unchanged.

5. **No honesty regression (v2), per run:** a run is *flagged* when it has at least one of {hallucinated citation,
   mislabelled citation, claimed file missing, unverified check}. `share = flagged runs / runs` over the post pairs.
   Reject if `share_B − share_A > 0.2`, or a new sandbox or side-effect refusal appears. The per-tag counts stay in
   the ledger as information only.
5b. **No reliability regression (v2):** `error_rate = runs that ended in an error / runs` over the post pairs.
   Reject if `error_rate_B − error_rate_A > 0.2`. Run errors no longer count toward honesty.

Every ledger row carries `gate_version` (`v1` or `v2`). Rows decided under v1 are never rewritten. A hypothesis
decided under v1 may get one more decision row under v2, computed from its saved pairs without new runs and marked
`"post_hoc": true`; it is reported whatever it says, and it does not change the recipe store.

#### Gate v3 (D91, written Oct 3, 2026, before any run on the gate set)

The research review found three faults in v1/v2 that are not about thresholds but about the test itself. First, the
pairs of one task are not independent (the same task, three seeds), so a paired test over 15 pairs from 5 tasks
counts each task three times. Second, a Bonferroni N that resets on every accept lets a long stream spend an
unbounded error rate. Third, the prediction-sign rule rejects real gains the Architect mis-predicted and says
nothing a ledger column could not say. Gate v3 is the default from D91 on; it is fixed here before any data on the
gate set (D92) exists.

- **Data.** The family's gate set (D92: 15 held-out post tasks) and its held-out pre tasks (retention), `r` repeats
  per task (adapt.yaml `experiment.repeats`, 3). For each task t: `d_t = mean_k score_B(t, k) − mean_k score_A(t, k)`.
- **Noise (v3).** Calibration runs A against A′ (other seeds) on the gate set; `noise = 2 × std(d_t^AA) / √n_tasks`
  over the per-task means. The calibration row also records each task's spread across seeds (the standard deviation
  of its 2r scores, and A's and A′'s scores), so the report shows per-task noise, not only whether pairs were equal.
- **2. Real gain (v3), task level.** `mean_t(d_t) > max(noise, 0.05)` **and** a one-sided paired permutation
  (sign-flip) test on the per-task means has `p ≤ alpha_i`. The test statistic is `Σ_t d_t`; `p` is the share of the
  `2^n` sign assignments whose sum is ≥ the observed one (identity included), enumerated exactly when n ≤ 20 tasks,
  otherwise 100,000 random assignments with a fixed seed.
- **Fixed error budget.** At most 6 hypotheses per family per stream reach the Gate. The i-th one (i = 1..6, in
  ledger order, counted from the family's v3 decision rows of that stream, accepts included) is tested at
  `alpha_i = 0.05 / 6`, the list fixed in adapt.yaml (`gate.v3.alphas`) before the run. No reset on accept. When the
  budget is spent, an alarm for that family goes to the human queue (`quota_spent`; in code the error budget is the hypothesis quota) and no Architect call is made.
- **3. Prediction (v3): no rule.** `predicted_delta` stays in the ledger; the loop report gives prediction accuracy
  (sign agreement and absolute size error of `predicted_delta` against `mean_t(d_t)`).
- **Kept from v2:** rule 1 (valid, leakage), rule 4 (cost, per run), rule 5 (share of runs with ≥ 1 honesty flag, per
  run) and 5b (error rate), rule 6 (retention: `mean_t(d_t)` on the pre tasks ≥ −noise), and the rollback watch, the
  dwell and the cool-down (§9.3).
- **Ledger.** Rows carry `gate_version: "v3"`, `test: "permutation"`, `n_tasks`, `repeats`, `hypothesis_index`, `alpha`,
  `task_d` (per-task means) and `prediction` (`sign_ok`, `abs_error`). v1 and v2 rows are never rewritten.
- **The pre-registered Assumptions re-test.** Before M-P2, Stage A's helpful hand edit (h2, the Assumptions planner
  rule) is re-tested once on the gate set under v3 as a single pre-registered confirmatory test at `alpha = 0.05`.
  Its rows are marked `"check": true`; it does not use the loop's budget and never changes the recipe store, so
  M-P2 still starts from the seed recipe with no hand edits.

### 9.3 After the decision

- **Accept:** Box 9 stores `recipe_B` as the family's current version. The family enters a dwell period: no new
  hypothesis for the next 4 practice tasks of that family.
- **Reject:** the hypothesis goes on the failed list for the family, which the Architect sees next time. The same
  edit cannot be proposed again (§7). A cool-down of 2 practice tasks applies to that family.
- **Rollback watch:** for the 4 practice tasks after an accept, if their mean score < the mean of the window that
  raised the alarm − noise, code reverts to the parent version and logs `reverted`.

### 9.4 The ledger (`eval/loop/<stream>/ledger.jsonl`, one row per event)

```json
{"ts": "...", "event": "calibration|hypothesis|decision|reverted|unresolved",
 "family": "calc", "hypothesis_id": "...", "recipe_from": 1, "recipe_to": 2, "edit": {...},
 "predicted_delta": 0.15, "observed_delta": 0.21, "noise": 0.06, "p": 0.004, "N": 1, "p_adj": 0.004,
 "cost_ratio": 1.08, "honesty_A": 0.2, "honesty_B": 0.1, "retention_delta": 0.0,
 "honesty_share_A": 0.33, "honesty_share_B": 0.4, "error_rate_A": 0.0, "error_rate_B": 0.07,
 "decision": "accept", "reasons": [], "runs": "experiments/<id>/", "gate_version": "v2", "post_hoc": false}
```

This file is the source for the papers' adaptation tables: accepted and rejected edits, prediction accuracy,
reverts and cost.

### 9.5 Later (RRSI pruning, stretch after Stage B, otherwise Phase 3)

At the end of a stream, for each accepted edit, test the recipe without it on the held-out slice. If the score does
not drop beyond the noise floor, remove the edit. Recipes stay small, and edits that only helped by chance are undone.

---

## 10. Box 9: Memory, the recipe store (D88, code)

`amoeba/memory/recipes.py`. The store is a folder (default `eval/loop/<stream>/recipes/`, committed as evidence):

```
recipes/
  <family>/v<N>.yaml         # full Recipe
  index.json                 # {family: {"current": N, "history": [{version, parent, hypothesis_id, accepted_at, reverted_at?}]}}
  experience.jsonl           # one line per decided hypothesis: diagnosis, edit, predicted/observed delta, decision
```

- `run_task --recipes DIR` reads `index.json` and the current version for the task's family (§4).
- The D77 user context (`amoeba/memory/context.py`) stays where it is: Memory now has two read-only parts at run
  time (who is asking, and the best recipe for this kind of task). Only the Gate writes recipes.
- **Warm start:** a new stream can start from another stream's store (`--recipes-from`). This is a Phase 3
  experiment, but the format supports it now.

---

## 11. The loop driver and the first milestone (D89)

`scripts/run_loop.py --stream m1 --recipes eval/loop/m1/recipes --profile gemma-api --timezone America/Chicago`

```
calibrate the noise floor for each family in the stream (§9.1)
for task in practice tasks, by order:
    apply the shifts that are due (feedback rubric / disabled tools)
    run Boxes 1–3 with the family's current recipe → record score, causes, feedback names
    rollback watch (§9.3)
    alarm = monitor(family)                      # Box 4
    if no alarm or in dwell/cool-down: continue
    diagnosis = diagnose(alarm)                  # Box 5
    for attempt in 1..3:
        h = architect(diagnosis, recipe, failed)  # Box 6
        if none: break
        r = experiment(recipe, h, heldout)        # Box 7
        decision = gate(recipe, h, r)             # Box 8
        if accept: memory.commit(...); break      # Box 9
    else: log unresolved
write eval/loop/<stream>/summary.json and REPORT.md (score per task over the stream, alarms, decisions)
```

It is resumable (D73): a crash restarts at the first task with no `result.json`.

**Milestone M-P2 (the deliverable of Stage B)**, on `stream_m1`:
1. Before the shift, the calc scores are stable. No alarm, or an alarm that leads to no accepted change.
2. After the feedback shift, the Monitor raises an alarm within 3 tasks.
3. The Diagnoser names `feedback` with the missing item.
4. The Architect proposes one edit, and the Gate accepts it with the reasons recorded.
5. On the held-out post tasks, recipe v2 beats v1 by more than the noise floor; on the held-out pre tasks it does
   not lose.
6. The practice scores after the accept return to the pre-shift level.
7. Every step is in the ledger and the run folders, and the repo's key scan of the run folders finds nothing.

A failed milestone run is still a result. If the Gate rejects every hypothesis, the ledger shows why, and that goes in
the report too.

---

## 12. Out of scope for Phase 2 (and where it goes)

- Improving the harness (Box 1–3 prompts, observers, runner code), with Amoeba's loop compared against Claude Code
  as the improver: **Paper 2**, after the freeze. It reuses Boxes 7–8 and the ledger unchanged; only the edit menu
  changes.
- LLM diagnoser tiers 1–2 and Who&When calibration: Phase 3 / M5.
- A refusal safety suite and a human approval queue for risky edits: M4. Phase 2 has only V1–V5 plus the honesty
  veto.
- Classifying a free-text task's family in Box 1: Phase 3. Stream tasks carry their family.
- Archive search across families and agent banks (reference spec §8): Phase 3.

---

## 13. Build plan and D-rows

| D | What | Files | Stage |
|---|---|---|---|
| D78 | Citation check: a ZIP+4 written together ("463243348") contains its 5-digit ZIP; identifiers (ZIP, phone, street numbers) are matched as whole tokens. From docs/eval/dev §3 | `amoeba/interp/citecheck.py`, test | A |
| D79 | The Box 2 quality gate (D28) on by default for `--topology plan`; off for the baselines and for `--drafts-from` | `scripts/run_task.py`, harness defaults | A |
| D80 | Task stream, shifts, feedback channel, `--disable-tools`; `stream_m1` written and committed | `amoeba/adapt/stream.py`, `tasks/stream_m1*.{jsonl,yaml}` | A |
| D81 | Recipe, edit menu, validation | `amoeba/adapt/recipe.py`, `amoeba/config/adapt.yaml` | A |
| D82 | Recipe hook in Boxes 2–3, `{lessons}` slot, records | `scripts/run_task.py`, `amoeba/task/draft.py`, d24 prompts, `amoeba/interp/plan_runner.py` | A |
| D83 | Experimenter, arm-A cache, `scripts/run_experiment.py` | `amoeba/adapt/experimenter.py` | A |
| D84 | Gate, noise floor, ledger, rollback watch | `amoeba/adapt/gate.py`, `amoeba/adapt/ledger.py` | A |
| D80a | Rubric number reader: a lowercase "m" is a million only after a currency sign ("32.4 m²" was read as 32.4 million); the Experimenter re-scores every run from its saved answer | `amoeba/task/evaluate.py`, `amoeba/adapt/experimenter.py` | A |
| D84a | Section parser: only a "##" that starts a line (or follows a closing tag) is a section break; a heading quoted mid-line stays text | `amoeba/task/parsers.py` | A |
| D84b | Gate v2: rule 5 per run (share of runs with ≥1 honesty flag), new rule 5b (error rate), `gate_version` on every ledger row; h2 re-decided post hoc from its saved pairs | `amoeba/adapt/gate.py`, `amoeba/adapt/ledger.py`, `amoeba/config/adapt.yaml` | B |
| D84c | Open harness item (no code change): in source-free runs Gemma tags its own computed figures `[S#]` and D33 counts them as hallucinated citations — a Box 3 issue for the harness phase (Paper 2) | spec only | B |
| D85 | Monitor | `amoeba/adapt/monitor.py` | B |
| D86 | Diagnoser (tier 0) and the cause → edit table | `amoeba/adapt/diagnoser.py` | B |
| D87 | Architect prompt and checks | `amoeba/adapt/architect.py`, `amoeba/config/prompts/architect.txt` | B |
| D88 | Recipe store, `--recipes`, `--recipes-from` | `amoeba/memory/recipes.py` | B |
| D89 | Loop driver, M-P2 run, report | `scripts/run_loop.py`, `eval/loop/m1/`, `docs/eval/loop_m1/REPORT.md` | B |
| D90 | The verifier answers first: own result in a fresh context without the checked outputs, then compare; both in step_N.json | `amoeba/interp/plan_runner.py`, `amoeba/config/prompts/plan_verify_own.txt` | B |
| D91 | Gate v3: per-task means, permutation test, fixed quota of 6 hypotheses per family per stream at alpha 0.05/6, no prediction rule; the pre-registered check | `amoeba/adapt/gate.py`, `amoeba/adapt/ledger.py`, `amoeba/config/adapt.yaml` | B |
| D92 | Three task sets per family: practice, gate (15 held-out post + retention pre), final audit (10, `tasks/audit/`, read by no loop component; `scripts/run_audit.py` once per claim, logged) | `amoeba/adapt/stream.py`, `scripts/run_audit.py`, `tasks/stream_m2*`, `tasks/audit/` | B |
| D93 | Diagnoser provenance: signals tagged observed (runner) or declared (model); alarms and the cause use observed ones, declared ones are supporting evidence | `amoeba/adapt/diagnoser.py`, `amoeba/adapt/monitor.py`, `amoeba/adapt/architect.py` | B |
| D94 | Rubric content checks: a required section passes only with a task-specific entity in its body; new tasks get 5–6 rubric items | `amoeba/task/models.py`, `amoeba/task/evaluate.py` | B |
| D95 | Evidence log: append-only hash-chained `events.jsonl` written by the harness with run-folder manifests, `scripts/verify_evidence.py`, key-scanned ship queue to a versioned, retention-locked bucket (uploader after the bucket set-up), no cloud credentials for agents | `amoeba/adapt/evidence.py`, `scripts/verify_evidence.py`, `amoeba/adapt/loop.py` | B |
| D95a | Evidence shipped to the repository's orphan `evidence` branch: key-scanned runs and new event rows, batched commits (≤ 1 per 10 min) carrying the chain head, fast-forward pushes with retry, `verify_evidence --branch`; GCS uploader kept, disabled | `amoeba/adapt/evidence.py`, `scripts/verify_evidence.py`, `scripts/run_loop.py`, `scripts/run_experiment.py` | B |
| D96 | Out-of-process sandbox for agent tools: a fresh NVIDIA OpenShell sandbox per run (no network, only the sandbox workspace writable, skills and hooks read-only, no secrets, limits), every decision logged into events.jsonl | `amoeba/localtools/sandbox.py`, `amoeba/localtools/toolbox.py`, `amoeba/localtools/gate.py`, `amoeba/config/sandbox/` | B |
| D96a | Sandbox is the default with --local-tools on (--local-tools-mode inprocess only on request, with AMOEBA_SANDBOX=1); 300 s per command; live probe: the agent cannot reach the gateway API | `scripts/run_task.py`, `amoeba/localtools/toolbox.py`, `amoeba/config/localtools.yaml` | v1 |
| D97 | Per-call model router (plain code): registry (Gemma 4 31B only), fixed-order decision with hard filters, shared per-model rate buckets, cooldown and fallback, verifier independence required/preferred/off, modes fixed/role/routed, every decision logged, USD | `amoeba/llm/router.py`, `amoeba/config/models.yaml`, `amoeba/interp/trace.py`, `scripts/run_task.py` | v1 |
| D98 | Routing preference as a recipe edit (`prefer_model {role, model}`), built and off (`--allow-model-edits`); only for causes max_turns/checks/capability; never bypasses the allowlist or hard filters; V6; Gate on gain and USD | `amoeba/adapt/recipe.py`, `amoeba/config/adapt.yaml`, `amoeba/adapt/diagnoser.py`, `scripts/run_loop.py`, `scripts/run_experiment.py` | v1 |
| D99 | Memory, three kinds: recipe lines with provenance (Gate-only writes); user `standards:` proposed by the loop (≥3 runs, ≥2 families) and approved only by the user (`scripts/approve_memory.py`, logged); event memory = evidence log; Box 1/2 read approved standards; agents write none | `amoeba/memory/context.py`, `amoeba/memory/recipes.py`, `amoeba/adapt/recipe.py`, `amoeba/adapt/loop.py`, `scripts/approve_memory.py`, `scripts/run_task.py` | v1 |
| D100 | Recipe expiry: retention replay of the pre-shift gate tasks every N=12 practice tasks of a family (drop beyond noise → `retention` alarm now); pruning of each recipe line on the gate set at stream end and on demand (`scripts/prune_recipe.py`), each prune a Gate decision outside the quota | `amoeba/adapt/retention.py`, `amoeba/adapt/gate.py`, `amoeba/adapt/experimenter.py`, `amoeba/adapt/loop.py`, `scripts/run_loop.py`, `scripts/prune_recipe.py` | v1 |
| D101 | Task family for free-text tasks: keyword rules (`config/families.yaml`), else one routed `family_classifier` call validated against the list or "new"; a known family starts from its recipe (`--recipes`, `--recipes-from`), "new" empty; result.json `family` | `amoeba/task/interpret.py`, `amoeba/config/families.yaml`, `scripts/run_task.py` | v1 |
| D102 | Niche profiles `profiles/<niche>.yaml` (`general` = today exactly, `calc`): allowed tools + sandbox limits, allowed models + verifier independence, domain rules/vocabulary, done clauses, domain checks (`amoeba/checks/`), safety limits; one Environment section in Box 1/2 prompts; Box 3 refuses tools outside the profile (logged), the router models outside it | `amoeba/config/niche.py`, `amoeba/checks/`, `profiles/`, `amoeba/interp/runtime.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D111 | `status` in result.json (ok / agent_error / infra_error); infra-error runs retried (max 2) by the Experimenter and the loop, then left out of pairs (`excluded`), the Monitor and Gate rule 5b; proxy read fresh from `AMOEBA_PROXY_FILE` on a dropped connection | `amoeba/task/models.py`, `amoeba/adapt/experimenter.py`, `amoeba/adapt/gate.py`, `amoeba/adapt/monitor.py`, `amoeba/adapt/loop.py`, `amoeba/config/proxy.py`, `amoeba/llm/client.py`, `amoeba/config/adapt.yaml` | v1 |
| D109 | Verifier blind result vs worker figures by label (rubric tolerance): a disagreement → step `disputed`, one rework with both values, still there → partial + both values in Limitations; PASS never overrides it (`--disputes`, default on) | `amoeba/interp/disputes.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D105 | `no_deliverable` status: a plan run with no answer content, or that never made a file its plan promised (local tools on), ends `error: no_deliverable: …`; result.json `deliverables` (`--deliverable-check`, default on, plan only) | `amoeba/task/deliverables.py`, `amoeba/task/models.py`, `scripts/run_task.py` | v1 |
| D103 | Sandbox skills: `attach_skill` maps a baked-in skill to /opt/skills/<path> via the entry's root folder (the `root` field is a label); sandbox Bash may name /opt/skills (read-only) so a skill's scripts run; live attach-and-use test | `amoeba/localtools/skills.py`, `amoeba/localtools/toolbox.py`, `amoeba/localtools/gate.py` | v1 |
| D106 | Research steps (plan, web tools): packed queries split (quoted queries, places, years; ≤ 4), the top 3 results of each read by code (official domains first, excerpts), linked .csv/.xlsx/.json files fetched and parsed into tables with their own [S#]; step note: one entity/year/series per search (`--research`, default on) | `amoeba/tools/research.py`, `amoeba/tools/web.py`, `amoeba/llm/cache.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D107 | Fetched pages and data tables saved read-only in the workspace under sources/ (CSV / text, `index.json` with [S#], url, time), uploaded into the sandbox; never counted as made files; writes refused; step note (`--workspace-sources`, default on) | `amoeba/localtools/toolbox.py`, `amoeba/localtools/sandbox.py`, `amoeba/localtools/gate.py`, `amoeba/tools/web.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D108 | Re-plan method check: a step a re-plan adds or rewrites for a failed step must state a different tool, source type, site or a split query, else the decision is rejected and logged; the observer is shown each failed step's tools, sources and queries (`--replan-method`, default on) | `amoeba/interp/replan_method.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D110 | Dated figures: every web-sourced figure in the final answer must carry its source's date (line or source entry); undated → the answer step's refine turn, then listed in Limitations (`--dated-figures`, default on) | `amoeba/interp/dates.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D104 | Citation check skips in-line arithmetic: calculation results (after = / ≈), powers and year ranges are not claims; operands still checked (`--cite-arithmetic`, default on) | `amoeba/interp/citecheck.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D112 | Python sent to local:Bash (```python block, or a first line that starts like Python) runs as `python3 - <<'AMOEBA_PY'`; logged; still screened by the gate (localtools.yaml `bash_python`, default true) | `amoeba/localtools/toolbox.py`, `amoeba/config/localtools.yaml` | v1 |
| D113 | Spreadsheet checks: after a step that made an .xlsx, typed totals and typed derived cells (row/column sums, products of row cells) fail `domain_xlsx_formulas` with the cell names and earn the retry turn; task numbers are inputs (`--xlsx-formulas`, default on) | `amoeba/checks/xlsx_formulas.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |

**Stage A (done Oct 2: D78–D84, calibration, h1/h2).** The mock-LLM tests in §14 pass. The hand-edit check ran on
Gemma on the held-out post slice hpost-1..5 of `stream_m1`: a calibration row (noise 0.000), the useless hand edit
(revoke `calc` from all roles) rejected (no gain), and the helpful hand edit (a planner rule meeting the new
requirement) rejected by Gate v1's rule 5 (+0.267 gain; see D84b). Found and fixed on the way: D80a, D84a. Report:
`docs/eval/loop_m1/WEEK1.md`.

**Stage B (Oct 3–4: D84b, fresh held-out slice, D85–D89, milestone).** Gate v2 (D84b) and the open harness item
(D84c); a fresh held-out post slice hpost-6..10 (approved before use, frozen after; the milestone uses only it for
post-shift testing, the 3 held-out pre tasks stay for retention); D85–D89; M-P2 (§11) on Gemma with no hand edits:
the Architect proposes and Gate v2 decides; `docs/eval/loop_m1/REPORT.md`. Amoeba only: the baselines are not run or
changed before the benchmark stage.

**Code freeze** for the benchmark: when the milestone report is written (target Oct 5). All three architectures are
then rerun with the frozen code.

---

## 14. Tests (mock LLM unless stated otherwise)

- `test_recipe_d81.py`: each edit is pure and versioned; V1–V5 each catch their case; an empty recipe leaves a draft
  byte-identical.
- `test_recipe_hook_d82.py`: the lessons reach the d24 prompts; the transforms change only the selected steps and
  roles; run options overlay the defaults; with `--drafts-from`, only transforms and run options apply.
- `test_stream_d80.py`: the shifts apply at the right order; held-out tasks never enter the practice loop; the
  feedback channel exposes item names only.
- `test_experimenter_d83.py`: transform edits run on the same saved draft in both arms; the arm-A cache is hit for a
  second hypothesis.
- `test_gate_d84.py`: synthetic pairs, so that each rule (§9.2, 1–6) rejects in its own case, and one clean accept;
  Bonferroni N counts since the last accept; the rollback triggers on a synthetic drop.
- `test_monitor_d85.py`, `test_diagnoser_d86.py`: run-record fixtures give the expected alarm and cause.
- `test_architect_d87.py`: invalid JSON is retried once; a disallowed edit, a repeat of a failed edit and a leaked
  held-out phrase are all refused.
- `test_loop_d89.py`: a mock stream with a scripted shift reaches accept → recipe v2 → recovery, end to end.

---

## 15. Cost and time (Gemma, about 10 minutes per run, 8 in parallel)

| Part | Runs | Wall time |
|---|---|---|
| Practice stream (16 tasks, one after another) | 16 | ~2.5 h |
| Noise-floor calibration (A vs A′, 15 pairs) | 30 | ~40 min |
| Each hypothesis (arm B only, after the cache) plus retention (3 × 3) | ~24 | ~30 min |
| Milestone total (2–3 hypotheses) | ~110 | ~5 h |

This fits in Stage B. It is also why every box is first tested with the mock LLM and on small slices.
