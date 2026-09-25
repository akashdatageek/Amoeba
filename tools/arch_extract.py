"""Extract the as-built architecture of Amoeba Phase 1 into docs/arch/architecture.json.

    python tools/arch_extract.py            # then: python tools/arch_render.py

Facts come only from: the source (Python ast + plain reads), git, a pytest run, and one sample run of the toy
task with the offline stand-in model (its prompts are captured, since the trace does not store them). No LLM.
The box registry below holds the plain-language text and says which code each box points at; every code fact
shown for a box is looked up, and a pointer that no longer resolves makes the box "missing".
"""
from __future__ import annotations

import ast
import hashlib
import html
import json
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
PKG = ROOT / "amoeba"
OUT = ROOT / "docs" / "arch"
PLAN_HTML = OUT / "plan_phase1.html"
PLAN_URL = "https://claude.ai/code/artifact/bbfb03d3-ee80-42fe-9ba1-d056e7c620ab"
SOURCE_FILES = sorted(PKG.rglob("*.py")) + sorted((ROOT / "scripts").glob("*.py"))
AI_METHODS = {"chat", "chat_messages", "chat_sections"}


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def sh(*cmd: str) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout.strip()


# ============================================================================================ box registry
# Plain-language text is written here; everything else on the page is looked up from the code.
# anchors: "path::Qualname" (nested functions as Outer.inner); optional [from, to) source markers limit the
# lines that count for guards and DEVIATION notes when several boxes share one function.
BOXES: list[dict] = [
    # ---------------------------------------------------------------- overview
    dict(id="ov_task", view="overview", title="1 · Task", kind="top", opens="task", plan="1 · Task",
         sentence="One job to do; practice jobs also carry the right answer, so the system can grade itself.",
         what=["A task is one job for the team: a line of text, plus the right answer when it is a practice job.",
               "Practice jobs come from a seed, so the same seed always gives the same jobs.",
               "A job you type yourself runs the same way but cannot be scored.",
               "Nothing in this box calls an AI."],
         proposes="Nothing: no AI works here.",
         disposes="Plain code makes the job and, after the run, scores the answer against the known one.",
         anchors=["amoeba/task/models.py::Task", "amoeba/task/source.py::ToyTaskSource",
                  "amoeba/task/evaluate.py::score"], guard_anchors=[]),
    dict(id="ov_plan", view="overview", title="2 · Plan a new team", kind="top", opens="plan",
         plan="2 · Plan a new team",
         sentence="An AI drafts a team and a step plan, two AIs critique it, then plain code checks it and builds the team.",
         what=["A planning AI proposes a set of helpers and a numbered step plan for the job.",
               "Two checking AIs critique the helpers and the plan; the planner revises from their latest comments.",
               "The last draft is used whether or not the checkers agreed.",
               "Plain code then cleans the draft, applies the rules and builds the team."],
         proposes="Helper names, descriptions, tools, instructions and the step plan.",
         disposes="Unreadable entries are skipped, tools we don't have are recorded as requests (never used), the "
                  "summariser is flagged, team size held to the allowed range, steps naming nobody dropped, and the team "
                  "must pass every validation rule.",
         anchors=["amoeba/task/draft.py::draft_team", "amoeba/task/instantiate.py::instantiate"], guard_anchors=[]),
    dict(id="ov_run", view="overview", title="3 · Team runs the task", kind="top", opens="run",
         plan="3 · Team runs the task",
         sentence="The helpers do the job step by step, as one writer with reviewers, or over the plan's step graph; "
                  "every AI call is logged.",
         what=["The team runs in one of three shapes chosen when you start the run, never by an AI.",
               "Over the step graph (plan): each step sees only the job and the outputs of the steps it depends on, "
               "code checks each step's output, and a summariser only assembles.",
               "Step by step: each plan step's helpers work in turns until they give a final answer.",
               "One writer with reviewers: the writer answers, the others review, and the writer revises on objections.",
               "Every AI call and tool call is written to a log with its token counts."],
         proposes="Each helper's action and text, or a review verdict.",
         disposes="Plain code routes every message, runs the tools, caps every loop and picks the final answer.",
         anchors=["amoeba/interp/runtime.py::Interpreter.run", "amoeba/interp/runtime.py::Interpreter.run_flat",
                  "amoeba/interp/runtime.py::Interpreter.run_boss_reviewers",
                  "amoeba/interp/plan_runner.py::PlanRunner.run"], guard_anchors=[]),
    dict(id="ov_leave", view="overview", title="What every run leaves behind", kind="data",
         plan="What every run leaves behind",
         sentence="Every run saves five files: the team, the draft, a log line per AI call, the tools or skills the "
                  "team asked for, and a result summary.",
         what=["Each run gets its own folder named by a random run id.",
               "It holds the team as built, the planner's draft with every round (each planner reply and both "
               "checkers' replies, kept even when drafting fails), the call log with each prompt and reply, the list "
               "of requested tools and skills (empty when none), and a one-line result.",
               "These files are the raw material later phases will learn from."],
         proposes="Nothing.", disposes="Plain code writes the files, even when drafting fails.",
         anchors=["scripts/run_task.py::run_one"], guard_anchors=[]),
    # ---------------------------------------------------------------- task view
    dict(id="toy_source", view="task", title="Toy task source", kind="code", plan="Toy task source",
         sentence="Makes practice jobs with known answers (sums, reversed words, vowel counts), the same for the same seed.",
         what=["Generates practice jobs from a seed number, cycling through three kinds of job.",
               "Each job's right answer is computed by code at the same time.",
               "The same seed always gives exactly the same jobs, so runs can be compared fairly."],
         proposes="Nothing.", disposes="Plain code picks the numbers and words and computes the answers.",
         anchors=["amoeba/task/source.py::ToyTaskSource", "amoeba/task/source.py::_make"]),
    dict(id="free_text", view="task", title="Free-text task", kind="plain", plan="Free-text task",
         sentence="A job you type yourself; it runs normally but has no known answer, so it gets no score.",
         what=["When you give a sentence instead of asking for practice jobs, it becomes a single job.",
               "It has no known answer, so its score stays empty.",
               "Everything else runs exactly as for a practice job."],
         proposes="Nothing.", disposes="Plain code wraps your text as a job.",
         anchors=["scripts/run_task.py::main", "scripts/run_task.py::parse_args"]),
    dict(id="task_record", view="task", title="Task", kind="data", plan="Task",
         sentence="The single record every later step reads: the job text, its kind and, for practice jobs, the answer.",
         what=["A small record with an id, the job text, its kind, the known answer if any, and tags.",
               "Jobs with no single right answer may carry a rubric instead: deliverables, numbers with units, "
               "constraints and things the answer must not do.",
               "The planner only ever reads the job text; the answer and the rubric are used only for scoring."],
         proposes="Nothing.", disposes="Plain code; the record's fields are fixed.",
         anchors=["amoeba/task/models.py::Task"]),
    dict(id="handoff", view="task", title="→ Box 2", kind="plain", plan="→ Box 2",
         sentence="Passes the job to the team planner, which reads only the job text.",
         what=["The job moves to the planning box.",
               "The planner sees the job text, never the known answer or the rubric (a test sends a rubric full of "
               "marker words through every prompt and checks none arrives)."],
         proposes="Nothing.", disposes="Plain code passes the record on.",
         anchors=["amoeba/task/draft.py::draft_team"], guard_anchors=[]),
    dict(id="scoring", view="task", title="Scoring (after Box 3)", kind="code", plan="Scoring (after Box 3)",
         sentence="Compares the team's answer with the known answer; a job with no single right answer is scored "
                  "against its rubric instead.",
         what=["After the run, the team's answer is compared with the known answer.",
               "Both are lower-cased, runs of spaces are squeezed to one, and trailing full stops are dropped.",
               "An exact match scores 1, anything else 0.",
               "A job with a rubric and no known answer gets the fraction of rubric items it passes: each deliverable "
               "and constraint found by pattern, each number found with its unit within a tolerance (10 TB and "
               "9.1 TiB are the same amount), and nothing it must not do (such as a price with no source nearby).",
               "No AI judges the answer in Phase 1; a hook can store a judge's view beside the score, never in it."],
         proposes="The answer text (from the team).", disposes="Plain code decides match or no match.",
         anchors=["amoeba/task/evaluate.py::normalise", "amoeba/task/evaluate.py::score",
                  "amoeba/task/evaluate.py::rubric_score", "amoeba/task/evaluate.py::number_found",
                  "amoeba/task/models.py::Rubric"]),
    # ---------------------------------------------------------------- plan view
    dict(id="planner", view="plan", title="Planner", kind="llm", plan="Planner", ai="planner",
         sentence="An AI writes the list of helpers and a numbered step plan; later rounds see only the latest critique.",
         what=["The planning AI reads the job and the tools that exist, then writes each helper as a small record "
               "and a numbered plan saying which helper does which step.",
               "From the second round on it also sees its own last draft and the checkers' latest suggestions.",
               "Its reply must contain five labelled parts; see Split sections for what happens if one is missing.",
               "It is told to prefer the tools that exist; a tool or skill it needs but we lack goes in an optional "
               "sixth part, Capability Requests, which costs no retry when absent.",
               "At most three rounds are run.",
               "With our prompts (d24) it may also list Open Questions: each ambiguity in the job and the assumption "
               "it took. With --interactive the person sees the requirements, assumptions and open questions and "
               "types continue, or a correction that is added to the job before one more round."],
         proposes="Helpers (name, description, tools, suggestions, instructions), the step plan, and replies to the "
                  "checkers' feedback.",
         disposes="Nothing is accepted yet: the draft goes to the two checkers, and only the last draft is cleaned "
                  "and checked by plain code after the loop.",
         prompts=["autoagents_create_roles", "autoagents_create_roles_format"], system="MANAGER_PREFIX",
         derived_prompts=["autoagents_create_roles_d19", "autoagents_create_roles_format_d19"],
         alt_prompts=["d24_planner_system", "d24_create_team", "d24_create_team_format"],
         output_checks=["amoeba/task/draft.py::_sections", "amoeba/interp/trace.py::TracedLLM.chat_sections", "amoeba/task/parsers.py::require"], ai_entry="amoeba/task/draft.py::_sections",
         anchors=[("amoeba/task/draft.py::draft_team", None, "# state 1"),
                  "amoeba/task/parsers.py::parse_open_questions", "scripts/run_task.py::ask_user"]),
    dict(id="split", view="plan", title="Split sections", kind="code", plan="Split sections",
         sentence="Cuts each AI reply into its labelled parts; a missing part gets one retry, then the plan is abandoned.",
         what=["Every AI reply in drafting and in step-by-step work is cut at its '##' headings into named parts.",
               "If a required part is missing, the AI is asked once more with the error attached.",
               "If the retry still lacks it, drafting stops with an error (or the run ends with a parse error)."],
         proposes="The reply text.", disposes="Plain code decides whether every required part is present.",
         anchors=["amoeba/task/parsers.py::parse_sections", "amoeba/task/parsers.py::require",
                  "amoeba/task/parsers.py::repair_prompt", "amoeba/interp/trace.py::TracedLLM.chat_sections",
                  "amoeba/task/draft.py::_sections"]),
    dict(id="agent_obs", view="plan", title="Agent Observer", kind="llm", plan="Agent Observer", ai="agent_observer",
         sentence="A second AI checks the list of helpers and replies with suggestions, or 'No Suggestions'.",
         what=["The checking AI reads the job, the drafted helpers, the capability requests and every earlier "
               "helper suggestion.",
               "A helper using a tool we lack that is not requested gets 'add a Capability Request for it', never "
               "'remove the tool'; a request may be questioned only if the job does not need that ability at all, "
               "not because an existing tool could work around it.",
               "It lists problems with the helpers, or writes 'No Suggestions'.",
               "It runs every round, even after it has once agreed."],
         proposes="Suggestions about the helpers, or 'No Suggestions'.",
         disposes="Plain code only looks for the words 'No Suggestions'; the text itself goes back to the planner.",
         prompts=["autoagents_check_roles", "autoagents_check_roles_format"], system="MANAGER_PREFIX",
         derived_prompts=["autoagents_check_roles_d19"],
         alt_prompts=["d24_agent_observer_system", "d24_review_team"],
         output_checks=["amoeba/task/draft.py::_sections", "amoeba/interp/trace.py::TracedLLM.chat_sections", "amoeba/task/parsers.py::require"], ai_entry="amoeba/task/draft.py::_sections",
         anchors=[("amoeba/task/draft.py::draft_team", "# state 1", "# state 2")]),
    dict(id="plan_obs", view="plan", title="Plan Observer", kind="llm", plan="Plan Observer", ai="plan_observer",
         sentence="A third AI checks the step plan; the loop stops when both checkers say 'No Suggestions' in one round.",
         what=["The plan-checking AI reads the job, the helpers, the step plan, the capability requests and every "
               "earlier plan suggestion; like the helper checker, it may question a request only on need.",
               "It lists problems with the plan, or writes 'No Suggestions'.",
               "Drafting stops early only when both checkers wrote 'No Suggestions' in the same round."],
         proposes="Suggestions about the plan, or 'No Suggestions'.",
         disposes="Plain code decides whether the round reached agreement.",
         prompts=["autoagents_check_plans", "autoagents_check_plans_format"], system="MANAGER_PREFIX",
         derived_prompts=["autoagents_check_plans_d19"],
         alt_prompts=["d24_plan_observer_system", "d24_review_plan"],
         output_checks=["amoeba/task/draft.py::_sections", "amoeba/interp/trace.py::TracedLLM.chat_sections", "amoeba/task/parsers.py::require"], ai_entry="amoeba/task/draft.py::_sections",
         anchors=[("amoeba/task/draft.py::draft_team", "# state 2", "# publish")]),
    dict(id="envelope", view="plan", title="Allowed tools and team size", kind="code", plan=None,
         sentence="The rulebook the planner is held to: which tools exist and how many helpers a team may have.",
         what=["Lists the tools each kind of helper may use and the largest team allowed.",
               "The planner and both checkers are shown this tool list in their prompts.",
               "Plain code uses it to strip unknown tools and to reject teams that break the rules."],
         proposes="Nothing.", disposes="Plain code; the AI cannot change it.",
         anchors=["amoeba/safety/envelope.py::Envelope"]),
    dict(id="checks", view="plan", title="Plain-code checks on the final draft", kind="code",
         plan="Plain-code checks on the final draft",
         sentence="Throws out broken or nameless helper entries, records tools we lack instead of dropping them, "
                  "flags the summariser, and drops steps that name nobody.",
         what=["Reads the helper records and the numbered steps out of the last draft.",
               "Skips records that are not valid, have no name, or repeat a name; tools we lack go to the tool "
               "resolver below.",
               "Flags the summariser: the helper the planner marked, else the last helper of the last step (having "
               "no tools no longer decides it; nothing is appended). Then requires a team size in the allowed range.",
               "Matches each step's names to helpers (exact first, then by part of the name) and drops steps that match "
               "nobody; no steps left means drafting failed.",
               "Measures the draft: every requirement covered, dependencies valid, helpers fully described, one "
               "summariser, a checking step done by a helper that did not produce what it checks, and task "
               "coverage: every number in the task and every deliverable verb (deliver, estimate, assess, prototype, "
               "test, gather, build, plan) must reach a requirement or a given.",
               "With the quality gate on, a draft failing a must-have check goes back to the planner for one more "
               "round with the failed checks listed, within the round cap."],
         proposes="The final draft text.",
         disposes="Everything listed here; the original project trusted the AI for all of it.",
         anchors=[("amoeba/task/draft.py::draft_team", "# publish", None), "amoeba/task/draft.py::pick_summariser",
                  "amoeba/task/draft.py::assemble", "amoeba/task/quality.py::draft_quality",
                  "amoeba/task/quality.py::gate_suggestions", "amoeba/task/quality.py::task_coverage",
                  "amoeba/task/draft.py::role_blobs",
                  "amoeba/task/parsers.py::parse_role_blobs", "amoeba/task/parsers.py::parse_plan",
                  "amoeba/task/models.py::DraftedRole"]),
    dict(id="instantiate", view="plan", title="Build the team (instantiate)", kind="code",
         plan="Build the team (instantiate)",
         sentence="Gives each helper a permanent id, wires the helpers for the chosen shape, and rejects the team "
                  "if any rule is broken.",
         what=["Each helper gets a permanent id and its drafted instructions, tools and suggestions.",
               "Step by step: every helper of one step hands on to every helper of the next.",
               "One writer with reviewers: the helper flagged as summariser writes, all others review.",
               "The finished team is checked against every validation rule; any failure stops the run."],
         proposes="Nothing new; it works from the cleaned draft.",
         disposes="Plain code builds and validates the team.",
         anchors=["amoeba/task/instantiate.py::instantiate", "amoeba/config/validate.py::validate"]),
    dict(id="resolver", view="plan", title="Tool resolver", kind="code", plan=None,
         sentence="Keeps the tools that exist; a tool we lack is recorded as a request, never used and never silently "
                  "dropped.",
         what=["After drafting: each helper's tools are split into the ones the registry has (kept) and the rest "
               "(its missing tools). Each missing one becomes a capability request unless the planner already "
               "asked for it.",
               "The planner's own Capability Requests part is read as JSON; entries without a name are ignored.",
               "During the run: a helper with missing tools is told 'Tool X is unavailable this run; proceed "
               "without it or answer BLOCKED: X'. BLOCKED ends that helper's step and is logged.",
               "A helper that names a tool it does not have gets a notice instead of an echo; the log gets an "
               "'unknown_tool' line and, if no such tool exists at all, a request is recorded.",
               "Nothing is built here. From D56 Box 3 starts by trying to fill each request from the tool/skill pool "
               "(see Stock the toolbox); a request it cannot fill keeps the behaviour above."],
         proposes="Tool names in helper records, the Capability Requests part, and helper actions.",
         disposes="Plain code decides what is registered; the AI can only ask.",
         anchors=["amoeba/task/draft.py::resolve_tools", "amoeba/task/draft.py::parse_capability_requests",
                  "amoeba/interp/runtime.py::Interpreter._dispatch", "amoeba/interp/runtime.py::with_unavailable"]),
    dict(id="capreq", view="plan", title="Capability requests", kind="data", plan=None,
         sentence="Every tool or skill the team asked for and did not get, saved as capability_requests.json.",
         what=["One record per request: name, tool or skill, for which helper, what it does, input, output and an "
               "example of each.",
               "Where it came from: the planner's list, a helper's tool list, or an action during the run.",
               "Also in result.json (with the steps that answered BLOCKED) and as one log line each.",
               "result.json also says how many requests round 1 proposed and how many were gone from the final draft "
               "(requests_proposed, requests_dropped_by_observers).",
               "Each request keeps the name as written and a standard name from a list of known aliases "
               "('Web Search' and 'web research' are both web_search); names not on the list are reported as "
               "unmapped so the list can grow.",
               "D56: each request also says what Box 3's toolbox step did with it: status filled or unfilled, the "
               "pool id picked, the candidates shown and the reason code when it stayed unfilled."],
         proposes="Nothing.", disposes="Plain code writes the file, empty when nothing was asked for.",
         anchors=["amoeba/task/models.py::CapabilityRequest", "amoeba/capabilities/__init__.py::normalise",
                  "scripts/run_task.py::run_one"], guard_anchors=[]),
    dict(id="teamconfig", view="plan", title="TeamConfig", kind="data", plan="TeamConfig",
         sentence="The finished team written down as data: who exists, what each may use and who hands work to whom.",
         what=["The team as a data record: helpers, connections, where work starts and which helper gives the answer.",
               "It is saved as team.yaml in the run folder and can be fingerprinted to spot identical teams."],
         proposes="Nothing.", disposes="Plain code.",
         anchors=["amoeba/config/schema.py::TeamConfig", "amoeba/config/schema.py::AgentSpec",
                  "amoeba/config/io.py::config_hash", "amoeba/config/io.py::dump_yaml"], guard_anchors=[]),
    # ---------------------------------------------------------------- run view
    dict(id="teamconfig@run", ref="teamconfig", view="run", title="TeamConfig", kind="data", plan=None,
         sentence="The team from Box 2.", anchors=[]),
    dict(id="interpreter", view="run", title="Interpreter", kind="code", plan="Interpreter",
         sentence="Reads the team's shape and hands the job to the matching runner.",
         what=["Opens the log entry for the whole run and picks the runner for the team's shape.",
               "If an AI reply cannot be read at all, the run ends with a parse error instead of crashing.",
               "It has an unused listening hook that a later phase's monitor will plug into."],
         proposes="Nothing.", disposes="Plain code chooses the runner; the shape was fixed when the run started.",
         anchors=["amoeba/interp/runtime.py::Interpreter.__init__", "amoeba/interp/runtime.py::Interpreter.run"]),
    dict(id="each_step", view="run", title="For each step", kind="code", plan="For each step",
         sentence="Walks through the plan's steps in order, giving each step everything the earlier steps produced.",
         what=["Takes the plan's steps one at a time, in order.",
               "Each step sees the job plus the published result of every earlier step.",
               "The run's answer is the last step's final answer."],
         proposes="Nothing.", disposes="Plain code decides the order and what each step sees.",
         anchors=[("amoeba/interp/runtime.py::Interpreter.run_flat", None, "while sum(consensus)"),
                  ("amoeba/interp/runtime.py::Interpreter.run_flat", "published = response", None)]),
    dict(id="helper", view="run", title="Helper(s) named in the step", kind="llm",
         plan="Helper(s) named in the step", ai="worker",
         sentence="The AI helper for a step reads the step, the earlier results and a shared scratchpad, then picks one action.",
         what=["Each helper named in the step gets its own drafted instructions plus the step, earlier results and "
               "a scratchpad shared with the other helpers of that step.",
               "If its role named a tool we lack, one line per such tool says it is unavailable this run and that "
               "it may answer BLOCKED.",
               "It must reply with a current sub-step, one action and that action's input.",
               "The action is a tool name, 'Print', or 'Final Output'."],
         proposes="One action and its input per turn.",
         disposes="Plain code decides whether the action is a real tool, runs it, and decides when the step is done.",
         prompts=["autoagents_custom_action", "autoagents_custom_action_format"], system="GROUP_PREFIX",
         output_checks=["amoeba/interp/trace.py::TracedLLM.chat_sections", "amoeba/task/parsers.py::require"],
         ai_entry="amoeba/interp/runtime.py::Interpreter._llm_sections",
         anchors=[("amoeba/interp/runtime.py::Interpreter.run_flat", "for i, agent in", "act, inp = sec"),
                  "amoeba/interp/runtime.py::with_unavailable"]),
    dict(id="read_action", view="run", title='Read "## Action"', kind="code", plan='Read "## Action"',
         sentence="Reads the helper's chosen action: runs a tool and loops, or accepts a final answer; gives up after five turns.",
         what=["If the chosen action is one of the helper's tools, the tool runs and its result goes on the scratchpad.",
               "'Final Output' marks that helper done; the step ends when every helper of it is done.",
               "'BLOCKED: X' also marks the helper done and is recorded; a blocked last step without a final answer "
               "ends the run with error 'blocked'.",
               "A tool the helper does not have is not run: it gets a notice and the log an 'unknown_tool' line.",
               "On the last allowed turn a 'please synthesize' hint is added to the scratchpad.",
               "If turns run out, the last reply is kept and the run is marked as having hit the turn limit."],
         proposes="The action name and input.",
         disposes="Plain code checks the action against the helper's own tool list and counts turns.",
         anchors=[("amoeba/interp/runtime.py::Interpreter.run_flat", "while sum(consensus)", "for i, agent in"),
                  ("amoeba/interp/runtime.py::Interpreter.run_flat", "act, inp = sec", "published = response"),
                  "amoeba/interp/runtime.py::Interpreter._dispatch", "amoeba/interp/runtime.py::Interpreter._tool"]),
    dict(id="solver", view="run", title="Solver", kind="llm", plan="Solver", ai="solver",
         sentence="One AI writes the answer and rewrites it whenever a reviewer objects; an empty reply gets one retry.",
         what=["The writer sees the job, then its own past answers and the reviewers' objections as chat history.",
               "It writes a full new answer each time it is asked.",
               "It is asked at most four times: once, then once per review round with an objection."],
         proposes="The answer text.",
         disposes="Plain code decides when it is asked again and takes its last answer as the result.",
         prompts=["agentverse_solver_prepend", "agentverse_solver_append"],
         derived_prompts=["agentverse_solver_append_generic"],
         ai_entry="amoeba/interp/runtime.py::Interpreter.run_boss_reviewers.call",
         anchors=["amoeba/interp/runtime.py::Interpreter.run_boss_reviewers.solve",
                  "amoeba/interp/runtime.py::Interpreter.run_boss_reviewers.call"]),
    dict(id="critics", view="run", title="Critics (all others)", kind="llm", plan="Critics (all others)", ai="critic",
         sentence="Every other helper reviews the answer and must reply Agree or Disagree; unreadable replies count as agreement.",
         what=["Each reviewer sees the job, its own role and the recent chat history (answers and objections).",
               "Its first line must be exactly 'Action: Agree' or 'Action: Disagree'; a disagreement carries a reason.",
               "A reply that cannot be read twice in a row is treated as silent, which counts as agreeing."],
         proposes="Agree, or Disagree with a reason.",
         disposes="Plain code reads the verdict with a strict pattern; anything else is retried once, then ignored.",
         prompts=["agentverse_critic_prepend", "agentverse_critic_append"],
         ai_entry="amoeba/interp/runtime.py::Interpreter.run_boss_reviewers.call",
         anchors=["amoeba/interp/runtime.py::Interpreter.run_boss_reviewers.review",
                  "amoeba/task/parsers.py::parse_critic"]),
    dict(id="disagree", view="run", title="Anyone disagree?", kind="code", plan="Anyone disagree?",
         sentence="Counts the objections: none ends the run; otherwise everyone sees them and the writer revises, "
                  "up to three rounds.",
         what=["After each review round, plain code keeps only the disagreeing reviews that carry a reason.",
               "None left: the run ends and the current answer is the result.",
               "Otherwise the objections are shared with everyone and the writer revises.",
               "After the last round the final revision is not reviewed again."],
         proposes="Nothing.", disposes="Plain code counts the objections and caps the rounds.",
         anchors=[("amoeba/interp/runtime.py::Interpreter.run_boss_reviewers", "plan = solve()", None),
                  "amoeba/interp/runtime.py::Interpreter.run_boss_reviewers.broadcast"]),
    # ---------------------------------------------------------------- run view: the plan runner (D31–D36)
    dict(id="plan_graph", view="run", title="Step graph (depends_on)", kind="code", plan=None,
         sentence="Builds the order of work from each step's 'depends on' line and rejects a plan that loops.",
         what=["Reads which earlier steps each step depends on; a plan with no such lines runs as a simple chain.",
               "A dependency on a step the planner wrote but Box 2 dropped is pointed at that step's own "
               "dependencies, and the change is logged.",
               "An unknown step number or a loop stops the team from being built, before any AI call.",
               "Steps whose inputs are ready form a wave; waves run one after another (the wave is logged)."],
         proposes="The depends_on lines (from the planner).",
         disposes="Plain code builds the graph, the order and what each step may see.",
         anchors=["amoeba/interp/plan_runner.py::waves", "amoeba/interp/plan_runner.py::dependencies",
                  "amoeba/interp/plan_runner.py::relink", "amoeba/interp/plan_runner.py::PlanRunner.run"]),
    dict(id="plan_step", view="run", title="Plan step helper(s)", kind="llm", plan=None, ai="plan_worker",
         sentence="An AI helper carries out one step, seeing only the job, its role card, its step and its inputs.",
         what=["The helper sees its role card (goal, skills, constraints, outputs, success criteria), the step with "
               "its do / output / done-when lines, and only the outputs of the steps it depends on.",
               "It must tag every figure with a source id [S#] or [unverified], and mark what it could not do as "
               "BLOCKED: <capability>.",
               "It picks one action per turn: a tool, Print, or Final Output; up to 5 turns per step.",
               "With --web-tools, a role that asked for web search also gets web_search and fetch_url.",
               "After the step, what plain code found goes back to the helper for one refine turn (--self-refine). In "
               "a step with several roles the first drafts and the others AGREE or REVISE with numbered issues, at "
               "most 2 rounds (--collab critique); the step keeps one output."],
         proposes="One action and its input per turn; the step's output.",
         disposes="Plain code decides what the helper sees, runs the tools, and caps the turns.",
         prompts=["plan_step", "plan_step_system", "plan_critique"],
         anchors=["amoeba/interp/plan_runner.py::PlanRunner.run_step", "amoeba/interp/plan_runner.py::PlanRunner._loop",
                  "amoeba/interp/plan_runner.py::PlanRunner._turn", "amoeba/interp/plan_runner.py::plan_card",
                  "amoeba/interp/plan_runner.py::step_detail", "amoeba/interp/plan_runner.py::full_action_input",
                  "amoeba/interp/plan_runner.py::PlanRunner.grant_web_tools",
                  "amoeba/interp/plan_runner.py::PlanRunner.refine", "amoeba/interp/plan_runner.py::PlanRunner.critique",
                  "amoeba/interp/plan_runner.py::PlanRunner._review"]),
    dict(id="step_check", view="run", title="Check the step", kind="code", plan=None,
         sentence="Checks each step's output against its output and done-when lines, reads verdicts and gaps.",
         what=["Checks what the planner said the step produces: the table:, list:, code: or memo: markers in its "
               "output line (keywords only when there are none), and a real use of its inputs.",
               "A failed check gets one retry with the reasons and two turns of its own; otherwise the step is "
               "incomplete.",
               "A step the planner marked kind: verify must answer PASS or FAIL; a FAIL sends each step it checked "
               "back once, then it checks again. Steps that already used the old output are marked stale "
               "(--rerun-stale redoes them once).",
               "BLOCKED lines make a producer step partial, with the missing capability listed; the answer step is "
               "never scanned for them."],
         proposes="The step's output and verdict (from the helper).",
         disposes="Plain code decides done, partial or incomplete, the retry and the rework.",
         anchors=["amoeba/interp/plan_runner.py::step_checks", "amoeba/interp/plan_runner.py::uses_inputs",
                  "amoeba/interp/plan_runner.py::output_markers", "amoeba/interp/plan_runner.py::PlanRunner.mark_stale",
                  "amoeba/interp/plan_runner.py::parse_verdict_block",
                  "amoeba/interp/plan_runner.py::blocked_marks", "amoeba/interp/plan_runner.py::PlanRunner.is_verification",
                  "amoeba/interp/plan_runner.py::PlanRunner.rework_producers"]),
    dict(id="provenance", view="run", title="Where each figure came from", kind="code", plan=None,
         sentence="Counts every number in a step's output as cited, unverified, given, derived, inherited or untagged.",
         what=["A number is cited when its line carries a source id the step could have seen.",
               "Numbers from the task, from a calculation shown or run, and from the step's inputs are counted apart.",
               "A source id the step never saw is counted as a made-up citation.",
               "A run-wide ledger keeps each figure's first status and step, so a figure that entered untagged stays "
               "untagged however often later steps or the answer copy it.",
               "It only measures; nothing is rejected on these counts."],
         proposes="Nothing.", disposes="Plain code counts; the totals go to result.json.",
         anchors=["amoeba/interp/provenance.py::check_provenance", "amoeba/interp/provenance.py::total",
                  "amoeba/interp/provenance.py::claim_numbers"]),
    dict(id="artifacts", view="run", title="Step artifacts", kind="data", plan=None,
         sentence="Each step's output saved as a file, with who wrote it, what it saw, its status and its sources.",
         what=["runs/<id>/artifacts/step_<n>.md holds the text; step_<n>.json the step, wave, roles, inputs, "
               "status, checks, verdict, sources and figure counts.",
               "A reworked step keeps its first version as step_<n>.first.md."],
         proposes="Nothing.", disposes="Plain code writes them.",
         anchors=["amoeba/interp/plan_runner.py::PlanRunner._save"]),
    dict(id="plan_summary", view="run", title="Summariser assembles", kind="llm", plan=None, ai="plan_summariser",
         sentence="An AI assembles the final answer from every step's output, adding nothing new, and lists the gaps.",
         what=["Sees every step's latest output with its status, missing capabilities, verdict and figure counts, "
               "and the deliverables the plan committed to (never the scoring rubric).",
               "Must add no new analysis or numbers, answer in the form the job asks for, and list gaps under "
               "Limitations when there are any.",
               "Code counts any number it adds, lists the answer's untagged and unverified figures, and appends a "
               "line for any missing capability it left out.",
               "Each input is cut at 6,000 characters and all of them at 30,000 (marked). When several final steps "
               "have no summariser step, code puts their outputs together under headings instead."],
         proposes="The final answer.",
         disposes="Plain code counts new numbers and completes the Limitations section.",
         prompts=["plan_summarise", "plan_step_system"],
         anchors=["amoeba/interp/plan_runner.py::PlanRunner.all_inputs_text",
                  "amoeba/interp/plan_runner.py::PlanRunner.summary_check",
                  "amoeba/interp/plan_runner.py::PlanRunner.enforce_limitations",
                  "amoeba/interp/plan_runner.py::PlanRunner.is_summary_step",
                  "amoeba/interp/plan_runner.py::PlanRunner.assemble_by_code",
                  "amoeba/interp/plan_runner.py::PlanRunner.ledger_update"]),
    dict(id="trace", view="run", title="Every AI call → one trace line", kind="data",
         plan="Every AI call → one trace line",
         sentence="Writes one log line per AI call and tool call: who, which model, tokens and time. Nothing enforces a budget.",
         what=["Every AI call becomes one log line with the helper, model, tokens in and out, and time taken.",
               "Tool calls, each helper's turn and the whole run get their own lines too.",
               "Point events are logged too: capability_request, blocked and unknown_tool.",
               "From the command line each AI line also holds the exact prompt sent and the reply received "
               "(turn off with --no-log-content).",
               "Token counts are only recorded; no code reads them to stop a run.",
               "Every line names the model profile; each AI line holds the model asked for and the exact model name "
               "the service returned."],
         proposes="Nothing.", disposes="Plain code writes the log.",
         anchors=["amoeba/interp/trace.py::TraceWriter", "amoeba/interp/trace.py::TraceWriter.event",
                  "amoeba/interp/trace.py::TracedLLM.chat_messages",
                  "amoeba/interp/trace.py::NoopListener"], guard_anchors=[]),
    dict(id="runresult", view="run", title="RunResult", kind="data", plan="RunResult",
         sentence="The one-line summary of a run: answer, score, calls, tokens, draft rounds and whether the checkers agreed.",
         what=["Summarises the run in one record saved as result.json.",
               "Calls and tokens are totalled from the log; draft rounds and agreement come from the draft.",
               "It also lists the steps that answered BLOCKED and every capability request, and counts how many "
               "requests round 1 made and how many the checkers talked the planner out of."],
         proposes="Nothing.", disposes="Plain code.",
         anchors=["amoeba/task/models.py::RunResult", "scripts/run_task.py::run_one"], guard_anchors=[]),
    dict(id="tools", view="run", title="Tool box", kind="code", plan=None,
         sentence="Repeat a text back or do arithmetic safely; with --web-tools the plan runner also has web search "
                  "and page reading.",
         what=["Tools are looked up by name; a name that is not registered is an error, not a web search.",
               "The arithmetic tool accepts numbers and + − × ÷ and powers only, never arbitrary code.",
               "web_search and fetch_url (Tavily) give every result a source id [S#]; searches and fetches per step, "
               "page length and time are capped, and a failure comes back as an error line, never a crash.",
               "Pool tools (D56) are remote MCP servers registered as pool:<name> for the helper that asked; they "
               "run here too, with the same caps, [S#] source ids and error lines.",
               "This is the single place any tool is ever run."],
         proposes="A tool name and its input (from a helper).",
         disposes="Plain code checks the name and the arithmetic before anything runs.",
         anchors=["amoeba/tools/registry.py::ToolRegistry", "amoeba/tools/registry.py::calc",
                  "amoeba/tools/registry.py::default_registry", "amoeba/tools/web.py::WebTools",
                  "amoeba/tools/web.py::TavilyProvider", "amoeba/tools/web.py::web_registry"]),
    dict(id="toolbox", view="run", title="Stock the toolbox", kind="code", plan=None,
         sentence="Before the team starts, tries to fill each tool or skill the team asked for from the pool; one AI "
                  "pick per request, everything else plain code.",
         what=["Match: the cached pool entries, tools and skills alike (the requested kind is only the planner's "
               "guess; the kind asked and the kind picked are logged), are ranked by the words they share with the "
               "request (its standard name and aliases, name, what it does, input and output); the best 5 "
               "(pool.yaml) are kept. None above zero: unfilled, no AI call.",
               "Pick: one short AI call shows the request and those candidates and must answer exactly one listed id "
               "or NONE; any other reply counts as NONE.",
               "Vet: a tool needs an HTTPS remote, a source repository, a pinned version, no key or its key in the "
               "environment, and an unchanged description (also re-checked against the server's tools/list at every "
               "connection); a skill must be instruction-only and at most 5,000 characters. At most 3 items per "
               "helper and 8 per run (pool.yaml).",
               "Attach: a tool becomes pool:<name> for the asking helper only; a skill's text goes on that helper's "
               "card. All pool text is shown inside marked data blocks, and the 'unavailable' line goes away.",
               "Every request's outcome and reason code is written to capability_requests.json and result.json; "
               "without a pool cache the run logs pool_unavailable and goes on as before."],
         proposes="The picker names one candidate (or NONE).",
         disposes="Plain code ranks the candidates, rejects anything unsafe or over the caps, and attaches.",
         anchors=["amoeba/pool/stock.py::stock_toolbox", "amoeba/pool/stock.py::pick", "amoeba/pool/stock.py::vet",
                  "amoeba/pool/match.py::rank", "amoeba/pool/mcp.py::PoolTools", "amoeba/pool/mcp.py::SdkConnector"]),
    dict(id="pool_index", view="run", title="Pool index (cache)", kind="data", plan=None,
         sentence="The tools and skills Box 3 may draw on, fetched ahead of time by `amoeba pool refresh`; a run only "
                  "reads it.",
         what=["Tools: the official MCP Registry, the latest version of each server (remote, repository, version, "
               "whether a key is needed).",
               "Skills: SKILL.md files from a shallow git clone of github.com/anthropics/skills (only the repository "
               "named in pool.yaml), with whether the skill ships scripts and the length of its text.",
               "Sources are listed in amoeba/config/pool.yaml, one line each; the cache is data/pool/."],
         proposes="Nothing.", disposes="Plain code fetches and stores; no AI call.",
         anchors=["amoeba/pool/index.py::refresh", "amoeba/pool/index.py::load_index",
                  "amoeba/pool/index.py::load_pool_config", "amoeba/cli.py::main"], guard_anchors=[]),
    dict(id="client", view="run", title="AI connection", kind="code", plan=None,
         sentence="The connection to any AI service that speaks the OpenAI format; it reports what each reply cost in tokens.",
         what=["Sends the messages to the AI service and returns the reply with its token counts.",
               "Waits out rate limits (HTTP 429/503: up to 5 retries, Retry-After honoured, each wait logged), dropped "
               "connections and timeouts too; an error still there after that ends the run with error 'api: …' "
               "and its records are still written. It can space calls out, fold the system message into the user "
               "message and set the reasoning effort.",
               "With --llm-cache every reply is stored and can be replayed without a call; --max-tokens-per-run / "
               "--max-calls-per-run stop a run cleanly; every run prints its tokens and estimated cost.",
               "A named profile (amoeba/config/models.yaml, default gemma-api) sets the service, the model and how to "
               "call it; each role group (planner, checkers, helpers, reviewers, summariser) may get its own model "
               "and reply length. Every log line names the profile, and each AI line the exact model the service "
               "returned.",
               "Temperature is set once for the connection, not per helper.",
               "Every call from every box goes through here, wrapped so it is logged."],
         proposes="Nothing.", disposes="Plain code sends and receives; it never changes the text.",
         anchors=["amoeba/llm/client.py::OpenAICompatibleClient", "amoeba/llm/client.py::LLMClient",
                  "amoeba/llm/client.py::ChatResponse", "amoeba/llm/client.py::merge_system",
                  "amoeba/llm/cache.py::CachedLLM", "amoeba/llm/limits.py::RunLimits",
                  "amoeba/llm/limits.py::estimate", "amoeba/llm/profiles.py::RoleRouter",
                  "amoeba/llm/profiles.py::build_router", "scripts/run_task.py::build_llm"]),
    dict(id="toymock", view="run", title="Offline stand-in AI", kind="llm", plan=None, ai=None,
         sentence="A scripted pretend AI that answers the practice jobs correctly, so everything runs without a real AI.",
         what=["Recognises which role is being asked from a fixed phrase in the prompt.",
               "Answers from a script: a two-helper team, agreeing checkers, the calculator for sums, agreeing reviewers.",
               "Used by the command line when no real AI is configured, and by every test."],
         proposes="Scripted replies.", disposes="Everything downstream treats it exactly like a real AI.",
         anchors=["amoeba/llm/toy_mock.py::toy_mock_client", "amoeba/llm/client.py::MockLLMClient"]),
]

