"""Source of docs/eval/round1/issues.md and issues.json (one list, two renderings). Run from the repo root:
    python eval/round1/issues_src.py
"""
import json
from pathlib import Path

R = "eval/round1/runs/"
RUN = {"r1-code-run": "r1-code-run__7242d0c0-bf30-4861-b5c6-f3d6fa055444",
       "r1-weather": "r1-weather__aea4d8ec-df0c-4a9f-b902-d47177f826d3",
       "r1-pdf-read": "r1-pdf-read__cc2ed6f7-957f-45ff-ad2e-c3aef0770cdd",
       "r1-xlsx": "r1-xlsx__0f9da92a-7749-43a1-af04-883bf9364dc3",
       "r1-chart": "r1-chart__4eace600-ecae-4ca6-a1e0-f799b71e7413",
       "r1-fx-email": "r1-fx-email__544fb5fa-13e0-401f-873c-4d1a1f62b8bd",
       "r1-route": "r1-route__54ab8b83-35c2-4acf-80da-dd48c0606ae9",
       "r1-repo": "r1-repo__b87a81c7-0c3a-4a17-a40e-dd85a307259b",
       "r1-deck": "r1-deck__fa0b5ab9-477d-4e11-8c4f-5aa174472975",
       "r1-full-chain": "r1-full-chain__a3ddb368-882b-4d8d-bea6-513cef4c5845"}


def ev(task, where, quote):
    return {"task": task, "run": RUN[task].split("__")[1], "where": R + RUN[task] + "/" + where, "quote": quote}


