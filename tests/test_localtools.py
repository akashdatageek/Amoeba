"""D59 — the local toolbox: Claude Code's tools and skills through `claude mcp serve`, sandboxed.
Offline: the mock LLM, and tests/fake_claude_serve.py standing in for `claude mcp serve` (a real stdio MCP server)."""
import copy
import json
import os
import sys
import time
from pathlib import Path

import pytest

from amoeba.interp.trace import TraceWriter
from amoeba.localtools.claims import claimed_files
from amoeba.localtools.gate import SandboxRequired, inside, screen_command
from amoeba.localtools.toolbox import LocalSetup, LocalToolbox, load_local_config
from amoeba.pool.index import refresh
from amoeba.pool.stock import PoolSetup, stock_toolbox
from amoeba.task.draft import draft_team
from amoeba.task.instantiate import instantiate
from amoeba.task.models import CapabilityRequest, Task
from amoeba.tools.registry import default_registry
from scripts.run_task import LOCAL_FIELDS, parse_args, run_one
from tests.conftest import fx, mock
from tests.test_pool import fake_clone, fake_web, tool

FAKE = [sys.executable, str(Path(__file__).parent / "fake_claude_serve.py")]
CAP = "draft_capability_requests"
SANDBOX = {"AMOEBA_SANDBOX": "1"}


@pytest.fixture
def skills(tmp_path):
    """A Claude Code skill folder with scripts (xlsx) and a kept anthropics/skills clone (pptx)."""
    user = tmp_path / "claude-skills"
    (user / "xlsx" / "scripts").mkdir(parents=True)
    (user / "xlsx" / "SKILL.md").write_text("---\nname: xlsx\ndescription: Make Excel spreadsheets with formulas\n---\n"
                                            "# XLSX\nUse openpyxl. Run scripts/recalc.py after saving.\n" + "x" * 6000)
    (user / "xlsx" / "scripts" / "recalc.py").write_text("print('recalc')\n")
    clone = tmp_path / "pool" / "repos" / "anthropics_skills" / "pptx"
    clone.mkdir(parents=True)
    (clone / "SKILL.md").write_text("---\nname: pptx\ndescription: Make PowerPoint decks\n---\nUse python-pptx.\n")
    return tmp_path


def lsetup(root: Path, env=SANDBOX, command=FAKE, **limits) -> LocalSetup:
    cfg = copy.deepcopy(load_local_config())
    cfg["skill_roots"] = [{"label": "claude-user", "path": str(root / "claude-skills")}]
    cfg["limits"].update(limits)
    return LocalSetup(config=cfg, command=command, pool_dir=root / "pool", env=env)


@pytest.fixture
def box(skills, tmp_path):
    b = LocalToolbox(lsetup(skills), tmp_path / "run", TraceWriter(None))
    b.start()
    b.begin_step(1)
    yield b
    b.finish()


def events(b, name):
    return b.trace.events(name)


# ---- 1. connect: allowed tools only ----------------------------------------------------------------------------
def test_allowed_tools_are_exposed_and_run_in_the_workspace(box):
    assert box.exposed == ["Bash", "Read", "Write", "Edit"]          # Glob and Grep: not offered by this server
    assert [e["gen_ai.tool.name"] for e in events(box, "local_tool_missing")] == ["Glob", "Grep"]
    out = box.call("Bash", "pwd")
    assert out.startswith("[local:Bash]") and str(box.workspace.resolve()) in out
    assert box.call("Write", json.dumps({"file_path": "notes/a.txt", "content": "hello"})).startswith("[local:Write]")
    assert (box.workspace / "notes" / "a.txt").read_text() == "hello"
    assert "hello" in box.call("Read", "notes/a.txt")
    box.call("Edit", json.dumps({"file_path": "notes/a.txt", "old_string": "hello", "new_string": "bye"}))
    assert (box.workspace / "notes" / "a.txt").read_text() == "bye"
    calls = events(box, "local_call")
    assert [c["gen_ai.tool.name"] for c in calls] == ["local:Bash", "local:Write", "local:Read", "local:Edit"]
    assert [c["amoeba.input"] for c in calls] == ["pwd", "notes/a.txt", "notes/a.txt", "notes/a.txt"]
    assert {c["amoeba.decision"] for c in calls} == {"allowed"} and "hello" not in json.dumps(calls)
    assert calls[1]["amoeba.files"] == ["notes/a.txt"] and all(c["amoeba.step"] == 1 for c in calls)


