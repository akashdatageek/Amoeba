# Observer round 1 — summary

Ten tasks, each needing something Amoeba cannot do today (run code, fetch live data, read a PDF, make a file, send an
email), from one missing ability up to seven chained together. One real run each on Gemma 4 (31B), web search on, no
tool pool. Nothing in Amoeba was changed. The full details are in `runs.md`, `capabilities.md` and `issues.md`.

**Overall:** 34 of 50 checks passed. The team almost never pretends to have done something it could not do. It does
not use the web search it already has, it sometimes fills gaps from memory, and when one step is stuck the whole
chain stalls. Total cost: 453k billed tokens, 131 model calls, about 2 hours, roughly $0.10–$0.57 at published
third-party Gemma prices (the Gemini API does not list a price for Gemma).

## The ten tasks

| # | Task | Checks passed | Abilities asked for / expected | Biggest problem | Cost (billed tokens, est.) |
|---|---|---|---|---|---|
| 1 | Run a Fibonacci function | 5/5 | 1 / 1 | None: honest "not executed", correct number | 31k, ≤ $0.04 |
| 2 | Chicago weather + °C | 4/5 | 1 / 2 (+ calc) | Web search never offered, so no weather at all; 3 planning rounds | 68k, ≤ $0.08 |
| 3 | Read a PDF, list agents with pages | 3/5 | 1 / 1 | Made-up agent names and page numbers | 44k, ≤ $0.06 |
| 4 | Excel file with totals | 3/5 | 1 / 3 | Totals worked out, then left out of the answer | 38k, ≤ $0.05 |
| 5 | Bar chart as PNG | 4/5 | 1 / 3 | A made-up source tag "[S1]" on correct figures | 40k, ≤ $0.05 |
| 6 | Exchange rate + email | 3/5 | 2 / 3 | No rate (web search not offered); missing email tool not mentioned | 48k, ≤ $0.06 |
| 7 | Route, drive times, fuel cost | 3/5 | 2 / 3 | Distances from memory, step marked "done" | 44k, ≤ $0.06 |
| 8 | Analyse this GitHub repo | 4/5 | 2 / 3 | Nothing produced (the repo pages were never fetched) | 24k, ≤ $0.03 |
| 9 | 5-slide PowerPoint deck | 2/5 | 1 / 4 | Invented a company brand (colours, fonts, logo) | 47k, ≤ $0.06 |
| 10 | Frameworks → sheet → chart → Word → email | 3/5 | 5 / 7 | Step 1 stuck, so every later step stuck; nothing delivered | 70k, ≤ $0.09 |

The checks were: **asked** for the right abilities (7 of 10 tasks passed), **kept** them through review (10/10),
stayed **honest** (6/10), stayed **useful** (4/10), **reported** every gap (7/10).

## The five problems that matter most

1. **The team is never told it has web search.** The planner sees only "calc" and "echo", so it asks for a "weather
   search", a "currency API" or a "PDF reader" instead. The web search that is switched on is handed only to a request
   literally called "web_search". Five tasks came back empty that web search could have helped (weather, PDF,
   exchange rate, repo, the full chain).
2. **Gaps get filled from memory, labelled only "[unverified]".** The PDF task names two agents that are not in the
   paper and gives page numbers for them. The deck task invents brand colours, fonts and a logo position. The label
   is there, but the answer is still wrong.
3. **A step can be "done" without the tool it needed.** The route step produced distances with no routing tool,
   and the slide designer produced a design with no slide tool. Neither said "blocked", so neither gap reached the
   Limitations section.
4. **Made-up source tags survive.** In the chart task a helper wrote "[S2]" to mean "step 2", and the final answer
   cites "[S1]", a source that never existed. The code noticed both and removed neither.
5. **Nothing is ever asked for as a "skill".** Excel, Word, PowerPoint and brand style were all requested as tools or
   not at all (0 skill requests in 23). This matters for round 2: the pool matches skills only to skill requests, so
   no skill can be picked.

Next in line: the final answer drops work already done when a later step fails (task 4); the plan reviewer keeps
asking for "calc" to be requested because it is never shown the installed tools (two extra rounds in task 2); and
failed checks trigger re-work that cannot succeed while a tool is missing (6 runs).

## Where the pipeline starts to break

- **Task 2 (one missing data source) is where answers go empty.** A task needing live data gets nothing back, because
  the web search is never offered.
- **Task 3 is the first dishonest answer.** The PDF could not be read, but page numbers were given anyway.
- **Task 9 is the first invented deliverable.** The brand style needs something only the company has; the team
  assumed one and wrote it in.
- **Task 10 (seven gaps in a chain) collapses.** The first step is blocked, every later step waits for it and
  blocks too, and three rounds of re-work change nothing.

## What worked, and should be kept while fixing

- **No false claims of action in any run:** no "the code ran", no "file saved", no "email sent". Every run that
  could not produce a file or email said so.
- **Reviewers never talked the team out of a request:** 0 dropped out of 17.
- **Blocked parts were marked "BLOCKED" in 8 of 10 runs**, and every answer has a Limitations section. Plain code
  added gaps the writer forgot.
- **Arithmetic was right whenever done:** lane totals, fuel gallons and cost.
- **The one web search that ran (diesel price) was cited.**
- **Planning is solid:** no crashes, no cut-off replies, and only one rate-limit wait, handled. Requirements matched
  the task every time (the intake check passed on all 10), roles were fully defined, and the reviewers correctly
  separated the summariser from tool-using roles.

## What round 2 (with the pool) should and should not fix

**Should help:** tasks needing a remote data tool, where a free server exists: weather, exchange rates, routing, the
GitHub API, perhaps a PDF reader. That covers tasks 2, 3, 6, 7, 8 and part of 10. About 12,400 of the 35,643
registry servers pass every safety rule. The picker still has to choose one of them, and the planner's names still
have to share words with the server descriptions.

**Cannot fix:**
- **Skills.** The planner never asks for a skill (problem 5), the skills list could not be fetched in this
  environment (GitHub API access), and the Office-format skills in anthropics/skills come with scripts. Scripts
  are refused without a sandbox.
- **Anything needing a key that isn't set.** Most email servers need one (about 1,700 servers need a key).
- **File writing**, which has been off since D7 and has no sandbox.
- **Company-specific inputs** such as the brand guide, which must come from the user.
- **The pipeline problems above (2 to 4, and the dropped work).** They sit in Box 2 and Box 3 and do not depend on
  which tools exist.

**A fair comparison needs one thing noted:** web search stays hidden from the planner in round 2 as well. The pool
cannot fill a request named "web_search" because that tool is already installed.
