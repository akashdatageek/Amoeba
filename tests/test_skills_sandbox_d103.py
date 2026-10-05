"""D103 — pool skills work in sandbox mode. A skill entry's `root` is the root's label (anthropics_skills), not a
path; the old code resolved it against the current directory, so every skill was refused as "not in the sandbox
image". Offline: the entry keeps its root folder (`root_path`; an older entry finds it among its parents) and maps to
/opt/skills/<path in the clone>; a skill from a root the image does not hold is still refused. Live (skipped without
the OpenShell gateway and the amoeba-sandbox:local image): the xlsx skill is attached to a helper in a fresh sandbox,
and its files are read and its script listed and run inside the sandbox."""
import json
from pathlib import Path

import pytest

from amoeba.config.schema import AgentSpec, PromptRef
from amoeba.interp.trace import TraceWriter
from amoeba.localtools.skills import list_skills, sandbox_skill_path, skill_root_path
from amoeba.localtools.toolbox import LocalSetup, LocalToolbox
from amoeba.tools.registry import default_registry
from tests.test_sandbox_d96 import live

CLONE = Path(__file__).resolve().parents[1] / "data" / "pool" / "repos"


def fake_clone(tmp_path, label="anthropics_skills"):
    d = tmp_path / "repos" / label / "xlsx"
    (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: xlsx\ndescription: spreadsheets\n---\nUse openpyxl.\n")
    (d / "scripts" / "recalc.py").write_text("print('ok')\n")
    return tmp_path


def agent():
    return AgentSpec(agent_id="a", name="Analyst", role="worker", model="m", prompt=PromptRef(system="s", user="u"))


def test_the_entry_maps_to_the_image(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                                   # the old bug resolved the label from here
    pool = fake_clone(tmp_path)
    [e] = list_skills({"skill_roots": [], "repo_skills": "repos"}, pool)
    assert e["root"] == "anthropics_skills" and Path(e["root_path"]) == pool / "repos" / "anthropics_skills"
    assert sandbox_skill_path(e) == Path("/opt/skills/xlsx")
    old = {k: v for k, v in e.items() if k != "root_path"}       # an entry made before D103
    assert skill_root_path(old) == pool / "repos" / "anthropics_skills" and sandbox_skill_path(old) == Path("/opt/skills/xlsx")


def test_a_skill_the_image_does_not_hold_is_refused(tmp_path):
    [e] = list_skills({"skill_roots": [], "repo_skills": "repos"}, fake_clone(tmp_path, "other_skills"))
    assert sandbox_skill_path(e) is None


def test_attach_in_sandbox_mode_without_starting_it(tmp_path):
    [e] = list_skills({"skill_roots": [], "repo_skills": "repos"}, fake_clone(tmp_path))
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    box = LocalToolbox(LocalSetup(env={}), run_dir, TraceWriter(run_dir / "trace.jsonl", episode_id="d103"))
    assert box.setup.isolation == "openshell"
    box.office = {"ok": True, "detail": "test"}
    a = agent()
    assert box.attach_skill(a, e, default_registry()) is True
    assert "Full skill files are in /opt/skills/xlsx/ (read-only)" in a.pool[-1]["text"]
    assert box.skills_attached[0]["path"] == "sandbox:/opt/skills/xlsx"
    ev = [json.loads(l) for l in (run_dir / "trace.jsonl").read_text().splitlines()]
    assert not any(x.get("name") == "skill_refused" for x in ev)


@live
def test_live_a_pool_skill_is_attached_and_used_in_the_sandbox(tmp_path):
    entries = [e for e in list_skills({"skill_roots": [], "repo_skills": "repos"}, CLONE.parent)
               if e["root"] == "anthropics_skills" and e["name"] == "xlsx"]
    if not entries:
        pytest.skip("no anthropics_skills clone with xlsx under data/pool/repos")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    box = LocalToolbox(LocalSetup(env={}), run_dir, TraceWriter(run_dir / "trace.jsonl", episode_id="d103"))
    box.start()
    try:
        assert box.box is not None and box.exposed, box.error
        box.begin_step(1)
        reg, a = default_registry(), agent()
        assert box.attach_skill(a, entries[0], reg) is True
        assert "local:Read" in a.tools and "local:Bash" in a.tools
        text = box.call("Read", "/opt/skills/xlsx/SKILL.md")                 # the helper reads the skill ...
        assert not text.startswith("refused") and "name: xlsx" in text
        listing = box.call("Bash", "ls /opt/skills/xlsx/scripts")             # ... finds its script ...
        assert not listing.startswith("refused") and "recalc.py" in listing
        out = box.call("Bash", "python3 -c \"import ast,sys; ast.parse(open('/opt/skills/xlsx/scripts/recalc.py')"
                               ".read()); print('PARSED')\"")                 # ... and runs code over it
        assert "PARSED" in out
    finally:
        box.finish()


def test_sandbox_bash_may_name_the_read_only_skill_root_but_never_write_there(tmp_path):
    from amoeba.localtools.gate import protected_command, screen_command
    cfg = {"readable_roots": ["/opt/skills"]}
    run = "python3 /opt/skills/xlsx/scripts/recalc.py out.xlsx"
    assert screen_command(run, tmp_path, cfg) is None                                    # sandbox: allowed
    assert screen_command(run, tmp_path)[1].startswith("path outside the workspace")      # in process: not
    assert screen_command("cat /etc/passwd", tmp_path, cfg)[1].startswith("path outside the workspace")
    assert screen_command("cat /opt/skills/../etc/passwd", tmp_path, cfg) is not None
    for w in ("cp evil.py /opt/skills/xlsx/scripts/recalc.py", "echo x > /opt/skills/xlsx/SKILL.md",
              "sed -i s/a/b/ /opt/skills/xlsx/SKILL.md"):
        assert protected_command(w), w