def test_a_disallowed_tool_is_refused_once_at_start_and_on_every_call(box):
    refused = events(box, "local_tool_refused")
    assert [(e["gen_ai.tool.name"], e["amoeba.reason"]) for e in refused] == [("WebFetch", "not_allowed"),
                                                                             ("Agent", "not_allowed")]
    assert box.call("WebFetch", "https://example.org").startswith("refused: local:WebFetch — not_allowed")
    assert box.refusals == {"not_allowed": 1} and box.calls == 0
    assert not any(e["id"] == "local:WebFetch" for e in box.entries())


# ---- 2. sandbox and gate ---------------------------------------------------------------------------------------
def test_paths_outside_the_workspace_are_refused(box, tmp_path):
    (tmp_path / "secret.txt").write_text("key")
    for path in ["/etc/passwd", "../secret.txt", str(tmp_path / "secret.txt")]:
        assert box.call("Read", path).startswith("refused: local:Read — outside_workspace")
    os.symlink(tmp_path, box.workspace / "link")                     # a symlink out is followed, then refused
    assert "outside_workspace" in box.call("Read", "link/secret.txt")
    assert "outside_workspace" in box.call("Write", json.dumps({"file_path": "/tmp/x.txt", "content": "x"}))
    assert box.refusals == {"outside_workspace": 5} and box.calls == 0
    refused = events(box, "local_refused")
    assert len(refused) == 5 and refused[0]["amoeba.input"] == "/etc/passwd"
    assert {(e["amoeba.decision"], e["amoeba.reason"]) for e in refused} == {("refused", "outside_workspace")}


@pytest.mark.parametrize("cmd", ["curl https://example.org", "wget http://x", "ssh host", "scp a host:b", "nc -l 80",
                                 "git clone https://github.com/x/y", "git push", "git fetch origin",
                                 "pip install requests", "python -m pip install x", "npm install left-pad",
                                 "python3 -c 'import urllib.request'"])
def test_network_commands_are_refused(tmp_path, cmd):
    assert screen_command(cmd, tmp_path)[0] == "network_command"


@pytest.mark.parametrize("cmd", ["rm -rf /", "rm -rf ~", "sudo ls", "cd / && ls", "cat ../x", "cat ~/.ssh/id_rsa",
                                 "cat /etc/passwd", "echo $HOME", "ln -s /etc etc", "kill -9 1", ":(){ :|:& };:",
                                 "python3 -c \"open('/tmp/x','w')\""])
def test_unsafe_commands_are_refused(tmp_path, cmd):
    assert screen_command(cmd, tmp_path)[0] == "unsafe_command"


@pytest.mark.parametrize("cmd", ["python3 make_chart.py", "ls -la", "echo hi > out.txt", "python3 -c 'print(2*3)'",
                                 "cat data.csv | head -5 2>/dev/null", "mkdir -p out && cp a.txt out/"])
def test_ordinary_commands_pass_the_gate(tmp_path, cmd):
    assert screen_command(cmd, tmp_path) is None


def test_gated_bash_calls_are_refused_and_counted(box):
    assert box.call("Bash", "curl https://example.org").startswith("refused: local:Bash — network_command")
    assert box.call("Bash", "rm -rf /").startswith("refused: local:Bash — unsafe_command")
    assert box.call("Bash", "cd /; ls").startswith("refused")
    assert box.refusals == {"network_command": 1, "unsafe_command": 2} and box.calls == 0
    assert events(box, "local_refused")[0]["amoeba.input"] == "curl https://example.org"


