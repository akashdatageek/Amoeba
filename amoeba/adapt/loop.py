"""D89 — the loop driver (Phase 2 spec §11): Monitor → Diagnoser → Architect → Experimenter → Gate → Memory over a
task stream. Resumable (D73): a practice run with a finished result is not run again, a decided hypothesis is not
re-tried, and the loop state is saved after every practice task.

    calibrate the noise floor for each family (current recipe, active held-out post slice)
    for each practice task, by order:
        run Boxes 1–3 with the family's current recipe (shifts apply: feedback rubrics, disabled tools)
        rollback watch (§9.3)
        alarm = monitor(family)                        Box 4 (none during dwell / cool-down)
        diagnosis = diagnose(alarm)                    Box 5
        up to 3 times: hypothesis = architect(...)     Box 6 (the only model call of the loop)
                       result = experiment(...)        Box 7
                       decision = gate(...)            Box 8 (v2)
                       accept → store.commit           Box 9; dwell
        no accept → unresolved (human_queue.jsonl); cool-down
    summary.json and REPORT.md

Practice orders ≤ parallel_until run as one batch before the loop looks at them (the recipe cannot change before an
alarm); the monitor still looks at them in order. Later tasks run one at a time, because each can trigger a change.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Callable

from pydantic import BaseModel, Field

from amoeba.adapt.architect import MAX_PER_ALARM, log_unresolved, propose
from amoeba.adapt.diagnoser import diagnose, diagnose_none
from amoeba.adapt.experimenter import Job, experiment
from amoeba.adapt.gate import alpha_for, cfg as gate_cfg, decide, decision_row, rollback_watch
from amoeba.adapt.ledger import Ledger
from amoeba.adapt.monitor import LoopState, PracticeRecord, monitor, practice_record
from amoeba.adapt.retention import prune_family, retention_alarm, retention_cfg, retention_check, retention_due
from amoeba.memory.context import propose_standards
from amoeba.adapt.recipe import apply_edit
from amoeba.adapt.stream import Stream, StreamTask
from amoeba.interp.trace import TraceWriter
from amoeba.memory.recipes import RecipeStore
from amoeba.adapt.evidence import EvidenceLog, GitShipper, Shipper, experiment_refs, make_shipper, run_finished


# box: loop
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# box: loop
class FamilyState(LoopState):
    watch: dict | None = None            # after an accept: {"accept_order", "alarm_mean", "noise", "version"}


# box: loop
class Loop(BaseModel):
    """The loop's state on disk (eval/loop/<stream>/loop_state.json)."""

    stream: str
    families: dict[str, FamilyState] = Field(default_factory=dict)
    processed: list[int] = Field(default_factory=list)        # practice orders whose alarm step is done
    events: list[dict] = Field(default_factory=list)          # alarms, hypotheses, decisions, reverts, unresolved
    unshipped: list[dict] = Field(default_factory=list)       # D95: runs and event rows not yet in the bucket
    ship_blocked: list[dict] = Field(default_factory=list)    # D95: runs the key scan stopped (never shipped)
    ship_state: dict = Field(default_factory=dict)            # D95: last evidence commit time, rows shipped, head


# box: loop
class LoopIO:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.state_file = self.root / "loop_state.json"
        self.practice_file = self.root / "practice.jsonl"

    def load(self, stream: Stream) -> Loop:
        if self.state_file.exists():
            return Loop.model_validate_json(self.state_file.read_text(encoding="utf-8"))
        return Loop(stream=stream.name, families={f: FamilyState(family=f) for f in stream.families()})

    def save(self, loop: Loop) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(loop.model_dump_json(indent=2), encoding="utf-8")

    def records(self) -> list[PracticeRecord]:
        if not self.practice_file.exists():
            return []
        return [PracticeRecord.model_validate_json(l) for l in self.practice_file.read_text(encoding="utf-8").splitlines()
                if l.strip()]

    def add(self, rec: PracticeRecord) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.practice_file, "a", encoding="utf-8") as fh:
            fh.write(rec.model_dump_json() + "\n")


