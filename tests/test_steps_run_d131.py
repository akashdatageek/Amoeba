"""D131 — inside the steps and around the run: a citation tag that names the wrong source is corrected when the claim
is in exactly one other source, a repeated tool error comes back with what the tool takes, habitual workspace paths
mean the workspace, a model call that hangs is ended and asked again with less room, and team.yaml names the model
the calls go to. Offline."""
from types import SimpleNamespace as S

from amoeba.interp.citecheck import mislabelled_citations, relabel_citations
from amoeba.interp.plan_runner import PlanRunner
from amoeba.llm.client import ChatResponse, MockLLMClient, OpenAICompatibleClient
from amoeba.localtools.toolbox import alias_paths
from scripts.run_task import planned_model
from tests.test_router_d97 import entry, router


def test_a_wrong_tag_is_corrected_only_when_one_other_source_has_the_claims():
    sources = {"S1": "Branch hours vary.", "S2": "Open 8:00am to 4:30pm.", "S3": "Closed on Sunday."}
    text = "The branch opens at 8:00am and closes at 4:30pm [S1]."
    found = mislabelled_citations(text, sources)
    fixed, fixes = relabel_citations(text, found)
    assert fixed == "The branch opens at 8:00am and closes at 4:30pm [S2]." and mislabelled_citations(fixed, sources) == []
    assert fixes[0]["from"] == "S1" and fixes[0]["to"] == "S2"
    both = {**sources, "S3": "Also open 8:00am to 4:30pm."}                 # two sources have it: not guessed
    assert relabel_citations(text, mislabelled_citations(text, both)) == (text, [])
    assert relabel_citations(text, mislabelled_citations(text, {"S1": "x", "S2": "y"})) == (text, [])   # nowhere


def test_the_same_tool_error_twice_comes_back_with_what_the_tool_takes():
    w = S(calls=[{"agent": "Analyst", "tool": "calc", "ok": False, "result": "error: invalid syntax (line 1)"},
                 {"agent": "Analyst", "tool": "calc", "ok": False, "result": "error: invalid syntax (line 3)"}])
    agent = S(name="Analyst", tools=["calc", "local:Bash"])
    fake = S(i=S(tools=S(descriptions=lambda: {"calc": "one arithmetic expression such as 12 * (3 + 4)"}),
                 trace=S(event=lambda *a, **k: None)), local=None)
    out = PlanRunner.same_error_hint(fake, agent, "calc", w, "error: invalid syntax (line 3)")
    assert "same error as your previous calc call" in out and "12 * (3 + 4)" in out and "local:Bash" in out
    w.calls[0]["ok"] = True
    assert PlanRunner.same_error_hint(fake, agent, "calc", w, "e") == "e"         # once is not a pattern


def test_habitual_workspace_paths_mean_the_workspace():
    assert alias_paths("cat /workspace/sources/a.csv && ls /workspace", "/runs/x/workspace") == \
        "cat /runs/x/workspace/sources/a.csv && ls /runs/x/workspace"
    assert alias_paths("ls /workspaces /etc /mnt/data/f.csv", "/w") == "ls /workspaces /etc /w/f.csv"
    assert alias_paths("ls /parameter", "/w") == "ls /parameter"              # anything else is the gate's to judge


def test_a_call_that_hangs_is_asked_again_with_half_the_room(monkeypatch):
    class APITimeoutError(Exception):
        pass
    client = OpenAICompatibleClient(base_url="http://x", api_key="k", model="m", max_tokens=8000,
                                    sleep=lambda s: None, request_timeout_s=30)
    seen = []

    def create(kw, seed):
        seen.append(kw["max_tokens"])
        if len(seen) == 1:
            raise APITimeoutError("timed out")
        return S(choices=[S(message=S(content="ok"), finish_reason="stop")], usage=None, model="m")
    monkeypatch.setattr(client, "_create", create)
    resp = client.chat_messages([{"role": "user", "content": "hi"}])
    assert resp.content == "ok" and seen == [8000, 4000] and resp.retries[0]["max_tokens_after"] == 4000


def test_team_yaml_names_the_model_the_calls_go_to(tmp_path):
    claude = entry("claude-sonnet-5-5")
    r = router([entry("gemma-4-31b"), claude], tmp_path, profile_allowed=["claude-sonnet-5-5"])
    assert planned_model(r) == "claude-sonnet-5-5-id"
    assert planned_model(router([entry("a"), entry("b")], tmp_path)) is None   # routed among several: per call
    assert planned_model(MockLLMClient(responder=lambda m, s: "x")) is None    # tests keep the envelope's default
