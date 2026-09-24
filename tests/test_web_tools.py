"""D32 — web_search and fetch_url behind a provider interface, with source ids and limits (mocked; no network)."""
import re

import pytest

from amoeba.interp.runtime import Interpreter
from amoeba.interp.trace import TraceWriter
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from amoeba.tools.web import TavilyProvider, WebLimits, WebToolError, WebTools, web_registry
from tests.conftest import fx, mock

APPROVE = fx("observer_d24_approve")


class FakeProvider:
    name = "fake"

    def __init__(self, fail: bool = False):
        self.fail, self.searches, self.fetches = fail, [], []

    def search(self, query, max_results):
        if self.fail:
            raise WebToolError("503 from provider")
        self.searches.append(query)
        return [{"title": f"Result {i} for {query}", "url": f"https://ex.com/{i}", "snippet": f"snippet {i}"}
                for i in range(1, 4)][:max_results]

    def fetch(self, url):
        self.fetches.append(url)
        return {"url": url, "title": "Page", "text": "x" * 10_000}


def tools(fail=False, **limits):
    web = WebTools(FakeProvider(fail), WebLimits(**limits))
    web.begin_step(1, TraceWriter(None))
    return web


def test_search_results_get_source_ids_and_repeat_urls_keep_theirs():
    web = tools()
    out = web.web_search("RDS PostgreSQL price per GB")
    assert "[S1] Result 1 for RDS PostgreSQL price per GB — https://ex.com/1" in out and "[S3]" in out
    web.begin_step(2)
    again = web.web_search("another query")
    assert "[S1] Result 1 for another query" in again and "[S4]" not in again        # same url, same id
    s1 = web.sources[0]
    assert s1["steps"] == [1, 2] and s1["fetched_at"] and s1["kind"] == "search"
    assert [s["id"] for s in web.sources_for(2)] == ["S1", "S2", "S3"]


def test_fetch_truncates_and_accepts_a_source_id():
    web = tools(max_fetch_chars=500)
    web.web_search("q")
    out = web.fetch_url("[S2]")
    assert out.startswith("[S2] Result 2 for q (https://ex.com/2)") and "first 500 of 10000 characters" in out
    assert len(out.split(":\n", 1)[1]) == 500 and web.sources[1]["fetched"] is True
    assert web.fetch_url("not a url").startswith("error: fetch_url needs")
    assert web.fetch_url("S9").startswith("error: fetch_url: no source S9")


def test_limits_per_step_are_enforced_and_traced():
    web = tools(max_searches_per_step=2)
    web.web_search("a"), web.web_search("b")
    assert web.web_search("c") == "error: web_search limit reached (2 per step); work with the sources you have"
    assert web.trace.events("tool_limit")[0]["amoeba.limit"] == 2
    web.begin_step(2)
    assert web.web_search("d").startswith("Search results")                      # the count is per step


def test_a_provider_failure_is_an_error_string_and_an_event():
    web = tools(fail=True)
    assert web.web_search("q") == "error: web_search failed: WebToolError: 503 from provider"
    [ev] = web.trace.events("tool_error")
    assert ev["gen_ai.tool.name"] == "web_search" and ev["amoeba.step"] == 1


def test_tavily_needs_its_key_from_the_environment(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(WebToolError, match="TAVILY_API_KEY is not set"):
        TavilyProvider()


def test_tavily_response_shapes(monkeypatch):
    p = TavilyProvider(api_key="k")
    calls = []

    def post(path, body):
        calls.append((path, body))
        if path == "search":
            return {"results": [{"title": "T", "url": "https://u", "content": "C", "score": 0.9}]}
        return {"results": [{"url": "https://u", "raw_content": "page text"}], "failed_results": []}
    monkeypatch.setattr(p, "_post", post)
    assert p.search("q", 3) == [{"title": "T", "url": "https://u", "snippet": "C"}]
    assert p.fetch("https://u") == {"url": "https://u", "title": "https://u", "text": "page text"}
    assert calls[0] == ("search", {"query": "q", "max_results": 3, "search_depth": "basic"})


# ---- in the plan runner -----------------------------------------------------------------------------------------
def researcher(messages, seed):
    user = messages[-1]["content"]
    n = re.search(r"# Your step \(step (\d+)\)", user).group(1)
    if n == "1" and "web_search" in re.search(r"You can use: (.*)", user).group(1) and "[S1]" not in user:
        return "## Thought\nsearch\n\n## CurrentStep\nprices\n\n## Action\nweb_search\n\n## ActionInput\nRDS price\n"
    return f"## Thought\nok\n\n## CurrentStep\nwrite\n\n## Action\nFinal Output\n\n## ActionInput\nOUT-{n} [S1]\n"


def test_roles_that_asked_for_web_search_get_the_tools(task, envelope, trace, tmp_path):
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE],
               plan_worker=researcher)
    cfg = instantiate(draft_team(task, llm, envelope, trace, prompts="d24"), "plan", task, envelope)
    reg = web_registry(FakeProvider())
    ep = Interpreter(llm, reg, trace, run_dir=tmp_path).run(cfg, task, seed=0)
    [mapped] = trace.events("capability_mapped")
    assert mapped["gen_ai.agent.name"] == "Cost Analyst" and mapped["amoeba.granted"] == ["web_search", "fetch_url"]
    assert mapped["amoeba.requested"] == ["web_search", "web_search"]   # missing tool + its capability request
    first = llm.calls_of("plan_worker")[0]["messages"][-1]["content"]
    assert "You can use: ['calc', 'web_search', 'fetch_url', 'Print', 'Final Output']" in first
    assert "Tool web_search is unavailable" not in first
    assert "Tool database_sandbox is unavailable" in llm.calls_of("plan_worker")[2]["messages"][-1]["content"]
    one = ep.steps[0]
    assert [s["id"] for s in one["sources"]][:1] == ["S1"] and one["sources"][0]["url"] == "https://ex.com/1"
    assert trace.events("web_tools")[0]["amoeba.web.max_searches_per_step"] == 4
    assert cfg.agents[mapped["gen_ai.agent.id"]].tools == ["calc"]           # the saved team is unchanged


def test_without_web_tools_nothing_is_mapped(task, envelope, trace, tools):
    llm = mock(planner=[fx("draft_d24_full")], agent_observer=[APPROVE], plan_observer=[APPROVE],
               plan_worker=researcher)
    cfg = instantiate(draft_team(task, llm, envelope, trace, prompts="d24"), "plan", task, envelope)
    Interpreter(llm, tools, trace).run(cfg, task, seed=0)
    assert trace.events("capability_mapped") == [] and trace.events("web_tools") == []
    assert "Tool web_search is unavailable" in llm.calls_of("plan_worker")[0]["messages"][-1]["content"]
