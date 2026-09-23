# Box 2 evaluation — gemini-3.1-flash-lite (2026-09-23)

    python -m scripts.eval_draft --tasks tasks/draft_eval.jsonl --repeats 3 --llm openai

This runs drafting only (the Planner, both observers and the plain-code checks), 10 tasks × 3 repeats, with the code
at main 14db642. Gemini's endpoint accepts no seed, so the repeats vary. The raw per-task table is in
`2026-09-23_draft_eval_gemini-3.1-flash-lite.csv`.

| | |
|---|---|
| drafts accepted | **25/30** (0.83) |
| accepted if roles were parsed brace-balanced (proposed D22) | **30/30** |
| rejected drafts | 5: all from the copied role regex dropping a role with `{…}` in its prompt ("roster size 1" ×3, "empty plan" ×2) |
| repair calls for a missing `## Section` / API errors | 0 / 0 |
| mean rounds / consensus (accepted drafts) | 1.92 / 0.68 |
| mean roles / plan steps | 2.12 / 2.16 |
| mean tokens / calls per draft | 7062 / 5.3 (211,866 tokens and 159 calls in total) |

| task | accepted | rounds | consensus | capability requests (final) |
|---|---|---|---|---|
| arith-1 | 1/3 | 1.0 | 1.0 | – |
| reverse-1 | 2/3 | 1.0 | 1.0 | – |
| vowels-1 | 3/3 | 3.0 | 0.0 | – |
| interest-1 | 3/3 | 1.0 | 1.0 | – |
| fx-rate | 3/3 | 1.67 | 1.0 | web_search, WebSearchTool, fetch_market_data (3/3 attempts) |
| papers-rag | 3/3 | 3.0 | 0.0 | web_search, Academic Search Tool (3/3) |
| pdf-summary | 3/3 | 2.0 | 1.0 | PDF Parser (1/3) |
| palindrome-code | 3/3 | 1.33 | 1.0 | PythonInterpreter (1/3) |
| kyoto-trip | 3/3 | 2.67 | 0.33 | calc (1/3), an **existing** tool |
| idiom-translate | 1/3 | 1.0 | 1.0 | – |

## Findings
1. **The format holds and the rejections are ours.** No repair call in 30 drafts. All 5 rejections come from the
   non-greedy role regex copied from environment.py:62, and a brace-balanced parse would have accepted every one.
2. **D19 works on tasks that need a tool.** 8 of the 12 need-a-tool attempts asked for a capability; the other 4 made
   do with calc or echo. No toy task asked for anything. Observers dropped **0** requests between round 1 and the final
   draft. The names are not normalised (`web_search` / `WebSearchTool` / `Academic Search Tool`).
3. **A request for a tool we already have is recorded as a request.** kyoto-trip #0 listed `calc` under Capability
   Requests. `parse_capability_requests` does not check the registry, so it should drop (or mark) registered names.
4. **Rounds and tokens depend on the task, not on the toy/real split.** vowels-1 and papers-rag never reach
   consensus (3 rounds, about 12–14k tokens), while most tasks agree in round 1 (about 3k tokens).