ISSUES = [
    # ---------------------------------------------------------------- Box 1
    dict(id="I1", box="Box 1", severity="low", title="The task intake check reads few deliverables and cuts some badly",
         tasks=["r1-fx-email", "r1-route", "r1-full-chain", "r1-deck"],
         evidence=[ev("r1-fx-email", "plan.json → quality.checks.task_coverage.phrases", "[\"test @example\"]"),
                   ev("r1-route", "plan.json → quality.checks.task_coverage.phrases",
                      "\"estimate the fuel cost at 6\" (cut at the decimal point of 6.5)"),
                   ev("r1-deck", "plan.json → quality.checks.task_coverage.phrases", "[\"delivered\"]")],
         cause="amoeba/task/quality.py DELIVERABLE_VERBS / deliverable_phrases: only 8 verbs (run, convert, email, make, "
               "save, write, list, read are not among them), and a phrase ends at any '.' — inside an email address or "
               "a decimal too. All 10 runs pass the check, so it says nothing about these tasks.",
         confirm="Call task_coverage on the ten prompts: 'run it', 'email the result', 'save it as a PNG' produce no phrase.",
         direction="Widen the verb list and end phrases at sentence punctuation only."),
    # ---------------------------------------------------------------- Box 2
    dict(id="I2", box="Box 2", severity="medium",
         title="Box 2 is never told web_search / fetch_url exist, and Box 3 grants them only to an exact alias",
         tasks=["r1-weather", "r1-pdf-read", "r1-fx-email", "r1-repo", "r1-full-chain"],
         evidence=[ev("r1-weather", "trace.jsonl, first planner chat, gen_ai.input.messages",
                      "\"# Installed tools … tool: calc … tool: echo\" — no web_search, no fetch_url"),
                   ev("r1-weather", "capability_requests.json", "weather_search (tool), canonical weather_search, mapped false"),
                   ev("r1-route", "trace.jsonl", "the only capability_mapped event of the round (request named web_search)"),
                   ev("r1-fx-email", "artifacts/step_1.md", "BLOCKED currency_api — no rate, although web_search was registered"),
                   ev("r1-full-chain", "capability_requests.json", "github_api_tool … no web_search request; nothing was found")],
         cause="Hypothesis: scripts/run_task.py:378 builds the Envelope that Box 2 sees from default_registry() (echo, "
               "calc) — D32 keeps the web tools out of Box 2 on purpose; amoeba/interp/plan_runner.py:355 "
               "grant_web_tools hands web_search/fetch_url only to a role whose request normalises to web_search via "
               "aliases.yaml. Any other name for a data source (weather_search, currency_api, pdf_reader, github_*) "
               "leaves the registered web tools unused.",
         confirm="Replay r1-weather with an alias weather_search → web_search (or with the web tools in the Envelope) "
                 "and see whether step 1 searches and cites.",
         direction="Let Box 2 see the tools Box 3 will have, and grant by what a request needs, not by its exact name."),
    dict(id="I3", box="Box 2", severity="medium", title="No capability is ever requested as a skill (0 of 23 requests)",
         tasks=["r1-xlsx", "r1-deck", "r1-full-chain"],
         evidence=[ev("r1-xlsx", "capability_requests.json", "excel_generator, kind tool"),
                   ev("r1-deck", "capability_requests.json", "presentation-generator, kind tool; no brand-style request"),
                   ev("r1-full-chain", "capability_requests.json", "spreadsheet_tool, word_doc_tool, chart_tool — all kind tool")],
         cause="Hypothesis: amoeba/config/prompts/d24_create_team.txt:29-30 defines a TOOL as something that 'acts or "
               "fetches' and a SKILL as 'know-how or a method (cost modelling, schema design…)'; producing an .xlsx / "
               ".pptx / .docx reads as acting, so it becomes a tool. Consequence for round 2: amoeba/pool/match.py rank() "
               "only compares entries of the request's kind, so anthropics/skills entries can never be candidates.",
         confirm="Count kinds over more drafts; draft r1-xlsx once with a skill example in the prompt and see the kind change.",
         direction="Say in the Planner prompt that a document format or a house style is a skill, or let the pool match across kinds."),
    dict(id="I4", box="Box 2", severity="medium",
         title="The Plan Observer does not know which tools are installed and asks for calc to be requested",
         tasks=["r1-weather", "r1-fx-email"],
         evidence=[ev("r1-weather", "plan.json → rounds[0].plan_observer",
                      "\"Add `calc` to Capability requests … so the Data Analyst has the necessary tool\""),
                   ev("r1-weather", "plan.json → rounds[1].plan_observer",
                      "\"The `calc` tool must be formally requested in the Capability requests section\""),
                   ev("r1-fx-email", "plan.json → rounds[0].plan_observer", "\"Add `calc` to Capability Requests\""),
                   ev("r1-weather", "result.json", "3 draft rounds, 18 calls, 67,686 billed tokens (median run: 12 calls, 44k)")],
         cause="Confirmed in the trace: the plan_observer prompt has no 'Installed tools' section, while "
               "amoeba/config/prompts/d24_review_plan.txt:33 asks it whether 'each step can actually be done with "
               "installed tools or a requested capability'. amoeba/task/draft.py:247-249 renders d24_review_plan without "
               "the tool list (the agent observer's d24_review_team.txt:13 has it).",
         confirm="Already seen: no 'Installed tools' string in any plan_observer prompt of the round.",
         direction="Give the Plan Observer the same installed-tools list the Agent Observer gets."),
    dict(id="I5", box="Box 2", severity="medium",
         title="The Planner leaves needed capabilities out, or turns a company-specific input into an assumption",
         tasks=["r1-deck", "r1-full-chain"],
         evidence=[ev("r1-deck", "plan.json → givens",
                      "\"assumption: The 'company brand style' implies a professional corporate template with specific "
                      "color palettes and font standards.\""),
                   ev("r1-deck", "capability_requests.json", "only presentation-generator; no chart, file writing or brand style"),
                   ev("r1-full-chain", "capability_requests.json", "no web_search and no code runner requested")],
         cause="Hypothesis: d24_create_team.txt asks for 'ideal capabilities' but also to settle ambiguity by assumption "
               "(D53); a brand guide the team cannot know is treated as an ambiguity to assume rather than an input to "
               "request or an Open Question. The observers' checklists do not ask 'what must come from the user?'.",
         confirm="Check whether any draft in the round lists an Open Question or a request for the brand guide (none does).",
         direction="Anything only the user or the company can supply becomes a request or an Open Question, never an assumption."),
    dict(id="I6", box="Box 2", severity="low", title="Failed draft checks change nothing without the quality gate",
         tasks=["r1-deck"],
         evidence=[ev("r1-deck", "plan.json → quality.failed_checks", "[\"summariser\", \"independent_verification\"] with both observers APPROVE")],
         cause="By design (D24/D28): draft_quality is recorded only unless --quality-gate, which this round's settings do "
               "not set. The deck plan has the Delivery Lead verify and then summarise its own work, and no real verify step.",
         confirm="result.json draft_quality of r1-deck.",
         direction="Decide whether the observer rounds should use --quality-gate (it would change the settings between rounds)."),
    dict(id="I7", box="Box 2", severity="low", title="16 of 18 request names are not in the alias list",
         tasks=["all"],
         evidence=[ev("r1-chart", "capability_requests.json",
                      "code_interpreter → canonical code_interpreter, mapped false (python_interpreter maps to code_execution)")],
         cause="amoeba/capabilities/aliases.yaml has no entries for these names (full list in capabilities.md). It matters "
               "wherever code relies on the standard name: web tool granting (I2), blocked-capability counts, reports.",
         confirm="result.json unmapped_capabilities of each run.",
         direction="Grow aliases.yaml from capabilities.md."),
    # ---------------------------------------------------------------- Box 3
    dict(id="I8", box="Box 3", severity="high",
         title="A helper without its tool can finish 'done' from memory, with no BLOCKED line",
         tasks=["r1-route", "r1-deck", "r1-fx-email", "r1-code-run"],
         evidence=[ev("r1-route", "artifacts/step_1.json",
                      "status done; the Logistics Specialist lacked route_engine; distances 185/175/185 [unverified]"),
                   ev("r1-deck", "artifacts/step_2.md:5-10",
                      "\"Deep Navy (#002060) … Segoe UI … Company Logo (Top Right)\" — the designer lacked presentation-generator; status done")],
         cause="Hypothesis: amoeba/interp/plan_runner.py:501-513 (run_step) derives the status only from BLOCKED actions "
               "and BLOCKED marks in the text; the helper's missing_tools and the step's open capability requests are "
               "not consulted, so a step whose helper simply writes an answer anyway is 'done'.",
         confirm="Compare each step's roles' missing_tools with its status: 9 'done' steps have a helper with a missing "
                 "tool; in 4 the step needed that tool — r1-route 1 (routing), r1-deck 2 (slides), r1-fx-email 3 (email: "
                 "'Not sent', no BLOCKED), r1-code-run 2 (verify without the interpreter, I16).",
         direction="A step whose helper lacks a requested capability cannot be 'done' without saying what it did instead."),
    dict(id="I9", box="Box 3", severity="high",
         title="Invented facts reach the answer, softened only by [unverified]",
         tasks=["r1-pdf-read", "r1-deck", "r1-route"],
         evidence=[ev("r1-pdf-read", "result.json → answer, lines 1-2",
                      "\"Agent Designer (Page 4 [unverified])\" — the paper's drafting-stage agents are Planner, Agent "
                      "Observer, Plan Observer; the PDF was never read"),
                   ev("r1-pdf-read", "result.json → summary_check", "answer_unverified ['4'] — seen by code, not acted on"),
                   ev("r1-deck", "result.json → answer", "invented brand colours, fonts and logo placement")],
         cause="Hypothesis: D33 treats [unverified] as an honest label, and amoeba/config/prompts/plan_step.txt:20 invites "
               "figures 'from your own knowledge' tagged [unverified] — even when the requirement itself (R4 'page "
               "number where each is described') can only be met by the capability that was BLOCKED.",
         confirm="In each run, list requirements whose covering step is partial/blocked yet whose figures appear in the "
                 "answer as [unverified] (r1-pdf-read R4).",
         direction="A requirement whose capability was blocked is reported as not met, never answered from memory."),
    dict(id="I10", box="Box 3", severity="high",
         title="[S#] is used for step numbers, and made-up citations stay in the final answer",
         tasks=["r1-chart"],
         evidence=[ev("r1-chart", "artifacts/step_3.md:7", "\"Total Revenues from Step 2: 22200 [S2], 16800 [S2] …\""),
                   ev("r1-chart", "artifacts/step_4.md:6-9", "\"Lane A: 22,200 [S1]\" … — no source S1 exists in this run"),
                   ev("r1-chart", "artifacts/step_4.json → provenance", "hallucinated_citations ['S1'], yet the answer keeps it")],
         cause="Hypothesis: the source ids S1, S2 … read like step numbers ('Step 2' → [S2]); provenance "
               "(amoeba/interp/provenance.py check_provenance) detects the unseen id but nothing removes it, and the "
               "summariser's step is not refined for it.",
         confirm="Search every answer of the round for [S#] with no sources in the run: only r1-chart; 2 hallucinated ids.",
         direction="Strip or flag an unseen [S#] in the answer by code, and name sources so they cannot be read as steps."),
    dict(id="I11", box="Box 3", severity="medium",
         title="Provenance tagging corrupts code and spreadsheet formulas",
         tasks=["r1-code-run", "r1-xlsx"],
         evidence=[ev("r1-code-run", "artifacts/step_1.md:8", "\"if n < 0: # 0 [unverified]\" (also in the final answer)"),
                   ev("r1-xlsx", "artifacts/step_1.md:22-23", "\"=SUM(B2 [unverified]:B5 [unverified])\""),
                   ev("r1-xlsx", "artifacts/step_1.md:5", "\"**1 [unverified]. Column Definitions**\"")],
         cause="Hypothesis: amoeba/interp/provenance.py:34 _line_numbers counts every number, including those inside code "
               "fences, cell references and bold list numbers (LIST_MARKER at :22 only matches a plain '1. '); the D50 "
               "refine turn (--self-refine on-issues) then asks the helper to tag them, and it does.",
         confirm="Run check_provenance on those lines: they come back as untagged figures.",
         direction="Leave code blocks, formulas, cell references and list numbering out of the figure count."),
    dict(id="I12", box="Box 3", severity="medium",
         title="The summariser drops work that was done when a later step fails",
         tasks=["r1-xlsx", "r1-fx-email", "r1-repo"],
         evidence=[ev("r1-xlsx", "artifacts/step_1.md", "full table with lane totals 22,200 / 16,800 / 28,400 / 12,400 and formulas"),
                   ev("r1-xlsx", "result.json → answer", "\"Verification Status: Failed … R1/R2/R3: Not met\" — no totals, no 79,800, no 1,855.81")],
         cause="Hypothesis: amoeba/config/prompts/plan_summarise.txt asks the summariser to assemble the deliverable from "
               "the step outputs; after a verify FAIL it writes a status memo instead, and nothing checks that the "
               "figures already produced upstream reach the answer.",
         confirm="Compare each step's numbers (figure_ledger) with the answer's figures: r1-xlsx loses all of step 1's.",
         direction="The answer carries every usable artifact produced upstream, next to what is missing."),
    dict(id="I13", box="Box 3", severity="medium",
         title="BLOCKED names turn sentences, step numbers and missing inputs into 'capabilities'",
         tasks=["r1-weather", "r1-xlsx", "r1-repo", "r1-full-chain"],
         evidence=[ev("r1-full-chain", "result.json → blocked_capabilities",
                      "keys 'Step 1', 'Step 2', 'Step 1 (OS Intelligence Analyst) — No framework data provided.'"),
                   ev("r1-weather", "result.json → answer",
                      "four appended BLOCKED lines for two gaps, one of them 'weather_data' (an input, not a tool)"),
                   ev("r1-full-chain", "result.json → answer",
                      "\"BLOCKED: Step 1 (OS Intelligence Analyst) — No framework data provided. (the team had no such capability; added by plain code)\"")],
         cause="Hypothesis: amoeba/interp/runtime.py:200 (_dispatch) keeps everything after 'BLOCKED:' up to the line end, "
               "including '— reason'; helpers also answer BLOCKED when an upstream input is missing; "
               "plan_runner.py:763/776 (blocked_capabilities / enforce_limitations) then key on that raw text.",
         confirm="result.json blocked_capabilities of the four runs.",
         direction="Cut the name at the first dash and record 'input missing' apart from 'capability missing'."),
    dict(id="I14", box="Box 3", severity="medium",
         title="Verify FAIL triggers rework that cannot help when the producer lacks a tool",
         tasks=["r1-weather", "r1-pdf-read", "r1-xlsx", "r1-fx-email", "r1-repo", "r1-full-chain"],
         evidence=[ev("r1-full-chain", "trace.jsonl", "3 rework events, 2 stale, 1 reverify — every reworked step blocked again"),
                   ev("r1-xlsx", "trace.jsonl", "rework of step 2 (BLOCKED excel_generator) → blocked again")],
         cause="Hypothesis: amoeba/interp/plan_runner.py:808 rework_producers re-runs every checked producer on FAIL "
               "without looking at why it failed; a missing capability does not change between attempts.",
         confirm="Sum the calls of reworked steps in the six runs (tokens spent with no change of status).",
         direction="Skip rework when the producer's only problem is a blocked capability."),
    dict(id="I15", box="Box 3", severity="medium", title="Limitations miss gaps that no helper wrote as BLOCKED",
         tasks=["r1-fx-email", "r1-route", "r1-deck"],
         evidence=[ev("r1-fx-email", "result.json → answer", "Limitations name currency_api only; email_service missing was never said"),
                   ev("r1-route", "result.json → answer", "route_engine not named; only 'distances … are [unverified]'"),
                   ev("r1-deck", "result.json → answer", "no pptx, chart or brand-guide gap named")],
         cause="Hypothesis: amoeba/interp/plan_runner.py:763 blocked_capabilities comes only from BLOCKED actions and "
               "marks; the run's unfilled capability requests (capability_requests.json) are not used by "
               "enforce_limitations.",
         confirm="Diff capability_requests.json against each answer's Limitations.",
         direction="Every unfilled capability request appears in Limitations, whatever the helpers wrote."),
    dict(id="I16", box="Box 3", severity="low", title="A verify step passes without the capability it needed",
         tasks=["r1-code-run"],
         evidence=[ev("r1-code-run", "artifacts/step_2.md", "\"Verdict: PASS … verified against the known mathematical value\" — QA lacked python_interpreter")],
         cause="Same mechanism as I8 for verify steps: nothing ties a verdict to the verifier's missing tools.",
         confirm="Verify steps whose role has missing_tools: only this one passed.",
         direction="A verifier without its tool says what it could not check."),
    dict(id="I17", box="Box 3", severity="low", title="calc is under-used", tasks=["r1-code-run", "r1-fx-email"],
         evidence=[ev("r1-code-run", "trace.jsonl", "no execute_tool span: F50 was not checked (calc can evaluate Binet's formula)")],
         cause="Hypothesis: helpers use calc for products and sums, not to cross-check a value they 'know'.",
         confirm="Tool calls per run in facts/*.json (calc: 0, 0, 0, 1, 4, 0, 1, 0, 1, 0).",
         direction="Low priority."),
    # ---------------------------------------------------------------- Cross-cutting
    dict(id="I18", box="Cross-cutting", severity="low", title="Cost is invisible in the run records",
         tasks=["all"],
         evidence=[ev("r1-code-run", "result.json → usage.cost_usd", "null — prices.yaml has no price for gemma-4-31b-it"),
                   ev("r1-weather", "result.json → usage", "reasoning 24,517 of 67,686 billed tokens")],
         cause="amoeba/config/prices.yaml leaves Gemma null; reasoning tokens are 38% of the round's billed tokens "
               "(171,251 of 453,133) and runs took 5–16.5 minutes each.",
         confirm="Sum usage over facts/*.json.",
         direction="Fill in a Gemma price (even $0 for the Gemini API) so cost appears per run."),
    dict(id="I19", box="Cross-cutting", severity="low", title="The environment can change a run without anyone noticing",
         tasks=["all"],
         evidence=[ev("r1-code-run", "result.json → models.returned", "gemma-4-31b-it — only because old AMOEBA_* variables were unset first"),
                   ev("r1-code-run", "result.json", "unrelated: the D55 Stop hook spent 22,670 arch-text tokens during the round (docs/arch/text_log.jsonl)")],
         cause="D54 precedence (AMOEBA_* > profile) is intended but silent; the Stop hook calls a model whenever box "
               "facts change.",
         confirm="docs/arch/text_log.jsonl entry of 2026-09-25T19:32Z.",
         direction="Print the effective model, endpoint and key source at the start of every run."),
]