# boxes where plain code rejects, corrects or caps what an AI produced (shield icon when they have guards)
SHIELD = {"planner", "agent_obs", "plan_obs", "split", "checks", "instantiate", "interpreter", "each_step", "helper",
          "read_action", "solver", "critics", "disagree", "tools", "resolver", "plan_graph", "plan_step", "step_check",
          "plan_summary", "toolbox"}

GLOSSARY = [
    ("helper", "One AI worker in a team, with its own name, instructions and allowed tools."),
    ("team shape (topology)", "How helpers are connected; fixed when a run starts, never chosen by an AI."),
    ("step by step (flat)", "The plan's steps run in order; each step's helpers take turns until they give a final answer."),
    ("one writer with reviewers (boss + reviewers)", "One helper writes the answer, the others review it, the writer revises on objections."),
    ("draft", "The planner's proposed helpers and step plan for one round."),
    ("round", "One planner reply plus one reply from each checker."),
    ("turn", "One reply from each helper of a step."),
    ("consensus", "Both checkers wrote 'No Suggestions' in the same round."),
    ("section", "A '## Heading' part of an AI reply that plain code cuts out and reads."),
    ("guard", "A plain-code check that rejects, corrects or caps what an AI produced (shield icon)."),
    ("envelope", "The fixed rules a team must satisfy: allowed tools per role and the team-size limit."),
    ("trace", "The log file with one line per AI call, tool call, helper turn and run."),
    ("token", "The unit AI services count text in; recorded per call, never enforced in Phase 1."),
    ("sample run", "One practice job run with the offline stand-in AI when this page was built."),
    ("stand-in AI", "A scripted fake AI used offline; it is not a real model."),
    ("deviation", "A deliberate difference from the original AutoAgents / AgentVerse code, marked in the source."),
]


