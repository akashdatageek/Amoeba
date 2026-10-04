"""D95 — shipping evidence to the repository's orphan `evidence` branch (a local bare repository stands in for
GitHub): key-scanned runs, events.jsonl and every path the new rows name are copied in the eval/loop/<stream>/ layout,
committed at most every batch interval as a fast-forward commit whose message carries the chain head, and pushed; a
failed push stays unshipped and goes out later; verify_evidence checks the branch's history and its head copy and
finds a rewritten row. Git runs in the harness only; agents' environments carry no git credentials. Offline."""
import json
import subprocess
from pathlib import Path

from amoeba.adapt.evidence import EvidenceLog, GitShipper, chain_head, run_env, verify_branch
from amoeba.adapt.loop import run_loop
from amoeba.llm.client import MockLLMClient
from tests.test_loop_d89 import GOOD, Runs, stream


def git(cwd, *a):
    p = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, capture_output=True,
                       text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def setup(tmp: Path):
    """origin.git (bare), repo/ (a clone with an orphan evidence branch on origin), root = repo/eval/loop/m2."""
    bare, repo = tmp / "origin.git", tmp / "repo"
    git(tmp, "init", "-q", "--bare", str(bare))
    git(tmp, "init", "-q", str(repo))
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "commit", "-q", "--allow-empty", "-m", "main")
    git(repo, "checkout", "-q", "--orphan", "evidence")
    (repo / "README.md").write_text("evidence\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-q", "-m", "evidence branch")
    git(repo, "push", "-q", "origin", "evidence")
    git(repo, "checkout", "-q", "master") if "master" in git(repo, "branch") else git(repo, "checkout", "-q", "main")
    root = repo / "eval" / "loop" / "m2"
    root.mkdir(parents=True)
    return bare, repo, root


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def run_folder(root, name, text="ok"):
    d = root / "practice" / name / "run1"
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"answer": text}))
    return d


def test_batched_fast_forward_commits_carry_the_chain_head(tmp_path):
    bare, repo, root = setup(tmp_path)
    clock = Clock()
    sh = GitShipper(root, "m2", tmp_path / "wt", repo, batch_seconds=600, clock=clock)
    ev = EvidenceLog(root)
    r1 = run_folder(root, "01-p1")
    ev.append("practice_run", {"order": 1}, [r1], key="p:1")
    sh.queue_run(r1)
    sh.queue_events()
    sh.state["last_ship"] = clock.t                      # a batch just went out: the next waits 10 minutes
    left = sh.flush()
    assert left and left[0]["error"] == "waiting for the next batch"
    clock.t += 601
    assert sh.flush() == []
    log = git(bare, "log", "--format=%B", "evidence")
    n, head = chain_head(root / "events.jsonl")
    assert f"Chain-Head: m2 {head}" in log and f"Chain-Rows: m2 {n}" in log
    files = git(bare, "ls-tree", "-r", "--name-only", "evidence")
    assert "eval/loop/m2/events.jsonl" in files and "eval/loop/m2/practice/01-p1/run1/result.json" in files
    # a second batch is a fast-forward on top of the first
    r2 = run_folder(root, "02-p2")
    ev.append("practice_run", {"order": 2}, [r2], key="p:2")
    sh.queue_run(r2)
    sh.queue_events()
    clock.t += 601
    assert sh.flush() == []
    assert len(git(bare, "rev-list", "evidence").split()) == 3
    res = verify_branch(repo, "evidence", "m2")
    assert res["ok"], res
    assert res["heads"] == 2


def test_force_flush_ships_at_once_and_nothing_new_makes_no_commit(tmp_path):
    bare, repo, root = setup(tmp_path)
    sh = GitShipper(root, "m2", tmp_path / "wt", repo, clock=Clock())
    EvidenceLog(root).append("x", {})
    sh.queue_events()
    sh.state["last_ship"] = 1000.0
    assert sh.flush(force=True) == []
    before = git(bare, "rev-parse", "evidence")
    sh.queue_events()
    assert sh.flush(force=True) == [] and git(bare, "rev-parse", "evidence") == before


