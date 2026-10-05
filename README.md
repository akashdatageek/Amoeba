# Amoeba

A research system  in which a team of AI helpers is drafted per task and, in later
phases, reshapes itself under plain-code control. Motto: **first make it, then make it better.** Principle
everywhere: **LLM proposes, deterministic code disposes.**

**Phase 1** (this repo) builds three boxes only:

```
Task  ──▶  Plan a new team  ──▶  Team runs the task
           (AutoAgents drafting:   flat (AutoAgents) or
            planner + 2 observers,  boss + reviewers (AgentVerse)
            ≤3 rounds, then plain   ≤5 turns/step · ≤3 review rounds
            code builds the team)   every LLM call traced
```

No memory, monitor, gate or cost handling yet. Token counts are recorded in the trace, never enforced.

## Quick start

```bash
./clone_sources.sh                       # read-only clones the prompts are copied from (AutoAgents MIT, AgentVerse Apache-2.0)
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
python -m scripts.extract_prompts        # byte-exact prompt files → amoeba/config/prompts/
pytest -q                                # T1–T11, all offline

python -m scripts.run_task --toy --seed 0 --n 20 --topology flat
python -m scripts.run_task --toy --seed 0 --n 20 --topology boss_reviewers
python -m scripts.run_task "Reverse the string 'adaptive' then uppercase it" --topology flat
# real model, any OpenAI-compatible endpoint:
python -m scripts.run_task --toy --n 5 --llm openai --base-url http://localhost:8000/v1 --model qwen2.5
```

Without `--llm openai` a scripted stand-in model (`amoeba/llm/toy_mock.py`) answers, so everything runs with no
key. Each run writes `runs/<run_id>/{team.yaml, plan.json, trace.jsonl, capability_requests.json, result.json}` and the CLI prints mean
score, tokens and LLM calls.

## Box 3 plan runner and web tools (D31–D32)

```bash
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --draft-prompts d24 --topology plan
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --draft-prompts d24 --topology plan --web-tools
python -m scripts.smoke_web "Amazon RDS for PostgreSQL storage price per GB-month"   # one real call per web tool
```

`--web-tools` gives the plan runner `web_search` and `fetch_url` through Tavily. The key is read from the
environment variable **`TAVILY_API_KEY`** (never from a file). In the Claude Code cloud environment, add the domain
**`api.tavily.com`** to the environment's network allowlist (cloud environment menu → Edit → Network access); search
and page extraction both go through that one domain, so no other site needs to be reachable.

## Box 3 stocks its toolbox from the tool/skill pool (D56)

```bash
python -m amoeba pool refresh        # or `amoeba pool refresh`: MCP Registry servers + anthropics/skills → data/pool/
python -m amoeba pool status         # what the cache holds
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --draft-prompts d24 --topology plan
python -m scripts.run_task ... --no-pool                 # the step off (e.g. to replay an older --llm-cache)
```

Before the runner is chosen, every capability request Box 2 recorded is matched against the cached pool by keywords
(plain code, the top 5, tools and skills alike: the requested kind is only the planner's guess, D58), one short AI call (role group `pool`, default the workers' model) picks one candidate or
NONE, and plain code vets and attaches it. D60: the candidates are vetted *before* the pick — the picker is shown only
the best 5 that pass (up to 50 keyword matches are vetted to find them; none pass → `all_refused`, no AI call) — and
the pick gets 6,000 tokens of reply room, asked once more with twice that when it is cut off. A tool must be read-only
(no send / email / post / publish / pay / purchase / delete / "write to", and since D60 nothing that creates, updates,
uploads, edits, inserts, removes, renames, submits or writes in an outside service — a deck, doc or sheet is made
locally with local tools instead — in its name or description, nor in any tool the server lists) and not on a pay-per-call host
(`paid_hosts` in pool.yaml), and needs an HTTPS remote, a source repository, a pinned version, no key or its key in
the environment variable named in `amoeba/config/pool.yaml` (`auth_env`), and a description unchanged
since the refresh and since it was first attached (`data/pool/pins.json`). It becomes `pool:<name>` for the asking
helper only and runs through `ToolRegistry.execute` with the MCP Python SDK, capped like web_search, every result an
[S#] source. A skill must be instruction-only and at most 5,000 characters; its SKILL.md text goes on the helper's
role card. Pool text only ever reaches a prompt inside marked POOL DATA blocks. Each request's outcome (status,
pool_id, candidates, reason) is in capability_requests.json; result.json has a `pool` summary. Without a cache the
run logs `pool_unavailable` and runs as before. Refreshing needs `registry.modelcontextprotocol.io` and `github.com`
(skills are read from a shallow `git clone`, D58, not the GitHub API); a run needs only the hosts of the servers it
attaches.

## Local tools (D59)

```bash
pip install -e ".[local]"            # openpyxl, python-docx, python-pptx, matplotlib, pypdf — beforehand, never at run time
export AMOEBA_SANDBOX=1              # only inside this cloud container or a Docker container, never on your own machine
python -m amoeba pool refresh        # also keeps the anthropics/skills folders under data/pool/repos/
python -m scripts.run_task --tasks tasks/observer_round1.jsonl --llm openai --topology plan --local-tools on
```

With `--local-tools on` (default off) Amoeba borrows Claude Code's own tools through `claude mcp serve`, started once
per run over stdio and closed at the end. Claude's model is never called: the server runs with no key, and only its
tools are used; Gemma decides, and Amoeba's plain-code gate checks every call. Only Bash, Read, Write, Edit, Glob and
Grep are allowed (Claude Code 2.1.283 offers no Glob or Grep); every other tool is refused and logged once. The allowed
ones become `local:<Name>` tools for the helper that asked, run through `ToolRegistry.execute`:

