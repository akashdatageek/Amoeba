# Observer round 2b — pool on, with the D60 pick fixes

Round 2's setting with one change: **D60**.
- Candidates are vetted *before* the pick, and the picker sees only the best 5 that pass.
- The pick gets 6,000 tokens of room, plus one retry when it is cut off.
- `side_effect` also refuses tools that create or change things in an outside service.

Everything else is identical to round 2:
- the same ten tasks, flags and model (Gemma 4 31B);
- round 1's own Box 2 drafts reused (`--drafts-from eval/round1/runs --draft-pick 0`);
- cache namespace `observer-r2b`;
- the $5 guard.

Box 1, Box 2, C1 and C2 are therefore the same as in rounds 1 and 2 by construction. Run folders are in
`eval/round2b/runs/`, facts in `eval/round2b/facts/`, and the dry run in `eval/round2b/dryrun.json`.

**Code that ran:** `30e73f9` (D60), with the extractor at `7d043e1`; neither changes pipeline code.

## Checks next to rounds 1 and 2

Rubric `eval/round1/rubrics.yaml` (unchanged). C6 "Filled and used" means the pool filled at least one request and
its helper called what was attached.

| Task | R1 | R2 | **R2b** | C1 | C2 | C3 | C4 | C5 | C6 | What changed in 2b |
|---|---|---|---|---|---|---|---|---|---|---|
| r1-code-run | 5/5 | 5/5 | **3/5** | pass | pass | fail | pass | fail | fail | Step 1 ended `done` with no BLOCKED line; Limitations no longer say the code was not run |
| r1-weather | 4/5 | 4/5 | **4/5** | pass | pass | pass | **pass** | fail | **pass** | The cited forecast reached the answer (highs 17.2 / 17.1 / 19.0 / 20.6 °C [S1], matching the tool). No Limitations section, and "current weather" is today's forecast high: the missing current conditions are not named |
| r1-pdf-read | 3/5 | 4/5 | **4/5** | pass | pass | pass | fail | pass | fail | As round 2: honest "unavailable" |
| r1-xlsx | 3/5 | 3/5 | **3/5** | fail | pass | pass | fail | pass | fail | As before; totals again left out of the answer |
| r1-chart | 4/5 | 5/5 | **5/5** | pass | pass | pass | pass | pass | fail | As round 2 |
| r1-fx-email | 3/5 | 3/5 | **4/5** | pass | pass | pass | **pass** | fail | **pass** | A real rate: USD→INR 95.82 [S3] (Frankfurter / ECB via fx-converter-mcp), $2,500 = ₹239,550. The missing email sender is still not named |
| r1-route | 3/5 | 3/5 | **3/5** | pass | pass | fail | pass | fail | fail | As before: distances from memory in a `done` step |
| r1-repo | 4/5 | 4/5 | **4/5** | pass | pass | pass | fail | pass | fail | As before |
| r1-deck | 2/5 | 2/5 | **2/5** | fail | pass | fail | pass | fail | fail | Brand invented again (#002366, Teal, Coral). The slide server picked was refused as `side_effect` |
| r1-full-chain | 3/5 | 3/5 | **3/5** | fail | pass | pass | fail | pass | fail | As before |
| **Total** | **34/50** | **36/50** | **35/50** | 7 | 10 | 7 | **6** | 5 | **2/10** | |

- **C4 (still useful) rose from 4 to 6.** Both gains are pool data that reached the answer, and that is the pool's
  doing: weather and FX.
- **C6 rose from 1 to 2.**
- **C3 and C5 fell by one each.** Code-run's step ended `done` without a BLOCKED line, and weather's answer has no
  Limitations section.
  - These are the Box 3 "done without the tool" and "gaps not reported" problems (round 1 issues I8 and I15).
  - Sampling decides whether they show up in a given run; the pool did not cause them.

## What the pool did (all 23 requests)

| Task | Request → helper | Shown to the picker (all passed vetting) | Picked | Outcome |
|---|---|---|---|---|
| code-run | python_interpreter → Developer, QA | xmp4, sandboxapi-mcp, wikimint, hal9ai run-python, context7fork | sandboxapi-mcp ×2 | `connect_failed` ×2 |
| weather | weather_search → Weather Data Specialist | weather-mcp-china, **weather-mcp**, predictionmarketspicks weather, datakoot us-weather, bluegamma | weather-mcp | **filled, 1 call, cited [S1] in the answer** |
| weather | calc → Data Analyst | — | — | `registered_tool` |
| pdf-read | pdf_reader → Analyst, QA | agent-web, sadri-dridi ×4 | NONE ×2 | `pick_none` (a real NONE; not cut off) |
| xlsx | excel_generator → Excel Engineer | sadri-dridi file-*-ok ×4 | NONE | `pick_none` |
| chart | code_interpreter → Visualization Engineer | png-magic, netcafe-images, sandboxapi-mcp, run-python, xmp4 | sandboxapi-mcp | `connect_failed` |
| fx-email | currency_api → Currency Specialist | datakoot fx, bluegamma, currency-intel, **fx-converter-mcp**, pianam exchange-rate | fx-converter-mcp | **filled, 5 calls, cited [S3] in the answer** |
| fx-email | email_service → Communications Lead | sadri-dridi compose-ok, prismix-status | NONE | `pick_none` |
| fx-email | currency_api → Quality Auditor | datakoot fx, frankfurtermcp, api-evangelist, publicdataoracle, shotanvil | datakoot fx | `side_effect` (a tool its server lists acts outside, checked at connect time) |
| fx-email | calc | — | — | `registered_tool` |
| route | route_engine → Logistics Specialist | mph-to-kmh, range-bytes, tz-mexico-city, muni-mcp, one-minute-akari | NONE | `pick_none` (none is a router) |
| route | web_search | — | — | `registered_tool` (used; diesel $6.5019 [S2]) |
| repo | github_repo_reader → Static Analysis Engineer | a2awire trending, agent-web, content-loc, github-repo-shape, github-repo-intelligence | NONE | `pick_none` |
| repo | python_code_analyzer | sadri-dridi ×5 | NONE | `pick_none` |
| repo | github_repo_reader → Architect | a2awire, github-repo-intelligence, github-repo-shape, github_public_repos_mcp, compuute | github_public_repos_mcp | `connect_failed` |
| deck | presentation-generator → Designer | anthropics/skills:brand-guidelines, slideforge, canvora | slideforge | `side_effect` at connect time |
| full-chain | github_api_tool, spreadsheet_tool, chart_tool, email_tool | mostly sadri-dridi and unrelated | NONE ×4 | `pick_none` |
| full-chain | word_doc_tool → Technical Writer | markovo, bson-ok, url-path-len, sumoffice, tensormaster pdf | sumoffice | `side_effect` at connect time |

**Totals**
- 20 picks: 7 ids and 13 NONE.
- 2 filled, and both were used.
- Refusals after the pick: 3 `connect_failed` and 3 `side_effect` (both checked at connection time).
- **Every pick was a candidate that passed vetting**, against 2 of 15 in round 2.
- **All 20 replies ended normally**, against 3 cut off in round 2.
- Pick cost: 17,091 tokens, against 29,364.

### Each pool tool call: host, what was sent, cited or not

| Task | Tool | Host | Sent | Came back | In the answer with its source id? |
|---|---|---|---|---|---|
| weather | weather-mcp · get_forecast | ads.getlulu.dev | `{"city": "Chicago", "days": 4}` | S1: 4 days, highs 17.2 / 17.1 / 19.0 / 20.6 °C, overcast | **Yes**, every high [S1] |
| fx-email | fx-converter-mcp · get_exchange_rate (×3) | ads.getlulu.dev | `{"from_currency": "USD", "to_currency": "INR"}` | S1: tool error "Output validation error: outputSchema defined but no structured output returned" (a server bug) | No (an error) |
| fx-email | fx-converter-mcp · convert_currency | ads.getlulu.dev | `{"amount": 1, …}` | S2: rate 95.82, 2026-09-25, "Frankfurter (ECB)", **plus a "Sponsored" ad text** | No (used S3 instead) |
| fx-email | fx-converter-mcp · convert_currency | ads.getlulu.dev | `{"amount": 2500, …}` | S3: converted 239,550, rate 95.82, plus an ad | **Yes**, "95.82 [S3]" |

## New problems (added to round 2's P0–P9)

- **P10: servers that pass vetting but cannot be used.**
  - `sandboxapi-mcp` (×3) and `github_public_repos_mcp` failed to connect.
  - Datakoot, slideforge and sumoffice list an acting tool at connection time.
  - The picker cannot know either in advance. Each such pick is one AI call spent on a request that stays unfilled.
- **P11: tool results carry adverts.** fx-converter-mcp adds a "Sponsored" block to every result ("Property investment
  opportunities…", "Book airport transfers…"). It stays inside the POOL DATA block and the helper ignored it, but ad
  text now reaches the prompt.
- **P12: a server's own tool is broken.** `get_exchange_rate` failed 3 times with a schema error before the helper
  switched to `convert_currency`. That cost 3 calls of the step's cap, and the verifier (Quality Auditor) got no tool
  of its own.
- **P13: a paid host is not on the list.** `api.shotanvil.com` answers 402 "payment required" but is not on
  `paid_hosts`. It was shown to one picker and not picked.
- **Unchanged from round 2:** keyword matches are still flooded by one publisher's near-empty "sensor" servers (P3).
  For xlsx, python_code_analyzer and chart_tool, *all* shown candidates were of that kind, and the picker rightly
  answered NONE.

## Cost

| Task | Run | Calls | In | Out | Reasoning | Billed | Est. cost | Wall |
|---|---|---|---|---|---|---|---|---|
| r1-code-run | 310b9d2e | 12 | 14,400 | 4,725 | 30,109 | 49,234 | $0.013–$0.066 | 16.2 min |
| r1-weather | 5f036936 | 20 | 33,673 | 6,325 | 31,545 | 71,543 | $0.016–$0.090 | 17.9 min |
| r1-pdf-read | f781b1a4 | 8 | 7,287 | 1,195 | 4,270 | 12,752 | $0.003–$0.015 | 7.7 min |
| r1-xlsx | 98ed43a6 | 13 | 18,585 | 5,579 | 22,102 | 46,266 | $0.011–$0.060 | 13.9 min |
| r1-chart | 580fa736 | 12 | 12,712 | 2,923 | 16,021 | 31,656 | $0.008–$0.041 | 8.9 min |
| r1-fx-email | ab3cc261 | 21 | 33,822 | 3,686 | 25,810 | 63,318 | $0.013–$0.077 | 14.1 min |
| r1-route | bb945441 | 9 | 11,851 | 2,121 | 10,125 | 24,097 | $0.005–$0.030 | 5.8 min |
| r1-repo | 111a0160 | 9 | 8,080 | 1,444 | 5,306 | 14,830 | $0.003–$0.018 | 3.3 min |
| r1-deck | 3f3706d8 | 8 | 14,890 | 7,870 | 9,989 | 32,749 | $0.007–$0.041 | 9.6 min |
| r1-full-chain | c3c15847 | 19 | 19,789 | 3,558 | 16,754 | 40,101 | $0.009–$0.050 | 9.9 min |
| **Total** | | **131** | **175,089** | **39,426** | **172,031** | **386,546** | **$0.09–$0.49** | **107 min** |

Prices are the same third-party Gemma 4 31B estimates as rounds 1 and 2, with reasoning priced as output.
