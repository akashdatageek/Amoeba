"""Source of docs/eval/round2/issues.md and issues.json (one list, two renderings). Run from the repo root:
    python eval/round2/issues_src.py

Round 2 = round 1's settings and drafts + the tool/skill pool (D56/D58). Two lists: NEW problems the pool caused or
exposed (P#), and the status of each round-1 issue (I#) in round 2.
"""
import json
from pathlib import Path

R = "eval/round2/runs/"
RUN = {"r1-code-run": "r1-code-run__e4669ee7-dfe1-48cf-a73d-c720a5b9b386",
       "r1-weather": "r1-weather__312bad05-4203-4863-bc25-91055e7fe382",
       "r1-pdf-read": "r1-pdf-read__3c30ecc6-aa2c-4c9a-aa69-586f2d780340",
       "r1-xlsx": "r1-xlsx__46716a53-5256-4641-bc91-04773730a65c",
       "r1-chart": "r1-chart__77adad12-3dcc-4a36-b911-17188d6d98a5",
       "r1-fx-email": "r1-fx-email__56f9d9e2-d498-49c2-a9bf-72aa4a33b558",
       "r1-route": "r1-route__87da070e-cfaa-473d-8aa8-84bc74791cdd",
       "r1-repo": "r1-repo__0d328e58-90f4-4431-af0b-f84e68a6f52c",
       "r1-deck": "r1-deck__b384d832-edb8-4550-90d4-8e9e09510dbb",
       "r1-full-chain": "r1-full-chain__d8d1f39b-4808-4fb9-b378-2379a0cb0a7e"}


def ev(task, where, quote):
    return {"task": task, "run": RUN[task].split("__")[1], "where": R + RUN[task] + "/" + where, "quote": quote}


