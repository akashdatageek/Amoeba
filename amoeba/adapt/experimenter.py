"""D83 — Box 7, the Experimenter (Phase 2 spec §8). Plain code; it calls no model itself — it runs Boxes 1–3 (which
do) on the family's held-out tasks, old recipe (arm A) against new (arm B), and returns the paired results.

    experiment(recipe_A, edit, ...) -> ReplayResult
      recipe_B = apply_edit(recipe_A, edit)
      for each held-out task of the family (post tasks first, then pre tasks for retention), for k in 0..repeats-1:
        arm A: a fresh draft with recipe A's rules (seed k), run with recipe A           — cached per recipe version
        arm B: a transform or run option edit → recipe B on arm A's saved draft (D45): the arms differ only by the edit
               a planner rule edit → a fresh draft with recipe B's rules (seed k): draft variance is part of the noise
        same seed, tools, model, time zone and limits in both arms

Arm A results are cached by (recipe A hash, task, k, seed) for the life of a recipe version, so a later hypothesis
against the same version runs arm B only. The calibration (A against A′ with other seeds, §9.1) fills the same cache.
Honesty flags per run: hallucinated citations + mislabelled citations + claimed files missing + unverified checks +
1 if the run ended in an error. Everything is written under eval/loop/<stream>/.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from amoeba.adapt.recipe import Edit, Recipe, adapt_config, apply_edit, write_store
from amoeba.adapt.stream import Stream, StreamTask, dump_task_line

RULE_OPS = ("add_planner_rule", "remove_planner_rule")
DRAFT_ROLES = ("interpreter", "planner", "agent_observer", "plan_observer")   # D98: a model preference for these
                                                                              # changes the draft itself


# box: experimenter
def changes_draft(op: str, params: dict | None = None) -> bool:
    """Arm B needs its own draft: the edit changes what Box 1/2 read or which model drafts."""
    return op in RULE_OPS or (op == "prefer_model" and (params or {}).get("role") in DRAFT_ROLES)
CALIBRATION_SEED_OFFSET = 1000          # arm A′ of the noise-floor calibration uses seed k + this
ROOT = Path(__file__).resolve().parents[2]


# box: exp_runners
@dataclass
class Job:
    """One run of Boxes 1–3 on one held-out task."""

    arm: str                       # "A", "A'" (calibration) or "B"
    task: StreamTask
    k: int                         # the repeat
    seed: int
    store: Path                    # the arm's recipe store (--recipes)
    out: Path                      # the folder that receives this run's folder (--runs-dir)
    namespace: str                 # LLM cache namespace: arms never share one; a crashed run resumes from it
    drafts_from: Path | None = None    # arm B of a transform / run-option edit: arm A's run folder (D45)
    disabled_tools: list[str] = field(default_factory=list)


# box: exp_runners
class RunRecord(BaseModel):
    arm: str
    task_id: str
    k: int
    seed: int
    run_dir: str = ""
    score: float | None = None
    tokens: int = 0
    usd: float = 0.0                                # D97: the router's estimated USD (0 without prices)
    honesty: float = 0.0
    refusals: int = 0
    error: str | None = None
    flags: dict = Field(default_factory=dict)       # D84b: honesty signals by kind (honesty_parts)

    def crashed(self) -> bool:
        """An error that is not the team's doing (model service, cache) — the run is redone once."""
        return not self.run_dir or str(self.error or "").startswith(("api:", "cache_miss", "runner:"))


# box: experimenter
class Pair(BaseModel):
    task_id: str
    phase: str
    k: int
    seed: int
    score_A: float
    score_B: float
    tokens_A: int
    tokens_B: int
    honesty_A: float
    honesty_B: float
    refusals_A: int = 0
    refusals_B: int = 0
    run_A: str = ""
    run_B: str = ""
    error_A: str | None = None
    error_B: str | None = None
    flags_A: dict = Field(default_factory=dict)     # D84b: honesty signals by kind, per arm
    flags_B: dict = Field(default_factory=dict)
    usd_A: float = 0.0                              # D97: the router's USD per run (0 without prices)
    usd_B: float = 0.0

    @property
    def d(self) -> float:
        return self.score_B - self.score_A


# box: experimenter
class ReplayResult(BaseModel):
    kind: str = "hypothesis"               # hypothesis | calibration
    hypothesis_id: str
    family: str
    recipe_from: int
    recipe_to: int | None
    recipe_A_hash: str
    recipe_B_hash: str | None = None
    edit: dict | None = None
    mode: str                              # same_draft (transform / run option) | own_draft (planner rule) | calibration
    pairs: list[Pair] = Field(default_factory=list)
    arm_a_cache_hits: int = 0
    runs: int = 0

    def post(self) -> list[Pair]:
        return [p for p in self.pairs if p.phase == "post"]

    def pre(self) -> list[Pair]:
        return [p for p in self.pairs if p.phase == "pre"]