- every path must resolve inside `runs/<id>/workspace/` (else `outside_workspace`); every Bash command starts there;
- network commands are refused (`network_command`: curl, wget, ssh, scp, nc, git clone/push/fetch, pip/npm install …),
  and destructive or escaping ones too (`unsafe_command`: sudo, `rm -rf /`, `cd /`, `../`, `~`, `/etc`, …);
- 60 s per call, 8,000 characters of output, 20 calls per step and 60 per run; a trace line for every call and refusal;
- python3 has openpyxl, python-docx, python-pptx, matplotlib and pypdf (installed beforehand, never at run time).

Local tools and skills are toolbox candidates, ahead of the pool's when an alias names them or they match at least as
well (D61; aliases: code runner → local:Bash, file
writing → local:Write, excel/spreadsheet → xlsx, presentation → pptx, word document → docx, pdf reader → pdf). Skills
come only from the kept anthropics/skills clone (D60: not from your own ~/.claude/skills); a skill with scripts is allowed now: its
folder is copied to `workspace/skills/<name>/` and its SKILL.md (frontmatter and first 5,000 characters) goes on the
helper's card. A step that says it saved a file the workspace does not hold ends `incomplete`
(`claimed_file_missing`). result.json adds `files_created`, `local_tool_calls`, `local_refusals` and
`skills_attached`, and the workspace is copied to `artifacts/files/`. With the flag off nothing of this runs.

## The step contract (D61)

Observer rounds 1–3 left the score near 35/50 because Box 3 recorded what happened (unfilled requests, tool calls,
files, sources) but never used it to judge a step or build the answer (gaps G1–G7 on the as-built page). With
`--step-contract on` (the CLI default; `off` gives the earlier runner for comparison) plain code closes them:

- **Before a step** it lists what each helper must account for: every capability it asked for and did not get, and
  every tool or skill attached to it. The list is on the helper's prompt.
- **After the step** it checks the evidence: every tool call (who, which tool, ok or failed), `BLOCKED: <name> — …`
  and `NOT NEEDED: <name> — <why>` lines. Anything left unaccounted for earns one refine turn naming it. If it is
  still unaccounted for, the step is `partial`: "not declared by the helper" (G1) or "attached unused" (G2).
  NOT NEEDED lines stay in the step's metadata and are removed from its text.
- **The answer's Limitations** also name undeclared missing capabilities and attached items left unused (`NOT USED`),
  matched by canonical name (G3).
- **A verify step** sees each checked step's sources, tool calls, figure counts and files (G4).
- **The answer step** is told which files each step made. Files and source-cited figures the answer leaves out earn one
  refine turn, and files still unnamed are listed by plain code under "Files made" (G5).
- **A producer whose only problem is a missing capability** is not sent back for rework (`rework_skipped`, G6).
- **A successful local tool call** gets a source id `[S#]` in the run's one source list, so a figure from it counts as
  cited (G7).

It also fixes two local-tool problems from round 3:
- A local item goes ahead of the internet candidates only when an alias names it or it matches at least as well (P14).
- A command written inside a code fence runs without the fence (P17).

result.json `refinement.contract` counts what the contract found. Each step_<n>.json has `contract`,
`contract_missing`, `unused`, `not_needed`, `causes`, `tool_calls` and `files_made`.

## Equal tools for the baselines (D62)

`--equal-tools on` gives the flat (AutoAgents) and boss_reviewers (AgentVerse) runners the same tool access as the plan
runner: the D32 web grant, tool calls for boss_reviewers' solver (which holds every tool the team was given) and
critics, and the same 8,192-token reply room. Their logic is otherwise unchanged; they never get the step contract.

## The Action Observer: mid-run re-plan (D63)

`--replan on` (plan topology; default off) lets the plan change while the team works. After each wave plain code looks
for a trigger: a step that lacked a capability, a verify step still failing after rework, a step that wrote
`MISSING INPUT: ...`, or a tool the plan never named held by a helper whose step is still waiting. On a trigger, one
planner call proposes one decision (CONTINUE, REVISE_REMAINING, ADD_STEP, REASSIGN_STEP, DROP_STEP or ADD_ROLE) for the
steps that have not run. Plain code validates it (finished steps never change, Box 2 rules, no cycles, new capability
requests through the toolbox step, at most 2 re-plans and 3 added steps per run, one added role) and applies it, or
logs it as rejected. Each plan version is saved as `plan.v<k>.json` with its diff; result.json `replan` lists every
decision and each requirement's final status (met / partly / not met; the answer step counts only when no other
step covers it). A revision may renumber the step that writes the answer; plain code finds it again in the
proposed plan, so such a revision is not rejected as a cycle.

## Shortened outputs keep the result (D64)

When a step's output or a program's output is too long for the next reader, plain code keeps its head and its tail,
marks what it left out (`[… N characters omitted …]`), and always keeps the lines with a final result (a count, a
total, an `=` line, the last 20 lines of program output). Helpers are asked to report results and short excerpts,
never whole lists.

## Check steps can re-check (D65)

With `--step-contract on`, a verify step gets calc, the web tools and local run / read (same sandbox gate) and the raw
tool results of every step it builds on. It is asked to re-run code, open files and re-check at least one cited
figure. A PASS with no re-checking tool call on code, files or cited figures is recorded as an unverified check and
makes the step partial.

## Provenance fixes (D66)

A number equal to a calc or local-tool result of the same step counts as derived, and an `[unverified]` tag next to
it is removed by plain code. A number given in the task that carries only a web source tag stays "given" and is
flagged for the refine turn.

## Freshness (D67)

For a task that asks for today's, the current or the latest value, research steps are asked for the most recent
official figure with its date, and one more search when it is dated. When the newest as-of date in the outputs is more
than 3 days before the run, plain code adds "Possibly not the latest (dated …)" to the answer's Limitations.

