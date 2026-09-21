# Amoeba — Phase 1

Amoeba is a research system (DTech thesis, Purdue Northwest) in which a team of AI helpers is drafted per task and, in later phases, reshapes itself under plain-code control. Motto: **first make it, then make it better.** Principle everywhere: **LLM proposes, deterministic code disposes.**

Phase 1 builds three boxes only: **Task → Plan a new team → Team runs the task.** No memory, monitor, gate, or cost handling.

## Read in this order
1. `spec/BUILD_SPEC_PHASE1.md` — the spec. §13 is your instruction. §11 lists deliberate deviations from the source papers.
2. `spec/VERIFICATION_PHASE1.md` — Part B has the pseudocode with `file:line` citations into the source repos; Part C the corrections already folded into the spec.
3. `repo_notes/` — what the source repos actually do (AutoAgents, AgentVerse, ATM's LLM client pattern).
4. `spec/BUILD_SPEC_FULL_reference_only.md` — the whole 8-layer system. Do not build from it; use it only to keep names compatible.

## Setup
    ./clone_sources.sh          # repos/ with AutoAgents, AgentVerse, jiuwen_atm (read-only; never import from them)
    python -m venv .venv && . .venv/bin/activate
    pip install pydantic pyyaml openai pytest playwright

## Rules
- Package name `amoeba`, layout exactly as spec §3. Python ≥3.11, pydantic v2.
- All tests run offline with `MockLLMClient`. No network in tests.
- Copy prompt text verbatim from the cited source files (AutoAgents MIT, AgentVerse Apache-2.0) into `amoeba/config/prompts/`, one source-header line each; keep template and format-example as separate files.
- Never copy code from `repos/EvoMAS` (CC BY-NC) — not cloned here on purpose.
- Add the no-op `listener` parameter to `Interpreter.__init__` (spec §12) so Phase 3 needs no signature change.
- Token counts are recorded in the trace, never enforced (spec §2 "Cost").

## Done when
T1–T11 in spec §9 pass, and `python -m scripts.run_task --toy --seed 0 --n 20 --topology flat` and `... --topology boss_reviewers` both run and print mean score, tokens and LLM calls. Report those numbers and any place you had to depart from spec §5–§6.

## The diagram
`diagram/amoeba_phase1.html` is the living architecture page (drill-down boxes, hover cards, per-box change requests). `diagram/CLAUDE_CODE_EDIT_LOOP.md` says how to serve it and apply the requests that land in `edits.jsonl`. When you change a module's behaviour, update its box's `data-card` (Description / Input / Output / Who decides / Limits / If it fails / Files / Code / Later) in the same commit.
`tests/test_diagram_sync.py` enforces the Files side of this in the normal `pytest` run: every `Files:` path in a card must exist under `amoeba/`, and every module under `amoeba/` must be named by at least one card.

Viewing and change requests (no republishing anywhere):
- The user opens `diagram/amoeba_phase1.html` directly from their checkout (a localhost server inside a remote container is not reachable to them; `python diagram/serve_edits.py diagram/amoeba_phase1.html` is only for a local checkout). After each milestone, say that the page has changed so they reload it.
- With no server behind the page, "Send" queues requests in the browser and "Copy edits" puts the JSON lines on the clipboard. The user pastes those lines into the chat with **"apply pending edits"**; append them to `diagram/edits.jsonl` (`status: "pending"`), apply them following `diagram/CLAUDE_CODE_EDIT_LOOP.md`, and show the list of lines set to `applied` / `skipped` with their notes. Never apply requests without that phrase.
