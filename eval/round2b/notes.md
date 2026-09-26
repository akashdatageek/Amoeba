# Observer round 2b — working notes

Setup: round 2's settings + D60 (vet before the pick, pick_max_tokens 6000 + one retry, wider side_effect,
clone-only skills). Code at 30e73f9 (D60) / 7d043e1. Cache namespace observer-r2b. Task files as rounds 1–2.

## r1-code-run — run 310b9d2e-7987-4bb1-9957-277566bd3893
- Pool: python_interpreter ×2; picker shown 5 passing candidates (xmp4, sandboxapi-mcp, wikimint, hal9ai run-python,
  context7fork); both picks sandboxapi-mcp (6,000-token room, finish stop, 378/493 reasoning) → connect_failed.
- Box 3: all three steps `done` — step 1 wrote the function and "12586269025 [unverified]" with no BLOCKED line;
  Limitations only say the constants and result are unverified, not that the code was not run (round 1–2 said so).
- Cost: 12 calls, 49,234 billed (14,400 in / 4,725 out / 30,109 reasoning); ≤ $0.07 at the high price.
