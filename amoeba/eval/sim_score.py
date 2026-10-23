"""D161 — the task score slot; D171 — the real scorers. A task names its scorers in its `sim` field (`scorers` with
weights; D161's one `scorer` is read as one); after the run, plain code asks each for the run's score on a seed, takes the weighted
mean and writes <run>/sim_score.json: score, the baseline score on the same seed, delta, seed, scorer, each part and
the judge hash (judge.py). Box 4 never reads it; only the outer loop (D166) compares it.

The scorers (SCORERS):
- standin (D161): the answer's first number against `sim.expected`.
- answer_key: numbers (each with an absolute `tol` and/or a relative `rel_tol`) and exact strings, from the task's
  key file `<sim.judge_set>_keys/<task id>.json`; score = the share found in the answer.
- hidden_tests: a pytest folder `<sim.judge_set>_hidden/<task id>/`, never in the task's files or the workspace, copied next
  to a copy of the delivered code in a temporary folder and run there; score = the share of tests passed.
- files: plain-code checks on the delivered files (the run's workspace): exists, rows (csv), formulas_live (xlsx),
  pages (pdf), image (png / jpg); score = the share passed.
- rubric: a fixed grader prompt (prompts/rubric_grader.txt), a fixed model and temperature (amoeba/eval/judge.yaml,
  never the team's client), `calls` grader calls (3); score = their median. The grader sees the task, the rubric and
  the answer only.

Every file a scorer reads is in the frozen judge (config/frozen.yaml): this module, judge.yaml, the grader prompt,
tasks/*_keys and tasks/*_hidden. A task whose input files include its key or hidden tests is refused (check_no_leak).
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from fnmatch import fnmatch
from pathlib import Path
from typing import Protocol

import yaml

ROOT = Path(__file__).resolve().parents[2]
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
SKIP_DIRS = ("sources", "skills", "made_tools", "inputs")   # not the team's delivered work (inputs/: D157's copies of the task's files)


# box: frozen_judge
class SimScorer(Protocol):
    name: str

    def score(self, run_dir: Path, sim, seed: int, task=None) -> dict:
        """{"score": float, ...} for the run in run_dir (sim: SimSpec; task: the Task)."""


# box: frozen_judge
class StandInScorer:
    """The stand-in until a simulator is chosen: the answer's first number against `sim.expected`
    (1.0 when equal, falling linearly to 0 at 100% relative error; 0 with no number). `sim.baseline` (default 0) is the
    baseline score; the seed is recorded and, being deterministic, changes nothing."""

    name = "standin"

    def score(self, run_dir: Path, sim, seed: int, task=None) -> dict:
        sim = spec(sim)
        m = NUMBER.search(answer_of(run_dir))
        if sim.expected is None:
            raise ValueError("the stand-in scorer needs sim.expected")
        expected = float(sim.expected)
        if m is None:
            s = 0.0
        else:
            got = float(m.group(0).replace(",", ""))
            s = max(0.0, 1.0 - abs(got - expected) / max(abs(expected), 1e-9))
        base = float(sim.baseline)
        return {"score": round(s, 6), "baseline": base, "delta": round(s - base, 6), "seed": int(seed)}


# box: frozen_judge
class AnswerKeyScorer:
    """D171: the key's numbers (within tol / rel_tol) and exact strings, each found anywhere in the answer."""

    name = "answer_key"

    def score(self, run_dir: Path, sim, seed: int, task=None) -> dict:
        key = load_key(sim, task)
        text = answer_of(run_dir)
        found = [float(x.replace(",", "")) for x in NUMBER.findall(text)]
        detail = []
        for n in key.get("numbers") or []:
            v = float(n["value"])
            tol = max(float(n.get("tol", 0) or 0), float(n.get("rel_tol", 0) or 0) * abs(v))
            hit = next((x for x in found if abs(x - v) <= tol + 1e-12), None)
            detail.append({"kind": "number", "name": n.get("name", str(n["value"])), "value": v, "tol": tol,
                           "ok": hit is not None, "found": hit})
        for s in key.get("strings") or []:
            detail.append({"kind": "string", "value": s, "ok": s in text})
        if not detail:
            raise ValueError(f"the answer key of {task.id} has no numbers and no strings")
        return {"score": round(sum(d["ok"] for d in detail) / len(detail), 6), "detail": detail}


