# Observer round 2 — working notes

Setup (for runs.md):
- Code that ran: `7b2c13e` (D58 complete: git-clone skills, cross-kind matching, side_effect / paid_endpoint vetting,
  pick read after Gemma's <thought> block). Page regenerated in `0651bef`.
- Pool cache: `python -m amoeba pool refresh` at 2026-09-25T22:37:45Z — 35,703 tools, 19 skills (9 instruction-only);
  the run saw 35,722 entries (tools + skills). data/pool/ in the working tree (gitignored); pins.json written by the
  run (trust on first use).
- Command: round 1's exact flags + `--pool --drafts-from eval/round1/runs --draft-pick 0`, cache namespace
  `observer-r2`. Task files as in round 1 (line 1, lines 2–10). AMOEBA_* variables unset, as in round 1.
- Drafts reused: every task gets round 1's Box 2 draft (`draft_reused` event), so Box 1/2 and C1/C2 are identical
  by construction; only Box 3 (and the pool step at its start) differs.

Void run (not counted): `eval/round2/void/r1-code-run__478893ad-before-thought-fix/` — the first round-2 attempt at
task 1 (commit 3ca96a6/275f975), stopped by hand after the pool step: both picks were parsed as NONE because Gemma
wrote "<thought>…</thought>io.github.lu-zhengda/mcp-python-exec-sandbox". Fixed pool-side in 7b2c13e (D58 (4)) and
task 1 rerun; its two pick replies came from the observer-r2 cache (same text, 0 tokens).

## r1-code-run — run e4669ee7-dfe1-48cf-a73d-c720a5b9b386 (23:03–23:13)
- Pool: 2 requests (python_interpreter for Developer and QA), top-5 candidates all code runners; the picker chose
  io.github.lu-zhengda/mcp-python-exec-sandbox both times → vet `not_remote` (a local package). The only remote
  candidate (Br0ski777/code-sandbox on klymax402) is a paid endpoint. Filled 0.
- Box 3 as round 1: step 1 partial (BLOCKED interpreter), verify done, answer 12586269025 [unverified]; code comments
  again carry [unverified] tags. Limitations name python_interpreter.
- Cost: 8 calls (2 cached), 23,133 billed.