def test_each_command_starts_in_the_workspace(box):
    box.call("Bash", "mkdir -p sub && cd sub")                      # the server's shell would keep this cwd
    assert f'"stdout": "{box.workspace.resolve()}"' in box.call("Bash", "pwd")


def test_inside_resolves_relative_paths_from_the_workspace(tmp_path):
    assert inside("a/b.txt", tmp_path) == (tmp_path / "a" / "b.txt").resolve()
    assert inside("a/../../x", tmp_path) is None and inside("", tmp_path) is None


# ---- 2. limits -------------------------------------------------------------------------------------------------
def test_a_call_times_out(skills, tmp_path):
    b = LocalToolbox(lsetup(skills, timeout_s=1), tmp_path / "run", TraceWriter(None))
    b.start()
    b.begin_step(1)
    t0 = time.perf_counter()
    out = b.call("Bash", "sleep 5")
    assert time.perf_counter() - t0 < 4.5 and "error" in out.split("\n")[0] and "timed out" in out
    assert b.trace.events("local_call")[0]["amoeba.is_error"] is True
    b.finish()


def test_output_and_call_caps(skills, tmp_path):
    b = LocalToolbox(lsetup(skills, max_output_chars=10, max_calls_per_step=2, max_calls_per_run=3),
                     tmp_path / "run", TraceWriter(None))
    b.start()
    b.begin_step(1)
    out = b.call("Bash", "python3 -c 'print(\"y\" * 50)'")
    assert "[… first 10 of" in out
    b.call("Bash", "ls")
    assert b.call("Bash", "ls").startswith("refused: local:Bash — step_cap")
    b.begin_step(2)
    b.call("Bash", "ls")
    assert b.call("Bash", "ls").startswith("refused: local:Bash — run_cap")
    assert b.calls == 3 and b.refusals == {"step_cap": 1, "run_cap": 1}
    assert b.finish()["local_refusals"] == {"step_cap": 1, "run_cap": 1}


def test_the_document_libraries_are_importable_from_bash(box):
    out = box.call("Bash", "python3 -c 'import openpyxl, docx, pptx, matplotlib, pypdf; print(\"libs ok\")'")
    assert "libs ok" in out


def test_without_amoeba_sandbox_it_refuses(skills, tmp_path, monkeypatch):
    with pytest.raises(SandboxRequired):
        LocalToolbox(lsetup(skills, env={}), tmp_path / "run", TraceWriter(None))
    monkeypatch.delenv("AMOEBA_SANDBOX", raising=False)
    with pytest.raises(SystemExit):
        parse_args(["a task", "--local-tools", "on"])
    monkeypatch.setenv("AMOEBA_SANDBOX", "1")
    assert parse_args(["a task", "--local-tools", "on"]).local_tools == "on"
    assert parse_args(["a task"]).local_tools == "off"                # off by default


def test_no_server_means_no_local_tools_and_the_run_goes_on(skills, tmp_path):
    b = LocalToolbox(lsetup(skills, command=["amoeba-no-such-command"]), tmp_path / "run", TraceWriter(None))
    b.start()
    assert b.server is None and b.trace.events("local_unavailable") and b.entries() == []
    assert b.call("Bash", "ls").startswith("error: local:Bash is not available")
    assert b.finish()["local_tool_calls"] == 0


# ---- 3 and 4. skills and matching --------------------------------------------------------------------------------
def req(name, kind="tool", role="Researcher", what="", **kw):
    return CapabilityRequest(name=name, kind=kind, for_role=role, what_it_does=what, **kw)


