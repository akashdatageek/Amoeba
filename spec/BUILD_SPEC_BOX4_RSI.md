# Amoeba build spec — Box 4 recursion, lesson library and the outer RSI loop (Oct 2026)

Source paper: Harness² (Xu et al., Google, arXiv 2610.14224, Oct 2026).
Code read: `akashdatageek/amoeba` at `c1db176` (21 Oct 2026).
Decisions D161–D166 (the repo's last was D160).

**Amended on 21 Oct 2026, when it was added to the repo.** The build prompt wins over the first draft of this spec:
- the decision numbers are D161 (stage 0) to D166 (stage 5);
- the verdict rules and the stage 0 scope follow the prompt;
- **everything is general, with no niche.** The first draft built the judge, the library and the outer loop around
  a crop-analysis niche. The user decided not to pick a niche here.
  - The library is shared by every task.
  - The scorer can be swapped per task, and only a deterministic stand-in exists for now.
  - The outer loop changes general settings only.

The first draft was the file attached to the build prompt; only this amended version is kept in the repo.

## In plain words

Box 4 already does the paper's main trick, at the level of one stuck step. When a step gets stuck, two helpers each
suggest one fix. "How the team works" (INV) suggests one, and "what an expert would know" (DOM) suggests the other.
Each fix is tried from the same saved starting point. Plain code keeps the better one and undoes the other.

What Box 4 does not do yet:
1. It never **combines** two fixes that each solved part of the problem.
2. It **forgets** everything when the task ends. No notebook carries over to the next task.
3. The Planner (Box 2) never **reads** what earlier tasks learned.
4. There is no **outer loop** that turns repeated lessons into a change to Amoeba itself.
5. There is no **frozen judge**: no fixed, hashed set of judging files and no task score to say whether a change made
   results better.

The build adds these in this order:

```
 [0] frozen judge (hashed judge files + a pluggable task scorer)     D161
        │
        ▼
 [1] Box 4 writes a record of every round                            D162  ← the data exists, just save it
        │
        ▼
 [2] verdicts + reflector + lesson library                           D163  ← the notebook
        │
        ▼
 [3] Box 2 and Box 4 read the library                                D164  ← the next task starts smarter
        │
        ▼
 [4] compose: try both fixes together                                D165  ← when each fixed a different part
        │
        ▼
 [5] outer loop: repeated lesson → general config change             D166  ← tested on frozen replay tasks
```

## How the paper maps onto the current code

| Harness² piece | Amoeba today | File | Gap |
|---|---|---|---|
| Execution harness (8 files) | the team + plan: role cards, rules, tool grants, tool guidance, watch rules, helpers, steps | `team.yaml`, `plan.json`, runner state | none |
| Reference execution | the stuck attempt of the step | `amoeba/interp/plan_runner.py` | only stuck steps, not finished ones |
| Propose (INV + DOM) | two scoped proposers | `amoeba/adapt/probe.py` `propose`, prompts `fix_proposer_inv.txt`, `fix_proposer_dom.txt` | none |
| "Cite a trajectory moment" | `because` must quote the evidence word for word | `amoeba/adapt/proposer.py` `quote_found` | none |
| Probe under matched conditions | `Snapshot` → apply → re-run → diff signals → undo | `amoeba/adapt/probe.py` `probe` | none (falls back to single in sandbox mode) |
| Compose | not done: "the two edits are never merged" | `probe.py` `pick` | **add** (D165) |
| KEEP_BASE | "neither cleared a signal: the original state is kept" | `probe.py` `pick` | none |
| Blind LLM selector | `pick` is plain code; `--fix-pick llm` is ablation only | `probe.py` | already better than the paper |
| Reflector | none | — | **add** (D163) |
| Improvement library | none for edits; only `ToolLibrary` for written tools | `amoeba/adapt/toolmaker.py` | **add** (D163) |
| Library read by Propose | none | — | **add** (D164) |
| Frozen evaluator | step checks, contract, quality checks; no task score for open tasks | `amoeba/task/quality.py`, `amoeba/checks/`, `amoeba/task/evaluate.py` | **add** the judge hash and a scorer slot (D161) |
| Replay suite | Stage E pair runner, `--drafts-from`, `--llm-cache`, `--picks-file` | `scripts/stage_e.py`, `scripts/run_task.py` | reuse, with a config arm (D166) |

## D161 (stage 0) — the frozen judge and the scorer slot

Why first: every later stage needs a number that says "better" or "worse", and none of the parts being edited may
be able to change that number.

1. **Frozen surface.** `amoeba/config/frozen.yaml` lists every judge file:
   - `amoeba/checks/`, `amoeba/task/quality.py` and `amoeba/task/evaluate.py`;
   - `amoeba/eval/` (the scorers);
   - the baseline result files (`data/baselines/`).

   At the start of each run, plain code hashes them (reusing `manifest_entries` and `sha256_text` in
   `amoeba/adapt/evidence.py`) and records the hash in `result.json`. A comparison of runs whose judge hashes differ
   is refused.
2. **Task score** `amoeba/eval/sim_score.py`: a `SimScorer` interface.
   - Its input is the run folder, the task's `sim` config and a seed.
   - It writes `sim_score.json` next to `result.json`, holding the score, the baseline score on the same seed, the
     delta, the seed, the scorer and the judge hash.
   - The scorer is picked per task (the task's `sim.scorer` field).
   - Only a deterministic stand-in exists now. It scores the answer's first number against `sim.expected`, so tests
     and toy runs have a score.
   - A real simulator becomes one more scorer later.
3. **Task sets.** Tasks may carry `set: stream | replay`. The **stream** set is used for learning. The **replay** set
   is never learned from and is used only by D166. `tasks/general_example.jsonl` holds small toy tasks of both sets.
4. `run_task --sim-seed N` (default: `--seed`).

Done when: a toy run writes `sim_score.json` with the same score twice for the same seed, and changing a frozen file
changes the hash and makes the comparison refuse.

## D162 (stage 1) — Box 4 saves a full record of each round

`probe.py` already builds, for each round, the candidates, their probes (`cleared`, `kept`, `new` signals, status,
tokens) and the pick. `finish()` writes these to the trace.

Add: write each round to `<run>/rounds.jsonl` and to the hash-chained `events.jsonl` (`EvidenceLog.append`, event
`round`). Each row includes:
- the task id, the niche (`general` unless a profile is chosen; recorded, never used to split) and the cause;
- each edit with its scope and its `because` quote;
- each probe's result;
- the pick and its reason;
- the step's final status.

The single-proposer rung is recorded in the same format, with one probe. A closing `run_end` row carries the run's
`sim_score` when the task has a scorer.

There is no model call and no behaviour change. Done when: a toy run with an injected fault (`--inject-fault`)
writes a round row that matches the trace.

## D163 (stage 2) — verdicts, reflector and the lesson library

**Verdicts are made by plain code, not by an LLM**, one per edit per round:

| Verdict | Rule (plain code, `amoeba/adapt/lessons.py`) |
|---|---|
| helped | the probe ended `done`, or it cleared at least one signal and added none |
| hurt | it added a new signal and cleared none |
| no_effect | nothing cleared, nothing new, and not done |
| confounded | the edit was only applied together with another one (D165 compose), or it cleared some signals and added others, or the probe's status is not done while its signals say nothing is stuck |

Every probe is one sample (`samples: 1`), so a single "helped" is weak. D166 needs repeats before it acts.

**One LLM call writes the lesson**, only when at least one edit is `helped`. A new prompt,
`amoeba/config/prompts/reflector.txt`, in our own words after the paper's Prompt 6.
- It receives the round records and the step card, never a score.
- It returns `cue` (the shape of the situation, with no task facts), `lesson` (the operation, naming the edit op and
  the scope) and `confidence`. Or it returns `NO_ENTRY`.
- Plain code refuses a lesson that contains a number or proper noun from the task prompt, is over the character cap,
  or uses denylisted wording (reusing `adapt.yaml limits`).
- A refused lesson is asked for once more, then dropped.
- The call is traced and counted. It is skipped and logged, never failing the run, when the run cap or the task's
  fix allowance would not hold it.

**The library** is `data/lessons/`, **one library for every task**, built like `ToolLibrary`.
- One folder per entry, holding `edit.json` (the op and params that helped) and `EXPERIENCE.md` (cue, lesson,
  evidence rows, run ids, task ids).
- `index.jsonl` gives:
  - the key `(cause, op, scope)`;
  - the verdict counts in total and per niche;
  - the distinct task ids;
  - the status: `unreviewed`, `approved`, `rejected`, `promoted` or `promotion_failed`.
- The niche is recorded, never used to split.
- New entries are saved `unreviewed`. You approve them with `python -m scripts.lessons list|show|approve|reject`.
- **A repeat updates counts, it does not add a row.** Every verdict updates the counts, `hurt` included, even when no
  lesson is written.
- Writes take a file lock and replace files atomically, so several runs may write at once.

Done when: three toy runs with the same injected fault give one entry with `helped: 3`, and a `hurt` probe raises
`hurt` without adding a lesson.

## D164 (stage 3) — Box 2 and Box 4 read the library

**Retrieval is plain code.** It picks entries that:
- are `approved` and have a lesson;
- have `helped > hurt` overall;
- have **never hurt in this run's niche**;
- for Box 4, match the cause (Box 2 takes any entry).

Entries from the run's own niche come first, then the most-helped. There are at most N entries and M characters
(`adapt.yaml lessons`), and no embeddings are used.

- **Box 4 proposers:** a section `# What helped before for this cause`, in `fix_proposer_inv.txt`,
  `fix_proposer_dom.txt` and `fix_proposer.txt` (the single rung). It lists the edit op, the lesson and how often it
  helped or hurt. The rule stays the same: the edit must still quote this run's evidence, so a lesson is a hint, never
  a license.
- **Box 2:** the lessons go to the Planner and both observers under `Lessons from earlier tasks`, through the
  drafting prompts' existing `{lessons}` slot (D82). The Planner prompt files do not change.
  - The general niche has no Environment section, so the slot is used instead.
  - The legacy d19 prompts have no slot.
- **Flags:**
  - `--lessons on|off` (reading, default off);
  - `--lessons-write on|off` (verdict counts and the reflector, default on with `--adapt on`);
  - both are on `run_task` and `stage_e`;
  - a `replay` task always runs with writing off.
- `result.json` lists the lessons shown, and each fix whose op matched a shown lesson and ended done.

Done when: with `--lessons on`, the proposer prompt for a matching cause shows the lesson. With `off`, the prompts are
byte-identical to today's.

## D165 (stage 4) — compose: try both edits together

`round_flags` already detects when two probes are **complementary**, meaning each cleared different signals. Today
the code just picks one.

Add a third probe in that case, and only in that case, when the budget allows (`probes_affordable`). Restore the
snapshot, apply both edits, re-run, and diff. Plain code keeps the combined state if it ends `done`, or if it clears
more signals than either probe alone with no new ones. Otherwise it falls back to today's `pick`.

- The third probe counts as a probe toward the fix tokens and dollars.
- Plan edits (`split_step`, `replan_remaining`) are never composed.
- Each edit keeps the verdict of its own probe. The composed probe is `confounded` for both.
- `adapt.yaml compose.enabled`, default false.

Done when: an injected run with two signals on one step records `complementary`, runs a composed probe, and keeps
it. The round row shows all three probes.

## D166 (stage 5) — the outer loop: repeated lessons become general config changes

`python -m scripts.promote --replay <tasks>`, run by hand, never during a task.

**Trigger, decided by plain code:** the entry is `approved`, has `helped ≥ promote.min_helped` (3) from at least
`promote.min_tasks` (2) different task ids, and has `hurt = 0` in every niche.

**What it may change.** General configuration in `amoeba/config/adapt.yaml` only. It never changes Python code,
prompts or the frozen judge. The allowed changes are:
- the order of a cause's list in `diagnoser.allowed_edits`, so an edit that keeps helping for a cause moves up its
  ladder;
- `promoted.planner_rules`: a general working rule, shown to the Planner and both observers under "Rules learned from
  earlier tasks";
- `promoted.tool_guidance`: a default guidance line for one tool, shown to every helper that holds it.

The last two start empty, so today's runs do not change.

**The test, by plain code:**
1. A proposer (one LLM call, `prompts/promote.txt`) writes the change from the entry. Plain code checks the change's
   kind, its target file, the text rules, and that the judge hash is the same before and after. It refuses any other
   target before any run.
2. The **replay set** runs twice through `scripts/stage_e.py --arms config`: once with today's config and once with
   the change, which is written to a temporary copy (`AMOEBA_ADAPT_CONFIG`), never the live file.
   - Both arms use the same drafts (`--drafts-from`), the same picks (`--picks-file`), the same lesson reading and the
     same sim seeds, with `promote.seeds` (3) seeds per task.
   - Both arms run with `--lessons-write off`.
3. **Accept** only if:
   - the mean `sim_score` delta is above zero;
   - no task drops by more than `promote.max_task_drop`;
   - the step-contract pass rate does not fall.

   Otherwise reject, and mark the entry `promotion_failed` so it is not tried again.
4. Every decision goes into `promotions/events.jsonl` and a short report, `promotions/<date>_<entry>.md`, next to a
   patch. **An accepted change is not applied automatically.** You apply it with `--apply <report>`.

**What the loop can never do:** edit `frozen.yaml` or any file it names, edit Python code, or skip your approval of
a lesson. A rejected promotion also never deletes a lesson.

## Cost per task, plan for it

| Pass | Model calls | Runs of a step |
|---|---|---|
| today, no stuck step | 0 extra | 0 extra |
| stuck step, scoped round | 2 proposers | 2 probes |
| + compose (D165, only when complementary) | 0 | 1 more probe |
| + reflector (D163, only when something helped) | 1 | 0 |
| outer loop (D166, rare) | 1 per promotion | the replay set × 2 arms × 3 seeds |

The outer loop is the expensive part, and it runs only when a lesson has repeated.

## Things to watch

- **The library only grows from stuck steps.** A task that never gets stuck teaches nothing. A later option is a
  whole-team pass after a finished task (the paper's version). It costs about 3 full runs per task, so add it only if
  the library stays thin.
- **Sandbox mode turns the scoped round off** (`fallback_reason`): probe files cannot be undone there. The single rung
  is recorded the same way, so the library still learns there.
- **Gemma quota (429)** stopped the last Box 4 probe. The proposer, reflector and outer loop add calls, so set
  `--max-tokens-per-run` and the per-task fix budget before a stream run.
- **One probe is one sample.** That is why lessons wait for 3 repeats and the outer loop tests on several seeds.
- **No niche is chosen.** When one is, its profile and tasks become fixtures for the same general loop; the library
  already records the niche of every count.