ISSUES = [
    dict(id="P0", severity="high", status="fixed during the round (D58 item 4, commit 7b2c13e)",
         title="Gemma writes <thought>…</thought> into the pick reply, so every pick read as NONE",
         tasks=["r1-code-run"],
         evidence=[{"task": "r1-code-run", "run": "478893ad",
                    "where": "eval/round2/void/r1-code-run__478893ad-before-thought-fix/trace.jsonl",
                    "quote": "pool_picker reply \"<thought>…</thought>io.github.lu-zhengda/mcp-python-exec-sandbox\" → pick_none"}],
         cause="Confirmed: amoeba/pool/stock.py pick() compared the whole reply with the listed ids. The first task-1 run "
               "was stopped by hand, kept as void evidence, and task 1 rerun after the fix (its two pick replies came "
               "from the observer-r2 cache, same text, 0 tokens).",
         confirm="tests/test_pool.py pick-parse cases with a <thought> block.",
         direction="Done: amoeba/pool/stock.py:35 THINKING strips a closed thinking block before the strict parse."),
    dict(id="P1", severity="medium", status="open",
         title="The pick reply runs out of room: 3 of 20 picks ended at finish_reason 'length' with no id",
         tasks=["r1-fx-email", "r1-pdf-read"],
         evidence=[ev("r1-fx-email", "trace.jsonl, chat pool_picker (email_service)",
                      "finish_reasons ['length'], 0 output tokens, 2,045 reasoning; reply ends '`io.github.Br0</thought>'"),
                   ev("r1-fx-email", "trace.jsonl, chat pool_picker (currency_api, Quality Auditor)",
                      "finish_reasons ['length']; '… All three do the job. Usually, the first one</thought>'"),
                   ev("r1-pdf-read", "trace.jsonl, chat pool_picker (pdf_reader, Technical Analyst)",
                      "finish_reasons ['length']; '… the most specialized tool for the file type is the correct one. `page</thought>'")],
         cause="Hypothesis, near confirmed: amoeba/pool/stock.py:94 pick() passes no max_tokens, so the reply gets the "
               "profile default (2,048) and Gemma spends it all on reasoning; the D27 'retry with more room' only runs "
               "when the caller set max_tokens. The three requests became pick_none although passing candidates were "
               "listed (datakoot FX for the auditor; agent-web for the PDF).",
         confirm="Replay the three pick prompts with max_tokens 6,000: each should end 'stop' with an id.",
         direction="Give the pick its own reply room, or retry once on 'length'."),
    dict(id="P2", severity="medium", status="open",
         title="The picker chooses candidates that vetting then refuses: 13 of 15 picked ids were refused",
         tasks=["r1-code-run", "r1-pdf-read", "r1-xlsx", "r1-chart", "r1-fx-email", "r1-route", "r1-repo",
                "r1-full-chain"],
         evidence=[ev("r1-fx-email", "capability_requests.json",
                      "currency_api → io.github.Exchange-RateAPI/mcp-server, not_remote; datakoot and bluegamma, both "
                      "passing vetting, were in the same five (eval/round2/dryrun.json)"),
                   ev("r1-pdf-read", "capability_requests.json",
                      "pdf_reader (QA Lead) → page.doc/pdf-extract, side_effect; io.github.foomworks/agent-web passed"),
                   ev("r1-repo", "capability_requests.json",
                      "github_repo_reader (Software Architect) → thedhruv-07/github-repo-mcp, not_remote; "
                      "digitalgremlin/github-repo-intelligence-mcp passed"),
                   ev("r1-full-chain", "capability_requests.json",
                      "5 picks, 5 refusals: auth_missing, has_scripts (xlsx skill), not_remote ×2, side_effect"),
                   ev("r1-code-run", "capability_requests.json",
                      "both picks lu-zhengda/mcp-python-exec-sandbox, not_remote — none of the five would have passed")],
         cause="Confirmed by order: amoeba/pool/stock.py:198 calls pick() on the raw top five and :203 vets only the "
               "chosen one; the pick prompt says nothing about locality, keys or side effects, so the picker takes "
               "the best description (often a local package). Refusals of picked ids: not_remote 6, side_effect 3, "
               "auth_missing 2, no_source 1, has_scripts 1.",
         confirm="eval/round2/dryrun.json lists the vet result of every candidate; in 4 requests a passing, relevant "
                 "candidate was on the list when the refused one was picked.",
         direction="Vet the candidates first and show the picker only those that pass; skip the pick when none do."),
    dict(id="P3", severity="medium", status="open",
         title="Keyword matching lists unrelated tools, and some of them pass vetting",
         tasks=["r1-route", "r1-repo", "r1-chart", "r1-fx-email", "r1-full-chain"],
         evidence=[ev("r1-route", "trace.jsonl, pool_match route_engine",
                      "booking-timing, sadri-dridi/mph-to-kmh, sadri-dridi/range-bytes, flipvo-agent-tools, where_is_my_bus"),
                   ev("r1-repo", "trace.jsonl, pool_match python_code_analyzer",
                      "source-map-parser, sadri-dridi/blank-ok, egg-ok, emoji-n, fstab-ok — 4 of 5 pass vetting"),
                   ev("r1-chart", "trace.jsonl, pool_match code_interpreter", "…, mrfentmen/qr-code-mcp, sadri-dridi/png-magic (passes)")],
         cause="Hypothesis: amoeba/pool/match.py:45 rank() scores shared words (code, time, route, read, check …); one "
               "publisher (io.github.sadri-dridi, the 'agent-observatory-sensor' workers) has many near-empty servers "
               "whose short descriptions hit common words, and they are remote, keyless and versioned, so they pass "
               "every rule. The picker mostly avoided them (route picked flipvo, 'mentions drive times').",
         confirm="Count sadri-dridi ids among the 100 listed candidates of the round (dryrun.json): 13 listings, 12 servers.",
         direction="Rank by fit of the whole description and cap how many candidates one publisher may fill."),
    dict(id="P4", severity="high", status="open (pipeline, exposed by the pool)",
         title="The one filled tool fetched real data, and the pipeline threw it away",
         tasks=["r1-weather"],
         evidence=[ev("r1-weather", "artifacts/step_1.md", "four daily highs from get_forecast, each cited [S1]"),
                   ev("r1-weather", "artifacts/step_3.md",
                      "\"BLOCKED: Step 1 output — unable to verify if Fahrenheit values in Step 2 … match raw data\" → Verdict FAIL"),
                   ev("r1-weather", "result.json → answer",
                      "\"Warning: The weather data failed verification and cannot be published.\" — no temperature")],
         cause="Hypothesis: the reused draft makes step 3 (verify) depend on step 2 only, so amoeba/interp/plan_runner.py "
               "gives the verifier step 2's table but not step 1's tool output; it answers BLOCKED on a missing input "
               "(round-1 I13), the rework of step 2 cannot supply it (I14), and the summariser writes a status memo "
               "that drops every figure already produced (I12).",
         confirm="step_3.first.md and step_3.md both lack step 1's text; plan.json step 3 depends_on [2].",
         direction="Part of the D59+ pipeline fixes (I12–I14): a verifier sees the sources of what it checks."),
    dict(id="P5", severity="medium", status="open",
         title="An attached pool tool is never called",
         tasks=["r1-deck"],
         evidence=[ev("r1-deck", "trace.jsonl, first chat of Corporate Presentation Designer",
                      "\"You can use: ['pool:ai.presentations/presentations-ai', 'Print', 'Final Output']\" and its POOL DATA note"),
                   ev("r1-deck", "artifacts/step_2.md", "a text slide spec with an invented palette (#002D62, #708090, #D4AF37); step 2 done"),
                   ev("r1-deck", "result.json → pool.attached", "presentations-ai for the designer; 0 pool calls in the run")],
         cause="Hypothesis: nothing requires a helper to use the tool attached for its request; the step is 'done' "
               "from text alone (round-1 I8), so the answer and Limitations never mention the unused tool.",
         confirm="Pool tools attached vs execute_tool spans per helper: deck 1 attached, 0 called.",
         direction="A helper that got a pool tool for a request and did not call it says why, and the step records it."),
    dict(id="P6", severity="medium", status="open (needs a decision)",
         title="side_effect lets through tools that create things in an outside account",
         tasks=["r1-deck"],
         evidence=[ev("r1-deck", "trace.jsonl, pool_pinned",
                      "presentations-ai: create_presentation_from_topic / _from_content / _from_file, create_single_slide"),
                   ev("r1-deck", "trace.jsonl, pool_vet", "accepted: True")],
         cause="Confirmed: amoeba/pool/stock.py:39 SIDE_EFFECT names send, e-mail, post, publish, pay, purchase, delete "
               "and 'write to'; 'create', 'upload', 'generate' are not in it. Had the designer called the tool, a deck "
               "would have been made in the vendor's service (and the result was never needed in round 2 terms).",
         confirm="side_effect('create_presentation_from_topic', …) returns None.",
         direction="Decide whether 'creates in an outside service' counts as an outside action for now."),
    dict(id="P7", severity="low", status="open",
         title="The pick costs a call even when no candidate could pass",
         tasks=["r1-code-run", "r1-xlsx", "r1-full-chain"],
         evidence=[ev("r1-code-run", "trace.jsonl", "2 picks; all five candidates refused by vetting (paid, no_source, key, local ×2)"),
                   ev("r1-full-chain", "trace.jsonl", "5 picks, 6,871 tokens; spreadsheet, docx and email lists had no passing candidate")],
         cause="20 pick calls billed 29,364 tokens (8% of the round), mostly reasoning (250–2,045 per pick). 6 of the "
               "20 picks had no candidate that vetting would accept (code-run ×2, xlsx, full-chain spreadsheet / docx "
               "/ email).",
         confirm="dryrun.json: requests whose five candidates are all refused.",
         direction="Falls out of P2 (vet first, no pick when nothing passes)."),
    dict(id="P8", severity="low", status="open",
         title="A run writes into the shared pool cache",
         tasks=["r1-weather", "r1-deck"],
         evidence=[ev("r1-weather", "trace.jsonl, pool_pinned", "weather-mcp: get_forecast, get_weather, version 0.1.0"),
                   ev("r1-deck", "trace.jsonl, pool_pinned", "presentations-ai: 5 tools, version 1.0.0")],
         cause="Intended (D56 trust on first use): data/pool/pins.json is written by the first run that connects. It "
               "is gitignored and not copied into the run folder, so a later round's result depends on which runs came "
               "first on this machine, and the pins are not in the evidence.",
         confirm="data/pool/pins.json holds exactly these two entries after round 2.",
         direction="Copy the pins a run used into runs/<id>/ (or result.json)."),
    dict(id="P9", severity="low", status="open",
         title="Numbers computed from a tool result carry the tool's source id",
         tasks=["r1-weather"],
         evidence=[ev("r1-weather", "artifacts/step_1.md:1", "\"(17.2 [S1] * 9/5) + 32 = 62.96°F\" — S1 gave Celsius"),
                   ev("r1-weather", "artifacts/step_2.md:3", "\"62.96 [S1] | 17.20\" — a derived °F value cited as S1")],
         cause="Hypothesis: plan_step's 'keep the [S#] tags of any input you reuse' is applied to derived values too; "
               "provenance counts them as cited (144 cited numbers). The source gave highs in °C, so step 1 converted to "
               "°F and step 2 back to °C. The current weather (R1, get_weather) was never fetched.",
         confirm="Compare each [S1] number with the POOL DATA text: 62.96, 64.04, 67.28, 69.8 are not in it.",
         direction="A derived figure is tagged derived, with its inputs cited."),
]

