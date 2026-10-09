# Amoeba Phase 2 build spec: the adaptation loop (Boxes 4–9)

> **Superseded by D117 (Oct 6, 2026).** The offline learning loop this spec describes (task streams, Experimenter,
> Gate, Monitor, Diagnoser, Architect, recipe store, retention, pruning, user-memory proposals, ledger; §§3–11) was
> removed. Adaptation now happens inside one task: §17 is the current design (stuck watch, code fixes, the fix
> proposer, the --adapt comparison). §§12–16 (D90–D116) still describe current Box 1–3 behaviour. The rest is kept as
> history; nothing in it is built any more except what §17 says is kept.

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
- Classifying a free-text task's family in Box 1: done early, as D101 (§16.6). Stream tasks still carry their family.
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
| D109 | Disagreement resolver: verifier blind figures vs worker figures by label (rubric tolerance); each disagreement goes to one fresh resolver call (plan_resolve.txt) that settles it by source text or a re-run, writing value / evidence / verdict; plain code checks the evidence (quote in the source, or value in its own tool output); a settled value replaces the wrong one; unresolved → partial, never PASS, Limitations; every dispute and resolution logged (`--disputes`, default on) | `amoeba/interp/disputes.py`, `amoeba/config/prompts/plan_resolve.txt`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D105 | Final-answer requirement check (with D110): each Box 2 requirement against the FINAL answer (key terms, BLOCKED lines, files it asks for) and each promised file against the workspace; missing → one refine turn, then Limitations, and `no_deliverable` when a core deliverable is missing; `requirement_status` = the final-answer result (`--deliverable-check`, default on, plan only) | `amoeba/task/deliverables.py`, `amoeba/interp/plan_runner.py`, `amoeba/task/models.py`, `scripts/run_task.py` | v1 |
| D103 | Sandbox skills: `attach_skill` maps a baked-in skill to /opt/skills/<path> via the entry's root folder (the `root` field is a label); sandbox Bash may name /opt/skills (read-only) so a skill's scripts run; live attach-and-use test | `amoeba/localtools/skills.py`, `amoeba/localtools/toolbox.py`, `amoeba/localtools/gate.py` | v1 |
| D106 | Research steps (plan, web tools): packed queries split (quoted queries, places, years; ≤ 4), the top 3 results of each read by code (official domains first, excerpts), linked .csv/.xlsx/.json files fetched and parsed into tables with their own [S#]; step note: one entity/year/series per search (`--research`, default on) | `amoeba/tools/research.py`, `amoeba/tools/web.py`, `amoeba/llm/cache.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D107 | Fetched pages and data tables saved read-only in the workspace under sources/ (CSV / text, `index.json` with [S#], url, time), uploaded into the sandbox; never counted as made files; writes refused; step note (`--workspace-sources`, default on) | `amoeba/localtools/toolbox.py`, `amoeba/localtools/sandbox.py`, `amoeba/localtools/gate.py`, `amoeba/tools/web.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D108 | Re-plan method check: a step a re-plan adds or rewrites for a failed step must state a different tool, source type, site or a split query, else the decision is rejected and logged; the observer is shown each failed step's tools, sources and queries (`--replan-method`, default on) | `amoeba/interp/replan_method.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D110 | Dated figures, part of the final-answer requirement check (D105): every web-sourced figure in the final answer carries its source's date (line or source entry); undated → the shared refine turn, then Limitations (`--dated-figures`, default on) | `amoeba/interp/dates.py`, `amoeba/task/deliverables.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D104 | Citation check skips in-line arithmetic: calculation results (after = / ≈), powers and year ranges are not claims; operands still checked (`--cite-arithmetic`, default on) | `amoeba/interp/citecheck.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D112 | Python sent to local:Bash (```python block, or a first line that starts like Python) runs as `python3 - <<'AMOEBA_PY'`; logged; still screened by the gate (localtools.yaml `bash_python`, default true) | `amoeba/localtools/toolbox.py`, `amoeba/config/localtools.yaml` | v1 |
| D113 | Spreadsheet checks: after a step that made an .xlsx, typed totals and typed derived cells (row/column sums, products of row cells) fail `domain_xlsx_formulas` with the cell names and earn the retry turn; task numbers are inputs (`--xlsx-formulas`, default on) | `amoeba/checks/xlsx_formulas.py`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py` | v1 |
| D114 | `max_input_chars` (3000–20000) and `max_summary_input_chars` (15000–60000) whitelisted as recipe run options; the Diagnoser allows them for the checks / feedback causes; Gate-tested like any edit | `amoeba/config/adapt.yaml`, `amoeba/adapt/recipe.py`, `scripts/run_task.py` | v1 |
| D116 | Ask the user about every reading the interpretation step would only assume (a tie included), before planning; no terminal → stop with `needs_clarification` + `clarification.json`; `--clarify ENTITY=READING`; `--ask-assumed off` = D77; experiments pass off | `amoeba/task/interpret.py`, `scripts/run_task.py`, `amoeba/task/models.py`, `amoeba/config/adapt.yaml` | v1 |
| D117 | The offline learning loop is removed; in-task adaptation replaces it (Stage A: removal; B: stuck watch; C: code fixes; D: fix-proposer agent; E: `--adapt` test). Kept: contract causes, cause → edit table, single-edit format + V1–V6, event log. Stage B built: stuck signals, one diagnosed cause, logged; Stage C built: code fixes with limits and a stop report, new cause missing_input; Stage D built: the fix proposer as the last rung (§17) | `amoeba/adapt/` (stuck, fixes, proposer, recipe, architect, evidence), `amoeba/config/prompts/fix_proposer.txt`, `amoeba/pool/stock.py`, `amoeba/config/adapt.yaml`, `amoeba/interp/plan_runner.py`, `scripts/run_task.py`, `scripts/stuck_report.py` | v1 |

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
- D90–D114 (§16): `test_verify_first_d90.py`, `test_gate_v3_d91.py`, `test_infra_d111.py`, `test_disputes_d109.py`,
  `test_deliverables_d105.py`, `test_dated_figures_d110.py`, `test_skills_sandbox_d103.py` (live part with the
  gateway), `test_research_d106.py`, `test_workspace_sources_d107.py` (live part), `test_replan_method_d108.py`,
  `test_cite_arithmetic_d104.py`, `test_bash_python_d112.py` (live part), `test_xlsx_formulas_d113.py`,
  `test_run_options_d114.py`, and the D96–D102 files (`test_sandbox_d96.py`, `test_router_d97.py`,
  `test_prefer_model_d98.py`, `test_memory_d99.py`, `test_retention_d100.py`, `test_family_d101.py`,
  `test_niche_d102.py`).

---

## 15. Cost and time (Gemma, about 10 minutes per run, 8 in parallel)

| Part | Runs | Wall time |
|---|---|---|
| Practice stream (16 tasks, one after another) | 16 | ~2.5 h |
| Noise-floor calibration (A vs A′, 15 pairs) | 30 | ~40 min |
| Each hypothesis (arm B only, after the cache) plus retention (3 × 3) | ~24 | ~30 min |
| Milestone total (2–3 hypotheses) | ~110 | ~5 h |

This fits in Stage B. It is also why every box is first tested with the mock LLM and on small slices.

---

## 16. Final architecture and probe fixes (D90–D114)

This section documents what was added after the first milestone design (§1–§15), in the order it was built. The
§13 table has one row for each. The rule is the same throughout: the AI proposes, plain code decides. Every feature
sits behind a flag; it is on by default for Amoeba's plan runner and off for the baselines (`flat`,
`boss_reviewers`), which stay unchanged.

### 16.1 Research review (D90–D95, Oct 3, 2026)

- **D90, the verifier answers first.** A verify step first works out its own result from the checked steps' inputs
  and its tools, in a fresh turn loop that never sees their outputs (`plan_verify_own.txt`). Only then are the outputs
  shown. Both sides and plain code's figure comparison (`compare_figures`: matched, own_only) go into `step_N.json`.
  Flag: `--verify-first`.
- **D91, Gate v3.** §9.2. Rule 2 on per-task means, a permutation test at a fixed per-family hypothesis quota, no
  prediction rule.
- **D92, three task sets per family.** Practice tasks feed the loop. A gate set of 15 held-out tasks (plus the
  pre-shift ones) feeds the Gate. An audit set is used only for the final report.
- **D93, observed against declared signals.** The Diagnoser counts a cause only when plain code observed it (a tool
  call, a check, a file). A cause only the model's own words support is kept apart as `declared`.
- **D94, rubric content checks.** A required section passes only if its body names one of the task's own entities;
  an empty heading fails.
- **D95, evidence.** One append-only, hash-chained `events.jsonl`, written only by the harness. Finished runs are
  key-scanned and shipped to the repository's orphan `evidence` branch (D95a). Agents never get git credentials.

### 16.2 Final architecture (D96–D102, Oct 4)

- **D96/D96a, sandbox.** Agent tools run in a fresh NVIDIA OpenShell sandbox per run: no network, Landlock, no
  secrets, one CPU, 1 GiB, 300 s per command, one hour per run. The harness gate refuses what it can see first.
  Sandbox mode is the default with `--local-tools on`.
- **D97, model router.** A per-call router over a registry (Gemma 4 31B only for now): allowed and available models,
  hard filters, choice, cooldowns, shared per-model rate buckets, USD per call.
- **D98, `prefer_model`.** A routing preference as a recipe edit. Built and off (`--allow-model-edits`).
- **D99, memory of three kinds.** Recipe lines carry provenance (written only by a Gate accept). User standards are
  proposed by the loop (three runs or more, two families or more) and approved only by the user
  (`scripts/approve_memory.py`).
- **D100, recipe expiry.** A retention replay of the pre-shift gate tasks every 12 practice tasks raises a
  `retention` alarm on a drop beyond noise. Pruning removes a recipe line when removing it loses nothing and saves
  cost; a prune is a Gate decision outside the hypothesis quota.
- **D101, task family.** Keyword rules first, then one routed classifier call checked against the list or "new". A
  known family starts from its current recipe.
- **D102, niche profiles.** `profiles/<niche>.yaml`: allowed tools and sandbox limits, models, domain rules, done
  clauses, domain checks (`amoeba/checks/`), safety limits. `general` changes nothing.

### 16.3 Probe fixes, batch 1: correctness (Oct 5)

From the hard probe (`docs/eval/probe_hard/REPORT.md`, problems 1–11).

- **D111, infrastructure errors.** `result.json` records `status`: `ok`, `agent_error`, `infra_error` or
  `no_deliverable`. An infra error is the model service after its retries, a connection or proxy failure, a cache miss
  or no result; a 400/413/422 is the team's. The Experimenter and the loop retry it, at most twice
  (`adapt.yaml infra.retries`). Still infra, it is left out of the pairs (`experiment.json excluded`), the Monitor and
  Gate rule 5b, which counts agent errors only. On a dropped connection the client re-reads the proxy from
  `AMOEBA_PROXY_FILE` and reconnects; each new run starts with the fresh proxy.
- **D109, the disagreement resolver** (amended, §16.5). Plain code compares the verifier's blind figures with the
  worker's by label, at the rubric's tolerance. Each disagreement goes to one fresh resolver call that settles it by
  the source text or a re-run. Code checks the evidence. A settled value replaces the wrong one; an unresolved one
  keeps the step from PASS and goes into Limitations.
- **D105, the final-answer requirement check** (amended together with D110, §16.5).
- **D103, skills in the sandbox.** `attach_skill` treated the root label as a path, so every skill was refused. A
  skill of the baked-in clone now maps to `/opt/skills/<path>`, and sandbox Bash may name that read-only root so the
  skill's scripts run.

### 16.4 Probe fixes, batch 2: capability (Oct 5)

- **D106, research steps.** Plain code splits a packed web search (several quoted queries, places or years; at most
  four). It reads the top three results of each, official domains first, and parses the data files (.csv, .xlsx,
  .json) a read page links into tables with their own [S#]. The step note asks for one entity, year or series per
  search. Flag: `--research`.
- **D107, fetched data in the workspace.** Every page and table read is saved read-only under `sources/` in the
  run's workspace and uploaded into the sandbox, with `sources/index.json` (source id, url, time). Writes there are
  refused; the files never count as made. Flag: `--workspace-sources`.
- **D108, re-plans change the method.** A step a re-plan adds or rewrites for a failed step must state a different
  tool, source type, site or a split query; otherwise the decision is rejected and logged. The observer is shown how
  each failed step worked. Flag: `--replan-method`.
- **D110, dates on web figures** (part of the final-answer check, §16.5). Flag: `--dated-figures`.
- **D104, citation check and arithmetic.** A calculation's result shown on the line, a power and a year range are
  not claims of their own; the operands are still checked. Flag: `--cite-arithmetic`.
- **D112, Python sent to Bash** runs with `python3` from a quoted heredoc; the gate still screens it
  (`localtools.yaml bash_python`).
- **D113, spreadsheet checks.** After a step that made a workbook, typed totals and typed derived cells fail the step
  check with the cell names. Flag: `--xlsx-formulas`.

### 16.5 Amendments of Oct 5, 2026 (review of two papers: VeriHarness and ScholarEvolve)

1. **D109 is a disagreement resolver**, not a rework of the worker. When code finds a figure where the worker and the
   blind verifier differ beyond the rubric's tolerance, one separate, fresh call (`plan_resolve.txt`) has only one
   job: settle each disputed figure against the fetched source text, a fetch, a calculation or a re-run in the
   sandbox. It records value, evidence (a quote or a command and its output) and verdict per figure. Plain code
   accepts a value only when its quote is in the source and states it, or the value is in the resolver's own tool
   output. A step with an unresolved difference is never PASS (it is partial; a PASS is recorded as `DISPUTED`). The
   resolved value replaces the wrong one in the producer's output; unresolved ones go to Limitations. Every dispute
   and resolution is logged (`disputed`, `dispute_resolution`).
2. **D105 and D110 are one final-answer requirement check**; both D-numbers are kept. After the summariser, code
   checks each requirement from Box 2's list (D24) against the FINAL answer, each promised file against the
   workspace, and that every web figure carries its date. Missing items earn one refine turn. Then the run ends
   `no_deliverable` when a core deliverable is missing (no answer content, a promised file never made, more than half
   of the requirements unmet), or the items are listed in Limitations. `requirement_status` records the final-answer
   result, not the steps' claims.
3. **D114, context size as recipe run options.** `max_input_chars` (3,000–20,000) and `max_summary_input_chars`
   (15,000–60,000) are whitelisted run options with ranges in `adapt.yaml`, so the loop can tune context size. The
   Diagnoser allows them for the checks and feedback causes; the Gate tests them like any edit.

**Not now (Paper 2).** These were considered and deferred:

- a consensus challenger: later, as its own Gate-tested change, with code checks first (units, currency, period,
  dates);
- multiple runs per task;
- a research-guided Architect;
- combined edits (more than one edit per hypothesis);
- episode memory.

### 16.6 User request of Oct 6, 2026

**D116, ask before assuming.** When the interpretation step (D77) would only assume a reading (no reading leads the
next by 0.3, a tie included), the user is asked first: every such entity, least certain first, one multiple-choice
question each, through `--interactive` or the terminal. With nobody to ask, the run stops before Box 2 with
`needs_clarification` and writes `clarification.json`; `--clarify ENTITY=READING` answers ahead of time. On by default
from the CLI (`--ask-assumed on`); experiment, loop and audit runs pass `off` (no one answers there), so a paused
M-P2 resumes with its configuration unchanged.

## 17. Change of direction: in-task adaptation (D117, Oct 6, 2026)

**Goal.** Drop the offline learning loop (§§3–11 above are history). Adaptation now happens inside a single task: when
a Box 3 step gets stuck, plain code (and, only when code fixes fail, a small fix-proposer agent) changes the planned
team using that run's own logs, results and errors, so the task can still finish. Nothing carries over between tasks.

**Stage A, removal (done).** Removed: task streams, Experimenter, Gate statistics, calibration, retention replay,
pruning, recipe memory (`memory/recipes.py`, `--recipes`, `--recipes-from`), user-memory proposals
(`approve_memory.py`), the human queue, the ledger, the Monitor, the loop's Diagnoser, the Architect's proposal loop,
`run_loop` and `run_experiment`. Kept and reused: the step-contract causes (stuck signals), the cause → allowed-edit
table in `adapt.yaml`, the Architect's single-edit JSON format and V1–V6 validation (both removed later, see the
D117 cleanup note at the end of this section), the hash-chained event log and the evidence branch.

**Stage B, watch and diagnose (code only).** After each Box 3 step attempt, plain code marks the step STUCK when the
same error appears twice in a row, checks still fail after the retries, max turns was reached, a requested capability
or skill is unfilled, or no output file changed between attempts. Diagnosis picks one cause with the kept table. Every
stuck event (step, cause, evidence lines) goes to the event log. Counts per cause from existing runs are reported
before Stage C.

*As built (B).* `amoeba/adapt/stuck.py`: `step_signals(meta, previous, unfilled, files_unchanged)` returns the
signals of one attempt — `repeated_error` (two failed tool calls in a row with the same tool and the same error once
digits are masked) → cause `tool_error` (new, after `capability` in `diagnoser.causes`; allowed edits add_role_rule,
grant_tool, set_run_option:max_turns); `checks_after_retry` → `checks`; `max_turns` → `max_turns`;
`capability_unfilled` (a BLOCKED or undeclared capability, or an unfilled request for one of the step's roles) →
`capability`; `no_file_change` (the step owes a file — claimed but missing, a file type in its output line and none
made, a failed spreadsheet check — and its files did not change across the refine turn or between two attempts) →
`claimed_file_missing`. `is_stuck`: the step did not end `done` and a signal holds. `diagnose`: the first cause in the
table order, its allowed edits (prefer_model only with model edits on), at most eight evidence lines. The plan runner
calls it after each attempt (`PlanRunner.watch`) when `PlanOptions.adapt == "on"` (`--adapt`, CLI default on;
library default off) and writes `meta["stuck"]`, a `stuck` trace event, a `stuck` row in `<run>/events.jsonl`
(hash-chained) and `result.json` `stuck`. `scripts/stuck_report.py` applies the same functions to stored run folders
(attempt before = `step_N.first.json`; unfilled requests from `capability_requests.json`). Counts over 618 stored
runs: `docs/eval/d117_stage_b/STUCK_COUNTS.md`. Tests: tests/test_stuck_d117.py.

*User changes to Stage C (Oct 6).* (1) A new cause `missing_input`, separate from capability: the step lacks data
an earlier step should have given; mixed cases are fixed for it first, then re-checked for capability. (2) Its code
fix: a. the upstream step is done and its output holds the data → add the dependency / pass the artifact, re-run only
the stuck step; b. the upstream output lacks it → re-run that upstream step once with the missing item added to its
done_when, then the stuck step — the only exception to "never redo completed steps", counted toward the per-step and
per-task limits. (3) Rung 2 needs the pool reachable: with the pool and local tools off it is skipped and logged
"capability fix unavailable: pool off". (4) Mislabelled citations stay out of the stuck signals.

*As built (C).* `classify_lacked` (amoeba/adapt/stuck.py) tells a missing input from a capability: a tool word in the
label → capability; a step, input, output, data or file named in the label, a step named in its explanation, another
step's role, or ≥ 50% of an earlier step's planned output words → missing input, with the upstream step(s) named,
else the role's, else the best-matching dependency. D63's "MISSING INPUT:" lines count too. `diagnoser.causes` is
now missing_input, capability, tool_error, checks, max_turns, …; missing_input allows add_dependency, rerun_upstream
and set_run_option:max_input_chars. Checks that fail because the helpers ran out of turns are max_turns, not checks.
`amoeba/adapt/fixes.py` `candidates(d, n, ctx)` lists the fixes, cheapest first, each one an edit the table allows
for the cause: missing_input → add_dependency (mode added, or passed_in_full when it is already a dependency: no cap
on that input and a note naming the item) when the upstream step is done and holds ≥ 60% of the item's own words,
rerun_upstream otherwise (once per upstream step per task); tool_error and max_turns → max_turns + 3; checks →
check_retry_turns + 1, then max_input_chars × 2 when an input was shortened (all within `recipe.run_options`);
capability → grant_tool (rung 2). `PlanRunner.fix_stuck` runs after each step of the wave loop with `--adapt on`:
it applies the first candidate not tried before in the task (`fix_key`), keeps the replaced attempt as
step_N.tryK.md/.json, re-runs only the stuck step (`run_step(…, fixing=…)`, recorded as `fix_of`) and re-checks it;
success = the step ends done (its checks and contract pass). Rung 2 (`attach_missing`): a lacked tool the run's
registry has is granted; anything else goes through the toolbox step (`stock_toolbox(…, code_pick=True,
exclude=…)`): the first vetted candidate of the shortlist not given before, no AI pick. Limits (`adapt` in
adapt.yaml): 3 fixes per step, 8 per task, 200,000 tokens and $1 (when the model has a price) of fix attempts per
task, checked before each fix. When the step is still stuck and no fix is left, the task stops
(`stop_when_exhausted`; set to false by the user on Oct 6 until Stage D makes the fix proposer the last rung): the run's answer and `<run>/adapt_report.md` say what was stuck, the cause, the evidence,
each fix tried with its tokens and why it failed, the rungs not tried, and the steps finished; the run status is
`stuck`. Every fix, skip and stop is a trace event and a row in `<run>/events.jsonl`; `result.json` `adaptation`
holds the fixes, recovered steps, tokens and cost. Fixes run only in the wave loop (not inside D34 rework or D39
re-runs). Steps that used an upstream output before its re-run are not redone (listed as `left_on_old_output`).
Re-count of stored runs with these rules: `docs/eval/d117_stage_b/STUCK_COUNTS.md`. Tests: tests/test_fixes_d117.py.

*User changes to Stage D (Oct 6).* `stop_when_exhausted` was set to false after Stage C and turned back on with
Stage D, so the fix proposer is the last rung before stopping. The proposer is called only after the code fixes for
the step are used up or not allowed ("capability fix unavailable: pool off" included). Its input is kept small; its
output is exactly one JSON edit with a short reason: add_role_rule, add_helper_role (the Planner's role-card schema),
grant_tool (only tools available in this run), split_step (2–3 sub-steps, a valid step graph), replan_remaining
(replacement steps for the part not done, the Planner's plan format) or work_around (capability only: another
method or a narrower done_when, stated in the final answer under Limitations). Code checks: allowed for the cause,
schema, size, wording and tools, the plan graph, never redo done steps, not a repeat; one retry on an invalid reply, a second failure
is no fix; all limits apply. After Stage D the final report and the answer list the steps that used an upstream
output from before a case-b re-run.

*As built (D).* `amoeba/adapt/proposer.py`: `FixReply` (strict: `edit` {op, params} and `reason` ≤ 300 characters),
one params model per op, `parse_fix`, `fix_problems` — allowed for the cause, work_around for capability only, size
(a rule, goal or done_when ≤ 300 characters, a role prompt ≤ 1,500, a sub-step's text ≤ 600), wording (the
denylist), tools (a granted tool or a new helper's tool is in this run's registry, acts nowhere outside, is not
paid), the role is one of the stuck step's, not a repeat (`FixEdit.key`). Prompt:
`amoeba/config/prompts/fix_proposer.txt` (ours). `PlanRunner.propose_fix` is the rung after `candidates` is empty:
it calls the proposer (agent `fix_proposer`, router role planner, 2,048 reply tokens) with the task (≤ 1,500
characters), the step's card (text, roles, depends_on, do, output, done_when), the cause and evidence, the last
attempt (status, turns, lacked, the last five failed tool calls and up to ten checks, each trimmed to 150
characters), the team (one line per role), the run's tools and skills, the allowed edits (only the proposer's ops,
with their shapes) and the fixes tried in the task; on an invalid reply it asks once more with plain code's
refusal. `_d_live` adds the live checks: a new helper's card is complete, its name new, the team within
`max_agents` (V5); a split names roles on the team, keeps the summariser last when the stuck step writes the answer,
stays within D63's added-step cap and leaves a usable graph; a re-plan goes through D63's `validate_decision` with
the stuck step reopened (done steps cannot change, the answer step cannot be dropped, the graph must be usable).
Applying: a rule joins the role's constraints (its card); a tool joins its tools; a helper joins the step (first
with `lead`); a work-around narrows done_when and tells the helpers to write "NOT NEEDED: <capability> — worked
around"; these re-run the step and succeed when it ends done. A split or a re-plan goes through D63's
`apply_decision` (plan.vN.json): the stuck attempt is kept as step_N.tryK and reopened, the wave loop recomputes the
waves, and the fix counts as recovered when every replacement step ends done. The proposer's tokens count toward the
adaptation caps, and each call toward the fixes per step and per task. The answer's Limitations (plain code) gets
"WORKED AROUND: …" for each accepted work-around and "OLD INPUT: step k used step u's output from before step u was
re-run …" for each step left on an old upstream output; `adapt_report.md` is written for every run with a stuck step
(each step, its fixes and results, rungs not tried, work-arounds, old-input steps, tokens) and is the answer when
the task stops. The cause table now lists the proposer's edits per cause (capability: add_helper_role, work_around,
split_step, replan_remaining with grant_tool; missing_input: add_role_rule, split_step, replan_remaining; tool_error:
add_helper_role, replan_remaining; checks: split_step, add_helper_role; max_turns: split_step, add_role_rule;
claimed_file_missing: grant_tool, split_step). Tests: tests/test_proposer_d117.py (15, mock LLM).

*User changes before Stage E (Oct 6).* (1) work_around is allowed only after a grant_tool or an add_helper_role was
tried for that step (code rung 2 or the proposer): until then it is not offered and is refused if proposed. A step it
finishes is reported as "finished with limitation" (`adaptation.finished_with_limitation_steps`), never as
recovered. (2) The proposer adds at most two helpers per task (`adapt.max_added_helpers: 2`); after that
add_helper_role is not offered and is refused. Tests: tests/test_proposer_d117.py (17).

**Stage C, code fixes (no AI), cheapest first.** (1) more turns, more retry turns or a larger input; (2) attach the
missing tool or skill from the pool shortlist. Apply, re-run only the stuck step, re-check.

**Stage D, fix-proposer agent.** Used only when the code fixes fail. It sees the stuck step, its logs and errors, the
current team, the edits allowed for the cause and the fixes already tried in this task, and returns exactly one JSON
edit: add_role_rule | add_helper_role | grant_tool | split_step | replan_remaining. Code validates it (size, wording and tools,
allowed for the cause, not a repeat), applies it to the live plan and re-runs the step. Success = the step contract passes
(done_when + checks); no rubric.

**Limits (code-enforced, configurable).** At most 3 fixes per step and a cap per task; a token/dollar cap for
adaptation per task; completed steps are never redone; a failed fix is never repeated; when all fail, the task stops
with a report for the user (what was stuck, the cause, each fix tried, why each failed).

**Stage E, test.** `--adapt on|off` (default on); the same tasks with it off and on (H1–H3 and tasks that failed
before): tasks finished, stuck steps recovered, extra tokens and cost per task.

**D117 cleanup (Oct 8).** The pieces of the loop Stage A had kept but the runtime never called are removed:
`amoeba/adapt/recipe.py` (Recipe, Edit, the edit menu, transforms and the V1–V6 validator), `amoeba/adapt/architect.py`
(the Architect's single-edit format and checks), the D98 `prefer_model` edit and D114's recipe run options as recipe
edits (the run options stay as code fixes), and their tests. `adapt_config()` and the answer-step helper moved to
`amoeba/adapt/config.py`. V1–V6 are no longer claimed for adaptation: the proposer's own checks — a rule, goal or done_when at most 300 characters (adapt.yaml `limits`), no denylisted wording, and only tools available in this run that act nowhere outside it and are not paid — live in `amoeba/adapt/proposer.py` (formerly V1, V3 and V4), and the
team-size and step-graph checks in `PlanRunner.propose_fix`. In `adapt.yaml` the `recipe:` section is renamed
`limits:`, and `diagnoser.allowed_edits` lists only edits a code fix or the proposer can apply; the causes feedback,
honesty and unused_tool are gone (no stuck signal maps to them). `amoeba/config/validate.py`'s V1–V6 are Phase 1's
TeamConfig checks and unrelated.

**D119, fault injection (test-only, Oct 9).** `--inject-fault <cause>:<step>[:<n>]` puts one known fault into one step
so the diagnosis and the fixes can be checked against a ground truth: tool_error, capability, missing_input,
missing_input_b, max_turns, checks (`amoeba/adapt/faults.py`; the table of what each does, its expected diagnosis and
first fix is in the README). Refused unless `AMOEBA_TEST_FAULTS=1`; it fires the same way with `--adapt off` and on;
`result.json` `faults`. The Stage E pilot adds three injected pairs on H1 (capability, missing_input, tool_error), both
arms reusing the clean off run's draft (`docs/eval/stage_e/PLAN.md`).