def test_local_skills_are_listed_from_claude_code_and_the_kept_clone(box):
    ids = [s["id"] for s in box.skills]
    assert ids == ["local:skill:claude-user/xlsx", "local:skill:anthropics_skills/pptx"]
    assert box.skills[0]["has_scripts"] is True and box.skills[0]["source"] == "local"


@pytest.mark.parametrize("name,expected", [("python_interpreter", "local:Bash"), ("code_runner", "local:Bash"),
                                           ("file_writing", "local:Write"), ("save_file", "local:Write"),
                                           ("excel_generator", "local:skill:claude-user/xlsx"),
                                           ("spreadsheet_tool", "local:skill:claude-user/xlsx"),
                                           ("presentation-generator", "local:skill:anthropics_skills/pptx")])
def test_aliases_put_the_local_item_first(box, name, expected):
    assert box.candidates(req(name), 5)[0][1]["id"] == expected


@pytest.fixture
def cache(tmp_path):
    """A pool cache with an internet code runner and an internet xlsx skill (with scripts)."""
    d = tmp_path / "pool"
    d.mkdir(exist_ok=True)
    entries = [tool("io.example/py-sandbox", "Python interpreter: runs python code in a remote sandbox"),
               {"id": "anthropics/skills:xlsx", "name": "xlsx", "title": "", "description": "Excel spreadsheets",
                "kind": "skill", "source": "repo", "has_scripts": True, "body_file": "skills/x.md"}]
    (d / "index.json").write_text(json.dumps({"refreshed_at": "2026-09-26T00:00:00+00:00", "entries": entries}))
    return d


def pool_setup(cache):
    cfg = {"sources": [], "cache_dir": str(cache), "auth_env": {}, "paid_hosts": [],
           "limits": {"max_candidates": 5, "max_per_helper": 3, "max_per_run": 8, "max_skill_chars": 5000,
                      "max_calls_per_step": 3, "timeout_s": 5, "max_result_chars": 6000}}
    return PoolSetup(config=cfg, env={})


def draft_cfg(task, envelope, text):
    trace = TraceWriter(None)
    llm = mock(planner=[text])
    return instantiate(draft_team(task, llm, envelope, trace), "flat", task, envelope)


def test_local_candidates_rank_above_internet_ones(cache, skills, tmp_path, task, envelope):
    cfg = draft_cfg(task, envelope, fx(CAP).replace("web_search", "python_interpreter"))
    b = LocalToolbox(lsetup(skills), tmp_path / "run", TraceWriter(None))
    llm = mock(pool_picker=lambda m, s: "local:Bash" if "local:Bash" in m[-1]["content"] else "NONE")
    q = req("python_interpreter", what="runs python code")
    reg, summary = stock_toolbox([q], cfg, default_registry(), llm, b.trace, pool_setup(cache), local=b)
    [match] = b.trace.events("pool_match")
    cands = match["amoeba.pool.candidates"]
    assert cands[0] == {"id": "local:Bash", "kind": "tool", "score": 100, "source": "local"}
    assert "io.example/py-sandbox" in [c["id"] for c in cands]
    assert [c.get("source") for c in cands].index(None) > 0          # every local one before the first internet one
    assert "anthropics/skills:xlsx" not in json.dumps(cands)         # index skills come through the local listing
    assert (q.status, q.pool_id) == ("filled", "local:Bash") and "local:Bash" in reg
    assert summary["attached"][0]["source"] == "local" and summary["local"]["exposed"][0] == "local:Bash"
    researcher = next(a for a in cfg.agents.values() if a.name == "Researcher")
    assert "local:Bash" in researcher.tools and "python_interpreter" not in researcher.missing_tools
    b.finish()


def test_a_skill_with_scripts_is_refused_with_the_flag_off(cache, task, envelope):
    cfg = draft_cfg(task, envelope, fx(CAP).replace("web_search", "excel_generator"))
    q = req("excel_generator", what="makes an Excel spreadsheet")
    llm = mock(pool_picker=["anthropics/skills:xlsx"])
    stock_toolbox([q], cfg, default_registry(), llm, TraceWriter(None), pool_setup(cache))
    assert (q.status, q.reason) == ("unfilled", "has_scripts")