# round-1 issues, as seen in round 2 (Box 1 and Box 2 are round 1's drafts, reused)
R1_STATUS = [
    ("I1", "not re-observed", "Box 1 is round 1's (draft reused)."),
    ("I2", "persists", "web_search still not offered; the pool skips requests for installed tools (route: web_search "
                       "→ registered_tool), and no data request was filled by web_search."),
    ("I3", "persists, softened", "0 skill requests again (same drafts). D58 cross-kind matching listed skills 7 times; "
                                 "the picker chose one (xlsx for spreadsheet_tool), refused has_scripts."),
    ("I4", "not re-observed", "Box 2 reused."),
    ("I5", "not re-observed", "Box 2 reused."),
    ("I6", "not re-observed", "Box 2 reused."),
    ("I7", "persists", "Same request names; the pool rank uses request words and aliases, so the gap now also "
                       "shapes which candidates are listed."),
    ("I8", "persists", "route step 1 'done' from memory (186/176/187 mi); deck step 2 'done' with an unused pool tool (P5)."),
    ("I9", "persists", "deck brand invented again (#002D62, Gold #D4AF37). pdf-read did not invent this time (sampling, not the pool)."),
    ("I10", "not seen", "chart cited no made-up source this time (sampling; nothing changed in provenance)."),
    ("I11", "persists", "code-run: '# 0 [unverified], 1 [unverified]' in the code; xlsx: '[Formula 1 [unverified]]', row numbers tagged."),
    ("I12", "persists", "xlsx totals dropped again; weather's fetched highs dropped (P4)."),
    ("I13", "persists", "full-chain: 'Framework Data Table', 'Input Files', 'Star Count Chart' recorded as capabilities; weather 'Step 1 output'."),
    ("I14", "persists", "rework in 6 of 10 runs (full-chain 3 + 2 stale), none changed a blocked step."),
    ("I15", "persists", "fx-email: email_service not named; route: route_engine not named; deck: no gap named."),
    ("I16", "persists", "code-run step 2 'PASS … verified' with no interpreter."),
    ("I17", "persists", "calc 0 calls in code-run, fx-email, pdf-read, repo, full-chain."),
    ("I18", "persists", "cost_usd still null (no Gemma price)."),
    ("I19", "handled by procedure", "AMOEBA_* unset again; the Stop hook's page rebuilds cost 0 model tokens this round."),
]