## Box 2 sees the real toolbox (D68)

With the d24 prompts, the Planner and both observers are shown every tool Box 3 will have (installed tools, web tools,
local tools and document skills, the pool) and how a role gets each. A document format or a house style is a skill;
anything only the user can supply is an open question or a capability request. The intake check knows more
deliverable verbs and does not cut a phrase inside an email address or a decimal.

## Document formats go to the local skill (D69)

With `--local-tools on`, a capability request that names a document format (xlsx, docx, pptx, pdf) is filled with the
vetted local skill for that format by plain code, with no AI pick. Other requests go to the picker as before.

## Baseline harness fixes (D70)

Fixes in our port, not in the baselines' design: AutoAgents' Write File block (`>>>file name` … `>>>END`) is turned
into our Write call; the flat reader keeps an answer's sub-headings; thinking tags are removed wherever they stand, even
malformed; a boss_reviewers reply that is only a tool request is not taken as the answer. `--picks-file FILE`
(with a `--picks-only` pre-pass) makes one pool pick per task that all three architectures reuse.

## Office suite in the sandbox (D71)

Spreadsheet formulas are recalculated with LibreOffice Calc headless. Install it once per machine or container:

    sudo scripts/setup_office.sh      # apt-get install libreoffice-calc, then a two-cell check

`amoeba/localtools/office.py` gives each call a fresh profile and HOME. With the xlsx skill attached, the local toolbox
checks once that a two-cell workbook comes back with its computed value, and tells the helper when it does not.


## Headings inside role prompts (D72)

Box 2 splits the Planner's reply into sections at `##`. A `##` that sits inside a JSON string (after a
written `\n`, as in a role prompt's `Output format:\n## Formula`) no longer starts a section, so such roles are not
lost.

## Crash resilience (D73)

HTTP 500, 502 and 504 from the model service are retried like 429/503 (same waits, same cap). A crashed run is
resumable: run the same task again with the same `--llm-cache` folder and `--llm-cache-namespace` and every call it
had finished replays from the cache for free; only the rest is paid. Web results keep the time they were really
fetched, so the replayed prompts are identical. Local tool calls (Bash, Write) run again, since they change files.

## Citation check by code (D74)

In the plan runner, every quoted phrase, time of day and number a step tags with [S#] must appear in the text the team
was shown for S# (search snippet, fetched page, tool output), after normalising spelling of times, dashes and
separators. A miss is recorded as a mislabelled citation: the step becomes partial and the answer's Limitations name
it, with the source that does contain it when there is one.

## Today's date and research rules (D75)

Every step prompt gets the run's date, weekday and time zone (`--timezone America/Chicago`; default the machine's
zone), so "today" questions never rest on a guessed date. Amoeba's step prompt also asks helpers to prefer the source
about the specific thing asked over general pages, never to infer a specific fact from a general page, and to say
so when sources disagree.

## Step endings and evidence size (D76)

On a helper's last turn only Final Output is offered, so a step ends with a written conclusion (a tool asked for
then is not run). A step whose output is only a search query or a tool request fails a `conclusion` check by code.
A verify step gets its producers' raw results as the excerpts that match the claims it checks, at most 20,000
characters in all, marked where cut.

## Task understanding before planning (D77)

Before the Planner drafts, one call lists what the task's names and terms could mean (abbreviations, acronyms,
voice-input errors such as "P and W" for "PNW"). A clear winner is used; otherwise `--interactive` asks one
multiple-choice question, and a non-interactive run takes the top reading and its answer opens with "I read X as Y;
if you meant Z, …". `--context user.yaml` (location, organisation, role; read-only) helps the reading:

    python -m scripts.run_task "How to pay the P and W universities parking citation?" --context user.yaml

    # user.yaml
    organisation: Purdue University Northwest
    location: Hammond, Indiana
## Identifiers in the citation check (D78)

Phone numbers, ZIP codes and street numbers are matched as whole tokens, digits only, never rounded or found inside a
longer number. A ZIP+4 printed run together ("463243348") contains its 5-digit ZIP, so an address copied correctly
is no longer flagged as a mislabelled citation.

## Quality gate on for the plan runner (D79)

`--quality-gate` is now `auto` by default: on for `--topology plan` (a draft failing a hard draft check goes back to
the Planner within the round cap), off for flat and boss_reviewers and when `--drafts-from` reuses a saved draft.
`--quality-gate on|off` overrides it.

## Task stream (D80, Phase 2)

Phase 2 (spec/BUILD_SPEC_PHASE2.md) learns from a stream of tasks. `tasks/stream_<name>.jsonl` holds practice tasks
(with an `order`) and held-out tasks, each with its family, its D30 rubric and whether it comes before or after the
family's shift; `tasks/stream_<name>.shifts.yaml` holds the shifts. A feedback shift adds rubric items the prompts
never mention; a tool shift takes a tool out of the family's runs:

    python -m scripts.run_task --tasks t.jsonl --topology plan --disable-tools calc,local:Bash

Held-out tasks never reach the practice loop or any prompt; the loop learns only the names of the rubric items a
practice run failed (`amoeba/adapt/stream.py::feedback`).

## Team recipes (D81, Phase 2)

A recipe (`amoeba/adapt/recipe.py`) is data per task family: planner rules shown to Box 2, transforms code applies to
the drafted plan (add a check step, tighten a done-when, grant or revoke a tool, add a role rule) and whitelisted run
options. Every family starts empty, and an empty recipe changes nothing. One typed edit makes the next version;
`validate_recipe` refuses unknown tools, out-of-range options, long or check-weakening text, and transforms that
break the step graph. Limits are in `amoeba/config/adapt.yaml`.

