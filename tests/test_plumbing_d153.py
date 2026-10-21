"""D153 — plumbing found in the live runs: --protocol auto, refused replies kept apart from unreadable ones, BLOCKED
lines, the shell aliases, requests for several roles, and team.yaml naming the models really used. Offline."""
import json

from amoeba.adapt.stuck import diagnose, step_signals
from amoeba.interp.plan_runner import PlanOptions, blocked_marks
from amoeba.interp.runtime import Interpreter
from amoeba.interp.trace import TraceWriter
from amoeba.llm.client import ChatResponse, MockLLMClient
from amoeba.llm.router import ModelRouter, load_registry
from amoeba.pool.stock import roles_named, split_by_role
from scripts.run_task import cli_plan_options, parse_args, protocol_used, relabel_team, resolve_protocol, run_one
from tests.conftest import fx, mock
from tests.test_fixes_d117 import good
from tests.test_plan_runner import plan_team, step_no

ENV = {"CLAUDE_API_KEY": "x", "GEMINI_API_KEY": "x"}


def router(allowed, no_tools=()):
    registry, policy = load_registry()
    for name in no_tools:
        registry[name].supports = {**registry[name].supports, "tools": False}
    return ModelRouter(registry, policy, make=None, mode="routed", profile_allowed=allowed, env=ENV)


# ---- A1: --protocol auto -------------------------------------------------------------------------------------------
def test_auto_is_the_cli_default():
    args = parse_args(["--topology", "plan", "--toy"])
    assert args.protocol == "auto" and cli_plan_options(args).protocol == "auto"


def test_auto_picks_v2_for_a_tools_model_and_legacy_otherwise():
    t = TraceWriter(None, episode_id="a1")
    v2 = resolve_protocol(PlanOptions(protocol="auto"), router(["claude-sonnet-5-5"]), t)
    assert (v2.protocol, v2.protocol_from) == ("v2", "auto")
    legacy = resolve_protocol(PlanOptions(protocol="auto"), router(["gemma-4-31b"], no_tools=["gemma-4-31b"]), t)
    assert (legacy.protocol, legacy.protocol_from) == ("legacy", "auto")
    assert [e["amoeba.protocol"] for e in t.events("protocol_auto")] == ["v2", "legacy"]
    assert protocol_used(legacy) == {"asked": "auto", "used": "legacy",
                                     "why": "the model has no native tool calling (supports.tools)"}
    assert protocol_used(PlanOptions(protocol="v2", protocol_from="auto", native_tools="on"))["asked"] == "auto"


def test_gemma_now_has_tools_after_its_model_check():
    assert resolve_protocol(PlanOptions(protocol="auto"), router(["gemma-4-31b"]),
                            TraceWriter(None, episode_id="g")).protocol == "v2"


def test_legacy_and_v2_override_auto():
    t = TraceWriter(None, episode_id="a1o")
    for asked in ("legacy", "v2"):
        assert resolve_protocol(PlanOptions(protocol=asked), router(["claude-sonnet-5-5"]), t).protocol == asked
    assert t.events("protocol_auto") == []
    assert resolve_protocol(PlanOptions(protocol="auto"), MockLLMClient(responder=lambda m, s: "x"),
                            t).protocol == "legacy"                         # a mock has no native tools


def test_the_baselines_stay_legacy(tmp_path, envelope, tools):
    llm = mock(planner=[fx("draft_round_ok")], worker=[fx("worker_final_output")] * 4)
    from amoeba.task.models import Task
    r = run_one(Task(prompt="Compute 17 * 23 + 5.", ground_truth="396"), "flat", llm, envelope, tools, tmp_path,
                plan_options=PlanOptions(protocol="auto"))
    rows = [json.loads(x) for x in (tmp_path / r.run_id / "trace.jsonl").read_text().splitlines()]
    assert not [x for x in rows if x.get("name") == "protocol_auto"]


# ---- A2: a refused reply is never a format slip ---------------------------------------------------------------------
BLOCKED = ChatResponse(content="", finish_reason="refusal", refusal_category="cyber")


