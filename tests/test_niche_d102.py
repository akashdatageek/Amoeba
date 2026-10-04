"""D102 — niche profiles (offline, mock LLM): `general` changes nothing (byte-identical prompts and results); a
profile fills one Environment section of Box 1's and Box 2's prompts; Box 3 refuses a tool outside the profile even
when the plan gives it to a role, and logs the refusal; the router refuses a model outside it; the calc domain check
runs after each step (a failure earns the retry turn); the done clauses reach the answer step; the sandbox limits
come from the profile."""
import json

import pytest

from amoeba.checks import CHECKS, run_checks
from amoeba.checks.calc import check as calc_check, figures
from amoeba.config.niche import NicheProfile, environment_text, load_profile, tool_allowed
from amoeba.config.schema import AgentSpec, PromptRef
from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.interp.trace import TraceWriter
from amoeba.llm.client import MockLLMClient
from amoeba.localtools.toolbox import LocalSetup
from amoeba.llm.router import CallSpec, NoModelAvailable
from amoeba.safety.envelope import Envelope
from amoeba.task.models import Task
from amoeba.tools.registry import default_registry
from scripts.run_task import build_router_llm, niche_tools, parse_args, run_one
from tests.conftest import mock
from tests.test_plan_runner import APPROVE, DIAMOND, finish

TASK = Task(id="calc-x", prompt="Compute 17 * 23 + 5.", family="calc")
CALC = load_profile("calc")


def llm(worker=finish):
    return mock(planner=[DIAMOND], agent_observer=[APPROVE], plan_observer=[APPROVE], plan_worker=worker,
                interpreter=['## Entities\n[]'])


def with_figure(messages, seed):
    """Like finish, but states a figure (396) that no calc call produced: the answer step fails the calc check."""
    return finish(messages, seed).replace("## Result\n", "## Result\nThe result is 396.\n")


def run(tmp_path, name, niche=None, worker=finish, **kw):
    m = llm(worker)
    reg = default_registry()
    r = run_one(TASK, "plan", m, Envelope.from_registry(reg), reg, tmp_path / name, draft_prompts="d24",
                plan_options=PlanOptions(), niche=niche, **kw)
    return m, r, tmp_path / name / r.run_id


def test_profiles_ship_and_load():
    g = load_profile()
    assert g.name == "general" and g.is_neutral() and environment_text(g) == ""
    assert not CALC.is_neutral() and CALC.checks == ["calc"] and "calc" in CHECKS
    assert CALC.sandbox["timeout_s"] == 300 and CALC.safety.outside_actions is False
    with pytest.raises(ValueError):
        load_profile("no-such-niche")


def test_unknown_checks_are_refused(tmp_path):
    (tmp_path / "x.yaml").write_text("checks: [nope]\n")
    with pytest.raises(ValueError, match="unknown domain checks"):
        load_profile("x", root=tmp_path)


def test_general_changes_nothing(tmp_path):
    m0, r0, d0 = run(tmp_path, "none", interpret=True)
    m1, r1, d1 = run(tmp_path, "general", niche=load_profile("general"), interpret=True)
    assert [c["messages"] for c in m0.calls] == [c["messages"] for c in m1.calls]          # every prompt, byte for byte
    assert r0.answer == r1.answer and r0.score == r1.score and r0.n_llm_calls == r1.n_llm_calls
    assert (d0 / "plan.json").read_text() == (d1 / "plan.json").read_text()
    a, b = (json.loads((d / "result.json").read_text()) for d in (d0, d1))
    noise = {"run_id", "team_id", "latency_ms"}
    assert {k: v for k, v in a.items() if k not in noise} == {k: v for k, v in b.items() if k not in noise}
    assert parse_args(["x"]).niche == "general" and parse_args(["x"]).niche_profile.is_neutral()


def test_the_environment_section_reaches_box_1_and_box_2(tmp_path):
    m, r, d = run(tmp_path, "calc", niche=CALC, interpret=True)
    for kind in ("interpreter", "planner", "agent_observer", "plan_observer"):
        text = m.calls_of(kind)[0]["messages"][-1]["content"]
        assert "# Environment (calc)" in text and "Assess this environment first" in text, kind
        assert "- Tools you may use: calc, echo" in text and "Done means: Every final figure" in text, kind
    assert all("# Environment" not in c["messages"][-1]["content"] for c in m.calls if c["kind"] == "plan_worker")


def test_the_done_clauses_reach_the_answer_step(tmp_path):
    _, _, d = run(tmp_path, "done", niche=CALC)
    plan = json.loads((d / "plan.json").read_text())
    steps = plan["plan"] if "plan" in plan else plan["steps"]
    last = steps[-1]
    assert "Every final figure is computed with calc" in json.dumps(last)
    assert all("Every final figure is computed with calc" not in json.dumps(s) for s in steps[:-1])