# ---- what a run left behind ---------------------------------------------------------------------------------------
# box: exp_score
def honesty_parts(run_dir: str | Path) -> dict:
    """D84b: the honesty signals of one run, by kind (counts), and whether it ended in an error."""
    d = Path(run_dir)
    r = json.loads((d / "result.json").read_text(encoding="utf-8"))
    out = {"hallucinated_citations": int((r.get("provenance") or {}).get("total", {}).get("hallucinated_citations", 0)
                                         or 0),
           "mislabelled_citations": 0, "claimed_files_missing": 0, "unverified_checks": 0}
    for f in sorted((d / "artifacts").glob("step_*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out["mislabelled_citations"] += len(s.get("mislabelled_citations") or [])
        out["claimed_files_missing"] += len(s.get("claimed_files_missing") or [])
        out["unverified_checks"] += 1 if s.get("unverified_check") else 0
    out["error"] = 1 if r.get("error") else 0
    return out


# box: exp_score
def flagged(parts: dict) -> bool:
    """D84b (Gate v2 rule 5): a run is flagged when it has at least one honesty signal; an error is not one."""
    return any(parts.get(k, 0) for k in ("hallucinated_citations", "mislabelled_citations", "claimed_files_missing",
                                         "unverified_checks"))


# box: exp_score
def honesty_flags(run_dir: str | Path) -> float:
    """Gate v1: hallucinated citations + Σ mislabelled citations + Σ claimed files missing + unverified checks + 1 if
    error (kept for v1 rows and as information)."""
    return float(sum(honesty_parts(run_dir).values()))


DRAFT_AGENTS = {"planner", "agent_observer", "plan_observer", "interpreter"}


# box: exp_score
def draft_tokens(run_dir: str | Path) -> int:
    """Tokens a run spent in Box 2 (interpretation, Planner, both Observers), from its trace."""
    t = Path(run_dir) / "trace.jsonl"
    n = 0
    for line in (t.read_text(encoding="utf-8").splitlines() if t.exists() else []):
        if '"chat"' not in line:
            continue
        r = json.loads(line)
        if r.get("name") == "chat" and r.get("gen_ai.agent.name") in DRAFT_AGENTS:
            n += int(r.get("gen_ai.usage.input_tokens") or 0) + int(r.get("gen_ai.usage.output_tokens") or 0)
    return n


# box: exp_score
def refusals(r: dict) -> int:
    """Sandbox refusals (local tools) and side-effect refusals (pool vetting) in one run."""
    n = sum((r.get("local_refusals") or {}).values())
    n += sum(v for k, v in ((r.get("pool") or {}).get("reasons") or {}).items() if "side_effect" in k)
    return int(n)


# box: exp_score
def score_of(result: dict, task: StreamTask) -> float | None:
    """The run's score by the current D30 scorer, from its saved answer (a scorer fix applies to every run alike,
    including runs scored before it)."""
    if task.rubric is None:
        return result.get("score")
    from amoeba.task.evaluate import rubric_score
    return rubric_score(result.get("answer"), task.rubric)["score"]


# box: exp_runners
def record_of(job: Job, run_dir: Path | None, error: str | None = None) -> RunRecord:
    if run_dir is None or not (run_dir / "result.json").exists():
        return RunRecord(arm=job.arm, task_id=job.task.id, k=job.k, seed=job.seed, error=error or "runner: no result")
    r = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    return RunRecord(arm=job.arm, task_id=job.task.id, k=job.k, seed=job.seed, run_dir=str(run_dir),
                     score=score_of(r, job.task), tokens=int(r.get("total_tokens") or 0),
                     usd=float((r.get("routing") or {}).get("usd") or 0.0), honesty=honesty_flags(run_dir),
                     refusals=refusals(r), error=r.get("error"), flags=honesty_parts(run_dir))


# box: exp_runners
def finished_run(out: Path) -> Path | None:
    """D73 resume: the newest run folder under `out` that has a result.json and did not crash."""
    runs = sorted((p for p in out.glob("*/result.json")), key=lambda p: p.stat().st_mtime) if out.exists() else []
    for p in reversed(runs):
        err = str(json.loads(p.read_text(encoding="utf-8")).get("error") or "")
        if not err.startswith(("api:", "cache_miss")):
            return p.parent
    return None


# ---- runners --------------------------------------------------------------------------------------------------------
# box: exp_runners
class InProcessRunner:
    """Runs each job with run_one in this process, one after another (the mock-LLM tests). llm_for(job) gives the
    client; tools() a fresh Box 3 registry."""

    def __init__(self, llm_for: Callable[[Job], object], tools: Callable[[], object] | None = None, **run_kw):
        from amoeba.tools.registry import default_registry
        self.llm_for, self.tools, self.run_kw = llm_for, tools or default_registry, run_kw
        self.jobs: list[Job] = []

    def run(self, jobs: list[Job]) -> list[RunRecord]:
        from amoeba.adapt.recipe import load_recipe
        from amoeba.interp.plan_runner import PlanOptions
        from amoeba.safety.envelope import Envelope
        from amoeba.task.saved_drafts import load_saved_drafts, pick
        from scripts.run_task import disable_tools, run_one
        out = []
        for job in jobs:
            self.jobs.append(job)
            done = finished_run(job.out)
            if done is not None:
                out.append(record_of(job, done))
                continue
            tools, _, _ = disable_tools(job.disabled_tools, self.tools())
            saved = pick(load_saved_drafts(job.drafts_from), job.task.id, 0) if job.drafts_from else None
            kw = {"draft_prompts": "d24", "plan_options": PlanOptions(), **self.run_kw}
            r = run_one(job.task.as_task(), "plan", self.llm_for(job), Envelope.from_registry(tools), tools, job.out,
                        seed=job.seed, saved_draft=saved, recipe=load_recipe(job.store, job.task.family),
                        disabled_tools=job.disabled_tools, **kw)
            out.append(record_of(job, job.out / r.run_id))
        return out


# box: exp_runners
class SubprocessRunner:
    """Runs each job as `python -m scripts.run_task` (the bench runners' pattern), `parallel` at once; a run whose
    folder already holds a finished result is not run again (D73 resume), and a crash that is not the team's doing
    (model service, cache) is re-run once. `flags`: everything but the per-job ones (model, cache, plan options,
    limits, time zone); `env`: the environment with the keys (never printed)."""

    def __init__(self, flags: list[str], env: dict | None = None, parallel: int = 8, scratch: Path | None = None,
                 log: Callable[[str], None] = print):
        self.flags, self.env, self.parallel = list(flags), env, parallel
        self.scratch = Path(scratch or ROOT / "runs" / "adapt_jobs")
        self.log = log
        self.on_done: Callable[[RunRecord], None] | None = None   # D95: the harness ships each finished run

    def command(self, job: Job) -> list[str]:
        self.scratch.mkdir(parents=True, exist_ok=True)
        tf = self.scratch / f"{job.namespace}.jsonl"
        tf.write_text(dump_task_line(job.task) + "\n", encoding="utf-8")
        cmd = [sys.executable, "-m", "scripts.run_task", "--tasks", str(tf), "--topology", "plan",
               "--recipes", str(job.store), "--seed", str(job.seed), "--llm-cache-namespace", job.namespace,
               "--runs-dir", str(job.out), *self.flags]
        if job.drafts_from is not None:
            cmd += ["--drafts-from", str(job.drafts_from), "--draft-pick", "0"]
        if job.disabled_tools:
            cmd += ["--disable-tools", ",".join(job.disabled_tools)]
        return cmd

    def _one(self, job: Job) -> RunRecord:
        for attempt in (1, 2):
            done = finished_run(job.out)
            if done is not None:
                return record_of(job, done)
            job.out.mkdir(parents=True, exist_ok=True)
            t0 = time.time()
            with open(job.out / "run_task.log", "a", encoding="utf-8") as fh:
                rc = subprocess.run(self.command(job), cwd=ROOT, env=self.env or os.environ.copy(), stdout=fh,
                                    stderr=subprocess.STDOUT).returncode
            runs = sorted(job.out.glob("*/result.json"), key=lambda p: p.stat().st_mtime)
            rec = record_of(job, runs[-1].parent if runs else None, None if runs else f"runner: rc={rc}")
            self.log(f"[{job.arm}] {job.task.id} k{job.k} score={rec.score} tokens={rec.tokens} "
                     f"error={rec.error} {int(time.time() - t0)}s" + (" (re-run after a crash)" if attempt == 2 else ""))
            if not rec.crashed():
                break
        if self.on_done is not None:
            try:
                self.on_done(rec)
            except Exception as e:                    # shipping never stops a run
                self.log(f"[ship] {job.task.id} k{job.k}: {type(e).__name__}: {e}")
        return rec

    def run(self, jobs: list[Job]) -> list[RunRecord]:
        with ThreadPoolExecutor(max_workers=self.parallel) as ex:
            return list(ex.map(self._one, jobs))


# ---- the arm-A cache -------------------------------------------------------------------------------------------------
# box: exp_cache
class ArmACache:
    """Arm A (and A′) runs per recipe version: <root>/armA/<recipe hash>/<task>.k<k>.s<seed>/<run_id>/, and an index
    <root>/armA/<recipe hash>/index.jsonl of their records."""

    def __init__(self, root: Path, recipe: Recipe):
        self.dir = Path(root) / "armA" / recipe.hash()
        self.index = self.dir / "index.jsonl"

    def out(self, task_id: str, k: int, seed: int) -> Path:
        return self.dir / f"{task_id}.k{k}.s{seed}"

    def get(self, task: StreamTask, k: int, seed: int) -> RunRecord | None:
        if not self.index.exists():
            return None
        for line in reversed(self.index.read_text(encoding="utf-8").splitlines()):
            r = RunRecord.model_validate_json(line)
            if (r.task_id, r.k, r.seed) == (task.id, k, seed) and not r.crashed() and Path(r.run_dir).exists():
                res = json.loads((Path(r.run_dir) / "result.json").read_text(encoding="utf-8"))
                return r.model_copy(update={"score": score_of(res, task)})        # re-scored (see score_of)
        return None

    def put(self, rec: RunRecord) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.index, "a", encoding="utf-8") as fh:
            fh.write(rec.model_dump_json() + "\n")


# ---- the experiment --------------------------------------------------------------------------------------------------
# box: exp_runners
def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in s)[:80]


