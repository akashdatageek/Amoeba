# D147 — every cut says where the full copy is

Status: **built** (branch claude/run-gaps). This gap was found in the fuel run 71d2f910.

## Why
In run 71d2f910, the helpers kept re-fetching pages whose answers sat in the part fetch_url had cut off: the EIA
history's newest rows and ATRI's totals. The whole page was already saved in the workspace (`sources/S#_….txt`,
D107), but the cut result never said so. Step 1 never read `sources/S4`. A data-file excerpt showed the first rows
of an oldest-first series, which leaves out the newest values.

## What
- **fetch_url**: a page cut at `max_fetch_chars` now ends with
  `… [N characters cut; the whole page is in sources/S#_….txt; open it with local:Read] …`. The wording follows
  D144's spill note. Without a workspace, the line says the page was not saved.
- **Data-file excerpts**: `table_excerpt` now also shows the table's last 4 rows (in table order), and the excerpt
  ends with `[the whole table is in sources/S#_….csv; open it with local:Read] …`.

The page is now saved before the result is built, so the path is known when the note is written. No site, format or
task is named. The model still decides whether to open the file.

## Tests (written first)
tests/test_cut_notes_d147.py.
- **Before the fix**, 3 of 4 tests failed: the cut page named no file, the no-workspace cut said nothing, and the
  table's last row was missing.
- **After the fix**, all 4 pass.

tests/test_web_tools.py now expects the cut line after the 500 characters.