# ============================================================================================ code facts
class Facts:
    def __init__(self) -> None:
        self.trees: dict[str, ast.Module] = {}
        self.src: dict[str, list[str]] = {}
        for p in SOURCE_FILES:
            text = p.read_text(encoding="utf-8")
            self.trees[rel(p)] = ast.parse(text)
            self.src[rel(p)] = text.split("\n")
        self.defs: dict[str, dict] = {}        # "path::Qual" -> record
        self.by_name: dict[str, list[str]] = {}
        for path, tree in self.trees.items():
            self._collect(path, tree.body, "", None)

    def _collect(self, path, body, prefix, cls):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = f"{prefix}{node.name}"
                key = f"{path}::{qual}"
                self.defs[key] = {"node": node, "path": path, "qual": qual, "cls": cls,
                                  "kind": "class" if isinstance(node, ast.ClassDef) else "function"}
                self.by_name.setdefault(node.name, []).append(key)
                if isinstance(node, ast.ClassDef):
                    self._collect(path, node.body, qual + ".", node.name)
                else:
                    self._collect(path, node.body, qual + ".", cls)

    def resolve(self, key: str) -> dict | None:
        return self.defs.get(key)

    def line(self, path: str, n: int) -> str:
        return self.src[path][n - 1] if 0 < n <= len(self.src[path]) else ""

    def marker_line(self, key: str, marker: str | None, default: int) -> int:
        if marker is None:
            return default
        d = self.defs[key]
        for n in range(d["node"].lineno, d["node"].end_lineno + 1):
            if marker in self.line(d["path"], n):
                return n
        raise KeyError(f"marker {marker!r} not found in {key}")


