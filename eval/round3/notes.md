# Observer round 3 — working notes

Setup: round 2b + `--local-tools on` (AMOEBA_SANDBOX=1). claude mcp serve 2.1.283; exposed local:Bash, Read, Write,
Edit (no Glob/Grep offered); 19 other tools refused once each. Skills: the anthropics/skills clone only. Cache
namespace observer-r3.

## r1-code-run — run 16513eee-b734-4db8-86ab-3bec63f29544
- Pool: python_interpreter ×2 → local:Bash first by alias (score 100); the picker chose local:Bash both times; filled 2/2.
- Box 3: the Developer wrote solution.py with a heredoc and ran it: stdout "12586269025" (the correct F50).
  QA's check call failed: it wrapped its command in a ```bash fence, which Bash ran literally (is_error).
- files_created: solution.py (step 1). Opened and run by the observer: prints 12586269025. Matches the task.
- Answer: "The 50th Fibonacci number is 12586269025 [S1]" — but a local tool result gets no source id, so [S1] is a
  made-up citation (provenance: 3 hallucinated citations). The figure itself is the real output.
- Cost: 10 calls, 28,511 billed (10,361 in / 2,547 out / 15,603 reasoning).
