# Probe: three hard tasks on the v1.0 candidate

This was an observation-only run: nothing was scored and nothing was fixed. Each of the three tasks in
`tasks/probe_hard.jsonl` (committed before any run, in `6423a95`) ran once with Amoeba.

**Code.** The runs used a separate worktree at PR #34's head (`6423a95`). The M-P2 chain kept its own checkout.

**Flags.**

- `--topology plan --routing routed --niche general`
- `--local-tools on --local-tools-mode sandbox` (the OpenShell sandbox)
- `--web-tools --replan on --timezone America/Chicago`
- `--draft-prompts d24` (Amoeba's configured prompts)
- All other flags at their CLI defaults (pool on, interpretation on, step contract on, verify-first on).

**Model and order.** Gemma 4 31B was the only model. The three tasks ran one after another while M-P2 ran on the same
key.

**Evidence.** Every run was shipped to the `evidence` branch under `eval/probe_hard/`: commits `36dedf2` (H1),
`3ce3508` (H2), `a777fef` (H3, first attempt) and `f214e41` (H3, re-run).

H3 ran twice. The first attempt (`e7d7000c`) was cut off by the environment, not by Amoeba. The Claude session
restarted at about 19:25 UTC and the HTTPS proxy moved to a new port. Processes started before the restart lost the
model API (`APIConnectionError`), and the run stopped at the summariser step. The same event broke four M-P2 check runs;
those were moved aside and the chain was restarted on the new port. H3 then ran once more (`5388906f`). Both H3 runs are
reported; the re-run is the one judged against the checkpoints.

## At a glance

| | H1 freight optimisation | H2 real income | H3 electric trucks memo (re-run) |
|---|---|---|---|
| Result against the checkpoints | **Right** (xlsx partly) | **Wrong** (honest gaps, no invented figures) | **Partly right** |
| Run status in result.json | partial (false citation flags) | no error (although nothing was delivered) | partial (citation flags) |
| Time | 30.9 min | 35.0 min | 68.4 min (first attempt: 57.0 min) |
| Model calls | 27 | 38 | 47 (39) |
| Tokens (in+out) | 119,704 | 153,377 | 281,765 (156,979) |
| Billed tokens incl. reasoning | 156,246 | 204,806 | 378,226 (227,971) |
| Cost | $0.00 (Gemma is free) | $0.00 | $0.00 |
| Rate-limit (429) retries | 4 | 10 | 10 (11) |
| Routing | 27/27 to gemma-4-31b | 38/38 | 47/47 (38/38) |
| Re-plans (Action Observer) | 1 call, kept the plan | 2 calls, 3 steps added | 1 call, 1 step added (2 calls) |

**Routing (all runs).** Every call went to Gemma with the reason "cheapest in tier large". There was no `no_model` and
no fallback. Each verifier call logged `verifier_same_family: no alternative`: 7 in H1, 7 in H2, 15 in the H3 re-run.
That is the expected `preferred` behaviour with one model.

**429s.** These came from sharing the key with M-P2, which ran four processes at a time. M-P2 still uses the old fixed
pause; the probe's router waited out its cooldowns of 16 s, 33 s and 19 s.

**Sandbox (all runs).**

- A fresh OpenShell sandbox was created and deleted for each run, with no network, 1 CPU and 1 GiB.
- No agent command was refused by the gate or the sandbox.
- The 17 `local_tool_refused` lines per run are the Claude Code tools outside the allowlist, logged once at start;
  this is expected.
- `Glob` and `Grep` are not offered by `claude mcp serve` 2.1.289.
- Every pool skill was refused as "not in the sandbox image" (problem 1). That was the xlsx skill in H1 and the docx
  skill in H3; H2 attached none.

## H1: freight optimisation

Every turn, command and check of this run is in [H1_STEPS.md](H1_STEPS.md).

**Box 1.** It took the family `calc` from the keyword rule ("total", "cost"). The interpretation step found nothing
ambiguous.

**Box 2.** It drafted four roles in two rounds, and both checkers agreed:

- Optimization Engineer;
- QA Engineer (`calc`);
- Document Specialist;
- Summariser.

The plan had four steps: 1 solve → 2 verify → 3 build the xlsx → 4 summary. The pool met the three capability requests
with the local xlsx skill and `local:Bash` for two helpers.

**Step by step**

1. **Solve.** The step took 4 turns, 2 `local:Bash` calls and one format retry (headings). The helper wrote and ran an
   exhaustive search in the sandbox (`itertools.product`, all 4¹⁰ = 1,048,576 assignments of 10 loads to 4 trucks, each
   checked against the weight and mileage limits) and returned **$6,356.25**. (Corrected 5 Oct: an earlier version
   called this a pruned depth-first search; that was the verifier's script, plan step 2.) The step was marked partial only
   because the citation check flagged "4¹⁰ = 1,048,576 [S1]" as a mislabelled citation.
2. **Re-plan.** After wave 1, the Action Observer ran once. Its trigger was "Document Specialist now holds local:Bash".
   It answered CONTINUE.
3. **Verify (blind first).** The verifier had `web_search`, `fetch_url`, `local:Bash` and `local:Read`.
   - It worked out its own answer without seeing step 1's output, in 3 turns with 2 tool calls. Its first Bash call
     failed because it sent Python code straight to Bash; it then wrote a here-doc.
   - Its own answer was $6,356.25 with the same assignment.
   - **No disagreement with the worker; verdict PASS.**
   - It was marked partial because in-line arithmetic such as "350 + 1,428.00 = 1,778.00 [S3]" was flagged as
     mislabelled citations.
4. **xlsx.** The step took 3 turns. The xlsx skill was refused by the sandbox (problem 1), so the helper wrote the file
   with openpyxl from Bash.
5. **Summary.** The table was correct. The proof of optimality is the exhaustive search.

**Final answer against the checkpoints**

| Checkpoint | Result |
|---|---|
| Optimum $6,356.25 | **Right**: $6,356.25 |
| Assignment A: L1,L2,L9 / B: L5,L7,L10 / C: L4,L6,L8 / D: L3 | **Right**: identical. A 44,500 lb, 680 mi, $1,778.00; B 44,500 lb, 540 mi, $1,484.00; C 27,000 lb, 1,055 mi, $2,451.75; D 22,000 lb, 150 mi, $642.50 |
| All four trucks used | **Right**. It did not give the 138,000 lb > 120,000 lb argument; the exhaustive search covers it |
| Solver written and run in the sandbox | **Right** |
| xlsx computes the total | **Partly**. Each truck's cost (`=B26+(C26*D26)`) and the total (`=SUM(E26:E29)` → 6,356.25) are formulas. Each truck's weight and miles are typed in as numbers instead of being summed from the load table |
| Verifier recomputed it blind | **Right**: it re-ran its own search before seeing the worker's output |

## H2: real median household income

**Box 1.** It took the family `research` from the keyword rule ("sources", "cite", "compare", "official"). Nothing was
ambiguous.

**Box 2.** It drafted four roles:

- Economic Data Researcher;
- Economic Data Analyst;
- Data Visualization Specialist;
- Delivery Lead.

The plan had five steps: 1 extract (year | US nominal | IN nominal | CPI-U | URL) → 2 adjust + CSV → 3 chart; 4 verify;
5 assemble. Python and file writing were met with `local:Bash` and `local:Write`. `web_search` and `fetch_url` were
already registered tools, handed out by `--web-tools`.

**Step by step**

1. **Extract.** The step took 5 turns: 3 searches and 1 fetch. It fetched the Census "Historical Income Tables:
   Households" landing page, whose figures live in linked .xlsx tables; only the first 6,000 of 15,736 characters were
   passed on.
2. **Re-plan 1 (REVISE_REMAINING).** Step 1 had no numbers, so the Observer added a new extract step and rewrote steps 2–5.
3. **Re-extract.** The step took 5 turns and 4 searches. Every query packed the US, Indiana, CPI-U and all nine years
   into one quoted string.
4. **Adjust, chart and assemble.** Each took 1 turn and wrote BLOCKED, because there was no data. There were zero
   sandbox calls in the whole run.
5. **Verify (blind first).**
   - Its own answer was "cannot verify: inputs missing", listing US 2015–2019, Indiana 2015–2023 and CPI-U 2015–2023.
   - Verdict FAIL, then rework and re-verify: FAIL again.
   - The verifier and the worker agreed that there was no data, so there was no figure disagreement.
6. **Re-plan 2 (REVISE_REMAINING).** It added steps 7–8. They repeated the same search method: 3 searches, 1 fetch of a
   Census ACS chart page that holds no figures.

In total there were 14 searches and 2 fetches. The run never fetched any of these:

- the FRED series pages (`MEHOINUSA646N`, `MEHOINUSINA646N`);
- the Census H-8 state table;
- ACS table B19013;
- a BLS CPI-U table.

**Final answer against the checkpoints**

| Checkpoint | Result |
|---|---|
| One survey, not ACS and CPS mixed | **Partly**: only CPS ASEC figures appear (US 2020–2023, nominal, from a FRED search snippet: $68,010; $70,780; $74,580; $80,610; FRED has $70,784 for 2021) |
| All values in 2023 dollars | **Wrong**: no adjusted value was produced |
| Index named | **Right**: CPI-U, with a generic justification |
| Every figure traceable to a fetched source | **Partly**: the four figures trace to a search-result snippet [S25], not a fetched page |
| Chart matches the CSV | **Wrong**: neither the CSV nor the PNG was made |
| Honesty | Every missing figure is BLOCKED and the Limitations explain the failed pipeline; no figure was invented |

The run's `result.json` shows `error: null` although nothing it was asked to deliver exists (problem 3).

## H3: electric trucks memo

**Box 1.** It took the family `calc` from the keyword rule ("compute", "total", "cost", "price"). Nothing was ambiguous.

**Box 2 (re-run).** It drafted four roles:

- Fleet Cost Analyst (`calc`);
- Technical Reviewer (`calc`);
- Document Specialist;
- Delivery Lead.

The plan had four steps: 1 research and model → 2 audit → 3 docx → 4 deliver. The pool met the requests with the docx
skill (then refused by the sandbox, problem 1) and `local:Bash` for three helpers.

**Step by step (re-run)**

1. **Research and model.** The step took 2 turns and no tool calls. Its answer had 33 untagged figures, cut to 16 after
   the refine turn.
2. **Re-plan (REVISE_REMAINING).** Step 1 "produced no actual data". The Observer added a research step and rewrote the
   rest.
3. **Research.** One query packed purchase price, 45W, Indiana incentives and Indiana rates together. It made 2 `calc`
   calls and 1 Bash call. The figures were then tagged, with 3 flagged as hallucinated before the retry.
4. **Audit (blind first).** It made 4 searches and fetched one page twice: an ICCT article on a *California* incentive
   programme.
   - Its own answer **disagreed with the worker** on three figures:
     - BEV price $325,000 [S6] against the worker's $400,000–$420,000;
     - Indiana commercial electricity $0.1415/kWh [S19] against $0.12/kWh;
     - diesel economy 7.0 mpg against 6.5 mpg.
   - It also said "45W $40,000 cap is correct per IRS", which contradicts the final $0.
   - Its final verdict was **PASS with no issues**. Of its corrections, only the 7.0 mpg reached the memo.
5. **docx.** The step took 4 turns and 2 Bash calls. It wrote the memo with python-docx in the sandbox
   (`TCO_Recommendation_Memo.docx`, 1,810 characters, under one page).
6. **Deliver.** It presented the memo.

**First attempt (cut off by the environment).** It wrote `TCO_Memo.docx` before the connection broke.

- It **applied the 45W credit** ($40,000 per truck, cited [S14, S15]), which is wrong for a 2026 purchase.
- Its arithmetic was correct: diesel $498,400 against BEV $532,800, recommendation NO.

**The federal credit, checked by hand.** The IRS FAQ on Public Law 119-21 (FS-2025-05, 21 Aug 2025) says the 45W
qualified commercial clean vehicle credit "will not be allowed for any vehicle acquired after September 30, 2025".
"Acquired" means a written binding contract plus a payment. So a 2026 purchase gets no 45W credit unless both were in
place by 30 Sep 2025. The 30C credit for charging equipment still applies to property placed in service by
30 June 2026. Neither run mentioned 30C.

Sources: <https://www.irs.gov/newsroom/faqs-for-modification-of-sections-25c-25d-25e-30c-30d-45l-45w-and-179d-under-public-law-119-21-139-stat-72-july-4-2025-commonly-known-as-the-one-big-beautiful-bill-obbb>
and 26 USC 45W.

**Final answer (re-run) against the checkpoints**

| Checkpoint | Result |
|---|---|
| Federal 45W credit for a 2026 purchase | **Right**: $0, "cancellation of IRA 45W" [S2], although the source is a news article, not the IRS. The first attempt got this **wrong** |
| Dated sources | **Wrong**: no figure carries a date, although the task asked for one |
| Assumptions stated | **Right**: mileage, mpg, fuel price, kWh/mi, electricity rate, maintenance and infrastructure are listed. Five of them are `[unverified]`: Indiana diesel $3.80/gal, Indiana electricity $0.12/kWh, maintenance $0.15 and $0.09 per mile, chargers $50,000 per truck |
| TCO arithmetic | **Right**. Diesel 185,000 + 228,000 (420,000 mi ÷ 7.0 mpg × $3.80) + 63,000 = **$476,000**. BEV 420,000 + 100,800 (420,000 × 2.0 kWh × $0.12) + 37,800 + 50,000 = **$608,600**. Difference $132,600 |
| Recommendation follows from the numbers | **Right**: keep diesel |
| Prices from relevant sources | **Partly**: both purchase prices are cited to a California incentive article [S2]; Indiana incentives "$0 [unverified]" |
| At most 2 pages, Word | **Right** |

## Problems found, with proposed fixes (D-row drafts; none implemented)

1. **D103: the sandbox refuses every pool skill.**
   - *Problem:* in `LocalToolbox.attach_skill` (`amoeba/localtools/toolbox.py:279`), `entry["root"]` is a label
     (`anthropics_skills`), but the code resolves it against the current directory as if it were a path. The
     "relative to the root" test therefore always fails, and every skill is refused as "not in the sandbox image" even
     though the image holds it under `/opt/skills`. The skills seen here were xlsx (H1) and docx (H3); the helpers fell
     back to openpyxl and python-docx.
   - *Fix:* keep the skill's absolute root path in the entry, or test the path against the configured clone path. Map
     the skill to `/opt/skills/<name>` and attach it.
   - *Test:* a live sandbox test that attaches the xlsx skill and reads its SKILL.md inside the sandbox.

2. **D104: the citation check flags arithmetic as mislabelled citations.**
   - *Problem:* these were flagged:
     - numbers computed on the same line from cited inputs ("350 + 1,428.00 = 1,778.00 [S3]");
     - powers such as "4¹⁰ = 1,048,576";
     - years listed beside a source ("2016 … 2019 [S5]");
     - small labels such as "45".

     Each flag alone set the step to `partial`, so H1 ended `partial` with a correct answer.
   - *Fix:* treat a number that results from arithmetic shown on its own line from cited or given numbers as derived,
     not mislabelled. Ignore years in a range or header and bare integers under 100 that are labels. Record
     mislabelled citations as a warning that does not change the step status unless it is also unverified.

3. **D105: the run status does not reflect missing deliverables.**
   - *Problem:* H2 ended with `error: null` while every committed output (CSV, PNG, adjusted values) was BLOCKED.
   - *Fix:* `result.json` gets `deliverables`, one entry per output the plan committed to (by its `csv:`, `png:`,
     `xlsx:` or `docx:` marker), recording whether it exists in the workspace and the share of BLOCKED figures in the
     answer. A run with a missing committed deliverable ends `incomplete`, never `null`.

4. **D106: research queries and fetches are too weak for data tasks.**
   - *Problem:* in H2 and H3, single queries packed every entity and year together, and very few pages were fetched
     (2 in 14 searches in H2; one California article fetched twice in H3). In H2 the data sat in linked .xlsx tables
     that a 6,000-character page view never reaches.
   - *Fix, part 1 (step contract):* a research step owes one query per figure group (entity × measure) and at least one
     fetched page per figure it reports; a figure backed only by a search snippet is reported as such.
   - *Fix, part 2 (`fetch_url`):* when the URL or a link on the page is a CSV or XLSX file, read it as a table (first
     sheet, header row and the rows that match the claims), within the same size caps.

5. **D107: fetched data cannot reach the sandbox.**
   - *Problem:* the sandbox has no network by design. The figures a researcher fetched reach the analyst only as prose,
     so no code can compute from them. H2's analyst and chart roles made zero sandbox calls.
   - *Fix:* the harness writes each fetched source's text (and any parsed table) to `workspace/sources/S<n>.txt`,
     read-only, before the next step runs. The step card says the files are there. Still no network in the sandbox.

6. **D108: re-plans repeat the method that failed.**
   - *Problem:* both H2 re-plans added steps with the same role, tools and query style, and they failed the same way.
   - *Fix:* the Action Observer is shown the failed tool calls (queries and URLs) and must name a different method or
     source, or stop with BLOCKED.
   - *Code:* refuse an added step whose role, tool set and inputs equal those of a failed step without a stated change
     of method. The refusal is logged.

7. **D109: the verifier's blind disagreements can be dropped silently.**
   - *Problem:* in H3, the verifier's own answer differed from the worker on the BEV price, the electricity rate and
     the 45W credit, yet the final verdict was PASS with "Issues: none". Only one correction reached the memo.
   - *Fix:* when `compare_figures` lists differences, a PASS must name each difference in Issues with the value kept
     and why. Code turns a PASS that leaves a listed difference unexplained into FAIL and sends it back for rework.

8. **D110: dates on figures are not checked.**
   - *Problem:* H3 asked to cite every figure with its date, and no figure in the memo has one.
   - *Fix:* add a domain check, `dated_citations`, used when the task asks for dates (Box 1 marks it) or by a niche
     profile. Every cited figure's line or source entry must carry a date (publication or as-of). A missing date earns
     the retry turn like any failed check.

9. **D111: experiment pairs can score infrastructure errors as 0.**
   - *Problem:* the session restart turned four M-P2 check runs into `api: APIConnectionError` runs with score 0.0. As
     a finished run they would have been reused and paired as a real 0 (they were moved aside by hand).
   - *Fix:* the Experimenter treats a run that ended in an infrastructure error (`api:` connection or timeout, or a
     killed process) as not finished. It reruns it, up to a cap, and never pairs it.
   - *Also:* `run_task` re-reads the proxy settings before retrying a connection error, so a long run survives a proxy
     restart.

10. **D112: Python sent to the Bash tool.**
    - *Problem:* the H1 verifier's first call sent a fenced Python block to `local:Bash`, which failed with a shell
      syntax error; it recovered on the next turn.
    - *Fix:* when the input to `local:Bash` is a fenced block tagged `python`, or starts with Python statements, run it
      as `python3 - <<'EOF' … EOF`. Log the rewrite, as D61 does for fences.

11. **D113: the xlsx plan cells are typed, not computed (minor).**
    - *Problem:* in H1, the per-truck weights and miles were typed in, not derived from the load table, so the
      workbook would not follow a change in the inputs.
    - *Fix:* a domain check for xlsx deliverables (in a profile that asks for formulas): every total in the plan area
      must be a formula referencing the input table; typed totals fail with the cell names.

12. **No fix needed, noted.**
    - The 429s (4, 10 and 10 retries) came from sharing the key with M-P2's four parallel runs. M-P2 runs the
      pre-router code. Once both use the router, the shared per-model bucket spaces them.
    - `Glob` and `Grep` are missing from `claude mcp serve` 2.1.289; the allowlist could drop them or note it.
