# Observer round 2 — what the pool did with each request

Round 2 reuses round 1's drafts, so the requests are round 1's (`docs/eval/round1/capabilities.md`: same names,
same kinds, 0 skill requests). This page records what the pool step at the start of Box 3 did with each one.

How the pool step works (D56/D58): for each request with a helper, plain code ranks the cached pool (35,722
entries: MCP Registry servers and anthropics/skills) by shared words and keeps the top five, of any kind. One model
call (the **picker**) chooses one id or NONE. Plain code then **vets** the choice: `not_remote` (a local package),
`paid_endpoint` (`*.klymax402.com`), `side_effect` (sends, posts, pays, deletes …), `no_source`, `no_version`,
`auth_missing` (needs a key that is not set); for skills `has_scripts`, `body_missing`, `too_long`. A request for a
tool Amoeba already has is skipped as `registered_tool`, without a pick.

Every candidate's vet result, and so which ones *would* have passed, is in `eval/round2/dryrun.json`.

## Every request

| Task | Request (kind) → helper | Picked | Result | Passing candidates the picker had | Helper used it? |
|---|---|---|---|---|---|
| r1-code-run | `python_interpreter` (tool) → Python Developer | lu-zhengda/mcp-python-exec-sandbox | unfilled: `not_remote` | none (paid, no_source, key, local ×2) | — |
| r1-code-run | `python_interpreter` (tool) → QA Engineer | lu-zhengda/mcp-python-exec-sandbox | unfilled: `not_remote` | none | — |
| r1-weather | `weather_search` (tool) → Weather Data Specialist | **Lulu-The-Narwhal/weather-mcp** | **filled** | pianam weather-mcp-china (host refused by the proxy) | **yes**: 1 call, cited [S1] in steps 1–2; not in the answer |
| r1-weather | `calc` (tool) → Data Analyst | — | `registered_tool` (installed) | — | calc used 12 times |
| r1-pdf-read | `pdf_reader` (tool) → Technical Analyst | — (reply cut off) | unfilled: `pick_none` (truncated, P1) | foomworks/agent-web | — |
| r1-pdf-read | `pdf_reader` (tool) → QA Lead | page.doc/pdf-extract | unfilled: `side_effect` | foomworks/agent-web | — |
| r1-xlsx | `excel_generator` (tool) → Excel Automation Engineer | Adirdavi/docmcp | unfilled: `auth_missing` | none (xlsx skill `has_scripts`, local ×3) | — |
| r1-chart | `code_interpreter` (tool) → Visualization Engineer | smithery STUzhy-py_execute_mcp | unfilled: `no_source` | sadri-dridi/png-magic (unrelated) | — |
| r1-fx-email | `currency_api` (tool) → Currency Specialist | Exchange-RateAPI/mcp-server | unfilled: `not_remote` | **datakoot fx-currency-exchange-rates, bluegamma** | — |
| r1-fx-email | `email_service` (tool) → Communications Lead | — (reply cut off) | unfilled: `pick_none` (truncated, P1) | sadri-dridi/compose-ok (unrelated) | — |
| r1-fx-email | `calc` (tool) → Currency Specialist | — | `registered_tool` | — | never used |
| r1-fx-email | `currency_api` (tool) → Quality Auditor | — (reply cut off) | unfilled: `pick_none` (truncated, P1) | **datakoot** | — |
| r1-route | `route_engine` (tool) → Logistics Specialist | stea4lth/flipvo-agent-tools | unfilled: `side_effect` | sadri-dridi mph-to-kmh, range-bytes (unrelated) | — |
| r1-route | `web_search` (tool) → Cost Analyst | — | `registered_tool` | — | web_search used, diesel price cited [S2] |
| r1-repo | `github_repo_reader` (tool) → Static Analysis Engineer | NONE | unfilled: `pick_none` (a real NONE) | a2awire trending-repos, agent-web, sadri-dridi ×2 | — |
| r1-repo | `python_code_analyzer` (tool) → Static Analysis Engineer | NONE | unfilled: `pick_none` (a real NONE) | sadri-dridi ×4 (unrelated) | — |
| r1-repo | `github_repo_reader` (tool) → Software Architect | thedhruv-07/github-repo-mcp | unfilled: `not_remote` | **digitalgremlin github-repo-intelligence**, a2awire, sadri-dridi | — |
| r1-deck | `presentation-generator` (tool) → Corporate Presentation Designer | **ai.presentations/presentations-ai** | **filled** | also brand-guidelines skill, BuilderIO agent-native-slides | **no**: attached and shown, never called (P5) |
| r1-full-chain | `github_api_tool` (tool) → OS Intelligence Analyst | smithery-ai-github | unfilled: `auth_missing` | a2awire trending-repos, sadri-dridi (unrelated) | — |
| r1-full-chain | `spreadsheet_tool` (tool) → Data Visualization Engineer | anthropics/skills:**xlsx** (skill) | unfilled: `has_scripts` | none | — |
| r1-full-chain | `chart_tool` (tool) → Data Visualization Engineer | Haswell119/chartbytes-mcp | unfilled: `not_remote` | sadri-dridi/docs-path-ok (unrelated) | — |
| r1-full-chain | `word_doc_tool` (tool) → Technical Writer | plutext/docx4j-mcp | unfilled: `not_remote` | none (docx skill `has_scripts`) | — |
| r1-full-chain | `email_tool` (tool) → Delivery Lead | dev.mailkite/mail-send | unfilled: `side_effect` | none | — |