# box: exp_cache
def heldout_disabled(stream: Stream, task: StreamTask) -> list[str]:
    """A remove_tool shift is in effect for the family's held-out post tasks."""
    return [s.tool for s in stream.shifts if s.family == task.family and s.kind == "remove_tool"
            and task.phase == "post"]


# box: exp_cache
def _arm_a(stream: Stream, recipe_A: Recipe, root: Path, tasks: list[StreamTask], repeats: int, runner,
           seed_offset: int = 0, arm: str = "A") -> tuple[dict, int]:
    """Arm A (or A′) records per (task, k), from the cache or run now (one batch)."""
    cache = ArmACache(root, recipe_A)
    store = write_store(cache.dir / "recipes", [recipe_A])
    got, todo = {}, []
    for t in tasks:
        for k in range(repeats):
            seed = k + seed_offset
            hit = cache.get(t, k, seed)
            if hit is not None:
                got[(t.id, k)] = hit
            else:
                todo.append(Job(arm=arm, task=t, k=k, seed=seed, store=store, out=cache.out(t.id, k, seed),
                                namespace=_slug(f"{stream.name}-A-{recipe_A.hash()}-{t.id}-k{k}-s{seed}"),
                                disabled_tools=heldout_disabled(stream, t)))
    for rec in runner.run(todo) if todo else []:
        cache.put(rec)
        got[(rec.task_id, rec.k)] = rec
    return got, sum(1 for _ in got) - len(todo)


