# Observer rounds 3b and 4 — the step contract off and on (3 repeats per task)

The two rounds are identical except for one flag:
- **Code:** current main (`ab107d1`, D61 merged).
- **Tasks:** the same ten (`tasks/observer_round1.jsonl`), scored against the unchanged rubric (`eval/round1/rubrics.yaml`).
- **Drafts:** round 1's Box 2 drafts, reused (`--drafts-from eval/round1/runs --draft-pick 0`).
- **Tools:** `--pool on --local-tools on` (with `AMOEBA_SANDBOX=1`).
- **Model:** Gemma 4 31B.
- **Repeats:** 3 per task. Each repeat has its own cache namespace (`observer-<round>-rep<k>`) and runs folder.
- **Cost guard:** $5 per round, checked before every run against the high price estimate (`eval/round4/run_rounds.py`).

The flag:
- **3b:** `--step-contract off`. This isolates the local-tools fixes of D61: P14 (ranking), P17 (fenced commands) and G7 (local results are sources).
- **4:** `--step-contract on`.

The prediction (`docs/eval/predictions.md`) was committed and pushed before any run (`d7162af`).

**Runs.** 60 scored, 63 attempts:
- Three attempts stopped on Gemini API errors: 3b rep 2 xlsx (429 quota), 3b rep 1 full-chain (500) and round 4 rep 1 repo (500).
- Each was run again with the same settings, and the re-run is the one scored. The failed folders are kept.

**Evidence:**
- Run folders are in `eval/round4/runs/<round>/rep<k>/`, with their workspaces and `artifacts/files/`.
- One digest per run is in `eval/round4/digests/`, with the facts in `eval/round4/facts.json`.
- Per-run scores with reasons are in `eval/round4/scores.yaml`.
- The tables are from `eval/round4/aggregate.py` (`aggregate.json`).
- The NOT NEEDED audit is in `docs/eval/round4/not_needed.md`.

## C1–C6 per task: mean over 3 runs (range), 3b next to round 4

C1–C5 are out of 5 per run. C6 ("filled and used") is 1 when the toolbox filled a request and the helper that got it
called it. R1–R3 are one run per task, for context.