# box: frozen_judge
class HiddenTestsScorer:
    """D171: the hidden pytest folder runs against a copy of the delivered code in a temporary folder (the workspace is
    never touched); score = passed / collected. No test collected scores 0."""

    name = "hidden_tests"
    timeout_s = 300

    def score(self, run_dir: Path, sim, seed: int, task=None) -> dict:
        sim = spec(sim)
        if not sim.judge_set:
            raise ValueError("the hidden_tests scorer needs sim.judge_set")
        tests = resolve(sim.folder("hidden")) / task.id
        if not tests.is_dir():
            raise ValueError(f"no hidden tests for {task.id} in {sim.folder('hidden')}")
        with tempfile.TemporaryDirectory(prefix="amoeba-hidden-") as tmp:
            work = Path(tmp) / "work"
            ws = Path(run_dir) / "workspace"
            if ws.is_dir():
                shutil.copytree(ws, work, ignore=shutil.ignore_patterns(*SKIP_DIRS, "__pycache__"), symlinks=False)
            else:
                work.mkdir()
            shutil.copytree(tests, work / "_hidden_tests")
            xml = Path(tmp) / "junit.xml"
            env = {**os.environ, "PYTHONPATH": str(work), "PYTHONDONTWRITEBYTECODE": "1"}
            try:
                subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(work),
                                f"--junitxml={xml}", "_hidden_tests"], cwd=work, env=env, capture_output=True,
                               timeout=self.timeout_s)
            except subprocess.TimeoutExpired:
                return {"score": 0.0, "detail": {"error": f"the hidden tests ran over {self.timeout_s} s"}}
            if not xml.exists():
                return {"score": 0.0, "detail": {"error": "pytest wrote no report"}}
            root = ET.parse(xml).getroot()
            suite = root if root.tag == "testsuite" else root.find("testsuite")
            total = int(suite.get("tests", 0))
            bad = int(suite.get("failures", 0)) + int(suite.get("errors", 0)) + int(suite.get("skipped", 0))
        passed = max(0, total - bad)
        return {"score": round(passed / total, 6) if total else 0.0,
                "detail": {"tests": total, "passed": passed}}


# box: frozen_judge
class FilesScorer:
    """D171: plain-code checks on the delivered files, from the key's `files` list; score = the share passed."""

    name = "files"

    def score(self, run_dir: Path, sim, seed: int, task=None) -> dict:
        checks = load_key(sim, task).get("files") or []
        if not checks:
            raise ValueError(f"the answer key of {task.id} has no files checks")
        files = delivered(run_dir)
        detail = [{**c, "ok": file_check(c, files)} for c in checks]
        return {"score": round(sum(d["ok"] for d in detail) / len(detail), 6), "detail": detail}