# box: loop
def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in s)[:80]


# box: loop
def practice_jobs(tasks: list[StreamTask], stream: Stream, store: RecipeStore, root: Path) -> list[Job]:
    """One practice run per task with its family's current recipe (the store itself is the run's --recipes)."""
    jobs = []
    for t in tasks:
        v = store.current_or_seed(t.family).version
        jobs.append(Job(arm="P", task=t, k=0, seed=0, store=store.root, out=root / "practice" / f"{t.order:02d}-{t.id}",
                        namespace=_slug(f"{stream.name}-practice-{t.id}-v{v}"), disabled_tools=stream.disabled_tools(t)))
    return jobs


# box: loop, ov_around
def run_loop(stream: Stream, runner, root: str | Path, llm_for: Callable[[str], object], repeats: int = 3,
             parallel_until: int = 0, diagnoser: str = "tier0", envelope=None, calibrate: Callable | None = None,
             log: Callable[[str], None] = print, secrets: list[str] = (), upload: Callable | None = None,
             shipper=None, retention_every: int | None = None, prune: str | None = None) -> dict:
    """The loop over the stream's practice tasks. llm_for(hypothesis_id) gives the Architect's client; calibrate(
    stream, family, runner, root, store, repeats) -> calibration row (scripts/run_experiment.ensure_calibration).
    D95: every event goes to <root>/events.jsonl (hash-chained); each finished run is key-scanned against `secrets`
    and queued for the shipper (scripts/run_loop.py: the evidence branch, evidence.make_shipper; default: a queue that
    ships nothing, or `upload(local_path, object_name)`); what is not shipped stays in loop_state.json."""
    from scripts.run_experiment import ensure_calibration, sample_draft
    calibrate = calibrate or ensure_calibration
    rc = retention_cfg()                        # D100: --retention-every / --prune, else adapt.yaml `retention`
    retention_every = int(rc["every"] if retention_every is None else retention_every)
    prune = prune or rc["prune"]
    root = Path(root)
    io = LoopIO(root)
    store = RecipeStore(root / "recipes")
    ledger = Ledger(root / "ledger.jsonl")
    g = gate_cfg()
    loop = io.load(stream)
    ev = EvidenceLog(root)
    if shipper == "config":                     # scripts/run_loop.py: the configured shipper (the evidence branch)
        shipper = make_shipper(root, stream.name, secrets, loop.unshipped, loop.ship_state)
    shipper = None if shipper == "none" else shipper
    shipper = shipper or Shipper(root, upload, secrets, prefix=f"{stream.name}/", pending=loop.unshipped)
    if hasattr(runner, "on_done"):              # each finished run is key-scanned and queued as it finishes
        runner.on_done = lambda rec: rec.run_dir and run_finished(ev, root, Path(rec.run_dir), shipper)
    for fam in stream.families():
        store.ensure_seed(fam)
        loop.families.setdefault(fam, FamilyState(family=fam))
        if not loop.processed:                   # a fresh loop; a later recipe version is calibrated when first tested
            calibrate(stream, fam, runner, root, store.root, repeats)
    io.save(loop)
    done = {r.order: r for r in io.records()}

    def run_practice(tasks: list[StreamTask]) -> None:
        todo = [t for t in tasks if t.order not in done]
        for t, rec in zip(todo, runner.run(practice_jobs(todo, stream, store, root)) if todo else []):
            v = store.current_or_seed(t.family).version
            pr = practice_record(t, rec.run_dir, v) if rec.run_dir else \
                PracticeRecord(order=t.order, task_id=t.id, family=t.family, score=None, error=rec.error,
                               recipe_version=v)
            io.add(pr)
            done[t.order] = pr
            ev.append("practice_run", pr.model_dump(), [rec.run_dir] if rec.run_dir else [], key=f"practice:{t.order}")
            if rec.run_dir:
                run_finished(ev, root, Path(rec.run_dir), shipper)
            log(f"[practice] #{t.order} {t.id} v{v} score={pr.score} failed={pr.failed_items} error={pr.error}")
        if todo:
            ship()

    def ship(force: bool = False) -> None:
        shipper.queue_events()
        loop.unshipped = shipper.flush(force) if isinstance(shipper, GitShipper) else shipper.flush()
        loop.ship_state = dict(getattr(shipper, "state", {}) or {})
        loop.ship_blocked += [b for b in shipper.blocked if b not in loop.ship_blocked]
        shipper.blocked = []
        io.save(loop)

    practice = stream.practice()
    run_practice([t for t in practice if t.order <= parallel_until])
    for t in practice:
        run_practice([t])
        if t.order in loop.processed:
            continue
        st = loop.families[t.family]
        recs = [done[o] for o in sorted(done) if o <= t.order]
        for prop in propose_standards(recs, root, ev):    # D99: a proposal only; the user approves (approve_memory)
            log(f"[memory] proposal {prop['id']}: {prop['item']!r} failed in runs {prop['runs']} ({prop['families']})")
        _watch(st, recs, t, store, ledger, loop, log, ev)
        alarm = monitor(recs, st)
        if alarm is not None:
            loop.events.append({"ts": _now(), "event": "alarm", "order": t.order, **alarm.model_dump()})
            ev.append("alarm", {"order": t.order, **alarm.model_dump()}, key=f"alarm:{t.order}:{t.family}")
            log(f"[alarm] #{t.order} {alarm.kind}: {alarm.before:.3f} -> {alarm.after:.3f} {alarm.signals}")
            _handle(alarm, t, st, recs, stream, runner, root, store, ledger, loop, llm_for, repeats, diagnoser,
                    envelope, calibrate, sample_draft, g, log, ev)
            ship()
        count = retention_due(recs, t.family, retention_every)
        if count:                               # D100: replay the pre-shift gate tasks with the current recipe
            _retention(t, st, count, recs, stream, runner, root, store, ledger, loop, llm_for, repeats, diagnoser,
                       envelope, calibrate, sample_draft, g, log, ev)
            ship()
        loop.processed.append(t.order)
        io.save(loop)
    if prune == "end":                          # D100: each recipe line, removed one at a time, on the gate set
        for fam in stream.families():
            cal = calibrate(stream, fam, runner, root, store.root, repeats)
            for row in prune_family(stream, fam, store, ledger, runner, root, repeats, cal["noise"], ev, log,
                                    loop_gate_version()):
                if not any(e.get("hypothesis_id") == row["hypothesis_id"] for e in loop.events):
                    loop.events.append({"ts": _now(), "event": "prune", "family": fam, "line": row.get("line"),
                                        "hypothesis_id": row["hypothesis_id"], "decision": row["decision"]})
            io.save(loop)
    summary = write_summary(stream, root, io.records(), ledger, store, loop)
    ship(force=True)                            # the last batch goes out now
    return summary


