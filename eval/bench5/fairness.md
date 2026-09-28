# Five-task benchmark — fairness check, done before any benchmark run

The tasks and rubrics were committed first, in `5913282`, before any drafting or run.

## 1. One draft per task, shared by all three architectures

- **How the drafts were made:** Box 2 drafted each of the 5 tasks once, with the d24 prompts and the default Gemma profile
  (`gemma-api`, gemma-4-31b-it), via `scripts.eval_draft --repeats 1`.
- **Where they are:** `eval/bench5/drafts/<task>.0.json`. Each file holds the full Box 2 record: every round's
  Planner reply, both Observers' replies and verdicts, and the final team and plan.
- **How they are used:** all three architectures read the same file (`--drafts-from eval/bench5/drafts --draft-pick 0`).
  No architecture drafts its own team.
- **Instantiation:** each architecture turns the same draft into its own team shape:
  - AutoAgents (flat): the steps in list order.
  - AgentVerse (boss_reviewers): the summariser role becomes the single writer, and every other role becomes a reviewer.
  - Amoeba (plan): the steps over their `depends_on` graph.
- **Check:** every draft has a summariser role, which AgentVerse needs as its writer (see the check below).

## 2. The same toolbox

**What every run gets:**
- The same tool registry: calc, echo, and web_search / fetch_url (Tavily, `--web-tools`).
- The same pool (`--pool`) and local tools (`--local-tools on`, `AMOEBA_SANDBOX=1`).
- Box 3's toolbox step runs before the runner in every architecture. It fills the draft's capability requests from the
  pool and the local tools in the same way whatever the topology.

**What the check found before the runs, and what was changed (D62, `--equal-tools on`, commit `07921c7`):**
1. **Web tools.** The D32 web grant ran only in the Amoeba plan runner. That grant gives web_search and fetch_url to a
   role that asked for web search. Now the same rule is applied to flat and boss_reviewers teams.
2. **AgentVerse made no tool calls at all.** Its solver and reviewers only write text, as in AgentVerse's
   vertical-solver-first setup. So a pool or local tool attached to one of its agents could never be used.
   - Now an agent may reply with an `Action: <tool>` / `ActionInput: <input>` pair. It runs through the same tool
     dispatcher as every other runner, and the result comes back to the agent: at most 5 calls, then it answers.
     Any other reply is its answer, exactly as before.
   - The writer produces the whole answer, so it holds every tool the team was given. The reviewers hold their own.
3. **Reply room.** Amoeba's helpers had 8,192 tokens per reply; the two baselines had the client default of 2,048.
   All three now get 8,192.
4. **Flat (AutoAgents) already called tools.** It uses its own Action / ActionInput format, including pool and local
   tools; nothing else was needed.

**What the baselines do not get:** the step contract, the step checks, refine turns, provenance, verify / rework or the
plan graph. The self-refine and critique flags are passed to all three runs but only the plan runner reads them.

## 3. Same model, limits and caps

For all three:
- The same model and profile.
- `--max-tokens-per-run 400000`, `--max-calls-per-run 150`, `--min-seconds-between-calls 1`.
- The same per-reply room (item 3 above).
- The LLM cache on, with namespace `bench5-<arch>`.

## 4. Running

- One task at a time, with its three architectures started together; then the next task.
- Driver: `eval/bench5/run_bench.py`.
- After batch 1 the driver projects cost and time. It stops if the projection passes $5 or 7:00 am Central.

## Known asymmetries left in place (they are the architectures)

- **Where the tools sit:** in AgentVerse the writer produces the whole answer and the reviewers only comment. In
  AutoAgents and Amoeba the helper named in each step does that step's work with that role's tools.
- **Separate toolbox picks:** the toolbox step's pick is one model call per request, made separately in each run. So the
  three runs of a task can, by sampling, fill a request differently. The report lists what each run actually got.