# ============================================================================================ box tags
# A `# box: id1, id2` comment right above a def or class (decorators may sit between) puts that code in those
# boxes. The tags are the anchors in the code; BOXES keeps only their order and [from, to) line markers.
TAG = re.compile(r"^\s*#\s*box:\s*(.*?)\s*$")


def box_tags(F: Facts) -> tuple[dict[str, list[str]], list[str]]:
    """key -> box ids, and the problems: a tag followed by no def/class, or naming a box that does not exist."""
    ids = {B["id"] for B in BOXES}
    at_line = {(d["path"], d["node"].lineno): k for k, d in F.defs.items()}
    tags: dict[str, list[str]] = {}
    errors: list[str] = []
    for path, lines in F.src.items():
        for i, line in enumerate(lines):
            m = TAG.match(line)
            if not m:
                continue
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j].lstrip().startswith("@")):
                j += 1
            key = at_line.get((path, j + 1))
            named = [x.strip() for x in m.group(1).split(",") if x.strip()]
            if key is None:
                errors.append(f"{path}:{i + 1}: '# box:' tag is not directly above a def or class")
                continue
            for b in named:
                if b not in ids:
                    errors.append(f"{path}:{i + 1}: '# box: {b}' names no box in tools/arch_extract.py BOXES")
            tags.setdefault(key, []).extend(b for b in named if b in ids)
    return tags, errors


def check_anchors(F: Facts, tags: dict[str, list[str]]) -> list[str]:
    """Every BOXES anchor must resolve to code, and that code must carry the box's tag."""
    errors = []
    for B in BOXES:
        for a in B.get("anchors", []):
            key = a if isinstance(a, str) else a[0]
            if key not in F.defs:
                errors.append(f"box {B['id']}: anchor {key} points at code that does not exist")
            elif B["id"] not in tags.get(key, []):
                errors.append(f"box {B['id']}: {key} has no '# box: {B['id']}' tag above it")
    return errors


def tagged_anchors(tags: dict[str, list[str]]) -> None:
    """A def tagged for a box that BOXES does not list yet joins that box (after the listed ones)."""
    for B in BOXES:
        listed = {a if isinstance(a, str) else a[0] for a in B.get("anchors", [])}
        extra = sorted(k for k, ids in tags.items() if B["id"] in ids and k not in listed)
        if extra and not B.get("ref"):
            B["anchors"] = list(B.get("anchors", [])) + extra


def unassigned(F: Facts, tags: dict[str, list[str]], prev_defs: set[str] | None) -> list[dict]:
    """Top-level defs and classes with no tag on themselves, anything inside them, or anything around them.
    `new` = not in the previous build (every one of them is new only when there is no previous list)."""
    tagged = set(tags)
    out = []
    for k, d in F.defs.items():
        if "." in d["qual"]:
            continue
        if k in tagged or any(t.startswith(k + ".") for t in tagged):
            continue
        out.append({"key": k, "name": d["qual"], "path": d["path"], "line": d["node"].lineno, "kind": d["kind"],
                    "new": prev_defs is not None and k not in prev_defs})
    return sorted(out, key=lambda u: (not u["new"], u["key"]))


def first_doc_line(node) -> str:
    doc = ast.get_docstring(node) if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) else None
    return doc.strip().split("\n")[0] if doc else ""


def signature(node: ast.FunctionDef) -> str:
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{node.name}({ast.unparse(node.args)}){ret}"


def modules(F: Facts) -> list[dict]:
    out = []
    for path, tree in F.trees.items():
        imports = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] in ("amoeba", "scripts"):
                imports.add(n.module)
        out.append({"path": path, "doc": first_doc_line(tree), "imports": sorted(imports),
                    "kind": "script" if path.startswith("scripts/") else "package"})
    return out


def class_record(F: Facts, key: str) -> dict:
    d = F.defs[key]
    node: ast.ClassDef = d["node"]
    fields, methods = [], []
    for s in node.body:
        if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
            fields.append({"name": s.target.id, "type": ast.unparse(s.annotation),
                           "default": ast.unparse(s.value) if s.value is not None else None, "line": s.lineno})
        elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) and (not s.name.startswith("_") or s.name == "__init__"):
            methods.append({"name": s.name, "signature": signature(s), "line": s.lineno, "doc": first_doc_line(s)})
    return {"key": key, "kind": "class", "name": node.name, "path": d["path"], "line": node.lineno,
            "end_line": node.end_lineno, "bases": [ast.unparse(b) for b in node.bases],
            "decorators": [ast.unparse(x) for x in node.decorator_list], "doc": first_doc_line(node),
            "fields": fields, "methods": methods}