## Recipes in a run (D82, Phase 2)

    python -m scripts.run_task --tasks t.jsonl --topology plan --recipes eval/loop/m1/recipes

loads the current recipe of each task's family (plan runner only; the baselines never get one). Its planner rules
appear as "Lessons for this kind of task" in the d24 Planner and Observer prompts, code applies its transforms to
the final draft (`plan.json` records them; `draft.json` keeps Box 2's own draft), and its run options overlay the run
settings unless a flag sets them. With no recipe the run is a Phase 1 run, byte for byte.

## The Experimenter (D83, Phase 2)

    python -m scripts.run_experiment --stream m1 --family calc --calibrate-only  --llm openai --profile gemma-api ...
    python -m scripts.run_experiment --stream m1 --family calc --edit edit.yaml   --llm openai --profile gemma-api ...

runs the family's current recipe (A) against A plus one edit (B) on the stream's held-out tasks, 3 repeats each with
the same seed. A transform edit reuses arm A's saved draft, so the arms differ only by the edit; a planner-rule edit
drafts in each arm. Arm A runs are cached per recipe version. Results go to `eval/loop/<stream>/experiments/<id>/`.

## The Gate (D84, Phase 2)

The Gate keeps a recipe edit only when, on the held-out post tasks, its mean gain beats both the noise floor (the
recipe against itself with other seeds) and 0.05, a one-sided paired test corrected for every hypothesis since the
last accept is significant, the gain was predicted, the token cost is justified, honesty flags and refusals do not
grow, and the held-out pre tasks lose nothing beyond the noise. Every calibration, hypothesis and decision is a line
in `eval/loop/<stream>/ledger.jsonl`; thresholds are in `amoeba/config/adapt.yaml`.

## Metres are not millions (D80a)

The rubric's number reader used to read the "m" of "32.4 m²" or "8 m long" as million. A lowercase "m" now scales to
a million only after a currency sign ($1.5m), and a scale letter followed by a digit, ² or ³ is no scale at all. The
Experimenter re-scores every run from its saved answer, so a scorer fix applies to both arms alike.

## Headings inside a line are text (D84a)

The reply parser now starts a new section only at a "##" that begins a line (or follows a closing tag such as
"</thought>"). A "##" quoted in the middle of a line, for example a role prompt that says "end with a section headed
'## Assumptions'", stays text, so the role is no longer cut apart and lost.

## Gate v2 (D84b, Phase 2)

Gate v2 judges honesty per run: a run is flagged when it has at least one made-up or mislabelled citation, missing
claimed file or unverified check, and the edit is rejected if the share of flagged runs grows by more than 0.2.
Run errors are judged separately (rule 5b, error rate). Every ledger row names its gate version, and a decision made
under v1 can be re-decided under v2 from its saved pairs, marked post hoc:

    python -m scripts.run_experiment --stream m1 --family calc --redecide h2-assumptions-rule --gate-version v2

## The Monitor (D85, Phase 2)

After every practice run, the Monitor compares the last three scores of that kind of task with its scores since the
last accepted change, and raises an alarm when they drop by more than max(2σ, 0.10), or when a step cause or a
missing rubric item suddenly appears in most recent runs. It stays quiet for a few tasks after a change is accepted
or rejected. Thresholds: `amoeba/config/adapt.yaml` monitor.

## The Diagnoser (D86, Phase 2)

After an alarm, the Diagnoser counts what the window's runs recorded (step causes, blocked capabilities, unused tools,
missing files, unverified checks, citation problems, failed rubric item names) and names the cause that rose most
compared with the runs before. The table in `amoeba/config/adapt.yaml` says which edits may answer it. No model is
called; `--diagnoser none` gives the Architect the alarm only, with every edit allowed.

## The Architect (D87, Phase 2)

The Architect is the only part of the loop that calls a model. Given the diagnosis, the current recipe, the edits it
may use and the changes already rejected, it proposes one typed edit with a reason and a predicted gain, as JSON
(prompt: `amoeba/config/prompts/architect.txt`). Code checks the proposal (allowed, valid, not a repeat, no text or
numbers from held-out tasks) and allows one retry; after three proposals for one alarm, the alarm waits for a person
in `eval/loop/<stream>/human_queue.jsonl`.

## The recipe store (D88, Phase 2)

`eval/loop/<stream>/recipes/` holds each kind of task's recipe versions (`<family>/v<N>.yaml`), an index naming the
current version with its history, and `experience.jsonl`, one line per decided change. Runs read it with
`--recipes`; `--recipes-from` adds a read-only fallback store (a warm start from another stream). Only the Gate's
accept writes a version; the rollback watch can revert to the parent.

## The loop (D89, Phase 2)

    python -m scripts.run_loop --stream m1 --parallel 4 --parallel-until 8 --env-file keys.env \
        --llm openai --profile gemma-api --timezone America/Chicago --llm-cache runs/cache

runs the stream's practice tasks with each kind's current recipe and, after an alarm, the Diagnoser, up to three
Architect proposals, the Experimenter and the Gate; an accepted change becomes the next recipe version. Everything is
written under `eval/loop/<stream>/` (practice runs, experiments, ledger, recipes, proposals, `summary.json`,
`REPORT.md`), and running the same command again resumes where it stopped.

## The verifier answers first (D90)

A verify step works in two parts. First, in a fresh context, it sees the task, what each step it checks was asked to
do and the inputs those steps had, but not what they produced, and works out its own result with its tools. Then it
sees the outputs, compares them with its own result and gives the verdict. Both parts and plain code's figure
comparison are in `step_N.json` (`verifier_own`, `comparison`). `--verify-first off` restores the earlier verifier.

## Gate v3 (D91, Phase 2)

