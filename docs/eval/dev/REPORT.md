# Two development tasks after D73–D77: the BMV question and the parking-citation question

*Run on 28–29 September 2026 (evening of Monday 28 September in US Central time).*

> **These are development tasks, not held-out tests.** Both questions were looked at while designing the fixes they
> now exercise: D73–D76 came from the first BMV run, and D77 from the first parking-citation run. Good results here
> show the fixes work on the case that prompted them. They do not show how the system does on unseen tasks.

Same setup as the bench5b benchmark:
- the same model (Gemma 4, 31B) and the same tools (web search and fetch, the tool pool, local tools, equal tool access);
- one Box 2 draft and one set of tool picks per task, shared by all three architectures;
- Amoeba runs with `--step-contract on --replan on`.

## 1. "Is BMV open in Hammond Indiana today?" (after D73–D76; 3 runs per architecture)

**Expected answer:** no, it is closed. The Hammond branch (7931 Indianapolis Blvd) is closed on Mondays and opens
Tuesday at 8:30 AM Central. The run clock (D75) was America/Chicago, where it was Monday 28 September.

| | AutoAgents | AgentVerse | Amoeba |
|---|---|---|---|
| Run 1 | "Yes, open, Monday 9:00–5:00" | "Open, 8:30–4:30" | **"No, it is closed"** |
| Run 2 | "Yes, open", and gives a wrong address | **"Closed on Mondays"** | **"No, it is closed"** |
| Run 3 | "Yes, open, 9:00–5:00" | "Open today, standard Monday hours" (only closed now because it is past 5 pm) | **"No, it is closed"** |
| **Correct** | **0 / 3** | **1 / 3** | **3 / 3** |
| Model calls, minutes, cost (3 runs) | 33 calls, 24 min, $0.12 | 58 calls, 28 min, $0.16 | 55 calls, 54 min, $0.36 |

All of Amoeba's "closed" answers cite pages it really fetched, such as a branch listing with "Mon Closed" and a
map listing with no Monday hours. Both baselines filled the missing Monday with "standard hours". That is exactly
what the D75 rule tells Amoeba's helpers not to do ("do not fill the gap from general knowledge"). The rule sits in
Amoeba's own step prompt, not in the baselines' paper prompts.

**What each fix did in these runs:**
- **D75, today's date:** all 9 answers knew it was Monday 28 September. In the first BMV test one team had decided it
  was "Tuesday, May 14, 2024".
- **D76, step endings:** every Amoeba step ended with a written conclusion. The first BMV test had a step whose output
  was only a search query.
- **D74, citation check:** one flag, in Amoeba run 3: "46324 not in S1". It is borderline. S1 printed the ZIP code
  joined to its extension ("463243348"), and the check found "46324" in two other sources. The step was marked
  partial and reworked, which is why that run took 30 minutes and 27 calls. The answer was still right.
- **D73, crash resilience:** no model-service error ended a BMV run.
- **Action Observer:** one call, in Amoeba run 2, on a "missing input" trigger. It decided CONTINUE, which was right:
  the next step found the hours.

**Mistakes that did not change the answer:**
- Amoeba run 1 gives "current local time: 3:59 PM" with a source tag. The real time was about 9 PM. A time of day
  copied from a web page is not today's time.
- AgentVerse run 3 worked out the time from the system timestamp. It got that right, but its hours were wrong.

## 2. "How to pay the P and W universities parking citation?" (after D77; one run per architecture per condition)

**Expected answer:** Purdue University Northwest (PNW). You can pay online by card through TouchNet (reached from
PNW's Bursar and myPNW pages), in person at the Bursar offices, or by check or money order by mail. PNW's rules say
to pay or appeal within 10 calendar days. The tempting wrong answer is Purdue West Lafayette's portal.

**What the new interpretation step (D77) read:**

| Condition | Reading | Confidence and how code settled it |
|---|---|---|
| No context, non-interactive | "P and W universities" = PNW University (Purdue University Northwest) | 0.8, clearly ahead: taken without asking |
| `--context` (organisation Purdue University Northwest, location Hammond, Indiana) | "P and W" = PNW | 0.95, clearly ahead: taken without asking |

- **Even without context, the step read "P and W" as a dictated "PNW".** So no question was needed, and no answer had
  to open with an assumption. Those two paths were exercised only in the mock tests, not in these live runs.
- With context, the Planner still wrote an open question ("Does PNW refer to Purdue University Northwest…?"). Code
  answered it from the interpretation, as D77 intends. The reading was stored as the bare "PNW", which is a little
  less explicit than the no-context reading.

| | AutoAgents | AgentVerse | Amoeba |
|---|---|---|---|
| **No context** | Right school and the online route (Bursar / TouchNet); leaves out in-person and mail; says no deadline is listed; gives the West Lafayette Bursar's phone number. **Partly** | Right school and the student online route; **invents** a "portal URL printed on the ticket" and paying at University Police. **Partly, with a made-up detail** | Right school and the fine schedule; says openly that payment methods "were not found" and points to the Office of Student Accounts. **Partly, honest** |
| **With context** | Right school and the Office of Student Accounts, but no actual payment method. **Partly** | Right school, the online route, and a useful warning not to use the West Lafayette portal; its visitor route (call University Police) is not in PNW's pages. **Partly** | **All three routes with PNW sources**: TouchNet portal (card or e-check, 3% / 4.25% fee), in person at Lawshe Hall 130 (Hammond) and Schwarz Hall 158 (Westville), and mail to both campus addresses; every detail checked against the fetched pages. **Solved** (the 10-day deadline is not mentioned) |

**Compared with the first parking test, before D77:** all three teams read "P and W" as two well-known universities,
and none looked at PNW. Now all six runs worked on the right school. That change comes from D77 and holds in both
conditions.

**What the context changed:** it mostly changed Amoeba, from "not found" to a complete answer. The no-context draft
was weak: only two roles, with its "verify" step done by the writer without tools. The researcher's one fetched page
was also cut before the sentence on paying the Office of Student Accounts. The with-context draft had a separate QA
role and a fuller plan. The two drafts differ, so part of this gap is Box 2 variance, not the context itself.

**Costs:** $0.38 for the six parking runs, plus one AutoAgents run with context that crashed on a rate limit (429)
while both tasks were running at once. It was re-run once, as logged in the ledger.

## 3. Known limits

- **One run per condition on the parking question, and three on BMV.** The differences are clear on these two tasks,
  but both are development tasks.
- **D74 false positive:** the number check does not treat a ZIP+4 run together ("463243348") as containing the ZIP.
  One Amoeba run lost 18 minutes to the rework this caused.
- **D75 gives the date, not the time of day.** One Amoeba answer cited a web page for the "current time". Questions
  about "now" (not just "today") would need the time too.
- **D77's question and stated-assumption paths were not triggered live**, because both readings here were clear. They
  are covered by tests only.
- **A weak Box 2 draft still limits Amoeba:** two roles, and a writer that also verifies. The Plan Observer approved it.

**Evidence:**
- Run folders: `eval/bmv/runs/<architecture>/<run id>/` and `eval/pnw/runs/<condition>/<architecture>/<run id>/`.
- Ledgers: `eval/bmv/ledger.jsonl` and `eval/pnw/ledger.jsonl`.
- Drafts, including the recorded interpretation, and picks: `eval/bmv/drafts/` and `eval/pnw/<condition>/drafts/`.
- Drivers: `eval/bmv/run_bench.py` and `eval/pnw/run_dev.py`.
- Total cost of both tasks: about **$1.05** at the high price estimate.