# box: frozen_judge
class RubricScorer:
    """D171: the fixed grader (judge.yaml rubric: model, temperature, calls) scores the answer against the key's
    rubric `calls` times; score = the median. The grader sees the task, the rubric and the answer only. A reply cut
    off by length before its SCORE line is asked once more with twice the room (counted in detail.retried)."""

    name = "rubric"

    def score(self, run_dir: Path, sim, seed: int, task=None) -> dict:
        cfg = judge_config()["rubric"]
        rubric = load_key(sim, task).get("rubric")
        if not rubric:
            raise ValueError(f"the answer key of {task.id} has no rubric")
        prompt = (ROOT / cfg["prompt"]).read_text(encoding="utf-8").split("\n", 1)[1]
        user = (prompt.replace("${task}", task.prompt).replace("${rubric}", rubric)
                .replace("${answer}", answer_of(run_dir)[:12000]))
        llm = grader_client(cfg)
        marks, raw, retried = [], [], 0
        for k in range(int(cfg["calls"])):
            ask = lambda room: llm.chat_messages([{"role": "user", "content": user}], seed=int(seed) + k,
                                                 max_tokens=room)
            resp = ask(int(cfg["max_tokens"]))
            if resp.finish_reason == "length" and not SCORE_LINE.search(resp.content or ""):
                resp, retried = ask(2 * int(cfg["max_tokens"])), retried + 1   # cut off before its SCORE line
            raw.append((resp.content or "")[-400:])
            marks.append(parse_mark(resp.content))
        return {"score": round(statistics.median(marks), 6),
                "detail": {"marks": marks, "replies": raw, "retried": retried},
                "grader": {"model": cfg["model"], "temperature": cfg["temperature"], "calls": len(marks)}}


SCORERS: dict[str, type] = {"standin": StandInScorer, "answer_key": AnswerKeyScorer,
                            "hidden_tests": HiddenTestsScorer, "files": FilesScorer, "rubric": RubricScorer}


# ---- helpers -----------------------------------------------------------------------------------------------------
# box: frozen_judge
def spec(sim):
    """A SimSpec from a SimSpec or a plain dict."""
    from amoeba.task.models import SimSpec
    return sim if isinstance(sim, SimSpec) else SimSpec.model_validate(sim)


# box: frozen_judge
def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


# box: frozen_judge
def answer_of(run_dir: Path) -> str:
    return str(json.loads((Path(run_dir) / "result.json").read_text(encoding="utf-8")).get("answer") or "")


# box: frozen_judge
def load_key(sim, task) -> dict:
    sim = spec(sim)
    if not sim.judge_set:
        raise ValueError("this scorer needs sim.judge_set (its keys are <judge_set>_keys/<task id>.json)")
    p = resolve(sim.folder("keys")) / f"{task.id}.json"
    if not p.exists():
        raise ValueError(f"no answer key for {task.id} in {sim.folder('keys')}")
    return json.loads(p.read_text(encoding="utf-8"))


# box: frozen_judge
def judge_config() -> dict:
    """amoeba/eval/judge.yaml: the rubric grader's fixed prompt, model, temperature, calls and reply room."""
    return yaml.safe_load((Path(__file__).parent / "judge.yaml").read_text(encoding="utf-8"))


# box: frozen_judge
def grader_client(cfg: dict):
    """The fixed grader: the models.yaml registry entry judge.yaml names, at its fixed temperature, built here and
    never shared with the team (its key comes from the environment only)."""
    from amoeba.llm.anthropic_client import make_client
    reg = (yaml.safe_load((ROOT / "amoeba" / "config" / "models.yaml").read_text(encoding="utf-8"))
           .get("registry") or {})[cfg["model"]]
    key = os.environ.get(reg["api_key_env"])
    if not key:
        raise ValueError(f"the rubric grader needs {reg['api_key_env']} in the environment")
    return make_client(reg.get("provider"), base_url=reg["base_url"], api_key=key, model=reg["model"],
                       max_tokens=int(cfg["max_tokens"]), merge_system=bool(reg.get("merge_system", True)),
                       temperature=float(cfg["temperature"]))


SCORE_LINE = re.compile(r"SCORE:\s*([01](?:\.\d+)?|\.\d+)", re.I)


# box: frozen_judge
def parse_mark(text: str | None) -> float:
    """The grader's last `SCORE: <0..1>` line (its reasoning may quote the format first); an unreadable reply
    scores 0."""
    m = ([None] + list(SCORE_LINE.finditer(text or "")))[-1]
    return min(1.0, max(0.0, float(m.group(1)))) if m else 0.0


