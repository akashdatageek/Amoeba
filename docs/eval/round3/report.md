# Observer round 3 — pool on + local tools (D59), D60 pick fixes

Round 2b's setting plus `--local-tools on` (with `AMOEBA_SANDBOX=1`). Otherwise the same ten tasks, flags, model
(Gemma 4 31B), round 1's Box 2 drafts, and $5 guard. The cache namespace is `observer-r3`.

- **Local server:** `claude mcp serve` 2.1.283 was started once per run.
  - Exposed: `local:Bash`, `Read`, `Write` and `Edit`. It offers no Glob or Grep.
  - The 19 other tools it lists were refused once each.
- **Skills:** from the anthropics/skills clone only.
- **Code that ran:** `28a24f2` / `8d49819`. No pipeline code changed since round 2b; the only change is the
  as-built page tool.
- **Evidence:** run folders are in `eval/round3/runs/`, including each `workspace/` and `artifacts/files/`, and
  facts are in `eval/round3/facts/`.

## Checks next to round 2b

The rubric is unchanged (`eval/round1/rubrics.yaml`). C1 and C2 are fixed by the reused drafts. C6 "Filled and
used" means the toolbox filled at least one request and the helper that got it called it. The "made" column says
whether that call produced anything.

| Task | R2b | **R3** | C1 | C2 | C3 | C4 | C5 | C6 | Made | What changed in round 3 |
|---|---|---|---|---|---|---|---|---|---|---|
| r1-code-run | 3/5 | **4/5** | pass | pass | fail | pass | **pass** | **pass** | yes | **The code ran**: `solution.py` printed 12586269025. But the answer cites it as "[S1]", a source that does not exist (a local result gets no source id), so C3 fails as in round 1's chart |
| r1-weather | 4/5 | **4/5** | pass | pass | pass | fail | pass | fail | — | **Lost the live forecast.** The five candidate slots were filled with barely-matching local skills; the picker chose `mcp-builder`, and the weather server was never shown. The answer is honest: "failed verification", with the gaps named |
| r1-pdf-read | 4/5 | **4/5** | pass | pass | pass | fail | pass | pass | no | The `pdf` skill was attached. The helper tried `curl` / `urllib` to download the PDF; the gate refused all three attempts (`network_command`). The answer honestly says the PDF could not be downloaded |
| r1-xlsx | 3/5 | **4/5** | fail | pass | pass | **pass** | pass | **pass** | **yes** | **`shipment_data.xlsx` made** with a totals row and formulas (`=SUM(B2:B5)`, `=SUM(D2:D5)`, `=D6/B6`). R1–R3 are reported "Met", correctly |
| r1-chart | 5/5 | **5/5** | pass | pass | pass | pass | pass | **pass** | **yes** | **`revenue_chart.png` made**, correct (see below). "Please find … attached as revenue_chart.png" is now true |
| r1-fx-email | 4/5 | **3/5** | pass | pass | pass | fail | fail | fail | — | **Lost the rate.** Local skills (xlsx, claude-api, pptx) took 3 of 5 slots; the picker chose datakoot (refused at connect, `side_effect`) twice; fx-converter was not shown |
| r1-route | 3/5 | **3/5** | pass | pass | fail | pass | fail | fail | — | As before: distances from memory; diesel $6.5019 [S1] cited |
| r1-repo | 4/5 | **4/5** | pass | pass | pass | fail | pass | pass | no | `local:Bash` for the analyzer; only `ls` / `find` in an empty workspace (the repository cannot be cloned: no network). Honest |
| r1-deck | 2/5 | **2/5** | fail | pass | fail | pass | fail | fail | — | The `pptx` skill was attached to the designer, with local Read/Bash/Write/Edit; **0 local calls**. The brand was invented again |
| r1-full-chain | 3/5 | **3/5** | fail | pass | pass | fail | pass | pass | no | xlsx / chart / docx filled locally, but step 1 (GitHub data) is still blocked, so nothing downstream ran; one `ls` |
| **Total** | **35/50** | **36/50** | 7 | 10 | 7 | 5 | 7 | **6/10** | **3** | |