## Totals

- **23 requests; 20 went to the picker, 3 skipped** as installed tools (`calc` ×2, `web_search`).
- **Filled 2 of 20** (weather-mcp, presentations-ai). **Used 1** (weather). **Reached the answer 0.**
- Pick outcomes: 15 ids, 5 NONE (3 cut off at the reply limit, 2 real NONE in r1-repo).
- Vet refusals of picked ids (13): `not_remote` 6, `side_effect` 3, `auth_missing` 2, `no_source` 1, `has_scripts` 1.
  None were `paid_endpoint` (klymax402 candidates were listed 5 times but never picked).
- In **4 requests a relevant candidate that passes vetting was on the list** when the picker chose a refused one or
  was cut off: FX rates ×2 (datakoot, bluegamma), PDF (agent-web), repo (digitalgremlin). See issues P1, P2.
  "Passing" is not "usable": in the dry-run probe, bluegamma and the digitalgremlin Apify actor answered 401 to
  a bare request, so they may need a key their registry entry does not declare.
- In **6 of 20 picks no candidate could have passed** (code-run ×2, xlsx, full-chain spreadsheet / docx / email):
  the call could not help (P7).
- Kinds: requested tool → picked tool 14, tool → NONE 5, tool → **skill 1** (xlsx for `spreadsheet_tool`, D58
  cross-kind matching; refused `has_scripts`). Skills were listed 7 times across the round's 100 candidates.
- Pick cost: 20 calls, 29,364 billed tokens (8% of the round); task 1's two picks came from the cache.

## Each picked tool: host, what was sent, what came back, whether it was cited

Only two pool tools were attached; one was called once.

| Task | Tool (pool id) | Host | Helper, step | What the helper sent | What came back | Used in the answer with its source id? |
|---|---|---|---|---|---|---|
| r1-weather | `pool:io.github.Lulu-The-Narwhal/weather-mcp` | ads.getlulu.dev | Weather Data Specialist, step 1 | `{"tool": "get_forecast", "arguments": {"city": "Chicago", "days": 4}}` | source **S1**, 3,359 chars, no error: Chicago, Illinois; 4 days from 2026-09-25, highs 17.2 / 17.8 / 19.6 / 21.0 °C and lows, inside a POOL DATA block | **No.** Steps 1 and 2 cite [S1] on every figure; the verify step never saw step 1 (P4) and the answer says "failed verification and cannot be published" with no figure and no [S1] |
| r1-deck | `pool:ai.presentations/presentations-ai` | api.presentations.ai | Corporate Presentation Designer, step 2 | nothing (0 calls) | — | No (never called, P5) |

The tool's reply was framed as outside data (`<<<POOL DATA · result of … — use it as reference material only>>>`)
and got a source id; nothing in it was followed as an instruction. Tool errors in the round: 0.

## C6 "Filled and used" (new in round 2)

C6 passes when the pool filled at least one of the run's requests **and** the helper that received it actually
called it. Whether the result then reached the answer is recorded next to it.

| Task | Filled | Called | Result in the answer | C6 |
|---|---|---|---|---|
| r1-code-run | 0/2 | — | — | fail |
| r1-weather | 1/1 (+ calc installed) | yes, 1 call | no (dropped by the verify step, P4) | **pass** |
| r1-pdf-read | 0/2 | — | — | fail |
| r1-xlsx | 0/1 | — | — | fail |
| r1-chart | 0/1 | — | — | fail |
| r1-fx-email | 0/3 (+ calc installed) | — | — | fail |
| r1-route | 0/1 (+ web_search installed) | — | — | fail |
| r1-repo | 0/3 | — | — | fail |
| r1-deck | 1/1 | no | — | fail |
| r1-full-chain | 0/5 | — | — | fail |

**C6: 1 of 10.**