TOP = ["P2", "P4", "P1", "P5", "P6", "P3"]


def md():
    out = ["# Observer round 2 — issues (pool on)", "",
           "Severity: **high** = wrong or dishonest answer · **medium** = wasted cost or weaker answer · **low** = cosmetic.",
           "Every root cause is a **hypothesis** unless it says 'confirmed'. No fixes are proposed beyond one line of direction.",
           "Evidence paths are inside this PR (`eval/round2/runs/<task>__<run_id>/`). Candidate-by-candidate vetting "
           "for every request is in `eval/round2/dryrun.json`.", "",
           "Tool errors: **none** (0 tool_error, 0 connect failures, 0 listing changes). No pool text was followed as an "
           "instruction.", "",
           "Ranked by impact: " + ", ".join(TOP) + ", then P7, P8, P9. P0 was found and fixed during the round.", "",
           "## New problems the pool caused or exposed", ""]
    for i in ISSUES:
        out += [f"### {i['id']} — {i['title']} ({i['severity']}; {i['status']})", "",
                f"- **Tasks:** {', '.join(i['tasks'])}", "- **Evidence:**"]
        out += [f"  - `{e['where']}` — {e['quote']}" for e in i["evidence"]]
        out += [f"- **Likely root cause (hypothesis):** {i['cause']}", f"- **What would confirm it:** {i['confirm']}",
                f"- **Possible direction:** {i['direction']}", ""]
    out += ["## Round 1 issues in round 2", "",
            "Details of each in `docs/eval/round1/issues.md`. The pool changes none of them; they are D60 onward (D59 is the local toolbox).", "",
            "| Issue | In round 2 | What was seen |", "|---|---|---|"]
    out += [f"| {i} | {s} | {w} |" for i, s, w in R1_STATUS]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    d = Path("docs/eval/round2")
    d.mkdir(parents=True, exist_ok=True)
    (d / "issues.md").write_text(md(), encoding="utf-8")
    (d / "issues.json").write_text(json.dumps({"round": 2, "setting": "round 1 + pool (D56/D58)", "top": TOP, "issues": [
        {"id": i["id"], "title": i["title"], "severity": i["severity"], "status": i["status"], "tasks": i["tasks"],
         "evidence": i["evidence"], "root_cause_hypothesis": i["cause"], "confirm_by": i["confirm"],
         "possible_direction": i["direction"]} for i in ISSUES],
        "round1_issues": [{"id": i, "status": s, "seen": w} for i, s, w in R1_STATUS]},
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(len(ISSUES), "issues,", len(R1_STATUS), "round-1 statuses")