def call_name(call: ast.Call) -> tuple[str | None, str]:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id, ""
    if isinstance(f, ast.Attribute):
        return f.attr, ast.unparse(f.value)
    return None, ""


def own_nodes(fn):
    """Walk a function body without descending into nested defs."""
    stack = list(fn.body)
    while stack:
        n = stack.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if not isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                stack.append(c)


def call_graph(F: Facts) -> dict[str, list[str]]:
    graph: dict[str, set[str]] = {}
    for key, d in F.defs.items():
        if d["kind"] != "function":
            continue
        callees = set()
        for n in own_nodes(d["node"]):
            if isinstance(n, ast.Call):
                name, recv = call_name(n)
                cands = F.by_name.get(name or "", [])
                if len(cands) > 1 and recv == "self" and d["cls"]:
                    same = [c for c in cands if F.defs[c]["cls"] == d["cls"] or F.defs[c]["qual"].startswith(d["cls"] + ".")]
                    cands = same or cands
                if len(cands) > 1:   # prefer a nested def of this same function
                    nested = [c for c in cands if c.startswith(key + ".")]
                    cands = nested or cands
                callees.update(cands)
        graph[key] = callees
    return {k: sorted(v) for k, v in graph.items()}


def function_record(F: Facts, key: str, graph) -> dict:
    d = F.defs[key]
    node = d["node"]
    callers = sorted(k for k, v in graph.items() if key in v)
    return {"key": key, "kind": "function", "name": d["qual"], "path": d["path"], "line": node.lineno,
            "end_line": node.end_lineno, "signature": signature(node), "doc": first_doc_line(node),
            "callers": callers, "callees": graph.get(key, [])}


# ---------------------------------------------------------------------------------------------- guards
def effect_of(stmts) -> str | None:
    for s in stmts:
        if isinstance(s, ast.Raise):
            return "raise " + (ast.unparse(s.exc.func if isinstance(s.exc, ast.Call) else s.exc) if s.exc else "")
        if isinstance(s, ast.Continue):
            return "skip (continue)"
        if isinstance(s, ast.Break):
            return "stop (break)"
        if isinstance(s, ast.Return):
            return "return " + (ast.unparse(s.value) if s.value is not None else "None")
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and call_name(s.value)[0] == "append":
            return "add " + ast.unparse(s.value.args[0]) if s.value.args else "append"
        if isinstance(s, (ast.Assign, ast.AugAssign)):
            return "set " + ast.unparse(s)[:90]
    return None


def guards(F: Facts) -> list[dict]:
    out = []
    for key, d in F.defs.items():
        if d["kind"] != "function":
            continue
        for n in own_nodes(d["node"]):
            rec = None
            if isinstance(n, ast.While):
                rec = ("loop cap", f"while {ast.unparse(n.test)}", "loop ends")
            elif isinstance(n, ast.For) and isinstance(n.iter, ast.Call) and call_name(n.iter)[0] == "range":
                rec = ("loop cap", f"for {ast.unparse(n.target)} in {ast.unparse(n.iter)}", "loop ends")
            elif isinstance(n, ast.If):
                eff = effect_of(n.body)
                if eff:
                    kind = "correct" if eff.startswith("add") else "reject" if eff.startswith(("raise", "skip")) \
                        else "decide" if eff.startswith("set") else "stop"
                    rec = (kind, f"if {ast.unparse(n.test)}", eff)
            elif isinstance(n, ast.IfExp):
                rec = ("fallback", ast.unparse(n), "choose value")
            elif isinstance(n, ast.comprehension):
                for cond in n.ifs:
                    out.append({"key": key, "path": d["path"], "line": cond.lineno, "kind": "filter",
                                "code": f"keep only if {ast.unparse(cond)}", "effect": "drop the rest"})
            elif isinstance(n, ast.ExceptHandler):
                typ = ast.unparse(n.type) if n.type else "any error"
                rec = ("fallback", f"except {typ}", effect_of(n.body) or ast.unparse(n.body[0])[:80])
            elif isinstance(n, ast.For) and n.orelse:
                pass
            if rec:
                out.append({"key": key, "path": d["path"], "line": n.lineno, "kind": rec[0], "code": rec[1],
                            "effect": rec[2]})
            if isinstance(n, ast.For) and n.orelse:
                out.append({"key": key, "path": d["path"], "line": n.orelse[0].lineno, "kind": "fallback",
                            "code": f"all attempts of `for {ast.unparse(n.target)} in {ast.unparse(n.iter)}` failed",
                            "effect": ast.unparse(n.orelse[0])})
    out.sort(key=lambda g: (g["path"], g["line"]))
    return out


def constants(F: Facts) -> list[dict]:
    out = []
    for path, tree in F.trees.items():
        for s in tree.body:
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name) \
                    and s.targets[0].id.isupper():
                try:
                    val = ast.literal_eval(s.value)
                except Exception:
                    val = ast.unparse(s.value)[:200]
                out.append({"name": s.targets[0].id, "path": path, "line": s.lineno, "value": val})
    return out


def field_default(F: Facts, cls_key: str, field: str):
    for f in class_record(F, cls_key)["fields"]:
        if f["name"] == field:
            return f
    return None


def const(C: list[dict], name: str, path: str | None = None):
    for c in C:
        if c["name"] == name and (path is None or c["path"] == path):
            return c
    return None


# ---------------------------------------------------------------------------------------------- prompts
def placeholders(text: str) -> list[str]:
    if "${" in text:
        return sorted(set(re.findall(r"\$\{(\w+)\}", text)))
    names = []
    try:
        for _lit, field, _spec, _conv in string.Formatter().parse(text):
            if field is not None and field not in names:
                names.append(field)
    except ValueError:
        return ["(unparseable)"]
    return names


def prompts(F: Facts) -> list[dict]:
    pdir = PKG / "config" / "prompts"
    loaders: dict[str, list[dict]] = {}
    for key, d in F.defs.items():
        if d["kind"] != "function":
            continue
        for n in own_nodes(d["node"]):
            stem = None
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "PROMPT":
                stem = n.attr
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("seed:"):
                stem = n.value[5:]
            if stem:
                loaders.setdefault(stem, []).append({"key": key, "path": d["path"], "line": n.lineno})
    out = []
    for p in sorted(pdir.glob("*.txt")):
        text = p.read_text(encoding="utf-8")
        head, _, body = text.partition("\n")
        style = "${x} (string.Template)" if "${" in body else "{x} (str.format, rendered once)"
        out.append({"stem": p.stem, "path": rel(p), "header": head, "text": body, "placeholders": placeholders(body),
                    "style": style, "loaded_by": loaders.get(p.stem, []),
                    "note": ("inserted as a value into another prompt, so its own placeholders stay literal"
                             if p.stem.endswith("_format") else "")})
    # the two AutoAgents system prefixes and the derived solver prompt are constants in prompts/__init__.py
    ppath = "amoeba/config/prompts/__init__.py"
    for s in F.trees[ppath].body:
        if isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name) and s.targets[0].id in ("MANAGER_PREFIX", "GROUP_PREFIX"):
            name = s.targets[0].id
            out.append({"stem": name, "path": f"{ppath}", "line": s.lineno, "header": f"constant in {ppath}:{s.lineno}",
                        "text": ast.literal_eval(s.value), "placeholders": [], "style": "literal system message",
                        "loaded_by": loaders.get(name, []) + [
                            {"key": k, "path": d["path"], "line": n.lineno} for k, d in F.defs.items()
                            if d["kind"] == "function" for n in own_nodes(d["node"])
                            if isinstance(n, ast.Name) and n.id == name], "note": ""})
    from amoeba.config.prompts import PROMPT
    line = next(i + 1 for i, l in enumerate(F.src[ppath]) if '"agentverse_solver_append_generic"' in l)
    out.append({"stem": "agentverse_solver_append_generic", "path": ppath, "line": line,
                "header": f"derived at load time in {ppath}:{line} from agentverse_solver_append",
                "text": PROMPT.agentverse_solver_append_generic, "placeholders": [], "style": "literal (derived)",
                "loaded_by": loaders.get("agentverse_solver_append_generic", []),
                "note": F.line(ppath, line - 3).strip() + " " + F.line(ppath, line - 2).strip()})
    from amoeba.config.prompts import CAPABILITY_EDITS
    line = next(i + 1 for i, l in enumerate(F.src[ppath]) if l.startswith("CAPABILITY_EDITS"))
    for stem, edits in CAPABILITY_EDITS.items():   # D19 variants: the verbatim file plus exact replacements
        out.append({"stem": f"{stem}_d19", "path": ppath, "line": line,
                    "header": f"derived at load time in {ppath}:{line} from {stem} (DEVIATION D19)",
                    "text": getattr(PROMPT, f"{stem}_d19"), "placeholders": placeholders(getattr(PROMPT, f"{stem}_d19")),
                    "style": "{x} (str.format, rendered once) — derived",
                    "loaded_by": loaders.get(f"{stem}_d19", []),
                    "derived_from": stem, "edits": [{"old": o, "new": n} for o, n in edits],
                    "note": f"{len(edits)} exact replacement(s): 'use only existing tools' → 'prefer existing tools; "
                            f"request a missing tool or skill under ## Capability Requests'"})
    return out


# ---------------------------------------------------------------------------------------------- AI call sites
def ai_call_sites(F: Facts) -> dict:
    sites = []
    for key, d in F.defs.items():
        if d["kind"] != "function":
            continue
        for n in own_nodes(d["node"]):
            if isinstance(n, ast.Call):
                name, recv = call_name(n)
                is_ai = name in AI_METHODS and ("llm" in recv or recv in ("self", "tl"))
                is_net = name == "create" and "completions" in recv
                if is_ai or is_net:
                    kw = {k.arg: ast.unparse(k.value) for k in n.keywords if k.arg}
                    pos = [ast.unparse(a) for a in n.args]
                    seed = kw.get("seed") or next((a for a in pos if "seed" in a), "default (0)")
                    sites.append({"key": key, "path": d["path"], "line": n.lineno, "call": f"{recv}.{name}",
                                  "seed": seed, "model": kw.get("model", "client setting"),
                                  "temperature": kw.get("temperature", "client setting"),
                                  "max_tokens": kw.get("max_tokens", "client setting")})
    init = F.defs["amoeba/llm/client.py::OpenAICompatibleClient.__init__"]["node"]
    a = init.args
    defaults = dict(zip([x.arg for x in a.args][-len(a.defaults):], [ast.unparse(x) for x in a.defaults]))
    build = F.defs["scripts/run_task.py::build_llm"]["node"]
    model_line = next((ast.unparse(s) for s in own_nodes(build)
                       if isinstance(s, ast.Assign) and ast.unparse(s.targets[0]) == "model"), "unknown")
    mock = next((ast.unparse(k.value) for n in ast.walk(F.defs["amoeba/llm/toy_mock.py::toy_mock_client"]["node"])
                 if isinstance(n, ast.Call) for k in n.keywords if k.arg == "model"), "unknown")
    runtime = F.trees["amoeba/interp/runtime.py"]
    per_helper_reads = sorted({n.attr for n in ast.walk(runtime) if isinstance(n, ast.Attribute)
                               and n.attr in ("model", "temperature", "max_tokens") and isinstance(n.ctx, ast.Load)})
    return {"sites": sites,
            "client_defaults": {"temperature": defaults.get("temperature", "unknown"),
                                "max_tokens": defaults.get("max_tokens", "unknown"),
                                "where": f"amoeba/llm/client.py:{init.lineno}"},
            "cli_model": model_line, "stand_in_model": mock,
            "per_helper_settings_read_by_runtime": per_helper_reads}


# ---------------------------------------------------------------------------------------------- tools
def tools(F: Facts) -> dict:
    node = F.defs["amoeba/tools/registry.py::default_registry"]["node"]
    regs = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and call_name(n)[0] == "register":
            name, desc, fn = (ast.literal_eval(n.args[0]), ast.literal_eval(n.args[1]), ast.unparse(n.args[2]))
            fkey = f"amoeba/tools/registry.py::{fn}"
            regs.append({"name": name, "description": desc, "function": fn, "line": n.lineno,
                         "fn_line": F.defs[fkey]["node"].lineno, "fn_doc": first_doc_line(F.defs[fkey]["node"])})
    ex = F.defs["amoeba/tools/registry.py::ToolRegistry.execute"]["node"]
    return {"registered": regs, "execute": {"path": "amoeba/tools/registry.py", "line": ex.lineno,
                                            "signature": signature(ex), "doc": first_doc_line(ex)}}