def test_a_run_failing_the_key_scan_is_never_shipped(tmp_path):
    bare, repo, root = setup(tmp_path)
    sh = GitShipper(root, "m2", tmp_path / "wt", repo, clock=Clock())
    bad = run_folder(root, "03-p3", "key AIza" + "x" * 35)
    sh.queue_run(bad)
    assert sh.blocked and sh.blocked[0]["path"] == "practice/03-p3/run1" and not sh.pending


def test_a_failed_push_stays_unshipped_and_goes_out_later(tmp_path):
    bare, repo, root = setup(tmp_path)
    good_url = str(bare)
    sh = GitShipper(root, "m2", tmp_path / "wt", repo, clock=Clock(), retries=2)
    sh.ensure_worktree()
    git(tmp_path / "wt", "remote", "set-url", "origin", str(tmp_path / "nowhere.git"))
    r1 = run_folder(root, "01-p1")
    EvidenceLog(root).append("practice_run", {"order": 1}, [r1])
    sh.queue_run(r1)
    sh.queue_events()
    left = sh.flush(force=True)
    assert left and all(p["error"].startswith("push failed") for p in left)
    git(tmp_path / "wt", "remote", "set-url", "origin", good_url)
    assert sh.flush(force=True) == []
    assert "eval/loop/m2/practice/01-p1/run1/result.json" in git(bare, "ls-tree", "-r", "--name-only", "evidence")


def test_verify_branch_finds_a_rewritten_row(tmp_path):
    bare, repo, root = setup(tmp_path)
    clock = Clock()
    sh = GitShipper(root, "m2", tmp_path / "wt", repo, clock=clock)
    ev = EvidenceLog(root)
    for i in range(3):
        ev.append("x", {"i": i})
        sh.queue_events()
        clock.t += 601
        assert sh.flush() == []
    assert verify_branch(repo, "evidence", "m2")["ok"]
    wt = tmp_path / "wt"
    f = wt / "eval" / "loop" / "m2" / "events.jsonl"
    lines = f.read_text().splitlines()
    lines[0] = lines[0].replace('"i": 0', '"i": 9')
    f.write_text("\n".join(lines) + "\n")
    n, head = len(lines), __import__("amoeba.adapt.evidence", fromlist=["sha256_text"]).sha256_text(lines[-1])
    git(wt, "commit", "-qam", f"tamper\n\nChain-Head: m2 {head}\nChain-Rows: m2 {n}\n")
    git(wt, "push", "-q", "origin", "HEAD:refs/heads/evidence")
    b = verify_branch(repo, "evidence", "m2")["first_break"]
    assert b["kind"] == "rewritten"


def test_a_whole_loop_ships_to_the_branch(tmp_path, gate_v2):
    bare, repo, root = setup(tmp_path)
    sh = GitShipper(root, "fx", tmp_path / "wt", repo, clock=Clock(), batch_seconds=600)
    run_loop(stream(), Runs(), root, lambda hid: MockLLMClient(script={"architect": [GOOD]}), repeats=2,
             parallel_until=8, log=lambda *_: None, shipper=sh)
    state = json.loads((root / "loop_state.json").read_text())
    assert state["unshipped"] == [] and state["ship_state"]["rows_shipped"] == len(EvidenceLog(root).rows())
    files = git(bare, "ls-tree", "-r", "--name-only", "evidence")
    assert "eval/loop/m2/events.jsonl" in files and any("/experiments/" in f for f in files.splitlines())
    res = verify_branch(repo, "evidence", "m2")
    assert res["ok"] and res["heads"] >= 1, res


def test_agents_get_no_git_credentials(monkeypatch):
    env = run_env({"GH_TOKEN": "x", "GITHUB_TOKEN": "y", "GIT_ASKPASS": "/a", "SSH_AUTH_SOCK": "/s", "PATH": "/bin"})
    assert env == {"PATH": "/bin"}