TOP5 = ["I2", "I9", "I8", "I10", "I3"]


def md():
    out = ["# Observer round 1 — issues (baseline, no pool)", "",
           "Severity: **high** = wrong or dishonest answer · **medium** = wasted cost or weaker answer · **low** = cosmetic.",
           "Every root cause is a **hypothesis** unless it says 'confirmed'. No fixes are proposed beyond one line of direction.",
           "Evidence paths are inside this PR (`eval/round1/runs/<task>__<run_id>/`).", "",
           "Ranked by impact (details below): " + ", ".join(TOP5) + ", then I12, I4, I13, I15, I11, I14.", ""]
    for box in ("Box 1", "Box 2", "Box 3", "Cross-cutting"):
        out += [f"## {box}", ""]
        for i in (x for x in ISSUES if x["box"] == box):
            out += [f"### {i['id']} — {i['title']} ({i['severity']})", "",
                    f"- **Tasks:** {', '.join(i['tasks'])}", "- **Evidence:**"]
            out += [f"  - `{e['where']}` — {e['quote']}" for e in i["evidence"]]
            out += [f"- **Likely root cause (hypothesis):** {i['cause']}", f"- **What would confirm it:** {i['confirm']}",
                    f"- **Possible direction:** {i['direction']}", ""]
    return "\n".join(out)


if __name__ == "__main__":
    d = Path("docs/eval/round1")
    (d / "issues.md").write_text(md(), encoding="utf-8")
    (d / "issues.json").write_text(json.dumps({"round": 1, "baseline": "no pool", "top5": TOP5, "issues": [
        {"id": i["id"], "title": i["title"], "box": i["box"], "severity": i["severity"], "tasks": i["tasks"],
         "evidence": i["evidence"], "root_cause_hypothesis": i["cause"], "confirm_by": i["confirm"],
         "possible_direction": i["direction"]} for i in ISSUES]}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(len(ISSUES), "issues")