The Gate now judges a change task by task: it averages each task's repeats first, then asks whether the per-task
gains could come from chance (an exact permutation test over the tasks). Each family gets six tries per stream, each
at a significance level fixed beforehand (0.05 / 6), and the count never resets. The Architect's predicted gain is no
longer a rule; how well it predicted is reported in the loop's REPORT.md.

    python -m scripts.run_experiment --stream m2 --family calc --edit h.yaml --check   # the one pre-registered check

## Three task sets (D92, Phase 2)

Each task kind has practice tasks (the loop learns from them), gate tasks (held out; only the Experimenter and the
Gate run them) and final-audit tasks in `tasks/audit/`, which no part of the loop can read. A claim about the loop is
checked once on the audit set, and the claim is logged before the runs:

    python -m scripts.run_audit --stream m2 --family calc --claim C1 --statement "..." --recipes-b eval/loop/m2/recipes ...

## Observed and declared signals (D93, Phase 2)

The Diagnoser tags each signal it counts: *observed* when the runner measured it (tool calls, files, source matches,
rubric results) and *declared* when the model wrote it (BLOCKED / NOT NEEDED lines, [S#] tags, verifier verdicts).
Alarms and the chosen cause use observed signals only; declared ones are listed beside the diagnosis as supporting
evidence.

## Sections are scored on content (D94)

A rubric item can list task-specific entities. Its section then passes only if the text under the heading names at
least one of them, so a heading with nothing under it fails.

## The evidence log (D95, Phase 2)

Everything the loop does goes into `eval/loop/<stream>/events.jsonl`, written only by the harness. Each line carries
the fingerprint (SHA-256) of the line before it and of every run folder it refers to, so any later change shows:

    python -m scripts.verify_evidence --stream m2      # prints the first break, exit 1; or "ok"

Finished runs are key-scanned and shipped, at most every 10 minutes, to this repository's `evidence` branch (no code,
same layout as `eval/loop/<stream>/`); each commit message carries the chain head, so GitHub's history witnesses the
chain (`python -m scripts.verify_evidence --branch evidence`). What has not been shipped yet is listed in
`loop_state.json`. Agents never get git or cloud credentials, and their local tools cannot reach the log.

## Agent tools in a sandbox (D96)

With local tools on, each run gets a fresh NVIDIA OpenShell sandbox: the tool server and every command an agent runs
execute there, with no network, nothing writable but the sandbox's own workspace, skills and hooks read-only and no
secrets; it is deleted at the end of the run. It is the default with `--local-tools on`; the older in-process server
runs only with `--local-tools-mode inprocess` (and AMOEBA_SANDBOX=1). One command may take up to 300 s. Set up once
per machine:

    dockerd &                                                       # if Docker is not running
    CA_BUNDLE=<proxy CA, if any> amoeba/config/sandbox/build.sh     # the sandbox image
    docker compose -p amoeba-sandbox -f amoeba/config/sandbox/docker-compose.yml up -d   # the gateway
    # the gateway's signing keys, once: docker run --rm --user 0 -v /var/lib/openshell:/var/lib/openshell \
    #   ghcr.io/nvidia/openshell/gateway:latest generate-certs --output-dir /var/lib/openshell/tls

## The model router (D97)

Every model call says what it is (role, step, size, needed features, data class) and plain code picks the model from
the registry in `amoeba/config/models.yaml`: only allowed and available models, never one that fails a hard filter
(context, features, privacy, cost cap, verifier independence), then the recipe's or the role's preference, else the
cheapest of the right size. Per-model rate buckets, shared by all processes, keep calls inside each model's limits.
`--routing routed` is the default for Amoeba; the baselines use `fixed`. Today the registry holds Gemma 4 31B only;
adding a model is a registry entry. Each decision is in the trace, events.jsonl and result.json.

## Model preference as a recipe edit (D98, off)

The recipe menu has one more edit, `prefer_model {role, model}`: it tells the router (D97) which model to try first for
one role in one task family. The router still applies every allowlist and hard filter first, so a preference can only
pick among models that were allowed anyway. The Diagnoser offers it only for the causes `max_turns`, `checks` and
`capability`, and the Gate judges it on gain and USD like any other edit. It is built but **off**
(`--allow-model-edits` on `scripts/run_loop.py` / `scripts/run_experiment.py` turns it on): Gemma 4 31B is the only
real model today.

## Memory: three kinds (D99)

- **Recipe memory** (the recipe store): only the Gate writes. Every recipe line says which hypothesis added it, on
  which date, and which Gate decision accepted it.
- **User memory** (`standards:` in the `--context` file): lasting preferences such as "answers end with an
  Assumptions section". The loop can only *propose* one (a feedback item failing in ≥3 practice runs across ≥2 task
  families → `eval/loop/<stream>/memory_proposals.jsonl`). It counts once you approve it:
  `python -m scripts.approve_memory --stream m2 --id P1 --context user.yaml` (logged in events.jsonl). Box 1 and
  Box 2 read approved standards.
- **Event memory**: the evidence log (`events.jsonl`, D95). It is append-only, written only by the harness, and never
  fed raw into prompts.

No agent can write any of these files.

## Recipe expiry: replay and pruning (D100)

Every 12 practice tasks of a family (`--retention-every N`, 0 = off), the loop replays the family's pre-shift gate
tasks with the current recipe and with the starting recipe. If the current recipe scores lower by more than the
noise, a `retention` alarm is raised straight away and handled like any other alarm. The Diagnoser sees scores
only, never the held-out tasks.

At the end of a stream (`--prune end`, the default; `off` disables it) and on demand
(`python -m scripts.prune_recipe --stream m2 --family calc`), each recipe line is removed in turn and tested on the
gate set. A line is dropped when removing it loses no score beyond the noise and saves cost. Each prune is a Gate
decision in the ledger (`prune: true`) and does not use up the hypothesis quota.