# box: experimenter
def _parts(run_dir: str) -> dict:
    return honesty_parts(run_dir) if run_dir and (Path(run_dir) / "result.json").exists() else {}


# box: experimenter
def _pair(t: StreamTask, k: int, a: RunRecord, b: RunRecord, shared_draft: bool = False) -> Pair:
    """shared_draft: arm B ran on arm A's saved draft, so A's drafting tokens count for B too (the cost comparison
    is per full run)."""
    extra = draft_tokens(a.run_dir) if shared_draft and a.run_dir else 0
    return Pair(task_id=t.id, phase=t.phase, k=k, seed=a.seed, score_A=a.score or 0.0, score_B=b.score or 0.0,
                tokens_A=a.tokens, tokens_B=b.tokens + extra, honesty_A=a.honesty, honesty_B=b.honesty,
                refusals_A=a.refusals, refusals_B=b.refusals, run_A=a.run_dir, run_B=b.run_dir,
                error_A=a.error, error_B=b.error, flags_A=a.flags or _parts(a.run_dir), flags_B=b.flags or _parts(b.run_dir),
                usd_A=a.usd, usd_B=b.usd)


# box: experimenter
def _rel(p: str) -> str:
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return p


# box: experimenter, ov_m7
def experiment(recipe_A: Recipe, edit: Edit, hypothesis_id: str, stream: Stream, runner, root: str | Path,
               repeats: int = 3, created_by: str = "human", slices: tuple[str, ...] = ("post", "pre")) -> ReplayResult:
    """Box 7: recipe A against recipe A + edit on the family's held-out tasks. Writes
    <root>/experiments/<hypothesis_id>/{experiment.json, pairs.jsonl, recipes_B/, runs/B/…}."""
    recipe_B = apply_edit(recipe_A, edit, created_by=created_by, hypothesis_id=hypothesis_id)
    return replay(recipe_A, recipe_B, hypothesis_id, stream, runner, root, repeats,
                  not changes_draft(edit.op, edit.params), edit.model_dump(), slices)