def test_a_step_whose_replies_are_all_refused_is_provider_blocked_only(task, envelope, trace, tools):
    def script(messages, seed):
        return BLOCKED if step_no(messages) == "1" else good(step_no(messages))
    llm, cfg = plan_team(task, envelope, trace, plan_worker=script)
    ep = Interpreter(llm, tools, trace, plan_options=PlanOptions(adapt="off")).run(cfg, task, seed=0)
    m = next(s for s in ep.steps if s["step"] == 1)
    assert m["blocked_turns"] and m["unreadable_turns"] == []
    assert "blocked replies:" in m["status_reason"] and "unreadable replies" not in m["status_reason"]
    sig = {s["signal"] for s in step_signals(m)}
    assert "provider_blocked" in sig and "unreadable_reply" not in sig and "capability_unfilled" not in sig
    assert diagnose(step_signals(m))["cause"] == "provider_blocked"
    assert not [c for c in llm.calls if "did not validate" in str(c["messages"][-1].get("content", ""))]


def test_old_runs_with_the_blocked_flag_replay_the_same():
    old = {"turns": 3, "finished": False, "unreadable_turns": [{"agent": "A", "turn": 1, "blocked": True,
                                                                  "category": "cyber"}]}
    assert diagnose(step_signals(old))["cause"] == "provider_blocked"


# ---- A3: BLOCKED lines ----------------------------------------------------------------------------------------------
def test_blocked_lines_in_every_form():
    h2 = "**BLOCKED:** Census API key. Every api.census.gov request needs a key, and I had none"
    assert blocked_marks(h2) == ["Census API key"]
    assert blocked_marks("__BLOCKED:__ X") == ["X"]
    assert blocked_marks("- **BLOCKED**: X") == ["X"]
    assert blocked_marks("BLOCKED: X — reason") == ["X"]
    assert blocked_marks("BLOCKED: api.census.gov key — x") == ["api.census.gov key"]   # a dot inside a name stays
    assert blocked_marks("BLOCKED: X — a\nBLOCKED: x — b") == ["X"]                       # case-blind duplicates


# ---- A4: the shell tool reaches the helper --------------------------------------------------------------------------
def test_shell_names_map_to_local_bash():
    from amoeba.capabilities import normalise
    assert {normalise(x)[0] for x in ("Bash", "shell", "python_interpreter", "code_execution", "terminal")} == \
        {"code_execution"}


def test_a_request_for_several_roles_is_one_row_per_role_and_the_watch_sees_it():
    names = ["Analyst", "Verifier", "Writer"]
    assert roles_named("Analyst; Verifier", names) == ["Analyst", "Verifier"]
    assert roles_named("Writer", names) == ["Writer"] and roles_named("Nobody", names) == []
    rows = [{"name": "pdf_reader", "for_role": "Analyst; Verifier", "status": "unfilled"}]
    split = split_by_role(rows, names)
    assert [r["for_role"] for r in split] == ["Analyst", "Verifier"]
    meta = {"step": 1, "status": "partial", "roles": ["Verifier"], "finished": True, "turns": 2}
    assert not [s for s in step_signals(meta, unfilled=rows) if s["signal"] == "capability_unfilled"]
    assert [s for s in step_signals(meta, unfilled=split) if s["signal"] == "capability_unfilled"]


# ---- A6: team.yaml names the models really used --------------------------------------------------------------------
class Fallback(MockLLMClient):
    """Answers one helper's calls from another model, as a routed fallback would."""
    def chat_messages(self, messages, seed=0, **kw):
        r = super().chat_messages(messages, seed, **kw)
        if step_no(messages) == "2":
            r.model = "fallback-model"
        return r


def test_team_yaml_names_the_model_a_fallback_used(task, envelope, trace, tools):
    llm, cfg = plan_team(task, envelope, trace, plan_worker=lambda m, s: good(step_no(m)))
    llm.__class__ = Fallback
    Interpreter(llm, tools, trace, plan_options=PlanOptions()).run(cfg, task, seed=0)
    planned = {aid: a.model for aid, a in cfg.agents.items()}
    assert relabel_team(cfg, trace)
    step2 = {aid for s in cfg.plan if s.index == 1 for aid in s.agent_ids}
    assert step2 and all("fallback-model" in cfg.agents[a].model for a in step2)
    assert all(cfg.agents[a].model == planned[a] or "fallback-model" not in cfg.agents[a].model
               for a in cfg.agents if a not in step2)