# ---------------------------------------------------------------------------------------------- DEVIATION notes
def deviations(F: Facts) -> list[dict]:
    out = []
    for path, lines in F.src.items():
        for i, l in enumerate(lines, 1):
            if "DEVIATION" in l and "#" in l:
                text = l[l.index("#"):].lstrip("# ").strip()
                ref = re.search(r"\bD(\d+)\b", l)
                out.append({"path": path, "line": i, "text": text, "id": f"D{ref.group(1)}" if ref else None})
    spec = (ROOT / "spec" / "BUILD_SPEC_PHASE1.md").read_text(encoding="utf-8").split("\n")
    table = []
    for i, l in enumerate(spec, 1):
        m = re.match(r"\| (D\d+) \| (.*?) \| (.*?) \| (.*?) \|$", l)
        if m:
            table.append({"id": m.group(1), "original": m.group(2), "ours": m.group(3), "why": m.group(4),
                          "path": "spec/BUILD_SPEC_PHASE1.md", "line": i})
    return out, table


# ============================================================================================ tests
def run_tests() -> dict:
    with tempfile.TemporaryDirectory() as td:
        xml = Path(td) / "junit.xml"
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}"],
                              cwd=ROOT, capture_output=True, text=True)
        results = {}
        for tc in ET.parse(xml).getroot().iter("testcase"):
            outcome = "failed" if tc.find("failure") is not None or tc.find("error") is not None else \
                      "skipped" if tc.find("skipped") is not None else "passed"
            fn = tc.get("name").split("[")[0]
            key = f"{tc.get('classname').replace('.', '/')}.py::{fn}"
            results.setdefault(key, []).append(outcome)
    summary = proc.stdout.strip().split("\n")[-1]
    return {"summary": summary, "results": {k: ("failed" if "failed" in v else "skipped" if all(x == "skipped" for x in v)
                                                 else "passed") + (f" ({len(v)} cases)" if len(v) > 1 else "")
                                             for k, v in results.items()}}


def test_map(F: Facts, graph, test_results) -> dict:
    """test -> directly referenced repo symbols (names used in the test body + fixtures it takes)."""
    conftest = ast.parse((ROOT / "tests" / "conftest.py").read_text())
    fixture_names = {}
    for n in conftest.body:
        if isinstance(n, ast.FunctionDef):
            fixture_names[n.name] = {x.id if isinstance(x, ast.Name) else x.attr for x in ast.walk(n)
                                     if isinstance(x, (ast.Name, ast.Attribute))}
    ep = ast.parse((ROOT / "scripts" / "extract_prompts.py").read_text())
    source_stems = next([ast.literal_eval(k) for k in s.value.keys] for s in ep.body
                        if isinstance(s, ast.AnnAssign) and ast.unparse(s.target) == "SOURCES")
    tests = {}
    for tf in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(tf.read_text())
        for fn in tree.body:
            if not (isinstance(fn, ast.FunctionDef) and fn.name.startswith("test")):
                continue
            names = {x.id if isinstance(x, ast.Name) else x.attr for x in ast.walk(fn) if isinstance(x, (ast.Name, ast.Attribute))}
            for a in fn.args.args:
                names |= fixture_names.get(a.arg, set())
            if "mock" in names:
                names |= fixture_names.get("mock", set())
            direct = sorted({k for nm in names for k in F.by_name.get(nm, [])
                             if not F.defs[k]["qual"].startswith("_") or "." in F.defs[k]["qual"]})
            seen, stack = set(direct), list(direct)
            while stack:
                for c in graph.get(stack.pop(), []):
                    if c not in seen:
                        seen.add(c); stack.append(c)
            # classes reached: their methods count as reached when called by name
            k = f"{rel(tf)}::{fn.name}"
            tests[k] = {"line": fn.lineno, "doc": first_doc_line(fn) or first_doc_line(tree),
                        "outcome": test_results["results"].get(k, "unknown"), "direct": direct,
                        "reached": sorted(seen - set(direct)),
                        "prompts": sorted(source_stems) if "SOURCES" in names else []}
    return tests


# ============================================================================================ sample run
def trim(s: str, n: int = 400) -> str:
    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + f" … [+{len(s) - n} chars]"


EVENT_BOX = {"capability_request": "capreq", "unknown_tool": "resolver", "blocked": "read_action",
             # D31–D36 plan runner events
             "plan_graph": "plan_graph", "dependency_relinked": "plan_graph", "step_input": "plan_step",
             "step_done": "step_check", "check_retry": "step_check", "rework": "step_check",
             "provenance": "provenance", "summary_check": "plan_summary", "limitations_added": "plan_summary",
             "capability_mapped": "tools", "web_tools": "tools", "web_search": "tools", "fetch_url": "tools",
             "tool_error": "tools", "tool_limit": "tools"}


def capability_example() -> dict:
    """One offline run of the D19/D21 paths: the planner fixture that requests tools, a helper that picks a tool it
    lacks, then answers. Scripted by the test fixtures, not by the toy stand-in (which never lacks a tool)."""
    import tempfile
    from amoeba.llm.client import MockLLMClient
    from amoeba.safety.envelope import Envelope
    from amoeba.task.models import Task
    from amoeba.tools.registry import default_registry
    from scripts.run_task import run_one
    fx = lambda n: (ROOT / "tests" / "fixtures" / f"{n}.txt").read_text(encoding="utf-8")
    llm = MockLLMClient(script={"planner": [fx("draft_capability_requests")],
                                "agent_observer": [fx("observer_no_suggestions")],
                                "plan_observer": [fx("observer_no_suggestions")],
                                "worker": [fx("worker_unknown_tool"), fx("worker_final_output")]})
    tools_ = default_registry()
    with tempfile.TemporaryDirectory() as tmp:
        r = run_one(Task(prompt="Compute 17 * 23 + 5.", ground_truth="396"), "flat", llm,
                    Envelope.from_registry(tools_, model=llm.model), tools_, tmp, seed=0)
        d = Path(tmp) / r.run_id
        reqs = json.loads((d / "capability_requests.json").read_text())
        events = [json.loads(l) for l in (d / "trace.jsonl").read_text().splitlines() if '"kind": "event"' in l]
    return {"fixtures": ["tests/fixtures/draft_capability_requests.txt", "tests/fixtures/worker_unknown_tool.txt",
                         "tests/fixtures/worker_final_output.txt"],
            "capability_requests_json": reqs, "events": events, "error": r.error, "answer": r.answer}


def coverage(timeline: list[dict]) -> dict:
    """D55: boxes no trace line maps to, and trace lines that name no (known) box."""
    ids = {B["id"] for B in BOXES if not B.get("ref")}
    seen = {t["box"] for t in timeline}
    return {"boxes_without_lines": sorted(ids - seen),
            "lines_without_box": [{"i": t["i"], "file_line": t["file_line"], "span": t["span"], "box": t["box"]}
                                  for t in timeline if t["box"] not in ids]}


def find_real_run() -> Path | None:
    """--replay-run DIR, else $ARCH_REPLAY_RUN, else the newest run under runs/ made with a real model (a profile)."""
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--replay-run=")), None)
    if arg or os.environ.get("ARCH_REPLAY_RUN"):
        d = Path(arg or os.environ["ARCH_REPLAY_RUN"])
        return d if (d / "trace.jsonl").exists() else None
    best = None
    for r in list((ROOT / "runs").glob("*/result.json")) + list((ROOT / "runs").glob("*/*/result.json")):
        try:
            if json.loads(r.read_text(encoding="utf-8")).get("profile") and (r.parent / "trace.jsonl").exists():
                if best is None or r.stat().st_mtime > best.stat().st_mtime:
                    best = r
        except (OSError, json.JSONDecodeError):
            continue
    return best.parent if best else None


