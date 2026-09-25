# Observer round 1 — capabilities asked for vs expected

Legend: **asked** `name` (kind) · **existing** = an installed tool was used instead · **folded** = covered by another
request's description, not asked on its own · **never** = not asked and not done · — = not expected for this task.
No request was dropped by the Observers in any run (requests_dropped_by_observers = 0 everywhere; 17 distinct
names proposed in round 1 across the ten runs, all kept), so the "dropped" column is empty and left out.

| Task | Code runner | Data / API source | calc | Document format | File writing | Chart / plot | Email | Other |
|---|---|---|---|---|---|---|---|---|
| r1-code-run | asked `python_interpreter` (tool) | — | — (not expected; unused, though it could have checked F50) | — | — | — | — | — |
| r1-weather | — | weather API: asked `weather_search` (tool) | existing, never reached (no data); also *requested* `calc` (tool) | — | — | — | — | — |
| r1-pdf-read | — | — | — | PDF reader: asked `pdf_reader` (tool) | — | — | — | — |
| r1-xlsx | — | — | existing (1 call) | xlsx skill: asked as **tool** `excel_generator` | folded (excel_generator) | — | — | — |
| r1-chart | asked `code_interpreter` (tool) | — | existing (4 calls) | — | folded (code_interpreter) | folded (code_interpreter) | — | — |
| r1-fx-email | — | FX source: asked `currency_api` (tool); web_search not used | *requested* `calc` (tool), never used | — | — | — | asked `email_service` (tool) | — |
| r1-route | — | routing: asked `route_engine` (tool); fuel price: asked `web_search` (tool) → **existing, used, cited** | existing (1 call) | — | — | — | — | — |
| r1-repo | asked as `python_code_analyzer` (tool) | GitHub: asked `github_repo_reader` (tool) | — | — | — | — | — | file reading: folded (repo reader) |
| r1-deck | — | — | existing (1 call) | pptx skill: asked as **tool** `presentation-generator` | **never** | **never** | — | brand style skill: **never** (invented) |
| r1-full-chain | **never** | GitHub: asked `github_api_tool` (tool); web_search: **never** | — | xlsx: asked as **tool** `spreadsheet_tool`; docx: asked as **tool** `word_doc_tool` | folded (format tools) | asked `chart_tool` (tool) | asked `email_tool` (tool) | — |

## Totals

- Expected capabilities (rubric): 30 across the ten tasks. Asked (under some name and kind): 15; existing tool used
  or available instead: 5 (calc in r1-weather, r1-xlsx, r1-fx-email, r1-route; web_search for the fuel price in
  r1-route); folded into another request's description: 5; never asked: 5 (r1-deck's chart, file writing and brand
  style; r1-full-chain's web_search and code runner).
- Requests with **kind "skill": 0 of 23** request records. Every document-format capability (xlsx ×2, docx, pptx) and the brand style
  was asked for as a tool, or not at all.
- Installed tools recorded as missing: `calc` twice (r1-weather, r1-fx-email), both after the Plan Observer asked for
  it.

## Request names, standard name and mapping (for `amoeba/capabilities/aliases.yaml` later)

Mapped (2 of 18 distinct names): `python_interpreter` → code_execution, `web_search` → web_search.

Unmapped (16, including the installed `calc`), with the standard name they most likely belong to:

| Name as written | Task | Likely standard name |
|---|---|---|
| `code_interpreter` | r1-chart | code_execution |
| `python_code_analyzer` | r1-repo | code_execution |
| `weather_search` | r1-weather | weather_api (new) — or web_search |
| `currency_api` | r1-fx-email | fx_rates (new) — or web_search |
| `route_engine` | r1-route | routing (new) |
| `pdf_reader` | r1-pdf-read | pdf_reader (new) |
| `github_repo_reader` | r1-repo | github_api (new) |
| `github_api_tool` | r1-full-chain | github_api (new) |
| `excel_generator` | r1-xlsx | xlsx (new; skill) |
| `spreadsheet_tool` | r1-full-chain | xlsx (new; skill) |
| `presentation-generator` | r1-deck | pptx (new; skill) |
| `word_doc_tool` | r1-full-chain | docx (new; skill) |
| `chart_tool` | r1-full-chain | chart (new) |
| `email_service` | r1-fx-email | email (new) |
| `email_tool` | r1-full-chain | email (new) |
| `calc` | r1-weather, r1-fx-email | calc (installed — should never be requested) |