# box: retention
def _retention(t, st, count, recs, stream, runner, root, store, ledger, loop, llm_for, repeats, diagnoser, envelope,
               calibrate, sample_draft, g, log, ev) -> None:
    """D100: one retention replay (once per family and count; resumable through the evidence key); a drop beyond
    noise is an alarm of cause `retention`, handled at once like any alarm."""
    key = f"retention:{t.family}:{count}"
    if ev.has(key):
        return
    cal = calibrate(stream, t.family, runner, root, store.root, repeats)
    row = retention_check(stream, t.family, store, runner, root, repeats, cal["noise"], count)
    with open(root / "retention.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": _now(), "order": t.order, **row}, ensure_ascii=False) + "\n")
    ev.append("retention", {"order": t.order, **row}, key=key)
    loop.events.append({"ts": _now(), "event": "retention", "order": t.order, **row})
    log(f"[retention] {t.family} after {count} practice tasks: {row.get('reference_mean')} -> {row.get('mean')} "
        f"{'ALARM' if row['alarm'] else row.get('skipped', 'ok')}")
    if row["alarm"]:
        alarm = retention_alarm(row, t.order)
        ev.append("alarm", {"order": t.order, **alarm.model_dump()}, key=f"alarm:{t.order}:{t.family}:retention")
        _handle(alarm, t, st, recs, stream, runner, root, store, ledger, loop, llm_for, repeats, diagnoser,
                envelope, calibrate, sample_draft, g, log, ev)