Summary by check:
- **Files made: 3 tasks**, against 0 in every earlier round: code-run, xlsx and chart.
- **C6 rose from 2 to 6.** Three of the six (pdf-read, repo, full-chain) called a local tool but produced nothing.
- **C4 fell from 6 to 5.** Two real results were gained (the xlsx file and the executed code), but the two live-data
  answers from round 2b (weather, FX) were lost to the ranking problem P14 below.
- **C5 rose from 5 to 7.** With a working runner there are fewer gaps to leave unreported.

## Local tools per task

| Task | Toolbox filled (local) | Local calls | Refusals | files_created (path, size, step) |
|---|---|---|---|---|
| code-run | local:Bash ×2 (alias) | 2 (1 error: a fenced command) | — | solution.py (235 B, step 1) |
| weather | skill mcp-builder (a wrong pick) | 0 | — | — |
| pdf-read | skill pdf ×2 (alias) | 4 (`ls -R`, `find`) | network_command 3 (curl ×2, urllib) | — |
| xlsx | skill xlsx (alias) | 4 (Write, Bash ×3; 2 errors: recalc.py) | — | generate_shipments.py (836 B), shipment_data.xlsx (5,102 B), step 2 |
| chart | local:Bash | 1 | — | generate_chart.py (409 B), revenue_chart.png (22,026 B), step 3 |
| fx-email | — (datakoot refused at connect) | 0 | — | — |
| route | — (NONE) | 0 | — | — |
| repo | local:Bash (python_code_analyzer) | 3 (`ls`, `find`) | — | — |
| deck | skill pptx (alias) | 0 | — | — |
| full-chain | local:Bash ×2, skill docx | 1 (`ls`) | — | — |
| **Total** | 13 filled locally | **15** | **3** (all network_command) | **5 files in 3 tasks** |

No `outside_workspace`, `unsafe_command` or cap refusals occurred, and no `claimed_file_missing`. Every claimed
file (shipment_data.xlsx ×2 and revenue_chart.png) exists.

## Every created file, opened

- **`solution.py`** (code-run): an iterative Fibonacci function with `print(fibonacci(50))`. Run by the observer, it
  prints **12586269025** (correct, F1 = F2 = 1). **Matches the task.**
- **`shipment_data.xlsx`** (xlsx), opened with openpyxl.
  - Contents: sheet "Shipments"; header `Lane | Loads | Avg Revenue | Total Revenue`; four rows (A 12 / 1,850 /
    22,200 … D 4 / 3,100 / 12,400); totals row 6: `B6 =SUM(B2:B5)`, `D6 =SUM(D2:D5)`, `C6 =D6/B6`.
  - Computed by hand: 43 loads, $79,800, **$1,855.81 per load**, all as the rubric expects.
  - **Matches the task, with two defects:**
    - The number format is written as `$"#,##0`, with an unclosed quote. Excel may have to repair the file when
      opening it.
    - The formulas have no cached values, because recalculation failed: the skill's `scripts/recalc.py` was first
      run from the wrong folder, then LibreOffice timed out after 29 s.
  - LibreOffice in this container cannot load *any* xlsx (a two-cell test file fails too), so the observer could not
    confirm how it opens.
- **`generate_shipments.py`**: the openpyxl script that wrote the file. Consistent with it.
- **`revenue_chart.png`** (chart), viewed. It is a 1000×600 bar chart titled "Total Revenue per Lane" with axis
  labels. The bars read Lane A 22,200 / B 16,800 / C 28,400 / D 12,400, matching the lane totals. **Matches the
  task.**
- **`generate_chart.py`**: the matplotlib script (hard-coded totals, `plt.savefig('revenue_chart.png')`). Consistent.

## New problems (P14 onward; P0–P13 are in rounds 2 and 2b)

