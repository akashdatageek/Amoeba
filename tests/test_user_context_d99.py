"""The user context file (D77, D99 as kept by D117): `standards:` the user wrote reach Box 1 and Box 2; no standards
leave every prompt unchanged; no agent can write the context file or the event log. (D117 removed recipe memory and
the loop's user-memory proposals and approvals.) Offline, mock LLM."""
from amoeba.interp.plan_runner import PlanOptions
from amoeba.localtools.gate import inside, screen_command
from amoeba.localtools.toolbox import load_local_config
from amoeba.memory.context import context_text, load_context, standards_slots
from amoeba.safety.envelope import Envelope
from amoeba.task.models import Task
from amoeba.tools.registry import default_registry
from scripts.run_task import run_one
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, DIAMOND, finish

TASK = Task(id="calc-x", prompt="Compute 17 * 23 + 5.", family="calc")


def run(tmp_path, name, **kw):
    m = mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=finish)
    r = run_one(TASK, "plan", m, Envelope.from_registry(default_registry()), default_registry(), tmp_path / name,
                draft_prompts="d24", plan_options=PlanOptions(), **kw)
    return m, r, tmp_path / name / r.run_id


def test_box_1_and_box_2_read_the_standards(tmp_path):
    ctx = tmp_path / "user.yaml"
    ctx.write_text("role: analyst\nstandards:\n  - Answers end with an Assumptions section.\n")
    c = load_context(ctx)
    assert "- standard: Answers end with an Assumptions section." in context_text(c)
    slots = standards_slots(c)
    assert set(slots) == {"planner", "plan_observer"} and "Assumptions section" in slots["planner"]
    assert standards_slots(load_context(None)) == {} and context_text(load_context(None)) == "None given."


def test_a_run_puts_the_standards_into_the_planner_prompt_and_none_change_nothing(tmp_path):
    ctx = tmp_path / "user.yaml"
    ctx.write_text("standards:\n  - Answers end with an Assumptions section.\n")
    m, r, d = run(tmp_path, "std", context=load_context(ctx))
    for kind in ("planner", "plan_observer"):
        assert "- Answers end with an Assumptions section." in m.calls_of(kind)[0]["messages"][-1]["content"], kind
    assert any('"user_standards"' in l for l in (d / "trace.jsonl").read_text().splitlines())
    m0, _, _ = run(tmp_path, "none")
    m1, _, _ = run(tmp_path, "plain", context=load_context(None))
    assert [c["messages"] for c in m0.calls] == [c["messages"] for c in m1.calls]


def test_agents_cannot_write_the_context_file_or_the_event_log(tmp_path):
    ws = tmp_path / "runs" / "run-x" / "workspace"
    ws.mkdir(parents=True)
    for m in (tmp_path / "user.yaml", tmp_path / "runs" / "events.jsonl"):
        assert inside(str(m), ws) is None, m                              # Write / Edit: outside_workspace
        assert screen_command(f"echo x >> {m}", ws), m                    # Bash: path outside the workspace
    s = load_local_config()["sandbox"]           # the sandbox's own paths only: no host folder is mounted into it
    assert set(s["read_write"]) <= {"/sandbox", "/tmp", "/dev/null"} and not any(
        p.startswith(("/home", "/root", "/var", "/workspace")) for p in s["read_only"])
