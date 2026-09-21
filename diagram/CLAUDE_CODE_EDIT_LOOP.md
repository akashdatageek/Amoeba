# Per-box change requests for the architecture pages

1. Serve the page and collect requests:
       python serve_edits.py amoeba_phase1.html        # opens on http://localhost:8765
   Clicking any inner box, or the pencil on a top-level box, opens a text field. "Send" appends
   {view, box, request, ts, page, status:"pending"} to edits.jsonl next to the HTML file.
   (On the published claude.ai copy there is no server; requests queue in the browser and
   "Copy edits" puts the same JSON lines on the clipboard — paste them into edits.jsonl.)

2. Apply them (instruction to Claude Code):
   > Read edits.jsonl. For each line with status "pending": find the box by `view` (svg id `v-<view>`)
   > and `box` (its `.t`/`.t2` title) in amoeba_phase1.html, make the requested change to that box —
   > its text, its hover card (`data-tip`), its arrows or caps — and, if the request changes the system
   > rather than the picture, make the matching change in BUILD_SPEC_PHASE1.md. Keep text inside the box
   > width (≈5.6 px per character at 11 px). Set the line's status to "applied" with a one-line `note`,
   > or "skipped" with a reason. Re-render once with Playwright at 1240 px to check nothing overflows.