# box: loop
def _watch(st: FamilyState, recs: list[PracticeRecord], t: StreamTask, store: RecipeStore, ledger: Ledger,
           loop: Loop, log, ev: EvidenceLog | None = None) -> None:
    """§9.3 rollback watch over the practice tasks after an accept."""
    if not st.watch:
        return
    after = [r.score or 0.0 for r in recs if r.family == st.family and r.order > st.watch["accept_order"]]
    verdict = rollback_watch(after, st.watch["alarm_mean"], st.watch["noise"])
    if verdict == "watching":
        return
    window = int(gate_cfg()["rollback_window"])
    row = {"event": "reverted" if verdict == "reverted" else "kept", "family": st.family, "order": t.order,
           "version": st.watch["version"], "practice_mean": round(mean(after[:window]), 4),
           "alarm_mean": st.watch["alarm_mean"], "noise": st.watch["noise"]}
    if verdict == "reverted":
        back = store.revert(st.family, f"rollback watch: practice mean {row['practice_mean']} < alarm window mean "
                                       f"{st.watch['alarm_mean']} - noise {st.watch['noise']}")
        row["reverted_to"] = back.version
        ledger.append({**row, "gate_version": loop_gate_version()})
    loop.events.append({"ts": _now(), **row})
    if ev is not None:
        ev.append(row["event"], row, key=f"{row['event']}:{st.family}:{t.order}")
    log(f"[watch] {row}")
    st.watch = None


# box: loop
def loop_gate_version() -> str:
    return gate_cfg().get("version", "v2")


