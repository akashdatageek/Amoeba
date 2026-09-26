# Observer round 2 — summary

Round 1's ten tasks again, with one change: the **tool/skill pool is on** (D56 + D58). Everything else is round 1's:
the same model (Gemma 4 31B), flags, web search, cost guard, and round 1's own team drafts reused, so only Box 3 and
the pool step at its start could change. One real run per task. Details in `runs.md`, `capabilities.md`, `issues.md`.

**Overall:** 36 of 50 checks passed (round 1: 34). The two extra passes are not the pool's doing. The pool filled
**2 of 20** requests. **One** filled tool was called (weather), and its data **did not reach the answer**. No
answer got better because of the pool. It caused no crashes, no tool errors and no unsafe calls. Total cost 363k
billed tokens, 118 calls, 112 minutes, about $0.09–$0.47. The 20 picks cost 29k tokens of that. Box 2 was reused,
so it cost nothing.

## Round 1 vs round 2, the five checks

| Check | Round 1 | Round 2 | What changed |
|---|---|---|---|
| C1 asked | 7/10 | 7/10 | Nothing: same drafts |
| C2 kept | 10/10 | 10/10 | Nothing: same drafts |
| C3 honest | 6/10 | **8/10** | pdf-read gave no page numbers; chart cited no made-up [S1]. Both are sampling: the pool did not reach either helper |
| C4 still useful | 4/10 | 4/10 | Weather got a real forecast but the answer dropped it |
| C5 reported | 7/10 | 7/10 | Same gaps unnamed (fx-email email, route routing, deck) |
| **Total** | **34/50** | **36/50** | |
| C6 filled and used (new) | — | **1/10** | Weather only; deck's tool was attached and never called |

## The ten tasks

| # | Task | Checks | Pool: filled / asked | Picked → outcome | What happened |
|---|---|---|---|---|---|
| 1 | Fibonacci | 5/5 | 0/2 | local sandbox ×2 → `not_remote` | As round 1; no usable code runner in the pool |
| 2 | Chicago weather | 4/5 | **1/1** | weather-mcp → **filled, called, cited [S1]** | Real forecast fetched, then the verify step couldn't see it and the answer says "failed verification" |
| 3 | PDF agents | 4/5 | 0/2 | cut off; pdf-extract → `side_effect` | Honest this time; a passing web-page reader was listed |
| 4 | Excel | 3/5 | 0/1 | docmcp → `auth_missing` | As round 1 |
| 5 | Chart PNG | 5/5 | 0/1 | py_execute → `no_source` | As round 1, without the fake [S1] |
| 6 | FX + email | 3/5 | 0/3 | local FX server → `not_remote`; 2 cut off | Two usable FX servers were on the list, not picked |
| 7 | Route + fuel | 3/5 | 0/1 | flipvo → `side_effect` | No router in the pool; distances from memory again |
| 8 | Repo analysis | 4/5 | 0/3 | NONE ×2; local repo reader → `not_remote` | As round 1 |
| 9 | Deck | 2/5 | **1/1** | presentations-ai → **filled, never called** | Brand invented again |
| 10 | Full chain | 3/5 | 0/5 | 5 picks, 5 refusals (incl. the xlsx skill) | As round 1: step 1 stuck, all stuck |

## Why so little was filled

1. **The picker picks what the rules refuse** (P2). Of 15 picked ids, 13 were refused:
   - 6 local packages;
   - 3 that act outside (send, post and the like);
   - 2 needing a key;
   - 1 without a source;
   - 1 skill with scripts.
   In 4 requests a usable candidate was on the same list: FX rates ×2, a web-page reader for the PDF, and a repo
   reader. The picker is never told the rules, and plain code vets only after it picks.
2. **The pick runs out of room** (P1). 3 of 20 pick replies spent the whole 2,048-token reply on reasoning and gave
   no id. The pick passes no reply limit, so the existing "retry with more room" never triggers.
3. **The pool often has nothing usable** (P3, P7). 6 of 20 requests had no candidate that could pass. Examples:
   code runners are local or paid, Office formats are local or skills with scripts, and email senders all act
   outside. Keyword matching also lists unrelated tools: 13 of the 100 listed candidates are one publisher's tiny
   "sensor" servers. Some of those pass vetting.
4. **Skills barely took part.** The planner still asks for tools only; round 2 reuses round 1's drafts. Cross-kind
   matching (D58) listed a skill 7 times and the picker chose one, the xlsx skill. It was refused because it has
   scripts.

## New problems the pool caused or exposed (`issues.md`)

- **P0, fixed during the round.** Gemma writes `<thought>…</thought>` before its pick, so every pick read as NONE.
  Fixed in D58 (item 4). The void run is kept.
- **P1, P2, P3, P7: the pick** (above).
- **P4: a filled result is lost.** Weather's cited forecast was dropped by the verify step and the summariser.
  This is a pipeline problem (round 1 issues I12 to I14) that the pool made visible.
- **P5: an attached tool is not used.** The deck designer saw its slide tool and wrote text instead.
- **P6: vetting gap.** `side_effect` misses tools that *create* things in an outside account; presentations-ai
  passed. This needs your decision.
- **P8: pins are kept outside the run.** A run writes the pool's pins file into the shared cache, not into the run
  folder.
- **P9: computed numbers carry the source tag.** Numbers computed from the tool result were tagged with its
  source id.
- **None seen for:** a tool error, a wrong tool that was actually called, or tool text followed as an instruction.
  The one tool reply was cited [S1] on every figure it gave.

## What worked, and should be kept

- The **safety rules held**:
  - `side_effect` stopped 3 senders or posters;
  - `paid_endpoint` covered 5 listed klymax402 servers (none were picked);
  - `not_remote` stopped 6 local packages;
  - the environment's proxy blocked the one host we chose not to allowlist.
- **The tool path works end to end:** pick, vet, pin, attach, call, then the result goes back to the helper as
  POOL DATA with source id S1, and the helper cites it. Its data was the round's only cited live figures besides
  the route task's diesel price.
- **The picker can say NONE sensibly** (repo, twice), and it can cross kinds (xlsx skill).
- **Round 1's honesty held:** no false claim of a run, a file or an email in any answer.

## What to do next (for decision)

- **Pool-side, small, before a rerun of round 2 (could go into D58 or a new D):**
  - vet the candidates first, show the picker only those that pass, and skip the pick when none do (P2, P7);
  - give the pick enough reply room, or retry once on "length" (P1).
  I have not made either change; they wait for your answer.
- **Pipeline fixes, as planned.** These now start at D60, because D59 is the local toolbox you asked for:
  - web search offered to the planner (I2);
  - "done" without the tool (I8, P5);
  - fake [S#] (I10);
  - filling gaps from memory (I9);
  - skill wording (I3);
  - a verifier that sees the sources of what it checks, with work already done kept in the answer (P4, I12).
- **Decision needed:** should tools that create things in an outside service count as `side_effect` (P6)?