| Task | R1 | R2 | R2b | R3 | **3b C1–C5** | **R4 C1–C5** | 3b C6 | R4 C6 | What moved |
|---|---|---|---|---|---|---|---|---|---|
| r1-code-run | 5 | 5 | 3 | 4 | **5.00** | **5.00** | 1.00 | 1.00 | G7: the executed result is a real [S#] in all 6 (R3's made-up citation gone); R4 answers name the file made |
| r1-weather | 4 | 4 | 4 | 4 | **4.00** | **4.33** (4–5) | 1.00 | 1.00 | P14: the weather server is back in all 6; the verify step still FAILs for lack of step 1's raw data (3b 2/3, R4 2/3) |
| r1-pdf-read | 3 | 4 | 4 | 4 | **4.00** | **4.00** | 1.00 | 1.00 | unchanged: downloads refused, honest "unavailable" |
| r1-xlsx | 3 | 3 | 3 | 4 | **4.00** | **4.00** | 1.00 | 1.00 | the file is correct in all 6 (opened with openpyxl); C1 fails by the draft |
| r1-chart | 4 | 5 | 5 | 5 | **5.00** | **5.00** | 1.00 | 1.00 | the chart is correct in all 6 |
| r1-fx-email | 3 | 3 | 4 | 3 | **4.00** | **4.33** (4–5) | 1.00 | 1.00 | P14: the real rate is back in all 6; the missing email sender is named only once (R4 rep 2) |
| r1-route | 3 | 3 | 3 | 3 | **3.00** | **4.00** | 0.00 | 0.00 | R4: BLOCKED instead of guessed distances (C3, C5 pass) but no estimate at all (C4 fails) |
| r1-repo | 4 | 4 | 4 | 4 | **4.00** | **4.00** | 0.00 | 0.00 | P14: the weak local:Bash match no longer goes first, so nothing is filled (C6 falls against R3) |
| r1-deck | 2 | 2 | 2 | 2 | **2.00** | **2.00** | 0.00 | 0.00 | the picker chose slideforge over the pptx skill (refused, side_effect); R4's designer writes NOT NEEDED |
| r1-full-chain | 3 | 3 | 3 | 3 | **3.00** | **3.00** | 1.00 | 0.33 (0–1) | blocked at step 1 as always; C6 depends on whether a helper happened to call a local tool |

Only two task means have a range, because most tasks gave the same score in all 3 repeats. Wherever a repeat
differs, the table shows it.

## By check: sums of the task means

| Check | R3 | 3b | R4 | R4 − 3b | 3b − R3 |
|---|---|---|---|---|---|
| C1 asked | 7 | 7.00 | 7.00 | 0 | 0 |
| C2 kept | 10 | 10.00 | 10.00 | 0 | 0 |
| C3 honest | 7 | 8.00 | **9.00** | **+1.00** | +1.00 |
| C4 still useful | 5 | 6.33 | 6.00 | −0.33 | +1.33 |
| C5 gaps reported | 7 | 6.67 | **7.67** | **+1.00** | −0.33 |
| C6 filled and used | 6 | 7.00 | 6.33 | −0.67 | +1.00 |
| **C1–C5** | **36** | **38.00** | **39.67** | **+1.67** | +2.00 |

Where the round 4 changes come from:
- **C3 +1.00:** entirely from **route** (all 3 runs block instead of guessing).
- **C5 +1.00:**
  - route +1;
  - fx-email +1/3 (rep 2 names the email sender);
  - weather −1/3 (one run fewer with a Limitations section).
- **C4 −0.33:**
  - route −1 (no estimate any more);
  - weather +2/3 (the forecast is kept in all 3 round 4 answers, even beside a failed check, against 1 of 3 in 3b).
- **C6 −0.67:** full-chain, where whether a helper made a local call varies between runs.

## What the local-tools fixes did on their own (3b against round 3)

- **P14 worked where it was aimed:**
  - The weather server and fx-converter were picked in all 6 runs, where round 3 lost both to weak local skills.
  - The live forecast and the real rate reached every answer (C4 +1.33).
- **P14 also removed a hollow fill:** repo's python_code_analyzer is no longer filled with local:Bash, which only ever
  listed an empty workspace. The picker now answers NONE (repo C6 1 → 0).
- **G7 worked:**
  - code-run's executed result is a real source [S#] in all 6, where round 3 had 3 made-up citations.
  - C3 +1.
- **P17:** no fenced command reached Bash in either round.
- **Deck regressed for a reason that is not P14:** the local pptx skill was shown first (alias, score 100), but in
  all 6 runs the picker chose slideforge, which the connect-time check refuses (side_effect). Round 3's single run
  picked the skill.

## What the step contract did (round 4 against 3b)

### Status changes

**No step changed from done to partial through the after-step check.** Across round 4's 120 latest steps, plain code
never turned a done step partial because of an undeclared missing capability or an unused tool. Every status change
came from the contract line on the helper's prompt, which made helpers declare BLOCKED or NOT NEEDED themselves.

| Step (runs) | 3b | R4 | Why | Right? |
|---|---|---|---|---|
| route step 1 (3) | done | partial | the helper wrote BLOCKED: route_engine at once | **Yes.** No routing tool existed; 3b guessed the distances. But it also dropped the [unverified] estimate the answer could still use |
| route step 2 (3) | done | partial | no distances from step 1 | **Yes** (and not reworked: G6, `rework_skipped`) |
| fx-email step 3 (rep 2) | done | partial | the auditor PASSed and the Communications Lead wrote BLOCKED: email_service | **Yes.** The only run in 4 rounds that names the email gap |
| full-chain step 4 (reps 1, 3) | done | partial | the Delivery Lead declared BLOCKED: email_tool in a verification step | **No.** Emailing is step 5's job, which declares it too. Harmless: the gap is real |
| weather step 3 (3) | partial | done | the verifier wrote NOT NEEDED: weather tool instead of BLOCKED: "Step 1 output"; the verdict is still FAIL in 2 of 3 | **Mixed.** A missing input is not a capability, so "done + FAIL" is closer to the truth than "lacked: Step 1 output". But the NOT NEEDED line hid that the attached tool could have fetched the data again |

The xlsx step differences between the rounds are sampling: the turn cap after a rework, or a verifier with no file
access. They occur in both rounds.

### The NOT NEEDED lines

The full list, with a judgement for each, is in `docs/eval/round4/not_needed.md`. There are 111 lines:
- **83 honest:** the tool wasn't needed or was used anyway.
- **16 noise:** 13 × "NOT NEEDED: Print", and 3 lines with no capability name.
- **12 evasive:**
  - **deck (3):** "NOT NEEDED: presentation-generator — The task required a visual specification … rather than the
    generation of a .pptx file". The task says "Make a 5-slide PowerPoint deck". This is the clearest evasion: it
    rewrites the task so the contract stops asking, and the gap never reaches Limitations.
  - **fx-email (3, masking):** "NOT NEEDED: email_service — The Quality Auditor reported 'FAIL', so the condition to send
    the email was not met". True for the run, but the team has no way to send email at all, and this line is what keeps
    that out of Limitations (C5 fails in those two runs).
  - **weather verifier (5 lines, 2 runs):** "NOT NEEDED: pool:…weather-mcp — This step requires verification of existing
    data … not new weather retrieval". The step then FAILs because Step 1's raw data is missing, which is exactly what
    the attached tool could fetch again.
  - **code-run QA (1, mild):** "NOT NEEDED: python_interpreter — verified via manual trace and … the known mathematical
    value". The QA's interpreter request was unfilled. It checked from memory; no score effect, because step 1 had really
    run the code.

This is the main weakness of D61 as built. The escape line was meant to stop a role-wide tool from marking every step
partial, and it does that (the 83 honest lines). But the contract accepts any NOT NEEDED line without checking it,
so a helper can talk its way past G1. That is why G1's after-step check fired only once in 30 runs.

### Refine turns and cost

| Round | Runs | Calls (mean per run) | Billed tokens (mean) | Est. cost (low–high) | Contract refine calls | Their tokens |
|---|---|---|---|---|---|---|
| 3b | 30 | 443 (14.8) | 1,419,064 (47,302) | $0.29–$1.74 | — | — |
| 4 | 30 | 424 (14.1) | 1,465,951 (48,865) | $0.30–$1.79 | 17 (3 contract-only) | 82,627 (5.6 % of round 4) |

- **Extra model calls:** 17 calls carried a contract finding in their refine note. Only 3 existed purely for the
  contract; the other 14 shared the D50 refine turn with failed checks or provenance findings, as designed.
- **Which gaps they came from:**
  - **16 from the answer check (G5).** 9 were for files (solution.py, generate_chart.py, generate_shipments.py): these
    worked, and the files are named in every round 4 answer. 7 were for figures, and the figure half is mostly noise
    (see P21).
  - **1 from the step checks (G1/G2):** full-chain rep 3, email_tool.
- **Round total:** round 4 billed 3.3 % more tokens than 3b (the contract line lengthens every step prompt, and the
  refine turns add 5.6 %) with 4 % fewer calls. The call difference is sampling: 3b had more reworks and turn-cap
  retries.
- **Guard:** each round cost at most $1.81 at the high estimate, including the failed attempts, against the $5 guard.
  The runs took 5.9 h (3b) and 5.8 h (round 4) of run time, 6 at a time.

## Did the prediction hold?

**Main prediction (round 4 against 3b): it held by the letter, on the thinnest possible margin, and mostly through one
task.**
- **The three conditions:**
  - C3 + C5 rose by +2.00, exactly the threshold ("at least 2 of 20").
  - C5 rose as much as C3, and more than every other check.
  - No other check fell by more than 1 (C4 −0.33, C6 −0.67).
- **The numbers inside it missed:**
  - C5 rose by 1.00, not the 1.5 predicted.
  - C6 fell instead of staying level.
  - The contract made runs 3 % more expensive, not 10–30 %.
- **The mechanism was not the one expected:**
  - The gain came from the prompt line making helpers declare gaps before acting (route), not from plain code
    catching undeclared gaps afterwards (G1 fired once).
  - Three of the four tasks named as likely gainers (fx-email, deck, weather) were held back by evasive NOT NEEDED lines.
  - The "surprise" named in the prediction, NOT NEEDED used evasively, happened 12 times.
- **Sample size:** with 3 repeats and one task carrying the whole C3 gain, this is a small, real effect on one kind of
  task (a capability the team plainly lacks), not a general one.

**Secondary prediction (3b against round 3): held.** C4 rose by 1.33 (predicted 1–2) and C3 by 1 (predicted up to 1),
while C5 (−0.33) and C6 (+1) stayed within ±1.

## New problems (P19 onward)

- **P19 — NOT NEEDED is unchecked (high).** Twelve evasive lines stopped the contract, in deck, fx-email and the weather
  verifier. **Direction:**
  - A NOT NEEDED line for a capability that the planner's own request tied to this role, or whose name appears in the
    step's done_when or output line, is not accepted without a second look (a refine turn quoting the task line).
  - A NOT NEEDED line in a step whose verdict is FAIL for missing data, when the named tool could supply that data, is
    rejected.
- **P20 — the contract forbids the useful estimate (medium).** "Never fill in from memory what it would have given"
  overrides D33's [unverified] rule. Route now blocks cleanly but gives no distances and no fuel total, where an
  [unverified] estimate, or a web_search for each leg, was possible (C4 −1). **Direction:** BLOCKED for the tool's
  exact result, plus an [unverified] estimate clearly marked as such, and a web_search try before either.
- **P21 — the G5 figure check is noisy (medium).**
  - It flags "18.20" as missing when the answer has "18.2", splits dates into 2026 / 09 / 26, lists the 32 of the °F
    formula, and treats a task-given $2,500 as a cited figure.
  - It cost 7 refine calls, and in weather it pushed a summariser to list raw figures under "Failed Figures".
  - **Direction:** normalise numbers (trailing zeros, thousands separators), skip dates, years, constants and figures
    given in the task, and compare against the ledger's `as` form.
- **P22 — contract noise.** Helpers apply the "for each one" line to their action list: 13 × "NOT NEEDED: Print", plus
  lines with no name. **Direction:** list the contract items by name in the line itself ("for each of: X, Y") and ignore
  lines naming anything else.
- **P23 — the Bash gate lets commands read outside the workspace (security, medium).**
  - `find / -name recalc.py`, `find / -name "*.pdf"` and `ls -la /` all ran. One listed pytest temp folders.
  - Running a file found that way was refused (`unsafe_command`), and nothing was written outside the workspace.
  - **Direction:** refuse any absolute path outside the workspace in any argument, not only in `cd`, or run the server
    inside a container or chroot of the workspace.
- **P24 — a blocked step can still write files with invented data (contract off).** 3b rep 3 full-chain: the Technical
  Writer's step says it is blocked, yet it wrote analysis_report.docx and a chart from invented star counts, tagged
  [unverified] inside the file. The answer never mentions them. With the contract on, G5 would list such a file under
  "Files made". **Direction:** a file made in a step that ends blocked or partial is listed with that status in the
  answer.
- **P25 — G4 shows only the direct inputs' evidence.** Weather's verify step depends on step 2 only, so its evidence
  never includes step 1's forecast source. **Direction:** include the evidence of every step upstream that the
  verified figures came from (via the figure ledger).
- **Unchanged from earlier rounds:**
  - BLOCKED names are whole sentences, and "BLOCKED: local:Bash — …" is also read as a capability named "local".
  - "Step 1 output" and "Missing inputs" are treated as capabilities in Limitations.
  - The picker still picks acting servers that are refused at connect (P10: deck).
  - Nobody tries web_search or fetch_url for the pdf, repo or full-chain data (C4).
  - The xlsx skill's recalc.py cannot run in this container (LibreOffice).
- **API reliability:** 3 of 63 attempts (5 %) died on Gemini API errors (one 429 quota, two 500s) after the client's
  retries.

## Cost per round

| Round | Attempts | Scored | Calls | In | Out | Reasoning | Billed | Est. cost |
|---|---|---|---|---|---|---|---|---|
| 3b | 32 | 30 | 443 | 753,920 | 127,885 | 537,259 | 1,419,064 | $0.29–$1.74 (≤ $1.81 incl. failed) |
| 4 | 31 | 30 | 424 | 797,292 | 118,827 | 549,832 | 1,465,951 | $0.30–$1.79 (≤ $1.79 incl. failed) |

Prices are the same third-party Gemma 4 31B estimates as rounds 1–3: $0.09–$0.99 per 1M input and $0.34–$1.49 per 1M
output, with reasoning priced as output.