# box: loop
def _handle(alarm, t, st, recs, stream, runner, root, store, ledger, loop, llm_for, repeats, diagnoser, envelope,
            calibrate, sample_draft, g, log, ev=None) -> None:
    ev = ev or EvidenceLog(root)
    tag = "r" if alarm.kind == "retention" else ""   # D100: a retention alarm's hypotheses get their own ids
    diag = diagnose(alarm, recs, stream) if diagnoser != "none" else diagnose_none(alarm)
    ev.append("diagnosis", diag.model_dump(), key=f"diagnosis:{t.family}:{t.order}{tag}")
    (root / "diagnoses").mkdir(parents=True, exist_ok=True)
    (root / "diagnoses" / f"o{t.order:02d}{tag}-{t.family}.json").write_text(diag.model_dump_json(indent=2),
                                                                            encoding="utf-8")
    loop.events.append({"ts": _now(), "event": "diagnosis", "order": t.order, "family": t.family,
                        "cause": diag.cause, "symptom": diag.symptom, "allowed_edits": diag.allowed_edits})
    log(f"[diagnosis] {diag.cause}: {diag.symptom} -> {diag.allowed_edits}")
    heldout = stream.heldout(t.family, everything=True)
    tried, accepted = [], False
    for attempt in range(1, MAX_PER_ALARM + 1):
        hid = f"{stream.name}-{t.family}-o{t.order:02d}{tag}-h{attempt}"
        decided = [r for r in ledger.rows(t.family, "decision") if r.get("hypothesis_id") == hid and not r.get("post_hoc")]
        recipe = store.current_or_seed(t.family)
        if decided:                                    # resumed: this hypothesis was already decided
            row, tried = decided[-1], tried + [hid]
            if row["decision"] == "accept":
                accepted = True
                break
            continue
        quota = ledger.hypotheses_used(t.family) + 1 if loop_gate_version() == "v3" else None
        if quota is not None and alpha_for(quota) is None:      # D91: the family's fixed quota is spent
            qrow = ledger.append({"event": "quota_spent", "family": t.family, "order": t.order,
                                  "hypothesis_id": hid, "gate_version": "v3"})
            ev.append("quota_spent", qrow, key=f"quota_spent:{hid}")
            loop.events.append({"ts": _now(), "event": "quota_spent", "order": t.order, "family": t.family})
            log(f"[gate] {t.family}: hypothesis quota spent; no Architect call")
            tried.append("quota_spent")
            break
        cal = calibrate(stream, t.family, runner, root, store.root, repeats)
        arch_dir = root / "architect"
        arch_dir.mkdir(parents=True, exist_ok=True)
        saved = arch_dir / f"{hid}.json"
        if saved.exists() and json.loads(saved.read_text(encoding="utf-8")).get("hypothesis"):
            from amoeba.adapt.gate import Hypothesis
            h = Hypothesis.model_validate(json.loads(saved.read_text(encoding="utf-8"))["hypothesis"])
        else:
            trace = TraceWriter(arch_dir / f"{hid}.trace.jsonl", episode_id=hid)
            h, rec = propose(diag, recipe, ledger.failed(t.family), heldout, llm_for(hid), trace, hid, seed=attempt,
                             envelope=envelope)
            trace.close()
            saved.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
            ev.append("architect", rec, [saved, arch_dir / f"{hid}.trace.jsonl"], key=f"architect:{hid}")
        if h is None:
            nrow = ledger.append({"event": "no_hypothesis", "family": t.family, "hypothesis_id": hid,
                                  "order": t.order, "gate_version": loop_gate_version()})
            ev.append("no_hypothesis", nrow, key=f"no_hypothesis:{hid}")
            loop.events.append({"ts": _now(), "event": "no_hypothesis", "order": t.order, "hypothesis_id": hid})
            log(f"[architect] {hid}: no valid hypothesis after one retry")
            break
        log(f"[architect] {hid}: {h.edit.op} {json.dumps(h.edit.params)[:200]} predicted {h.predicted_delta:+.2f}")
        hrow = ledger.append({"event": "hypothesis", "family": t.family, "hypothesis_id": hid,
                              "recipe_from": recipe.version, "edit": h.edit.model_dump(),
                              "predicted_delta": h.predicted_delta, "rationale": h.rationale,
                              "created_by": "architect", "order": t.order, "diagnosis": diag.cause,
                              "gate_version": loop_gate_version()})
        ev.append("hypothesis", hrow, key=f"hypothesis:{hid}")
        res = experiment(recipe, h.edit, hid, stream, runner, root, repeats, created_by="architect")
        ev.append("experiment", res.model_dump(exclude={"pairs"}) | {"n_pairs": len(res.pairs)},
                  experiment_refs(root, root / "experiments" / hid), key=f"experiment:{hid}")
        recipe_B = apply_edit(recipe, h.edit, created_by="architect", hypothesis_id=hid)
        dec = decide(recipe, recipe_B, h, res, cal["noise"], ledger.tried_since_accept(t.family) + 1, heldout,
                     envelope, sample_draft(res), hypothesis_index=quota)
        row = ledger.append({**decision_row(h, recipe, recipe_B, dec, f"experiments/{hid}/"), "order": t.order})
        ev.append("decision", row, key=f"decision:{hid}")
        store.record(diag.model_dump(exclude={"examples"}), h.model_dump(mode="json"), row)
        tried.append(hid)
        loop.events.append({"ts": _now(), "event": "decision", "order": t.order, "hypothesis_id": hid,
                            "decision": dec.decision, "reasons": dec.reasons, "observed_delta": dec.observed_delta})
        log(f"[gate] {hid}: {dec.decision} d={dec.observed_delta:+.3f} {dec.reasons}")
        if dec.decision == "accept":
            store.commit(recipe_B, row)
            st.reference_from = t.order + 1
            st.quiet_until = t.order + int(g["dwell"])
            if alarm.kind != "retention":             # the rollback watch compares practice scores with the alarm's
                st.watch = {"accept_order": t.order, "alarm_mean": alarm.after, "noise": cal["noise"],
                            "version": recipe_B.version}
            accepted = True
            break
    if not accepted:
        row = log_unresolved(root, alarm.model_dump(), diag, tried)
        ev.append("human_queue", row, key=f"human_queue:{t.family}:{t.order}{tag}")
        ledger.append({"event": "unresolved", "family": t.family, "order": t.order, "hypotheses_tried": tried,
                       "gate_version": loop_gate_version()})
        loop.events.append({"ts": _now(), "event": "unresolved", "order": t.order, "hypotheses_tried": tried})
        st.quiet_until = t.order + int(g["cooldown"])
        log(f"[unresolved] #{t.order}: {tried}")