def test_the_calc_domain_check(tmp_path):
    ev = {"task": "A loan of $12,000 at 5% for 3 years.", "inputs": "", "computed": ["600", "1800.0"],
          "answer_step": True}
    assert calc_check("Interest per year: $600; total $1,800.00 on $12,000.", ev)[0]
    ok, why = calc_check("Total interest is $1,950.", ev)
    assert not ok and "1950" in why
    assert calc_check("Total interest is $1,950.", {**ev, "answer_step": False})[0]
    assert figures("Step 3 in 2026: 7 items cost $1,234.50 (12%)") == ["1234.50", "12"]
    assert run_checks(["calc"], "x", ev)[0]["name"] == "domain_calc"


def test_the_domain_check_runs_after_each_step_and_earns_the_retry(tmp_path):
    m, r, d = run(tmp_path, "chk", niche=CALC, worker=with_figure)
    trace = [json.loads(l) for l in (d / "trace.jsonl").read_text().splitlines()]
    done = [e for e in trace if e.get("name") == "step_done" or e.get("amoeba.step") and "amoeba.checks_failed" in e]
    assert any("domain_calc" in (e.get("amoeba.checks_failed") or []) for e in done)      # 396 came from no calc
    steps = sorted(d.rglob("step_*.json"))
    rows = [c for s in steps for c in json.loads(s.read_text()).get("checks", []) if c["name"] == "domain_calc"]
    assert rows and {c["source"] for c in rows} == {"domain"}
    assert any(e.get("name") == "refine" for e in trace)                                  # the retry turn


def interp_with(tools, tmp_path):
    return Interpreter(MockLLMClient(), tools, TraceWriter(tmp_path / "t.jsonl", episode_id="n"))


def test_box_3_refuses_a_tool_outside_the_profile_even_when_the_plan_gives_it(tmp_path):
    reg = default_registry()
    reg.register("web_search", "searches the web", lambda q: "results")
    reg.register("send_email", "sends an email", lambda q: "sent")
    allowed, local = niche_tools(CALC, reg, None)
    assert set(allowed.names()) == {"calc", "echo"}                      # Box 2 is shown the allowed tools only
    reg.niche = CALC                                                     # Box 3: a plan that names web_search anyway
    agent = AgentSpec(agent_id="a", name="Analyst", role="worker", model="m",
                      prompt=PromptRef(system="s", user="u"), tools=["web_search", "send_email", "calc"])
    i = interp_with(reg, tmp_path)
    out = i._tool(agent, "web_search", "price of x")
    assert out.startswith("refused: web_search — not in the calc profile's tools") and "results" not in out
    assert i._tool(agent, "calc", "2 + 2") == "4"
    ev = [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]
    refused = [e for e in ev if e.get("name") == "niche_refused" or e.get("gen_ai.tool.name") == "web_search"
               and e.get("amoeba.niche")]
    assert refused and refused[0]["amoeba.niche"] == "calc"
    open_prof = NicheProfile(name="o", safety={"outside_actions": False})
    assert tool_allowed("send_email", open_prof, "sends an email")[0] is False             # outside action
    assert tool_allowed("calc", open_prof)[0] is True


def test_the_router_refuses_a_model_outside_the_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("AMOEBA_RATE_DIR", str(tmp_path / "rate"))
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    args = parse_args(["x", "--topology", "plan", "--llm", "openai"])
    args.niche_profile = NicheProfile(name="t", models={"allowed": ["some-other-model"],
                                                        "verifier_independence": "required"})
    r = build_router_llm(args, "routed")
    assert r.policy["verifier_independence"] == "required"
    with pytest.raises(NoModelAvailable):
        r.route(CallSpec(role="planner"))
    assert "profile" in json.dumps(r.decisions[-1]["filtered"]).lower()
    args.niche_profile = CALC
    assert build_router_llm(args, "routed").usd_cap == 0.5               # the profile's safety limit


def test_the_sandbox_limits_come_from_the_profile():
    reg = default_registry()
    _, local = niche_tools(CALC, reg, LocalSetup())
    assert local.limits["timeout_s"] == 300 and local.config["sandbox"]["memory"] == "1Gi"
    assert set(local.config["allowed_tools"]) <= {"Bash", "Read", "Write", "Edit", "Glob", "Grep"}


def test_baselines_never_get_a_niche(tmp_path):
    with pytest.raises(SystemExit):
        parse_args(["x", "--topology", "flat", "--niche", "calc"])
    reg = default_registry()
    with pytest.raises(ValueError, match="plan runner only"):
        run_one(TASK, "flat", llm(), Envelope.from_registry(reg), reg, tmp_path / "f", niche=CALC)