def real_run(d: Path) -> dict:
    """D55: a real run from runs/, replayed on the page from its own trace: every line placed by its amoeba.box
    (older traces without it are placed by the same rules as the sample runs, and say so)."""
    spans = [json.loads(l) for l in (d / "trace.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    result = json.loads((d / "result.json").read_text(encoding="utf-8"))
    depth = {"invoke_workflow": 0, "invoke_agent": 1, "chat": 2, "execute_tool": 2}
    ordered = sorted(enumerate(spans), key=lambda iv: (iv[1]["ts"], depth.get(iv[1]["name"], 3), iv[0]))
    stamped = any("amoeba.box" in s for s in spans)
    timeline = []
    for file_idx, s in ordered:
        box = s.get("amoeba.box") if stamped else (
            {"planner": "planner", "agent_observer": "agent_obs", "plan_observer": "plan_obs"}.get(s.get("gen_ai.agent.name", ""))
            or ("interpreter" if s["name"] == "invoke_workflow" else "tools" if s["name"] == "execute_tool"
                else EVENT_BOX.get(s["name"]) if s.get("kind") == "event" else None))
        out = (s.get("gen_ai.output.messages") or [{}])[0].get("content", "")
        if s["name"] == "chat":
            result_txt = next((l for l in out.splitlines() if l.strip()), "") if out else f"finish: {s.get('gen_ai.response.finish_reasons')}"
        elif s.get("kind") == "event":
            result_txt = f"{s['name']}: " + ", ".join(f"{k.split('.')[-1]}={v}" for k, v in s.items() if k.startswith("amoeba.")
                                                      and k not in ("amoeba.box", "amoeba.profile"))
        else:
            result_txt = s.get("error.type", "")
        raw = {k: v for k, v in s.items() if k not in ("gen_ai.input.messages", "gen_ai.output.messages")}
        timeline.append({"i": len(timeline), "file_line": file_idx + 1, "span": s["name"], "box": box,
                         "helper": s.get("gen_ai.agent.name", ""),
                         "tokens": s.get("gen_ai.usage.input_tokens", 0) + s.get("gen_ai.usage.output_tokens", 0),
                         "latency_ms": s.get("latency_ms", 0), "result": trim(result_txt, 120), "raw": raw})
    per_box = {}
    for t in timeline:
        if t["span"] in ("chat", "execute_tool", "invoke_workflow"):
            b = per_box.setdefault(t["box"], {"calls": 0, "tokens": 0, "ms": 0})
            b["calls"] += t["span"] == "chat"
            b["tokens"] += t["tokens"]
            b["ms"] += t["latency_ms"]
    keep = ("task_id", "topology", "score", "error", "profile", "models", "usage", "n_llm_calls", "total_tokens")
    return {"real": True, "stamped": stamped, "run_id": d.name, "dir": rel(d) if d.is_relative_to(ROOT) else str(d),
            "files": sorted(p.name for p in d.iterdir()), "result": {**{k: result.get(k) for k in keep},
                                                                    "answer": trim(result.get("answer") or "", 300)},
            "n_trace_lines": len(spans), "timeline": timeline, "per_box": per_box, "coverage": coverage(timeline),
            "calls": [], "artifacts": [], "examples": {}}


def sample_runs() -> dict:
    import yaml
    from amoeba.llm.toy_mock import toy_mock_client
    from amoeba.safety.envelope import Envelope
    from amoeba.task.parsers import parse_critic, parse_sections
    from amoeba.task.source import ToyTaskSource
    from amoeba.tools.registry import calc, default_registry
    from scripts.run_task import run_one

    tools_ = default_registry()
    task = ToyTaskSource(seed=0, n=1).tasks()[0]
    from amoeba.task.models import Task
    free = Task(prompt="Reverse the string 'adaptive' then uppercase it").model_dump()   # as scripts/run_task.py main builds it
    out = {"free_text_task": free, "task": task.model_dump(), "toy_tasks": [t.model_dump() for t in ToyTaskSource(seed=0, n=3).tasks()],
           "calc_example": {"input": "17 * 23 + 5", "output": calc("17 * 23 + 5")}, "runs": {},
           "capability_example": capability_example()}
    for topology in ("flat", "boss_reviewers", "plan"):
        llm = toy_mock_client()
        env = Envelope.from_registry(tools_, model=llm.model)
        r = run_one(task, topology, llm, env, tools_, ROOT / "runs", seed=0)
        d = ROOT / "runs" / r.run_id
        team = yaml.safe_load((d / "team.yaml").read_text())
        plan = json.loads((d / "plan.json").read_text())
        spans = [json.loads(l) for l in (d / "trace.jsonl").read_text().splitlines()]
        roles = {aid: a["role"] for aid, a in team["agents"].items()}
        depth = {"invoke_workflow": 0, "invoke_agent": 1, "chat": 2, "execute_tool": 2}
        ordered = sorted(enumerate(spans), key=lambda iv: (iv[1]["ts"], depth.get(iv[1]["name"], 3), iv[0]))
        calls = list(llm.calls)
        chat_i = 0
        timeline = []
        for file_idx, s in ordered:
            name = s.get("gen_ai.agent.name", "")
            role = roles.get(s.get("gen_ai.agent.id", ""), "")
            if s.get("amoeba.box"):          # D55: the trace names its box; the rules below are for older traces
                box = s["amoeba.box"]
            elif s["name"] == "invoke_workflow":
                box = "interpreter"
            elif s["name"] == "execute_tool":
                box = "tools"
            elif s.get("kind") == "event":   # point events (D19/D21), not calls
                box = EVENT_BOX.get(s["name"], "trace")
            elif name in ("planner", "agent_observer", "plan_observer"):
                box = {"planner": "planner", "agent_observer": "agent_obs", "plan_observer": "plan_obs"}[name]
            elif topology == "plan":   # D31: plan steps and the summariser, told apart by the prompt's kind
                kind = calls[chat_i]["kind"] if s["name"] == "chat" and chat_i < len(calls) else "plan_worker"
                box = "plan_summary" if kind == "plan_summariser" else "plan_step"
            else:
                box = {"worker": "helper", "solver": "solver", "critic": "critics"}.get(role, "unknown")
            result = ""
            if s["name"] == "chat":
                result = calls[chat_i]["response"].strip().split("\n")[0] if chat_i < len(calls) else "unknown"
                if box in ("helper", "plan_step", "plan_summary"):
                    sec = parse_sections(calls[chat_i]["response"])
                    result = f"Action: {sec.get('Action', '?')} · ActionInput: {sec.get('ActionInput', '?')}"
                chat_i += 1
            elif s["name"] == "execute_tool":
                result = f"ran tool {s.get('gen_ai.tool.name')} (result is not written to the trace)"
            elif s["name"] == "invoke_workflow":
                result = f"answer {r.answer!r}"
            elif s.get("kind") == "event":
                result = f"{s['name']}: " + ", ".join(f"{k.split('.')[-1]}={v}" for k, v in s.items()
                                                       if k not in ("ts", "episode_id", "kind", "name"))
            timeline.append({"i": len(timeline), "file_line": file_idx + 1, "span": s["name"], "box": box,
                             "helper": name, "tokens": s.get("gen_ai.usage.input_tokens", 0) + s.get("gen_ai.usage.output_tokens", 0),
                             "latency_ms": s.get("latency_ms", 0), "result": trim(result, 120), "raw": s})
        per_box = {}
        for t in timeline:
            if t["span"] in ("chat", "execute_tool", "invoke_workflow"):
                b = per_box.setdefault(t["box"], {"calls": 0, "tokens": 0, "ms": 0})
                b["calls"] += t["span"] == "chat"
                b["tokens"] += t["tokens"]
                b["ms"] += t["latency_ms"]
        first = {}
        for c in calls:
            first.setdefault(c["kind"], c)
        worker_secs = [parse_sections(c["response"]) for c in calls if c["kind"] == "worker"]
        critic_verdicts = []
        for c in calls:
            if c["kind"] == "critic":
                try:
                    critic_verdicts.append({"agree": parse_critic(c["response"])[0], "reason": parse_critic(c["response"])[1]})
                except Exception as e:
                    critic_verdicts.append({"unparseable": str(e)[:80]})
        cov = coverage(timeline)
        solver = next((a for a in team["agents"].values() if a["role"] == "solver"), None)
        out["runs"][topology] = {
            "run_id": r.run_id, "dir": f"runs/{r.run_id}", "files": sorted(p.name for p in d.iterdir()),
            "result": json.loads((d / "result.json").read_text()),
            "team_trimmed": {"topology": team["topology"], "entry": team["entry"], "exit": team["exit"],
                             "agents": {aid: {k: (trim(v, 90) if isinstance(v, str) else v) for k, v in a.items()
                                              if k in ("name", "role", "tools", "role_prompt", "model", "max_history")}
                                        for aid, a in team["agents"].items()},
                             "edges": team["edges"], "plan": team["plan"]},
            "plan_trimmed": {**{k: v for k, v in plan.items() if k != "raw_draft"},
                             "raw_draft": trim(plan.get("raw_draft", ""), 600)},
            "trace_lines": [json.dumps(s, ensure_ascii=False) for s in spans[:3]],
            "n_trace_lines": len(spans), "timeline": timeline, "per_box": per_box, "coverage": cov,
            "artifacts": [json.loads(p.read_text()) for p in sorted((d / "artifacts").glob("step_*.json"))]
            if (d / "artifacts").exists() else [],
            "calls": [{"kind": c["kind"], "messages": [{"role": m["role"], "content": m["content"]} for m in c["messages"]],
                       "response": c["response"]} for c in first.values()],
            "examples": {
                "raw_text": trim(first["planner"]["response"], 500),
                "sections": {k: trim(v, 120) for k, v in parse_sections(first["planner"]["response"]).items()},
                "suggestions": trim(first.get("agent_observer", {}).get("response", ""), 200),
                "worker_sections": worker_secs[:3], "critic_verdicts": critic_verdicts,
                "solver_agent": {k: trim(v, 90) if isinstance(v, str) else v for k, v in (solver or {}).items()
                                 if k in ("name", "role", "max_history", "prompt", "description")},
                "envelope": env.model_dump()}}
    return out


# ============================================================================================ plan page
def plan_boxes() -> list[dict]:
    src = PLAN_HTML.read_text(encoding="utf-8")
    out = []
    for vm in re.finditer(r'<svg id="v-(\w+)"(.*?)</svg>', src, re.S):
        view, body = vm.group(1), vm.group(2)
        for g in re.finditer(r'<g ((?:"[^"]*"|[^>"])*)>(.*?)</g>', body, re.S):
            attrs, inner = g.group(1), g.group(2)
            cm = re.search(r'data-card="([^"]*)"', attrs)
            if not cm:
                continue
            card = html.unescape(html.unescape(cm.group(1)))
            fields = {dt: html.unescape(re.sub(r"<[^>]+>", "", dd)).strip()
                      for dt, dd in re.findall(r"<dt>(.*?)</dt><dd[^>]*>(.*?)</dd>", card, re.S)}
            texts = [html.unescape(re.sub(r"<[^>]+>", "", t)) for t in re.findall(r"<text[^>]*>(.*?)</text>", inner, re.S)]
            title = next((html.unescape(t) for t in re.findall(r'class="t2?">(.*?)</text>', inner)), texts[0] if texts else "")
            out.append({"view": view, "title": title, "card": fields, "texts": texts})
        if view == "overview":
            m = re.search(r'class="t2">(What every run leaves behind[^<]*)</text>\s*<text[^>]*class="src">([^<]*)</text>', body)
            if m:
                out.append({"view": "overview", "title": "What every run leaves behind",
                            "card": {"Description": html.unescape(m.group(1)), "Output": html.unescape(m.group(2))},
                            "texts": [html.unescape(m.group(1)), html.unescape(m.group(2))]})
    return out


# ============================================================================================ compare
def compare(B: dict, F: Facts, C, facts: dict, plan: dict) -> list[tuple[str, str]]:
    """Box-specific plan-vs-built checks. Returns [(level, message)], level in ok|differs|missing."""
    res: list[tuple[str, str]] = []

    def cap(label, plan_val, code_val, where):
        if code_val is None:
            res.append(("missing", f"{label}: the plan says {plan_val}; no such cap found in the code"))
        elif str(plan_val) != str(code_val):
            res.append(("differs", f"{label}: the plan says {plan_val}; the code has {code_val} ({where})"))
        else:
            res.append(("ok", f"{label}: {code_val} ({where})"))

    def src_of(key):
        d = F.defs[key]
        return "\n".join(F.src[d["path"]][d["node"].lineno - 1:d["node"].end_lineno])

    pid = B["id"]
    card = plan.get("card", {}) if plan else {}
    if pid in ("ov_plan", "planner"):
        c = const(C, "MAX_ROUNDS")
        cap("Drafting rounds", 3, c and c["value"], f"{c['path']}:{c['line']}" if c else "")
    if pid in ("ov_plan", "checks"):
        f = field_default(F, "amoeba/safety/envelope.py::Envelope", "max_agents")
        cap("Largest team", 5, f and f["default"], f"amoeba/safety/envelope.py:{f['line']}" if f else "")
    if pid in ("ov_run", "read_action", "helper"):
        f = field_default(F, "amoeba/config/schema.py::Limits", "max_turns")
        cap("Turns per step", 5, f and f["default"], f"amoeba/config/schema.py:{f['line']}" if f else "")
    if pid in ("ov_run", "disagree", "critics"):
        f = field_default(F, "amoeba/config/schema.py::TeamConfig", "max_inner_turns")
        cap("Review rounds", 3, f and f["default"], f"amoeba/config/schema.py:{f['line']}" if f else "")
    if pid == "solver":
        f = field_default(F, "amoeba/config/schema.py::TeamConfig", "max_inner_turns")
        cap("Most times the writer is asked", 4, f and 1 + int(f["default"]), "1 + max_inner_turns")
        s = src_of("amoeba/interp/runtime.py::Interpreter.run_boss_reviewers.solve")
        if "if not raw.strip()" in s:
            res.append(("differs", "The plan says an empty reply gives an empty answer; the code first asks the "
                                   "writer once more (runtime.py solve: `if not raw.strip(): raw = call(...)`)."))
    if pid == "critics":
        s = src_of("amoeba/interp/runtime.py::Interpreter.run_boss_reviewers.review")
        m = re.search(r"for _attempt in range\((\d+)\)", s)
        cap("Read attempts per review", 2, m and m.group(1), "runtime.py review")
    if pid == "toy_source":
        fam = const(C, "FAMILIES")
        plan_text = " ".join(plan.get("texts", []))
        cap("Number of job kinds", 3, fam and len(fam["value"]), f"{fam['path']}:{fam['line']}")
        if "JSON" in plan_text and not any("json" in x for x in fam["value"]):
            res.append(("differs", f"The plan lists 'arithmetic chains · string transforms · JSON extraction'; the code "
                                   f"has {list(fam['value'])} ({fam['path']}:{fam['line']}): sums, reversing a word, "
                                   f"counting vowels. There is no JSON-extraction job."))
    if pid == "handoff":
        sig = function_record(F, "amoeba/task/draft.py::draft_team", {})["signature"]
        planned = re.search(r"draft_team\((.*?)\)", card.get("Code", ""))
        params = [a.arg for a in F.defs["amoeba/task/draft.py::draft_team"]["node"].args.args]
        if planned and [p.strip() for p in planned.group(1).split(",")] != params:
            res.append(("differs", f"The plan's call is draft_team({planned.group(1)}); the code is {sig}: an extra "
                                   f"seed argument (default 0) that is passed on to every AI call."))
    if pid == "scoring":
        s = src_of("amoeba/task/evaluate.py::normalise")
        extra = []
        if "\\s+" in s:
            extra.append("squeezes runs of spaces inside the text to one")
        if "rstrip('.')" in s or 'rstrip(".")' in s:
            extra.append("drops trailing full stops")
        if extra:
            res.append(("differs", "The plan says the comparison only trims spaces and ignores case; the code also "
                                   + " and ".join(extra) + " (evaluate.py normalise)."))
    if pid == "checks":
        g = [x for x in facts["guards"] if x["key"] == "amoeba/task/draft.py::draft_team"]
        extra = []
        if any("b.get('name'" in x["code"] for x in g):
            extra.append("a helper entry without a name is skipped")
        if any("x.name == r.name" in x["code"] for x in g):
            extra.append("a second entry reusing a name is dropped (the first is kept)")
        if extra:
            res.append(("differs", "Checks the plan does not list: " + "; ".join(extra) + " (draft.py)."))
    if pid == "instantiate":
        s = src_of("amoeba/task/instantiate.py::instantiate")
        if "role_prompt=" in s:
            res.append(("differs", "The drafted instructions are stored in a separate helper field, role_prompt "
                                   "(the plan attaches them to the prompt); they are filled into the step prompt's "
                                   "{role} slot at run time."))
        if "agentverse_solver_append_generic" in s:
            res.append(("differs", "For one writer with reviewers, the writer uses a trimmed copy of the AgentVerse "
                                   "closing prompt (agentverse_solver_append_generic) without 'Write the code step by step.'"))
    if pid == "teamconfig":
        reads = facts["ai"]["per_helper_settings_read_by_runtime"]
        unused = [f for f in ("model", "temperature", "max_tokens") if f not in reads]
        if unused:
            res.append(("differs", f"Each helper's {', '.join(unused)} are written into the team file but the runner "
                                   f"never reads them: every AI call uses the connection's own settings."))
    if pid == "runresult":
        s = src_of("scripts/run_task.py::run_one")
        if "total_tokens=trace.total_tokens" in s:
            res.append(("differs", "The plan builds it from the Episode and Draft; the code builds it in "
                                   "scripts/run_task.py from the trace (tokens, calls) and the Draft (rounds, consensus)."))
    if pid == "ov_leave":
        files = facts["sample"]["runs"]["flat"]["files"]
        want = ["plan.json", "result.json", "team.yaml", "trace.jsonl"]
        extra = [f for f in files if f not in want]
        res.append(("ok" if files == want else "differs", f"Files written by the sample run: {', '.join(files)}"
                    + (f" (the plan lists four; {', '.join(extra)} is new, D19)" if extra else "")))
    return res


# ============================================================================================ assemble
def box_facts(F: Facts, graph, facts, plan_by_title) -> list[dict]:
    out = []
    for B in BOXES:
        b = {k: v for k, v in B.items() if k != "anchors"}
        if B.get("ref"):
            out.append({**b, "anchors": [], "status": "ref"})
            continue
        anchors, missing, ranges = [], [], []
        for a in B["anchors"]:
            key, frm, to = (a, None, None) if isinstance(a, str) else a
            d = F.resolve(key)
            if not d:
                missing.append(key)
                continue
            rec = class_record(F, key) if d["kind"] == "class" else function_record(F, key, graph)
            lo = F.marker_line(key, frm, d["node"].lineno)
            hi = F.marker_line(key, to, d["node"].end_lineno + 1)
            rec["range"] = [lo, hi - 1]
            if frm or to:
                rec["range_note"] = f"lines {lo}–{hi - 1} ({frm or 'start'} … {to or 'end'})"
            anchors.append(rec)
            ranges.append((key, d["path"], lo, hi - 1))
        b["anchors"] = anchors
        gkeys = B.get("guard_anchors")
        granges = ranges if gkeys is None else [r for r in ranges if r[0] in gkeys]

        def inside(path, line, key=None, rs=ranges):
            return any(p == path and lo <= line <= hi and (key is None or key == k or key.startswith(k + "."))
                       for k, p, lo, hi in rs)
        b["guards"] = [g for g in facts["guards"] if inside(g["path"], g["line"], g["key"], granges)]
        b["deviations"] = [d for d in facts["deviations"] if inside(d["path"], d["line"])]
        b["output_guards"] = [g for g in facts["guards"] if g["key"] in B.get("output_checks", [])]
        b["shield"] = B["id"] in SHIELD and bool(b["guards"] or b["output_guards"])
        if B.get("ai_entry"):
            seen, stack = {B["ai_entry"]}, [B["ai_entry"]]
            while stack:
                for c in graph.get(stack.pop(), []):
                    if c not in seen:
                        seen.add(c); stack.append(c)
            b["ai_sites"] = [s for s in facts["ai"]["sites"] if s["key"] in seen]
        else:
            b["ai_sites"] = [s for s in facts["ai"]["sites"] if inside(s["path"], s["line"], s["key"])]
        b["src"] = f"{anchors[0]['path']}:{anchors[0]['line']}" if anchors else "unknown"
        plan = plan_by_title.get((B["view"], B.get("plan"))) if B.get("plan") else None
        b["plan_card"] = plan["card"] if plan else None
        b["plan_texts"] = plan["texts"] if plan else None
        checks = [("missing", f"{m} not found in the code") for m in missing] + compare(B, F, facts["constants"], facts, plan or {})
        if B.get("plan") and not plan:
            checks.append(("missing", f"plan box {B['plan']!r} not found on the plan page"))
        b["checks"] = [{"level": l, "msg": m} for l, m in checks]
        if not B.get("plan"):
            b["status"] = "extra"
        elif any(l == "missing" for l, _ in checks) and not anchors:
            b["status"] = "missing"
        elif any(l in ("differs", "missing") for l, _ in checks):
            b["status"] = "differs"
        else:
            b["status"] = "built"
        # tests covering the box
        akeys = {a["key"] for a in anchors}
        for a in anchors:
            if a["kind"] == "class":
                akeys |= {f"{a['key']}.{m['name']}" for m in a["methods"]}
        stems = set(B.get("prompts", []))
        b["tests"] = []
        for tk, t in facts["tests"].items():
            how = "direct" if akeys & set(t["direct"]) else "indirect" if akeys & set(t["reached"]) else \
                  "prompt file" if stems & set(t["prompts"]) else None
            if how:
                b["tests"].append({"test": tk, "line": t["line"], "outcome": t["outcome"], "how": how})
        b["tests"].sort(key=lambda t: ({"direct": 0, "prompt file": 1, "indirect": 2}[t["how"]], t["test"]))
        b["fingerprint"] = hashlib.sha256(json.dumps(
            [anchors, b["guards"], b["checks"], [t["outcome"] for t in b["tests"]],
             [p["text"] for p in facts["prompts"] if p["stem"] in stems], b["sentence"]],
            sort_keys=True, default=str).encode()).hexdigest()[:16]
        out.append(b)
    return out


def data_types(F: Facts) -> dict:
    keys = {"Task": "amoeba/task/models.py::Task", "Draft": "amoeba/task/models.py::Draft",
            "TeamConfig": "amoeba/config/schema.py::TeamConfig", "PlanStep": "amoeba/config/schema.py::PlanStep",
            "AgentSpec": "amoeba/config/schema.py::AgentSpec", "Envelope": "amoeba/safety/envelope.py::Envelope",
            "Episode": "amoeba/task/models.py::Episode", "RunResult": "amoeba/task/models.py::RunResult",
            "_Msg": "amoeba/interp/runtime.py::_Msg", "ChatResponse": "amoeba/llm/client.py::ChatResponse",
            "CapabilityRequest": "amoeba/task/models.py::CapabilityRequest",
            "DraftRound": "amoeba/task/models.py::DraftRound"}
    return {k: class_record(F, v) for k, v in keys.items() if v in F.defs}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    state = {"commit": sh("git", "rev-parse", "HEAD"), "short": sh("git", "rev-parse", "--short", "HEAD"),
             "branch": sh("git", "rev-parse", "--abbrev-ref", "HEAD"), "commit_date": sh("git", "log", "-1", "--format=%cI"),
             "dirty": bool(sh("git", "status", "--porcelain", "--", "amoeba", "scripts", "tests", "spec")),
             "dirty_scope": "amoeba/ scripts/ tests/ spec/"}
    F = Facts()
    tags, errors = box_tags(F)
    errors += check_anchors(F, tags)
    from amoeba.interp.trace import BOX2_BOX, EVENT_BOX as TRACE_EVENTS, SPAN_BOX      # D55: the trace's box ids
    known = {B["id"] for B in BOXES}
    errors += [f"amoeba/interp/trace.py names box {b!r}, which is not on the page"
               for b in sorted((set(TRACE_EVENTS.values()) | set(SPAN_BOX.values()) | set(BOX2_BOX.values())) - known)]
    if errors:                     # a tag or an anchor that points at nothing: the page would lie, so stop
        print("arch_extract: box anchors are out of step with the code:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 2
    tagged_anchors(tags)
    prev_path = OUT / "architecture.json"
    prev = json.loads(prev_path.read_text(encoding="utf-8")) if prev_path.exists() else {}
    prev_defs = set(prev["defs"]) if "defs" in prev else None
    graph = call_graph(F)
    C = constants(F)
    devs, dev_table = deviations(F)
    facts = {"constants": C, "guards": guards(F), "deviations": devs, "prompts": prompts(F), "ai": ai_call_sites(F)}
    print("running pytest …", flush=True)
    tr = run_tests()
    facts["tests"] = test_map(F, graph, tr)
    print("sample runs …", flush=True)
    facts["sample"] = sample_runs()
    rr = find_real_run()
    if rr:
        facts["sample"]["runs"]["real"] = real_run(rr)
        cov = facts["sample"]["runs"]["real"]["coverage"]
        print(f"real run replayed: {rel(rr) if rr.is_relative_to(ROOT) else rr} — {len(cov['lines_without_box'])} "
              f"line(s) with no box; boxes with no line: {len(cov['boxes_without_lines'])}")
    pb = plan_boxes()
    plan_by_title = {(p["view"], p["title"]): p for p in pb}
    boxes = box_facts(F, graph, facts, plan_by_title)
    from arch_text import update_texts                    # the words: cache, hand text, or a cheap model (D55)
    hand = {B["id"]: {"sentence": B.get("sentence", ""), "what": B.get("what", [])} for B in BOXES if not B.get("ref")}
    text_log = update_texts(boxes, F, C, {p["stem"]: p["text"] for p in facts["prompts"]}, hand,
                            llm=None if "--no-llm" in sys.argv else "auto", commit=state["short"])
    print(f"box text: {text_log['unchanged']} unchanged, {text_log['hand']} from hand text, {text_log['checked']} "
          f"re-checked by {text_log['model'] or 'no model'} ({text_log['kept']} kept, {text_log['rewritten']} rewritten, "
          f"{text_log['rejected']} rejected), {text_log['stale']} stale; tokens {text_log['input_tokens']} in / "
          f"{text_log['output_tokens']} out / {text_log['reasoning_tokens']} reasoning")
    mapped = {(b["view"], b.get("plan")) for b in BOXES}
    unmapped_plan = [p["title"] for p in pb if (p["view"], p["title"]) not in mapped
                     and not (p["view"] == "run" and p["title"] == "TeamConfig")]
    cls_keys = sorted({a["key"] for b in boxes for a in b["anchors"] if a["kind"] == "class"})
    fn_keys = sorted({a["key"] for b in boxes for a in b["anchors"] if a["kind"] == "function"} |
                     {k for k in F.defs if F.defs[k]["kind"] == "function" and F.defs[k]["qual"].split(".")[-1] in
                      ("draft_team", "instantiate", "run", "run_flat", "run_boss_reviewers", "validate", "parse_sections",
                       "parse_role_blobs", "parse_plan", "parse_critic", "normalise", "score", "require", "render")})
    from datetime import datetime, timezone
    arch = {"generated_by": "tools/arch_extract.py", "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "repo": state, "plan_page": PLAN_URL,
            "plan_source": rel(PLAN_HTML), "modules": modules(F),
            "classes": [class_record(F, k) for k in sorted(k for k in F.defs if F.defs[k]["kind"] == "class")],
            "functions": [function_record(F, k, graph) for k in fn_keys],
            "prompts": facts["prompts"], "ai": facts["ai"], "constants": C, "guards": facts["guards"],
            "tools": tools(F), "tests": {"summary": tr["summary"], "tests": facts["tests"]},
            "deviations": {"in_code": devs, "spec_table": dev_table}, "sample": facts["sample"],
            "data_types": data_types(F), "boxes": boxes, "plan_boxes_not_mapped": unmapped_plan,
            "tags": tags, "defs": sorted(k for k, d in F.defs.items() if "." not in d["qual"]),
            "unassigned": unassigned(F, tags, prev_defs),
            "glossary": GLOSSARY, "text_log": text_log}
    counts = {}
    for b in boxes:
        counts[b["status"]] = counts.get(b["status"], 0) + 1
    arch["status_counts"] = counts
    target = OUT / "architecture.json"
    if target.exists():
        shutil.copyfile(target, OUT / "architecture.prev.json")
    target.write_text(json.dumps(arch, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    new_un = [u["key"] for u in arch["unassigned"] if u["new"]]
    print(f"untagged top-level code: {len(arch['unassigned'])}" + (f"; NEW and unassigned: {', '.join(new_un)}" if new_un else ""))
    print(f"wrote {rel(target)}: {len(boxes)} boxes {counts}; tests: {tr['summary']}; "
          f"unmapped plan boxes: {unmapped_plan}; classes used as anchors: {len(cls_keys)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