def test_a_skill_with_scripts_is_attached_with_the_flag_on(cache, skills, tmp_path, task, envelope):
    cfg = draft_cfg(task, envelope, fx(CAP).replace("web_search", "excel_generator"))
    b = LocalToolbox(lsetup(skills), tmp_path / "run", TraceWriter(None))
    q = req("excel_generator", what="makes an Excel spreadsheet")
    llm = mock(pool_picker=["local:skill:claude-user/xlsx"])
    reg, summary = stock_toolbox([q], cfg, default_registry(), llm, b.trace, pool_setup(cache), local=b)
    assert (q.status, q.reason) == ("filled", "")
    assert (b.workspace / "skills" / "xlsx" / "scripts" / "recalc.py").is_file()   # the whole folder, scripts too
    researcher = next(a for a in cfg.agents.values() if a.name == "Researcher")
    [card] = [p["text"] for p in researcher.pool if p["kind"] == "skill"]
    assert "name: xlsx" in card and "Use openpyxl." in card                          # frontmatter + body
    assert "[… first 5000 of" in card and "x" * 5001 not in card
    assert card.endswith("Full skill files are in skills/xlsx/; read them with local:Read if needed.")
    assert {"local:Read", "local:Bash", "local:Write", "local:Edit"} <= set(researcher.tools)
    out = b.finish()
    assert out["skills_attached"] == [{"id": "local:skill:claude-user/xlsx", "name": "xlsx", "root": "claude-user",
                                       "path": "workspace/skills/xlsx", "helpers": ["Researcher"]}]
    assert out["files_created"] == []                                 # a copied skill is not a file the team made


def test_pool_refresh_keeps_the_skill_folders(tmp_path):
    cfg = {"sources": [{"kind": "skill", "source": "repo", "repo": "anthropics/skills", "path": "skills"}],
           "cache_dir": str(tmp_path / "pool")}
    refresh(cfg, get=fake_web({}), clone=fake_clone(), log=lambda _: None)
    kept = tmp_path / "pool" / "repos" / "anthropics_skills"
    assert (kept / "pdf" / "scripts" / "fill.py").is_file() and (kept / "brand" / "SKILL.md").is_file()
    assert (kept / ".commit").read_text()


# ---- 5. claims and the run record --------------------------------------------------------------------------------
def test_claimed_files_are_read_from_claims_only():
    assert claimed_files("The chart was saved to revenue_chart.png. Done.") == ["revenue_chart.png"]
    assert claimed_files("I created totals.xlsx and report.docx.") == ["totals.xlsx", "report.docx"]
    assert claimed_files("The PNG could not be saved to chart.png.") == []
    assert claimed_files("BLOCKED: code_interpreter — nothing saved to chart.png") == []
    assert claimed_files("It will be saved as out.csv") == []
    assert claimed_files("```python\nplt.savefig('a.png')  # saved a.png\n```") == []


def plan_worker(make: bool):
    """The Researcher runs local:Bash once (making chart.png when `make`), then says it saved chart.png."""
    def reply(messages, seed):
        user = messages[-1]["content"]
        if "'local:Bash'" in user and "[local:Bash" not in user:
            cmd = "python3 -c \"open('chart.png', 'wb').write(b'PNG')\"" if make else "ls"
            return f"## Thought\nplot\n\n## CurrentStep\nplot\n\n## Action\nlocal:Bash\n\n## ActionInput\n{cmd}\n"
        return ("## Thought\nok\n\n## CurrentStep\nwrite\n\n## Action\nFinal Output\n\n## ActionInput\n"
                "The bar chart was saved to chart.png.\n")
    return reply


