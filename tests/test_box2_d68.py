"""D68 — Box 2 gaps: the Planner and both observers see every tool Box 3 will really have; a document format or a
house style is a skill; what only the user can supply is an open question or a request, never an assumption; the
intake check knows more deliverable verbs and does not end a phrase inside an email address or a decimal."""
from amoeba.task.draft import draft_team, toolbox_text
from amoeba.task.quality import deliverable_phrases
from scripts.eval_draft import parse_args as eval_args
from tests.conftest import fx, mock

APPROVE = fx("observer_d24_approve")


def prompts_of(task, envelope, trace, toolbox):
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE])
    draft_team(task, llm, envelope, trace, prompts="d24", toolbox=toolbox)
    return {k: llm.calls_of(k)[0]["messages"][-1]["content"] for k in ("planner", "agent_observer", "plan_observer")}


def test_all_three_see_the_real_toolbox(task, envelope, trace):
    box = toolbox_text(envelope, web=True, local=True, pool=True)
    seen = prompts_of(task, envelope, trace, box)
    for who, text in seen.items():
        assert "- calc: evaluates an arithmetic expression" in text, who
        assert "- web_search: searches the web" in text and "- fetch_url:" in text, who
        assert "local tools, sandboxed in the run's own workspace" in text and "xlsx, docx, pptx, pdf" in text, who
        assert "a tool pool: plain code matches every capability request" in text, who
    assert "# Tools the team will have when it runs" in seen["plan_observer"]


def test_without_a_toolbox_the_installed_list_is_shown(task, envelope, trace):
    seen = prompts_of(task, envelope, trace, None)
    assert "tool: calc, description:" in seen["planner"] and "web_search: searches" not in seen["planner"]
    assert toolbox_text(envelope).count("\n") == 1                         # calc and echo only


def test_formats_are_skills_and_user_only_data_is_asked_for(task, envelope, trace):
    seen = prompts_of(task, envelope, trace, None)
    assert "A document format (xlsx, docx, pptx, pdf) or a house style is a\n   SKILL, not a tool." in seen["planner"]
    assert "(brand style, internal data, credentials, account access) is never an assumption" in seen["planner"]
    assert "9. User-only inputs: anything only the user or their company can supply" in seen["plan_observer"]


def test_more_deliverable_verbs_and_phrases_end_at_sentence_punctuation():
    got = [(k, p) for k, p, _ in deliverable_phrases(
        "Email the summary to anna@example.com and save it as report.xlsx. Compute 3.5% of $1,850, then list the lanes.")]
    assert got == [("email", "Email the summary to anna@example.com"), ("save", "save it as report.xlsx"),
                   ("compute", "Compute 3.5% of $1,850"), ("list", "list the lanes")]
    assert [k for k, _, _ in deliverable_phrases("Write and run a Python program; convert, compare, read, make it")] \
        == ["write", "run", "convert", "compare", "read", "make"]


def test_eval_draft_can_describe_the_box3_toolbox():
    a = eval_args(["--web-tools", "--local-tools", "on", "--pool"])
    assert a.web_tools and a.local_tools == "on" and a.pool
    assert not eval_args([]).pool