## Task family for new tasks (D101)

A free-text task (one whose source gave no family) is assigned a task family before planning, so it can start from
that family's recipe. Keyword rules in `amoeba/config/families.yaml` are tried first. Only if none decides does one
routed model call pick from the family list or "new", and code checks the answer. The family and how it was chosen
are recorded in result.json (`family`). This is on by default for Amoeba's plan runner and off for the baselines
(`--family-classify auto|on|off`). A "new" family starts with an empty recipe.

## Niche profiles (D102)

An environment is described in one file, `profiles/<niche>.yaml`. It sets the allowed tools and the local-sandbox
limits, the allowed models and the verifier-independence setting, the domain's rules and vocabulary, what "done"
means, which domain checks run after each step (`amoeba/checks/<name>.py`), and safety limits. Choose one with
`--niche <name>`. The default, `general`, changes nothing.

With any other profile, the prompts get one "Environment" section: assess the environment first and plan only with
what is allowed. Code enforces the rest: Box 3 refuses any tool outside the profile and logs the refusal, the router
refuses any model outside it, and the domain checks earn a retry turn when they fail. Two profiles ship today:
`general`, and `calc` (every final figure must be reproducible by calc from the task's numbers).

## Infrastructure errors (D111)

Every result.json records a `status`: `ok`, `agent_error`, or `infra_error`. An infra error is one that is not the team's doing: the model service still failing after the client's retries (a dropped connection, a timeout, a proxy that moved, 429 or 5xx), a replay-cache miss, or a run that left no result. A 400, 413 or 422 comes from what the team sent, so it stays the team's.

An infra-error run is never a score. The Experimenter and the loop run it again, at most twice (`amoeba/config/adapt.yaml` `infra.retries`). If it still fails, it is left out of the pairs (listed in `experiment.json` under `excluded`), out of the Monitor's window and out of the Gate's reliability rule, which counts agent errors only. Each case is logged.

If your HTTPS proxy can move (a cloud session restart does this), set `AMOEBA_PROXY_FILE` to a file that always holds the current proxy. On a dropped connection the client reads it and reconnects through the new proxy, and each new run starts with it.

## Verifier disagreements: the resolver (D109)

A verify step first works out its own result without seeing the outputs it checks (D90). Plain code then pairs the figures of that blind result with the checked outputs' figures by their labels ("BEV purchase price", "electricity rate") and compares the values with the rubric's tolerance (5%).

Every disagreement goes to a resolver. This is one separate, fresh call whose only job is to settle each disputed figure: by the source text the team was shown, by fetching the source again, by a calculation, or by re-running the code in the sandbox. For each figure it writes a value, its evidence (a quote from the source, or a command and its output) and a verdict. Plain code accepts a value only if the quote really is in the source and states the value, or the value is in the resolver's own tool output.

A settled value that differs from the worker's replaces the wrong one in the producer's output, so later steps and the answer use it. An unresolved figure keeps the step from PASS: the step is partial, the verdict is recorded as `DISPUTED`, and both values are listed in the answer's Limitations. Every dispute and resolution is logged. `--disputes off` turns this off; it needs `--verify-first on`.

## Final-answer requirement check (D105 + D110)

After the summariser writes the answer, plain code checks the final answer, not what the steps claimed:

- each requirement from Box 2's list is covered (its key terms are in the answer, and no BLOCKED line is about it);
- each file the plan promised is in the workspace (with `--local-tools on`);
- every figure that cites a web source carries that source's date, on its line or in its source entry (D110).

Anything missing gets the answer step one refine turn. What is still missing afterwards is listed in Limitations. The run ends with `status: no_deliverable` when a core deliverable is missing: no answer content, a promised file never made, or more than half of the requirements unmet. result.json's `requirement_status` is the result on the final answer. `--deliverable-check off` turns off the requirement and file part; `--dated-figures off` turns off the dates.

## Skills in the sandbox (D103)

With `--local-tools on` the skills the pool picks (xlsx, docx, pdf, pptx …) now reach the helpers in the OpenShell sandbox. The sandbox image holds the skills clone read-only at `/opt/skills/<name>/`. A helper reads the skill there with `local:Read` and runs its scripts with `local:Bash`. Writing into `/opt/skills` is still refused. Before this fix every skill was refused in sandbox mode, so helpers fell back to plain openpyxl or python-docx.

## Research steps (D106)

With `--web-tools`, Amoeba's research steps get help from plain code (`--research on`, the default for the plan runner; the baselines never get it):

- A packed search is split. Several quoted queries in one string, several places ("USA and Indiana") or several years become one search each, at most four.
- Each search reads its top three results itself, official domains first (.gov, .edu, statistical agencies). The helper sees the lines that match its query, with the source's [S#].
- When a page links a data file (.csv, .xlsx, .json), plain code downloads and parses it, and shows the header rows and the matching rows as a table with its own [S#]. A `fetch_url` of a data file is read the same way.

The helpers are also told to search one entity, year or series at a time and to prefer the official source and the data file. Every page and data file read is cached with `--llm-cache`.

## Fetched data in the workspace (D107)

With `--web-tools` and `--local-tools on`, every page and data file the web tools read is saved in the run's workspace under `sources/`: data tables as CSV, pages as text. The files are read-only on the host and inside the sandbox, and `sources/index.json` lists each one with its [S#], url, title and fetch time. Analysts in the sandbox, which still has no network, can compute from the data itself, and steps with local tools are told the files are there. Writes into `sources/` are refused, reading and copying from it are allowed, and the files never count as files the team made. Turn it off with `--workspace-sources off`.

## Re-plans that change the method (D108)

With `--replan on`, the Action Observer may add or rewrite steps after a step fails. It is now shown how each failed step worked: the tools it used, the sites it read and its queries. A step it adds or rewrites for a failed step must change the method and say how in its text: a different tool, a different source type (a data file, an official source, an API, another site), or one search per entity, year or series. A step that repeats the method gets the whole decision rejected, and the rejection is logged with what was repeated. `--replan-method off` turns this off.

## Citation check and arithmetic (D104)

The citation check (D74) no longer flags arithmetic. A number the line shows as a calculation's result (after `=` or `≈`), the base and exponent of a power, and the years of a range are not treated as claims about the cited source. The calculation's operands are still checked. `--cite-arithmetic off` restores the earlier check.

## Python sent to Bash (D112)

When a helper sends a Python program to `local:Bash`, either a fenced block tagged `python` or text whose first line starts like Python, it now runs with `python3` from a quoted heredoc instead of failing as a shell command. The rewrite is logged and the gate still screens the program. Set `bash_python: false` in `amoeba/config/localtools.yaml` to turn this off.

## Spreadsheet formulas (D113)

After a step that made a workbook (.xlsx), plain code checks that totals and derived cells are formulas, not typed numbers. Three kinds of typed number are flagged: one in a total row or column, one that equals the sum of the cells beside or above it, and one that equals the product of two cells in its row. A flagged cell fails the step check with the cell names, which earns the step's retry turn. Numbers the task states are inputs and are never flagged. `--xlsx-formulas off` turns this off.

## Context size as a recipe option (D114)

A recipe may now set `max_input_chars` (3,000–20,000 characters of one input a step is shown; default 6,000) and `max_summary_input_chars` (15,000–60,000 characters the summariser is shown; default 30,000) as run options. The ranges are in `amoeba/config/adapt.yaml`. The loop can propose them for the checks and feedback causes, and the Gate tests them like any other edit. A flag given on the command line still wins.

## Cost controls (D45–D48)

```bash
# reuse the Box 2 drafts an eval_draft run already paid for (repeat k = --draft-pick k); no drafting calls
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --topology plan \
    --drafts-from runs/draft_eval/cmp2-gemini-3.1-flash-lite-d24 --draft-pick 0 \
    --llm-cache runs/cache --llm-cache-mode record --llm-cache-namespace rep0 \
    --max-tokens-per-run 200000 --min-seconds-between-calls 1
```

- `--drafts-from DIR --draft-pick K`: reuse saved drafts (an eval_draft folder or a runs folder); result.json names
  the `draft_source`.
- `--llm-cache DIR --llm-cache-mode record|replay|off [--llm-cache-namespace NAME]`: every model reply and web result
  is stored; `replay` never calls anything (a miss ends the run with `error="cache_miss"`).
- `--max-tokens-per-run N`, `--max-calls-per-run N`: the run stops cleanly with `error="budget"`; what ran is saved.
  Every run prints its billed tokens and an estimated cost from `amoeba/config/prices.yaml` (fill in the prices;
  a model without one gets tokens only).
- HTTP 429/503, dropped connections and timeouts are retried up to `--max-rate-retries` (5) with exponential waits
  or the server's Retry-After; `--min-seconds-between-calls` spaces calls out for free tiers. An error still there
  after the retries ends the run with `error: "api: ..."`, and its plan.json, trace and result.json are still
  written (D57), so a re-run with the same `--llm-cache` replays the calls already paid for.

## Model profiles and Gemma 4 (D49, D54)

With `--llm openai` the model is chosen by a **profile** in `amoeba/config/models.yaml`. The default profile is
**`gemma-api`**. Without `--llm openai` (the default, and in every test) the offline stand-in model answers.

| profile | endpoint | model | settings |
|---|---|---|---|
| `gemma-api` (default) | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemma-4-31b-it` | merge_system (no reasoning_effort: the API rejects it for Gemma, D57); key in `GEMINI_API_KEY` |
| `gemma-openrouter` | `https://openrouter.ai/api/v1` | `google/gemma-4-31b-it:free` | merge_system; key in `OPENROUTER_API_KEY` |
| `gemini-flash-lite` | Gemini API | `gemini-3.1-flash-lite` | as in the 2026-09-24 baseline; key in `GEMINI_API_KEY` |
| `gemini-flash` | Gemini API | `gemini-3.5-flash` | as in the 2026-09-24 baseline; key in `GEMINI_API_KEY` |

To switch, pass `--profile NAME` to `run_task` or `eval_draft`, or change `default:` in the file:

```bash
export GEMINI_API_KEY=<your Gemini API key>        # never commit it; AMOEBA_API_KEY, when set, is used first
python -m scripts.list_models --profile gemma-api   # check the model names this endpoint really offers
python -m scripts.run_task --tasks tasks/draft_eval_complex.jsonl --llm openai --profile gemma-api \
    --draft-prompts d24 --topology plan --max-calls-per-run 60
python -m scripts.run_task ... --llm openai --profile gemini-flash-lite
```

**Model names must be checked against the provider.** Model names in the file are what the provider called its
models when the file was written. Providers rename and retire them, so run `scripts/list_models.py` first; it
marks the profile's models with `*` and names any it cannot find. OpenRouter ids carry the provider prefix and a
`:free` suffix for the free variant.

A profile can set:
- `base_url` and `model`;
- `api_key_env`: the variable that holds the key;
- `merge_system`: Gemma takes no system message on some endpoints, so the system text goes into the user message;
- `reasoning_effort`: `off | low | medium | high`, sent only when set;
- `max_tokens`: the reply limit of calls that set none;
- `roles`: a `model` and `max_tokens` per role group. The groups are `planner`, `observers` (both Box 2 checkers),
  `workers`, `reviewers` (boss_reviewers critics, the plan runner's verify steps and critique reviews) and
  `summariser`.

What overrides the profile:
- `--base-url` / `--model` flags, then `AMOEBA_BASE_URL` / `AMOEBA_MODEL`, replace the profile's endpoint and
  default model. Per-role models still apply.
- `--merge-system` / `--no-merge-system` and `--reasoning-effort` (`unset` sends nothing) replace the profile's
  settings.
- `--planner-max-tokens` / `--observer-max-tokens` replace the profile's per-role limits.

Every trace line carries `amoeba.profile`. Each AI line holds `gen_ai.request.model` (asked for) and
`gen_ai.response.model` (the exact name the API returned). result.json has `profile` and `models`
(`requested` per role group, `returned`).

**Free tiers may use your prompts and replies to improve their products** (Google's free Gemini API tier and many
free OpenRouter models say so in their terms). Do not send anything confidential through a free tier; use a paid
key for private data.

## The as-built page keeps itself up to date (D55)

`docs/arch/phase1.html` is rebuilt from the code by `python tools/arch_update.py`. That script does nothing when no input
changed. After `git config core.hooksPath tools/hooks` it runs after every commit, and the Claude Code Stop hook
(`.claude/settings.json`) runs it when Claude Code stops. Code joins a box with a `# box: <id>` line above its def or
class. Box text is re-checked by a cheap model (`arch-text` profile) only for boxes whose extracted facts changed, and
the tokens are logged in `docs/arch/text_log.jsonl`. Numbers in the text come from the code. Set `ARCH_TEXT_LLM=off` to
never call a model; changed boxes are then marked stale.

## Layout

```
amoeba/
  llm/client.py            OpenAICompatibleClient, MockLLMClient
  llm/toy_mock.py          scripted stand-in model for the toy tasks
  llm/profiles.py          D54: model profiles (config/models.yaml), per-role routing
  config/schema.py         TeamConfig, AgentSpec, Edge, PlanStep, Limits, PromptRef
  config/validate.py       V1 V3 V5 V6 V7 V8
  config/io.py             load_yaml, dump_yaml, config_hash
  config/prompts/          verbatim prompt files (one source-header line each) + render()
  task/models.py           Task, Episode, Draft, RunResult, ...
  task/source.py           ToyTaskSource — 3 families with known answers
  task/evaluate.py         exact-match scoring (no AI judge in Phase 1)
  task/parsers.py          parse_sections, parse_role_blobs, parse_plan, parse_critic (regexes from the sources)
  task/draft.py            BOX 2: draft_team()
  task/instantiate.py      Draft → TeamConfig (flat | boss_reviewers)
  interp/runtime.py        BOX 3: Interpreter.run() → run_flat / run_boss_reviewers
  interp/trace.py          TraceWriter (JSONL, OpenTelemetry GenAI names), TracedLLM
  tools/registry.py        echo, calc
  safety/envelope.py       allowed_tools per role, max_agents
  pool/                    D56: index (refresh), match, stock (pick, vet, attach), mcp (pool tools)
  localtools/              D59: claude mcp serve (server), gate, skills, claims, toolbox (--local-tools on)
  cli.py                   D56: `amoeba pool refresh` / `python -m amoeba pool refresh`
scripts/run_task.py        CLI
scripts/list_models.py     D54: the models an endpoint offers (check a profile's names)
scripts/extract_prompts.py copies the prompts out of repos/
tests/                     T1–T11 with fixtures
spec/                      BUILD_SPEC_PHASE1.md (the spec), VERIFICATION_PHASE1.md, full spec for reference
repo_notes/                what the source repos actually do
diagram/                   living architecture page (drill-down boxes, hover cards, change requests)
```

## Read in this order

1. `CLAUDE.md` — rules for anyone (human or agent) changing this repo.
2. `spec/BUILD_SPEC_PHASE1.md` — §13 is the build instruction; §11 lists deliberate deviations from the papers.
3. `spec/VERIFICATION_PHASE1.md` — pseudocode with `file:line` citations into the source repos.
4. `diagram/amoeba_phase1.html` — open it in a browser; `diagram/CLAUDE_CODE_EDIT_LOOP.md` explains the edit loop.

## Phase 1 results (offline stand-in model, seed 0, n = 20)

| topology | mean score | mean tokens | mean LLM calls |
|---|---|---|---|
| flat | 1.000 | 4046.0 | 5.35 |
| boss_reviewers | 1.000 | 3112.7 | 5.00 |

Tokens are the mock's estimate (`len(text) // 4`). The score is 1.0 because the stand-in is well-behaved by
construction — it verifies the pipeline does not lose the answer, not model quality.

## Where the code departs from the spec

- `AgentSpec.role_prompt` holds the drafted role prompt (rendered into `{role}` of the worker's user message).
- `agentverse_solver_append` is stored verbatim; the deviation (dropping "Write the code step by step.") is
  applied at load time as `seed:agentverse_solver_append_generic`.
- `tests/fixtures/manager_output_real.txt` is hand-composed in AutoAgents' output format, not a captured run.
- Draft post-checks: a role blob without a `name` is skipped; duplicate names keep the first.

Everything else — the caps 3/5/3, the `No Suggestions` / `Final Output` sentinels, the observer history strings,
the 5th-iteration hint, the shared scratchpad, chat-history delivery of plans and reviews, silent-agree, solver ≤ 4
calls — follows the source code, with every deliberate departure marked `DEVIATION` in the code and spec §11.

## Licences of copied text

Prompt text in `amoeba/config/prompts/` is copied verbatim from AutoAgents (MIT) and AgentVerse (Apache-2.0);
each file's first line names the source path and lines. Nothing is copied from EvoMAS (CC BY-NC).