# box: frozen_judge
def delivered(run_dir: Path) -> dict[str, Path]:
    """The team's delivered files (the workspace without sources/, skills/, made_tools/, inputs/), by relative path."""
    ws = Path(run_dir) / "workspace"
    if not ws.is_dir():
        return {}
    return {str(f.relative_to(ws)): f for f in sorted(ws.rglob("*"))
            if f.is_file() and f.relative_to(ws).parts[0] not in SKIP_DIRS}


# box: frozen_judge
def file_check(c: dict, files: dict[str, Path]) -> bool:
    """One files check: {check, path (a glob), min, max}."""
    hits = [p for rel, p in files.items() if fnmatch(rel, c["path"]) or fnmatch(Path(rel).name, c["path"])]
    if not hits:
        return False
    lo, hi = c.get("min"), c.get("max")
    within = lambda n: (lo is None or n >= lo) and (hi is None or n <= hi)
    kind = c["check"]
    try:
        if kind == "exists":
            return True
        if kind == "image":
            heads = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")
            return any(p.read_bytes()[:8].startswith(heads) for p in hits)
        if kind == "rows":
            return any(within(max(0, sum(1 for r in csv.reader(p.open(encoding="utf-8", newline="")) if r) - 1))
                       for p in hits)
        if kind == "formulas_live":
            import openpyxl
            for p in hits:
                wb = openpyxl.load_workbook(p, data_only=False)
                if sum(1 for ws in wb.worksheets for row in ws.iter_rows() for x in row
                       if isinstance(x.value, str) and x.value.startswith("=")) >= (lo or 1):
                    return True
            return False
        if kind == "pages":
            from pypdf import PdfReader
            return any(within(len(PdfReader(str(p)).pages)) for p in hits)
    except Exception:                         # an unreadable file fails its check
        return False
    raise ValueError(f"unknown files check {kind!r}")


# box: frozen_judge
def check_no_leak(task) -> None:
    """D171: a task's input files may not include its answer key or hidden tests (nor any tasks/*_keys or
    tasks/*_hidden file): ValueError otherwise."""
    sim = getattr(task, "sim", None)
    guarded = [resolve(x) for x in ((spec(sim).folder("keys"), spec(sim).folder("hidden")) if sim else ()) if x]
    guarded += [p for pat in ("tasks/*_keys", "tasks/*_hidden") for p in ROOT.glob(pat)]
    for f in getattr(task, "files", None) or []:
        fp = resolve(f).resolve()
        for g in guarded:
            if fp == g.resolve() or g.resolve() in fp.parents:
                raise ValueError(f"task {task.id}: input file {f} is inside its answer key or hidden tests ({g})")


# box: frozen_judge
def score_task(run_dir: str | Path, task, seed: int) -> dict:
    """The task's score: the weighted mean of its scorers' scores, each part kept."""
    sim = spec(task.sim)
    parts, total, weights = [], 0.0, 0.0
    for ref in sim.scorers:
        cls = SCORERS.get(ref.name)
        if cls is None:
            raise ValueError(f"unknown scorer {ref.name!r}; known: {sorted(SCORERS)}")
        got = cls().score(Path(run_dir), sim, seed, task=task)
        parts.append({"name": ref.name, "weight": ref.weight, **got})
        total += ref.weight * got["score"]
        weights += ref.weight
    s = round(total / weights, 6) if weights else 0.0
    base = float(sim.baseline)
    return {"score": s, "baseline": base, "delta": round(s - base, 6), "seed": int(seed),
            "scorer": parts[0]["name"] if len(parts) == 1 else "+".join(p["name"] for p in parts), "parts": parts}


# box: frozen_judge
def score_run(run_dir: str | Path, task, seed: int, judge: str) -> dict | None:
    """Score one finished run with its task's scorers and write sim_score.json; None when the task names none."""
    if not getattr(task, "sim", None):
        return None
    out = {**score_task(run_dir, task, seed), "judge_hash": judge}
    (Path(run_dir) / "sim_score.json").write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    return out