# box: experimenter
def replay(recipe_A: Recipe, recipe_B: Recipe, hypothesis_id: str, stream: Stream, runner, root: str | Path,
           repeats: int, same_draft: bool, edit: dict | None = None,
           slices: tuple[str, ...] = ("post", "pre")) -> ReplayResult:
    """Recipe A against any recipe B on the family's held-out tasks (an edit, or D100's prune: A minus one line).
    same_draft: arm B reuses arm A's saved draft (B changes nothing the Planner reads)."""
    root = Path(root)
    tasks = [t for ph in slices for t in stream.heldout(recipe_A.family, ph)]
    exp = root / "experiments" / hypothesis_id
    store_B = write_store(exp / "recipes_B", [recipe_B])
    a, hits = _arm_a(stream, recipe_A, root, tasks, repeats, runner)
    jobs = []
    for t in tasks:
        for k in range(repeats):
            ra = a[(t.id, k)]
            jobs.append(Job(arm="B", task=t, k=k, seed=ra.seed, store=store_B, out=exp / "runs" / "B" / f"{t.id}.k{k}",
                            namespace=_slug(f"{stream.name}-{hypothesis_id}-B-{t.id}-k{k}"),
                            drafts_from=Path(ra.run_dir) if same_draft and ra.run_dir else None,
                            disabled_tools=heldout_disabled(stream, t)))
    b = {(r.task_id, r.k): r for r in runner.run(jobs)}
    res = ReplayResult(hypothesis_id=hypothesis_id, family=recipe_A.family, recipe_from=recipe_A.version,
                       recipe_to=recipe_B.version, recipe_A_hash=recipe_A.hash(), recipe_B_hash=recipe_B.hash(),
                       edit=edit, mode="same_draft" if same_draft else "own_draft",
                       pairs=[_pair(t, k, a[(t.id, k)], b[(t.id, k)], same_draft) for t in tasks for k in range(repeats)],
                       arm_a_cache_hits=hits, runs=len(jobs) + (len(tasks) * repeats - hits))
    write_result(exp, res)
    return res


# box: exp_calib
def calibrate(recipe_A: Recipe, stream: Stream, runner, root: str | Path, repeats: int = 3) -> ReplayResult:
    """§9.1 runs: recipe A against itself (A vs A′, A′ with seeds k + 1000) on the family's held-out post slice.
    Both arms land in the arm-A cache; arm A (seeds 0..repeats-1) is what later hypotheses reuse."""
    root = Path(root)
    tasks = stream.heldout(recipe_A.family, "post")
    a, hits = _arm_a(stream, recipe_A, root, tasks, repeats, runner)
    a2, hits2 = _arm_a(stream, recipe_A, root, tasks, repeats, runner, seed_offset=CALIBRATION_SEED_OFFSET, arm="A'")
    res = ReplayResult(kind="calibration", hypothesis_id=f"calibration-{recipe_A.family}-v{recipe_A.version}",
                       family=recipe_A.family, recipe_from=recipe_A.version, recipe_to=None,
                       recipe_A_hash=recipe_A.hash(), mode="calibration",
                       pairs=[_pair(t, k, a[(t.id, k)], a2[(t.id, k)]) for t in tasks for k in range(repeats)],
                       arm_a_cache_hits=hits + hits2, runs=2 * len(tasks) * repeats - hits - hits2)
    write_result(root / "experiments" / res.hypothesis_id, res)
    return res


# box: experimenter
def write_result(folder: Path, res: ReplayResult) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    rel = res.model_copy(update={"pairs": [p.model_copy(update={"run_A": _rel(p.run_A), "run_B": _rel(p.run_B)})
                                           for p in res.pairs]})
    (folder / "pairs.jsonl").write_text("".join(p.model_dump_json() + "\n" for p in rel.pairs), encoding="utf-8")
    (folder / "experiment.json").write_text(rel.model_dump_json(indent=2, exclude={"pairs"}), encoding="utf-8")


# box: exp_runners
def experiment_flags() -> list[str]:
    """The run_task flags every experiment run gets (amoeba/config/adapt.yaml experiment.run_flags)."""
    return [str(x) for x in adapt_config().get("experiment", {}).get("run_flags", [])]
