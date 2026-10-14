"""D130 — plan checks before Box 3: each done_when states what its requirements ask for, plans for actions no tool may
do, and is something the helpers can meet in their turns; the Planner is told the turns. Plain code only."""
from types import SimpleNamespace as S

from amoeba.task.draft import toolbox_text
from amoeba.task.quality import (done_when_properties, done_when_reachable, gate_suggestions, outside_action_fallback,
                                 properties_in)


def step(i, done_when="", output="", do="", text="", covers=()):
    return S(index=i - 1, done_when=done_when, output=output, do=do, text=text or f"{i}. [Role]: step {i}",
             covers=list(covers))


def test_the_properties_a_requirement_asks_for():
    assert properties_in("Write a 2-page Word report with citations") == {"#2", "pages", "word document", "citations"}
    assert properties_in("Cite every figure with its date") == {"citations", "dates"}
    assert properties_in("Deliver a CSV of the figures and a bar chart (PNG)") == {"csv", "chart"}
    assert properties_in("Compute a 7-year total cost") == set()              # a period is not a deliverable size


def test_a_done_when_that_only_checks_existence_is_caught():
    d = S(requirements={"R1": "Write a 2-page Word report with citations", "R2": "Make a chart"},
          plan=[step(1, "Word document is generated", "path to report.docx", do="2 pages, cite sources", covers=["R1"]),
                step(2, "chart.png exists", "png: chart", covers=["R2"])])
    r = done_when_properties(d)
    assert not r["ok"] and r["gaps"] == {"R1": {"missing": ["#2", "citations", "pages"], "steps": [1]}}
    d.plan[0].done_when = "the .docx is at most 2 pages and every [n] maps to a listed source"
    assert done_when_properties(d)["ok"]
    d.requirements["R3"] = 'Open the final answer with the line: "I read X as Y"'   # the system's line: code checks it
    assert done_when_properties(d)["ok"]


def test_an_outside_action_needs_a_fallback():
    send = step(5, "Email is successfully dispatched", text="5. [Delivery Lead]: Final delivery",
                do="Send email to test@example.com with both files attached")
    assert outside_action_fallback([send]) == {"ok": False, "steps": [5]}
    send.done_when = "the send tool returns success, or the .eml file exists and is marked NOT SENT"
    assert outside_action_fallback([send])["ok"]
    for harmless in ("record published_at from the API", "a first RERUN REQUIRED sends the work back to step 5",
                     "use a published ACS table"):
        assert outside_action_fallback([step(1, "done", do=harmless)])["ok"], harmless


def test_a_done_when_the_helpers_cannot_meet():
    exact = step(7, "the closing sentence matches the given text exactly")
    opening = step(8, "the first paragraph matches the mandated string exactly (programmatic comparison)")
    many = step(1, "a; b; c, d, e and f, g")
    r = done_when_reachable([exact, opening, many, step(2, "5 repos have stars and dates")])
    assert r["exact_match"] == [7] and r["too_many_conditions"] == [{"step": 1, "conditions": 7}] and not r["ok"]


def test_the_gate_tells_the_planner_what_to_change():
    q = {"hard_failed": ["outside_action_fallback", "done_when_properties"], "checks": {
        "outside_action_fallback": {"steps": [5]},
        "done_when_properties": {"gaps": {"R6": {"missing": ["pages"], "steps": [3]}}}}}
    text = gate_suggestions(q)
    assert "R6 asks for pages and step(s) 3 never state it" in text and "marked NOT SENT" in text


def test_the_planner_is_told_the_turns_and_what_no_tool_may_do():
    env = S(allowed_tool_names=["calc"], tool_descriptions={"calc": "arithmetic"})
    text = toolbox_text(env, web=True, turns=5)
    assert "at most 5 turns per step" in text and "no tool acts outside the run" in text
    assert "turns per step" not in toolbox_text(env) and "acts outside" not in toolbox_text(env)