# ---- outputs -------------------------------------------------------------------------------------------------------
# box: loop
def write_summary(stream: Stream, root: Path, records: list[PracticeRecord], ledger: Ledger, store: RecipeStore,
                  loop: Loop) -> dict:
    """summary.json and a plain REPORT.md next to the ledger."""
    recs = sorted(records, key=lambda r: r.order)
    rows = ledger.rows()
    summary = {"stream": stream.name, "practice": [r.model_dump(include={"order", "task_id", "family", "score",
                                                                         "failed_items", "recipe_version", "error"})
                                                   for r in recs],
               "alarms": [e for e in loop.events if e["event"] == "alarm"],
               "decisions": [r for r in rows if r.get("event") == "decision" and not r.get("prune")],
               "prunes": [r for r in rows if r.get("event") == "decision" and r.get("prune")],     # D100
               "retention": [e for e in loop.events if e["event"] == "retention"],
               "unresolved": [r for r in rows if r.get("event") == "unresolved"],
               "reverts": [r for r in rows if r.get("event") == "reverted"],
               "recipes": store.index(),
               "prediction_accuracy": prediction_accuracy(rows)}
    (root / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Loop run on stream {stream.name}", "", "| order | task | phase | recipe | score | failed items |",
             "|---|---|---|---|---|---|"]
    phase = {t.id: t.phase for t in stream.practice()}
    for r in recs:
        lines.append(f"| {r.order} | {r.task_id} | {phase.get(r.task_id, '')} | v{r.recipe_version} | {r.score} | "
                     f"{', '.join(r.failed_items) or '—'} |")
    pa = summary["prediction_accuracy"]
    lines += ["", "## Prediction accuracy (reported, never a Gate rule: D91)", "",
              f"{pa['n']} decided hypotheses; sign right in {pa['sign_right']} "
              f"({pa['sign_share'] if pa['sign_share'] is not None else '—'}); mean absolute size error "
              f"{pa['mean_abs_error'] if pa['mean_abs_error'] is not None else '—'}.", ""]
    for r in pa["rows"]:
        lines.append(f"- {r['hypothesis_id']}: predicted {r['predicted']:+.3f}, observed {r['observed']:+.3f}, "
                     f"sign {'right' if r['sign_ok'] else 'wrong'}, error {r['abs_error']:.3f}")
    lines += ["", "## Events", ""]
    for e in loop.events:
        lines.append("- " + json.dumps({k: v for k, v in e.items() if k not in ("window", "reference_orders")},
                                       ensure_ascii=False)[:600])
    (root / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


# box: loop
def prediction_accuracy(rows: list[dict]) -> dict:
    """D91: how well the Architect's predicted_delta matched the observed gain (sign and size), over the stream's
    decided hypotheses (post-hoc rows and the pre-registered check left out)."""
    out = []
    for r in rows:
        if r.get("event") != "decision" or r.get("post_hoc") or r.get("check") or r.get("observed_delta") is None \
                or r.get("predicted_delta") is None:
            continue
        p, o = float(r["predicted_delta"]), float(r["observed_delta"])
        out.append({"hypothesis_id": r.get("hypothesis_id"), "predicted": p, "observed": o,
                    "sign_ok": (p > 0) - (p < 0) == (o > 0) - (o < 0), "abs_error": round(abs(p - o), 4)})
    n = len(out)
    right = sum(x["sign_ok"] for x in out)
    return {"n": n, "sign_right": right, "sign_share": round(right / n, 3) if n else None,
            "mean_abs_error": round(sum(x["abs_error"] for x in out) / n, 4) if n else None, "rows": out}
