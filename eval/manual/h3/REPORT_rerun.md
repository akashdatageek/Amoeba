# H3 (EV trucks), re-run after the D121 fixes

Run `3fcf80bb-1770-4bc5-a42b-3bbbb1fcc2f1` · code `96e2b17` (PR #38: the two Box 4 fixes) · Oct 11, 2026,
06:55–08:46 UTC. Same command as the first run (`REPORT.md`, run `fe375170`), same cache, so Box 1, the planning search
and Box 2 replayed for free and are identical to run 1.

**Result in one line:** the fixes worked. Step 1 was not stopped this time, and the team worked through steps 1–4. The
check step (4) caught real errors (the federal 45W credit expired on Sept 30, 2025) and sent steps 1–3 back for
rework, and the corrected TCO came out at **$480,067 for diesel vs $678,831 for battery-electric per truck over 7
years: keep diesel**. The run then **hit the 600,000-token cap** (`error: budget`, status `agent_error`) while
re-checking step 4. Step 5 (the final memo) never ran, so `result.json` has **no answer**: the numbers above sit in
`artifacts/step_3.md`.

| | |
|---|---|
| Status / error | `agent_error` · `budget` (`budget_stop`: 607,618 of 600,000 tokens, 63 live calls) |
| Billed tokens | 607,618 (389,303 input, 48,200 output, 170,115 hidden reasoning); 13 calls replayed free |
| LLM calls | 76 (63 live) |
| Wall time | 110.5 min |
| Web | 24 searches, 35 page fetches, 4 data files |
| Cost | $0.00 (no price set) |

## Box 1, planning search, Box 2

These were identical to run 1 (replayed from the cache): no ambiguous entities; the planning search decided `not_needed` ("The steps required to calculate a total cost of ownership (TCO) are standard …", 1,341 tokens); 3 drafting rounds, 13 requirements, the same 5 roles and 5 steps. See `REPORT.md` for the quotes.

## Box 3: execution (attempts in time order)

| # | Attempt | Status | Tool calls | Why not done | Output (excerpt) |
|---|---|---|---|---|---|
| 1 | step 1 (first) | partial | web_search ×1 ok | `mislabelled citation: '7.0' not in S2; '2.0' not in S2` | `\| Class 8 BEV Purchase Price \| 400,000 \| USD \| Industry Average [unverified] \|` |
| 2 | step 2 (first) | partial | web_search ×2 ok, calc ×1 failed | `mislabelled citation: '$150,000' not in S18; …` | "**150kW DC Fast Chargers (DCFC)** are selected." |
| 3 | step 3, try 1 | partial, **stuck** | calc ×3 **failed** | `mislabelled citation: '$231,000' not in S2; …` | `\| Purchase Price (Net) \| $180,000 [unverified] \| $360,000 \|` |
| 4 | step 3, try 2 (8 turns) | partial, **stuck** | calc ×5 failed | the same | the same table |
| 5 | step 3 (first, after a rule) | partial | calc ×4 **ok** | `mislabelled citation: '420,000' not in S2; …` | the same figures, now computed |
| 6 | step 4 (first) | partial, verdict **FAIL** | web_search ×4 ok / 1 failed, calc ×4 failed | `lacked: docx_generator; disputed, unresolved: …` | "2. Step 1: The Federal Commercial Clean Vehicle Credit (45W) of $40,000 is applied to a 2026 purchase, but independent verification indicates th…" |
| 7 | step 1 (rework by step 4) | partial | web_search ×4 ok | `mislabelled citation: '180,000' not in S51; …` | `\| Federal Commercial Clean Vehicle Credit (45W) \| 0 \| USD \| [S43], [S45] \| 2026 (Expired 2025-09-30) \|` |
| 8 | step 2 (rework) | partial | web_search ×2 ok | `mislabelled citation: '150' not in S10; …` | "According to the *EV Fleet Charging Infrastructure Guide 2026* [S89] …" |
| 9 | step 3 (rework) | partial | calc ×4 ok | `lacked: docx_generator; mislabelled citation: '$401,500' not in S51,S79; …` | the final table below |
| 10 | step 4, re-check | partial, verdict **DISPUTED**, **stuck** | none | `lacked: docx_generator; unverified check: PASS with no re-checking tool call …; disputed, unresolved: …` | "Verdict: PASS / Issues: none / … Diesel: $180,000 (Purchase) + $237,067 (Energy) + $63,000 (Maintenance) = $480,067." |

Step 5 (Final Delivery) did not run.

**The final TCO table** (`artifacts/step_3.md`, after the rework):
```
| Purchase Price (Net) | $180,000 [S51, S79] | $401,500 | … BEV: $420,000 [S20] - $18,500 [S41] - $0 [S43, S45] = $401,500 |
| Energy Cost (7-Year) | $237,067 | $101,031 | Diesel: (420,000 mi / 6.75 MPG [S84]) * $3.81/gal [S63] …; BEV: (420,000 mi * 1.7 kWh/mi [S72]) * $0.1415/kWh [S26] |
| Maintenance (7-Year) | $63,000 | $37,800 | …
| Infrastructure | $40,000 | $138,500 [S10, S9, S94, S17] | Per-truck share of depot charging installation …
| **Total 7-Year TCO** | **$480,067** | **$678,831** | Diesel: $180,000 + $237,067 + $63,000 = $480,067; BEV: … = $678,831 |
```
Recommendation (step 3): "it is recommended that the carrier **do not** replace the current diesel fleet with
battery-electric vehicles (BEVs) at this time." BEVs save about $23,034 a year per truck to run, but cost $221,500 more
to buy now that the federal 45W credit has expired [S45], plus $138,500 per truck for charging.

## Box 4: adaptation

There were 5 stuck events. **None was the false capability gap from run 1**, and the fix proposer's reply was read
correctly. Both fixes held.

| Step | Cause | Evidence | Fix tried | Result | Tokens |
|---|---|---|---|---|---|
| 3 | tool_error | "TCO Modeler: calc failed twice in a row with the same error: error: invalid syntax" | more turns (5 → 8), code rung 1 | failed: still stuck | 36,495 |
| 3 | tool_error | the same | **proposer, add_role_rule**: "When using the calc tool, provide only a pure mathematical expression. Do not include currency symbols ($), commas, units, or any descriptive text in the input." | **the calc errors stopped** (4 ok calls); the step was then "not stuck but partial" (mislabelled citations) | 22,098 |
| 4 | capability (with repeated_error, no_file_change) | "lacked: docx_generator", "requested capability docx_generator for Quality Auditor: unfilled (pick_none)", "the output line asks for a file (docx: Final Memo File) and none was made" | grant_tool, code rung 2 | failed: "the pool shortlist had nothing to attach for docx_generator" | 0 |

The step 4 capability gap is **real** this time: no tool in the run or the pool makes a .docx file (the picker chose
none). The next rung (the fix proposer) never ran, because the token cap stopped the run first. Nothing recovered
outright, and adaptation used 58,593 tokens.

## Box 5: around every box

All 76 calls went to `gemma-4-31b-it` (routed: 76 decisions, 0 fallbacks). `verifier_same_family: 20`, meaning the
checker was the same model family as the workers in 20 calls, with no alternative model available. 32 s were spent in
cooldown after rate limits, and 11 `rate_limited` events were all recovered. Billed tokens by agent: Quality Auditor
282,861 (20 calls), TCO Modeler 188,236 (24), Infrastructure Engineer 70,429, Fleet Market Analyst 62,056, planner
44,051, observers 34,066, fix proposer 4,036.

## Final

`answer: ''` (empty) · `status: agent_error` · `error: budget` · 607,618 billed tokens · 76 calls · 110.5 min.

## What looks wrong or missing

1. **The run spent its budget before the deliverable.** Box 4's in-task fixes and the check step's rework both
   consume the run's token cap, and no reserve is kept for the final step. The 600k cap fell between step 4's re-check
   and step 5, so a run that had a good TCO table ended with no answer at all. A run stopped by the budget could still
   assemble an answer by code from the finished steps (D41's `assemble_by_code` exists for a related case).
2. **False disputes cost the most tokens (Quality Auditor, 283k).** The disagreement resolver (D109) paired figures
   that only share a label word. "range: step 2 $35 vs check $325,000" pairs a charger cost with a truck price, and
   "diesel: step 3 420,000 vs check 6.5" pairs miles with MPG. There were 16 `dispute_resolution` events. Matching
   figures by unit and label as well, not by one shared word, would remove most of them.
3. **The re-check made no tool calls and was marked "unverified check".** On re-check, step 4 said PASS with no
   re-checking tool call (D65), then DISPUTED because of item 2.
4. **The .docx deliverable had no tool behind it from the start.** Box 2 asked for `docx_generator`, the pool had
   none (`pick_none`), and the plan still put a docx file on step 4. With local tools on, the xlsx/docx skills (D69)
   would cover it; this command ran without `--local-tools`.
5. **Mislabelled citations are on every attempt and are never fixed.** Each attempt ended partial for figures not
   found in the source they cite. Most are computed values (`$231,000`, `420,000`) cited to a source that holds only
   their inputs. D104's arithmetic exemption should cover "a result computed from cited inputs" more widely.
6. **The final table has small inconsistencies.** The diesel column lists $40,000 for infrastructure that its total
   leaves out, and one note is garbled ("Diesel: $0.15/mi mi * $0.15/mi").
7. **A real fix worked.** The fix proposer's `add_role_rule` made the TCO Modeler's calc calls succeed (0 of 8 ok
   before it, 4 of 4 after). This is the first live recovery of a tool_error by a proposer edit, even though the step
   then stayed partial for citations.
