"""D137 — security: a pool server that runs code is refused unless --allow-remote-exec; the harness's own fetches
reach only public http(s) addresses, every redirect hop checked; local and made tools are not outside actions.
Offline: stub resolvers and openers, no network."""
import io
import urllib.error
from dataclasses import replace
from email.message import Message

import pytest

from amoeba.config.niche import load_profile, tool_allowed
from amoeba.pool.stock import remote_exec, stock_toolbox, vet
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from amoeba.tools.registry import default_registry
from amoeba.tools.web import NOT_PUBLIC, WebToolError, check_url, http_get, public_address
from tests.conftest import fx, mock
from tests.test_pool import CAP, FakeServer, cache, picker, req, setup, tool  # noqa: F401  (cache: fixture)

# the registry entry the Sonnet probe's Box 4 picked for "Bash" (eval/manual/sonnet/REPORT.md); it was stopped only
# because its connection failed
SANDBOXAPI = {"id": "io.github.MichielDeRuiter/sandboxapi-mcp", "name": "io.github.MichielDeRuiter/sandboxapi-mcp",
              "title": "SandboxAPI", "kind": "tool", "source": "registry",
              "description": "Execute code in 8 languages (Python, JS, TS, Go, Java, C++, C, Bash) in gVisor sandboxes.",
              "source_repo": "https://github.com/sandboxapi/sandboxapi-mcp", "version": "1.0.0",
              "remote_url": "https://mcp.sandboxapi.dev/mcp", "transport": "streamable-http", "auth_required": False,
              "auth_headers": [], "description_sha256": "174f85d4c4b0372d78d2665e5f75916f04bcf1730518a27e4b5b3d463810197c"}


def test_remote_exec_words():
    assert remote_exec("io.example/code", "Runs Python code") == "Runs Python"
    assert remote_exec("tool", "execute python snippets") == "execute"
    assert remote_exec("jupyter-server") == "jupyter" and remote_exec("x", "a shell for you") == "shell"
    assert remote_exec("weather", "Weather forecasts for a city") is None
    assert remote_exec("evaluation-metrics", "evaluate a model") is None               # whole words only


def test_a_candidate_that_executes_python_is_refused_unless_allowed(cache):
    t = tool("io.example/runner", "Helpful runner", tools=[{"name": "go", "description": "execute python and return"}])
    assert vet(t, setup(cache))[0] == "remote_exec"
    assert vet(t, replace(setup(cache), allow_remote_exec=True))[0] is None
    assert vet(SANDBOXAPI, setup(cache))[0] == "remote_exec"                      # the probe's server


def test_a_server_whose_tool_runs_code_is_refused_after_connecting(cache, task, envelope, trace):
    server = FakeServer()
    server.listing.append({"name": "run_code", "description": "Run code in an interpreter", "input_schema": {}})
    llm = mock(planner=[fx(CAP)], pool_picker=picker)
    cfg = instantiate(draft_team(task, llm, envelope, trace), "flat", task, envelope)
    q = req("web_search", what="search the web")
    reg, _ = stock_toolbox([q], cfg, default_registry(), llm, trace, setup(cache, server))
    assert (q.status, q.reason) == ("unfilled", "remote_exec") and "pool:io.example/search" not in reg
    ev = trace.events("pool_refused_remote_exec")
    assert ev and ev[0]["amoeba.stage"] == "connect" and ev[0]["amoeba.word"].lower() in ("run code", "interpreter")


@pytest.mark.parametrize("url", ["http://127.0.0.1/x", "http://10.1.2.3/", "http://169.254.169.254/latest/meta-data/",
                                 "http://[::1]/", "http://localhost:8080/", "http://192.168.0.1/",
                                 "http://[::ffff:127.0.0.1]/", "http://0.0.0.0/"])
def test_private_and_local_addresses_are_refused(url):
    with pytest.raises(WebToolError, match=NOT_PUBLIC):
        http_get(url, 1000, resolve=lambda h, p: [])


def test_hosts_are_resolved_and_schemes_limited():
    private = lambda h, p: [(2, 1, 6, "", ("10.0.0.5", 0))]        # noqa: E731
    public = lambda h, p: [(2, 1, 6, "", ("93.184.216.34", 0))]    # noqa: E731
    with pytest.raises(WebToolError, match=NOT_PUBLIC):
        check_url("https://internal.example.com/a", private)
    check_url("https://www.eia.gov/a", public)
    with pytest.raises(WebToolError, match="only http and https"):
        check_url("file:///etc/passwd", public)
    assert public_address("8.8.8.8") and not public_address("fd00::1") and not public_address("224.0.0.1")


class Opener:
    """Answers each URL from a table: a redirect (status, location) or a body."""

    def __init__(self, table):
        self.table, self.seen = table, []

    def open(self, req, timeout=None):
        self.seen.append(req.full_url)
        got = self.table[req.full_url]
        if isinstance(got, tuple):
            h = Message()
            h["Location"] = got[1]
            raise urllib.error.HTTPError(req.full_url, got[0], "moved", h, io.BytesIO(b""))
        r = io.BytesIO(got)
        r.headers, r.status = {"Content-Type": "text/csv"}, 200
        r.__enter__, r.__exit__ = (lambda: r), (lambda *a: None)
        return _Resp(got)


class _Resp(io.BytesIO):
    headers, status = {"Content-Type": "text/csv"}, 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def resolver(h, p):
    return [(2, 1, 6, "", ("10.0.0.9" if h == "intranet.example" else "93.184.216.34", 0))]


def test_a_redirect_to_a_private_address_is_refused_and_hops_are_capped():
    o = Opener({"https://a.example/x": (302, "http://intranet.example/secret")})
    with pytest.raises(WebToolError, match=NOT_PUBLIC):
        http_get("https://a.example/x", 1000, resolve=resolver, opener=o)
    ok = Opener({"https://a.example/x": (301, "/y"), "https://a.example/y": b"a,b\n1,2\n"})
    assert http_get("https://a.example/x", 1000, resolve=resolver, opener=ok)[0] == b"a,b\n1,2\n"
    loop = Opener({f"https://a.example/{i}": (302, f"/{i + 1}") for i in range(10)})
    with pytest.raises(WebToolError, match="more than 3 redirects"):
        http_get("https://a.example/0", 1000, resolve=resolver, opener=loop)
    assert len(loop.seen) == 4


def test_the_calc_profile_allows_local_write_but_still_refuses_outside_actions():
    prof = load_profile("calc")
    assert tool_allowed("local:Write", prof, "writes a file") == (True, "")
    assert tool_allowed("local:Edit", prof, "edits a file") == (True, "")
    assert tool_allowed("pool:mailer", prof)[0] is False                            # not in the allow list
    open_prof = prof.model_copy(update={"tools": {"allowed": "all"}})
    assert tool_allowed("pool:mailer", open_prof, "sends an email")[0] is False      # the side-effect gate holds