def run_plan(tmp_path, skills, envelope, make, pool=None):
    llm = mock(planner=[fx(CAP).replace("web_search", "python_interpreter")],
               pool_picker=lambda m, s: "local:Bash" if "local:Bash" in m[-1]["content"] else "NONE",
               plan_worker=plan_worker(make))
    r = run_one(Task(prompt="Make a bar chart of 1, 2, 3 and save it as a PNG."), "plan", llm, envelope,
                default_registry(), tmp_path / "runs", pool=pool, local=lsetup(skills))
    return r, tmp_path / "runs" / r.run_id


def test_a_real_file_keeps_the_step_done_and_is_recorded(skills, tmp_path, envelope):
    r, run = run_plan(tmp_path, skills, envelope, make=True)
    step1 = json.loads((run / "artifacts" / "step_1.json").read_text())
    assert step1["status"] == "done" and step1["claimed_files"] == ["chart.png"] and step1["claimed_files_missing"] == []
    res = json.loads((run / "result.json").read_text())
    assert res["files_created"] == [{"path": "chart.png", "size": 3, "step": 1}]
    assert res["local_tool_calls"] == 1 and res["local_refusals"] == {} and res["skills_attached"] == []
    assert (run / "artifacts" / "files" / "chart.png").read_bytes() == b"PNG"
    assert res["pool"]["local"]["exposed"] == ["local:Bash", "local:Read", "local:Write", "local:Edit"]
    assert res["pool"]["pool"] == "off"                                # --no-pool: local items only
    lines = [json.loads(l) for l in (run / "trace.jsonl").read_text().splitlines()]
    assert [l["gen_ai.tool.name"] for l in lines if l["name"] == "local_call"] == ["local:Bash"]
    assert all(l.get("amoeba.box") for l in lines)                      # every line names its box (D55)
    assert not (run / "localtools_home").exists()


def test_a_claimed_file_that_is_missing_makes_the_step_incomplete(skills, tmp_path, envelope):
    r, run = run_plan(tmp_path, skills, envelope, make=False)
    step1 = json.loads((run / "artifacts" / "step_1.json").read_text())
    assert step1["status"] == "incomplete" and "claimed_file_missing: chart.png" in step1["status_reason"]
    res = json.loads((run / "result.json").read_text())
    assert res["files_created"] == [] and res["local_tool_calls"] == 1
    assert '"name": "claimed_file_missing"' in (run / "trace.jsonl").read_text()


# ---- 6. flag off is identical --------------------------------------------------------------------------------------
def test_flag_off_touches_nothing_local(cache, tmp_path, envelope, monkeypatch):
    import amoeba.interp.plan_runner as pr
    import amoeba.localtools.toolbox as lt

    def boom(*a, **k):
        raise AssertionError("local code ran with --local-tools off")
    monkeypatch.setattr(lt.LocalToolbox, "__init__", boom)
    monkeypatch.setattr(pr, "claimed_files", boom)

    def run(runs):
        llm = mock(planner=[fx(CAP)], pool_picker=["NONE", "NONE"], plan_worker=plan_worker(False))
        r = run_one(Task(prompt="Make a bar chart."), "plan", llm, envelope, default_registry(), runs,
                    pool=pool_setup(cache))
        return r, [c["messages"] for c in llm.calls], runs / r.run_id
    r1, calls1, run1 = run(tmp_path / "a")
    r2, calls2, run2 = run(tmp_path / "b")
    assert calls1 == calls2
    res = json.loads((run1 / "result.json").read_text())
    assert not LOCAL_FIELDS & set(res) and "local" not in res["pool"]
    assert not (run1 / "workspace").exists() and not (run1 / "artifacts" / "files").exists()
    trace = (run1 / "trace.jsonl").read_text()
    assert '"name": "local_' not in trace and "claimed_file" not in trace
    step1 = json.loads((run1 / "artifacts" / "step_1.json").read_text())
    assert "claimed_files" not in step1 and step1["status"] == "done"   # the same claim, not checked when off