- **P14: local candidates crowd out better internet ones (high).**
  - D59 puts every local match first, whatever its score. Generic skills such as `discernment-nudge`, `claude-api`,
    `pptx` and `mcp-builder` share one or two words with almost any request.
  - For weather, all five slots went to local skills scoring 1–2, while the weather server (score 7) and
    fx-converter (score 6) were never shown.
  - **Direction:** put a local item first only when an alias names it or it matches at least as well as the best
    internet candidate.
- **P15: a local result is not a source.** A local tool's output gets no [S#] id. The helper cited the real,
  executed F50 as "[S1]", which provenance counts as a made-up citation (3 in code-run).
  - **Direction:** give local results source ids ("local run" sources).
- **P16: attached skills are rarely followed.** pptx (deck) got no call, and the pdf skill led straight to a
  download attempt.
  - The xlsx skill was followed. Its own `recalc.py` needs LibreOffice, which does not work in this container.
- **P17: fenced commands.** A helper wrote its ActionInput inside a ```bash fence, and Bash ran the fence
  characters.
  - **Direction:** strip a surrounding code fence before the gate.
- **P18: skill scripts and paths.** The helper first ran `scripts/recalc.py` from the workspace root instead of
  `skills/xlsx/scripts/`.
  - **Direction:** the card line could give the exact path.
- **Unchanged:** the Box 3 problems of rounds 1–2 remain and are for the pipeline fixes after this round:
  - "done" without the tool (route, deck);
  - an invented brand;
  - gaps not reported (fx email, route routing).

## Cost

| Task | Run | Calls | In | Out | Reasoning | Billed | Est. cost | Wall |
|---|---|---|---|---|---|---|---|---|
| r1-code-run | 16513eee | 10 | 10,361 | 2,547 | 15,603 | 28,511 | $0.007–$0.037 | 8.6 min |
| r1-weather | c1dbdb8a | 10 | 18,285 | 1,722 | 6,336 | 26,343 | $0.004–$0.030 | 3.9 min |
| r1-pdf-read | dbdfb745 | 16 | 43,231 | 2,743 | 12,491 | 58,465 | $0.009–$0.065 | 17.3 min |
| r1-xlsx | 2da0909f | 12 | 30,903 | 4,059 | 20,045 | 55,007 | $0.011–$0.067 | 11.9 min |
| r1-chart | 22e03bd2 | 13 | 14,136 | 2,872 | 10,764 | 27,772 | $0.006–$0.034 | 6.5 min |
| r1-fx-email | 7fb70fb0 | 11 | 9,767 | 1,810 | 10,836 | 22,413 | $0.005–$0.029 | 6.0 min |
| r1-route | 28a16db2 | 9 | 12,140 | 2,346 | 11,312 | 25,798 | $0.006–$0.032 | 6.5 min |
| r1-repo | 71c762ea | 13 | 13,890 | 2,187 | 7,142 | 23,219 | $0.004–$0.028 | 4.6 min |
| r1-deck | 2a018a0c | 8 | 18,678 | 7,350 | 13,289 | 39,317 | $0.009–$0.049 | 9.7 min |
| r1-full-chain | 31fe4b77 | 19 | 27,318 | 3,573 | 19,228 | 50,119 | $0.010–$0.061 | 10.8 min |
| **Total** | | **121** | **198,709** | **31,209** | **127,046** | **356,964** | **$0.07–$0.43** | **86 min** |

## Four rounds side by side

| | R1 (no pool) | R2 (pool) | R2b (pool + D60) | R3 (pool + D60 + local) |
|---|---|---|---|---|
| C1–C5 | 34/50 | 36/50 | 35/50 | 36/50 |
| C4 still useful | 4 | 4 | **6** | 5 |
| C6 filled and used | — | 1/10 | 2/10 | **6/10** |
| Files actually made | 0 | 0 | 0 | **5 (3 tasks)** |
| Live data cited in an answer | 1 (diesel) | 1 (diesel) | **3** (diesel, weather, FX) | 1 (diesel) |
| Billed tokens | 453k | 363k | 387k | 357k |
