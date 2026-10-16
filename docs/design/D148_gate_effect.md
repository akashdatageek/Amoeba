# D148 — the gate judges effect, not text

Status: **built** (branch claude/run-gaps). This gap was found in the fuel run 71d2f910.

## Why
The gate refused every Bash command whose text contained `..` or `../`, wherever the path led. In 71d2f910 step 1, a
helper ran `cd sources && python3 -c "open('../eia_weekly.csv', 'w')…"`, which writes inside the workspace, and was
refused as `unsafe_command ('..')`. The refusal named only `..` and gave no way to rewrite the command. The helper
lost turns, and Box 4 counted the refusals as a failing held tool.

## What
- The plain-text `..` rules are removed from `UNSAFE`. Every other gate rule is unchanged: network commands, sudo,
  `rm -rf /`, `cd /`, `cd ~`, `~/`, `$HOME`, absolute paths outside the workspace, and protected configs.
- `escaping_path` follows the command as the shell would:
  - it starts in the workspace;
  - each `cd <dir>` moves the current folder, resolved, so it must stay inside;
  - every relative path containing `..`, as an argument or inside quoted code, is resolved from the current folder.

  Only a path that lands outside the workspace is refused, and the refusal names that exact part (`cd ..`,
  `../../etc/passwd`).
- Every refusal now ends with one line on how to rewrite the call (`REWRITE` in toolbox.py). For unsafe_command:
  "write paths from the workspace root (e.g. sources/S1_page.txt, out/table.csv), no cd out of it, no ~ or system
  paths".

Symlinks are followed by `resolve()`, as for Read and Write. The gate stays a screen, not a jail: the sandbox
(AMOEBA_SANDBOX=1) is what contains a determined command.

## Tests (written first)
tests/test_gate_effect_d148.py.
- **Before the fix**, 7 of 9 tests failed:
  - the four commands that stay inside were refused on `..`;
  - three refusals named only `../` instead of the path;
  - the refusal had no rewrite line.
- **After the fix**, all 9 pass.

The existing gate tests still pass: `cat ../x`, `cd .. && cat result.json` and `cat ../../../../events.jsonl` are
refused, because they land outside the workspace.
