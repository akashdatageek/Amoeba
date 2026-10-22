"""D166 — the outer loop, run by hand (never during a task): a lesson that kept helping becomes a general config
change, tested first on the replay set, and applied only by the user.

    python -m scripts.promote --list                                     # the candidates (plain-code trigger)
    python -m scripts.promote --replay tasks/general_example.jsonl [--entry ID] [--seeds 3] -- <run_task flags>
    python -m scripts.promote --apply promotions/<date>_<entry>.md       # the user applies an accepted change

1. **Trigger (plain code).** The entry is approved, helped >= promote.min_helped on >= promote.min_tasks different
   tasks, and hurt 0 in every niche; promoted or promotion_failed entries are never tried again.
2. **Proposal (one LLM call, prompts/promote.txt).** One change of the general surface in adapt.yaml:
   - the order of the cause's list in `diagnoser.allowed_edits`;
   - a `promoted.planner_rules` line (shown to the Planner and both observers);
   - a `promoted.tool_guidance` line for one tool (shown to every helper that holds it).

   Plain code refuses any other kind or file: Python, prompts, frozen.yaml or a file it lists. It also refuses a
   text over the cap or with denied wording, an unknown tool, and an order that is not today's edits reordered. It
   checks that the judge hash is the same before and after.
3. **Test.** Only the replay set (`set: replay`) runs, through `scripts/stage_e.py --arms config`.
   - The two arms are today's adapt.yaml and a temporary copy with the change. The live file is never touched.
   - Both arms use the same drafts, picks and sim seeds (`promote.seeds` per task) and `--lessons-write off`.
   - Every run must carry the same judge hash.
4. **Accept (plain code)** only if:
   - the mean sim-score delta (changed - current) is above 0;
   - no task's mean score drops by more than `promote.max_task_drop`;
   - the step-contract pass rate does not fall.
5. **Output.**
   - `promotions/<date>_<entry>.md` (plain words), plus `.json` and a `.patch`;
   - the entry's status becomes promoted or promotion_failed (a lesson is never deleted);
   - a `promotion` row in `promotions/events.jsonl`.

   **Nothing is applied**: `--apply <report>` writes the change to adapt.yaml, and only while that file is still the
   one the report was made from.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from amoeba.adapt.config import CONFIG, adapt_config
from amoeba.adapt.evidence import EvidenceLog
from amoeba.adapt.lessons import LessonLibrary
from amoeba.eval.judge import JudgeMismatch, frozen_paths, judge_hash, same_judge

ROOT = Path(__file__).resolve().parents[1]
CONFIG_REL = "amoeba/config/adapt.yaml"
KINDS = {"reorder_allowed_edits": {"kind", "cause", "order", "file"}, "planner_rule": {"kind", "text", "file"},
         "tool_guidance": {"kind", "tool", "text", "file"}}


# box: promote
def promote_config() -> dict:
    return {"min_helped": 3, "min_tasks": 2, "seeds": 3, "max_task_drop": 0.05, "max_text_chars": 300,
            "proposal_max_tokens": 1024, "dir": "promotions", **(adapt_config().get("promote") or {})}


# box: promote
def candidates(lib: LessonLibrary) -> list[dict]:
    """The plain-code trigger: an approved lesson that helped >= min_helped on >= min_tasks tasks and hurt 0 in every
    niche. D167: a lesson's own counts (its uses), never its family's."""
    c = promote_config()
    out = [e for e in lib.lessons() if e.get("status") == "approved" and (e.get("lesson") or "").strip()
           and e["counts"]["helped"] >= int(c["min_helped"]) and len(e.get("task_ids") or []) >= int(c["min_tasks"])
           and e["counts"]["hurt"] == 0 and not any((v or {}).get("hurt") for v in (e.get("by_niche") or {}).values())]
    return sorted(out, key=lambda e: (-e["counts"]["helped"], e["id"]))


# box: promote
def known_tools() -> list[str]:
    """The tools a guidance line may name: the registry's, the web tools and the local tools."""
    from amoeba.localtools.toolbox import load_local_config
    from amoeba.tools.registry import default_registry
    return sorted(set(default_registry().names()) | {"web_search", "fetch_url", "fetch_data"}
                  | {f"local:{t}" for t in load_local_config().get("allowed_tools", [])})


# box: promote
def change_problems(change: dict, cfg: dict, tools: list[str]) -> list[str]:
    """Why plain code refuses a proposed change ([] = it may be tested)."""
    if not isinstance(change, dict) or change.get("kind") not in KINDS:
        return [f"kind must be one of {sorted(KINDS)}"]
    out = []
    target = change.get("file", CONFIG_REL)
    frozen = frozen_paths()
    if target != CONFIG_REL:
        why = "a frozen judge file" if any(target == f or target.startswith(f.rstrip("/") + "/") for f in frozen) \
            else "code" if target.endswith(".py") else "a prompt" if "/prompts/" in target else "outside the surface"
        out.append(f"file: {target} is {why}; only {CONFIG_REL} may change" +
                   (" (frozen)" if why == "a frozen judge file" else ""))
    extra = set(change) - KINDS[change["kind"]]
    if extra:
        out.append(f"unknown keys {sorted(extra)}")
    lim = int(promote_config()["max_text_chars"])
    deny = (cfg.get("limits") or {}).get("denylist") or []
    if change["kind"] == "reorder_allowed_edits":
        today = ((cfg.get("diagnoser") or {}).get("allowed_edits") or {}).get(change.get("cause"))
        if today is None:
            out.append(f"cause {change.get('cause')!r} has no allowed_edits list")
        elif sorted(change.get("order") or []) != sorted(today) or len(change.get("order") or []) != len(today):
            out.append("order must hold exactly today's edits for the cause, reordered")
        elif list(change["order"]) == list(today):
            out.append("order is today's order: nothing changes")
    else:
        text = change.get("text")
        if not isinstance(text, str) or not text.strip():
            out.append("text: empty")
        else:
            if len(text) > lim:
                out.append(f"text: {len(text)} characters > {lim}")
            low = " ".join(text.lower().split())
            hits = [w for w in deny if re.search(r"(?<![a-z0-9])" + re.escape(w), low)]
            if hits:
                out.append(f"text: denied wording {hits}")
        if change["kind"] == "tool_guidance" and change.get("tool") not in tools:
            out.append(f"tool {change.get('tool')!r} does not exist")
    return out


# box: promote
def apply_change_text(text: str, change: dict) -> str:
    """The change written into adapt.yaml's text, keeping every comment; the result must still be valid YAML."""
    lines = text.splitlines(keepends=True)
    if change["kind"] == "reorder_allowed_edits":
        cause = change["cause"]
        fmt = lambda x: json.dumps(x) if ":" in x else x
        pat = re.compile(rf"^    {re.escape(cause)}: \[.*?\]", re.M | re.S)
        new, n = pat.subn(f"    {cause}: [" + ", ".join(fmt(x) for x in change["order"]) + "]", text, count=1)
        if n != 1:
            raise ValueError(f"no allowed_edits line for {cause}")
        out = new
    else:
        key = "planner_rules" if change["kind"] == "planner_rule" else "tool_guidance"
        item = f"    - {json.dumps(change['text'])}\n" if key == "planner_rules" else \
            f"    {json.dumps(change['tool'])}: {json.dumps(change['text'])}\n"
        start = next(i for i, l in enumerate(lines) if l.startswith("promoted:"))
        at = next(i for i in range(start + 1, len(lines)) if lines[i].startswith(f"  {key}:"))
        if lines[at].rstrip().endswith(("[]", "{}")):
            lines[at] = f"  {key}:\n"
            lines.insert(at + 1, item)
        else:
            end = at + 1
            while end < len(lines) and lines[end].startswith("    "):
                end += 1
            if key == "tool_guidance":
                lines = [l for k, l in enumerate(lines) if not (at < k < end and
                                                                l.startswith(f"    {json.dumps(change['tool'])}:"))]
                end = min(end, len(lines))
                while end > at + 1 and not lines[end - 1].startswith("    "):
                    end -= 1
            lines.insert(end, item)
        out = "".join(lines)
    yaml.safe_load(out)
    return out


# box: promote
def replay_ids(tasks: Path) -> list[str]:
    """The replay set's task ids (never the stream set, never an unmarked task)."""
    rows = [json.loads(l) for l in Path(tasks).read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r["id"] for r in rows if r.get("set") == "replay"]


# box: promote
def stage_e_runner(tasks, ids, seeds, out, config_b, passthrough) -> list[dict]:
    """The two config arms through scripts/stage_e.py (same drafts, picks and seeds; lesson writing off)."""
    from scripts.stage_e import CONFIG_ARMS, run_pairs
    return run_pairs(Path(tasks), list(ids), list(seeds), Path(out), list(passthrough), arms=CONFIG_ARMS,
                     lessons_write="off", config_b=str(config_b))


# box: promote
def contract_rate(run: Path) -> float | None:
    """The share of the run's steps whose step contract passed (D61), from artifacts/step_N.json; None without any."""
    metas = []
    for f in sorted((Path(run) / "artifacts").glob("step_*.json")):
        if re.fullmatch(r"step_\d+\.json", f.name):
            m = json.loads(f.read_text(encoding="utf-8"))
            metas.append(m.get("meta", m))
    with_contract = [m for m in metas if "contract" in m]
    if not with_contract:
        return None
    return sum(not m.get("contract_missing") for m in with_contract) / len(with_contract)


# box: promote
def summarise(rows: list[dict]) -> dict:
    """Per task: the arms' mean scores and the drop; overall: the mean delta and contract rates. JudgeMismatch when
    the runs were judged differently; ValueError when a run has no task score."""
    results, pairs = [], {}
    for x in rows:
        if not x.get("run"):
            raise ValueError(f"{x['task']} seed {x['seed']} {x['arm']}: the run left no folder")
        res = json.loads((Path(x["run"]) / "result.json").read_text(encoding="utf-8"))
        if (res.get("sim_score") or {}).get("score") is None:
            raise ValueError(f"{x['task']} seed {x['seed']} {x['arm']}: no task score (the task needs a `sim` scorer)")
        results.append(res)
        pairs.setdefault((x["task"], x["seed"]), {})[x["arm"]] = {"score": res["sim_score"]["score"],
                                                                  "contract": contract_rate(Path(x["run"]))}
    judge = same_judge(results)
    full = {k: v for k, v in pairs.items() if {"current", "changed"} <= set(v)}
    if not full:
        raise ValueError("no task has both arms")
    per_task = []
    for t in sorted({k[0] for k in full}):
        a = [v["current"]["score"] for k, v in full.items() if k[0] == t]
        b = [v["changed"]["score"] for k, v in full.items() if k[0] == t]
        per_task.append({"task": t, "seeds": len(a), "current": sum(a) / len(a), "changed": sum(b) / len(b),
                         "drop": sum(a) / len(a) - sum(b) / len(b)})
    deltas = [v["changed"]["score"] - v["current"]["score"] for v in full.values()]
    rate = lambda arm: [v[arm]["contract"] for v in full.values() if v[arm]["contract"] is not None]
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    return {"judge_hash": judge, "pairs": len(full), "mean_delta": mean(deltas), "per_task": per_task,
            "contract_current": mean(rate("current")), "contract_changed": mean(rate("changed"))}


# box: promote
def accept(summary: dict, cfg: dict) -> tuple[bool, str]:
    """The plain-code accept rule."""
    if summary["mean_delta"] is None or summary["mean_delta"] <= 0:
        return False, f"the mean score delta is {summary['mean_delta']:+.4f}, not above 0"
    worst = max(summary["per_task"], key=lambda t: t["drop"])
    if worst["drop"] > float(cfg["max_task_drop"]):
        return False, f"task {worst['task']} drops by {worst['drop']:.4f} > {cfg['max_task_drop']}"
    a, b = summary["contract_current"], summary["contract_changed"]
    if a is not None and (b is None or b < a):
        return False, f"the step-contract pass rate falls ({a:.3f} → {b if b is None else round(b, 3)})"
    return True, (f"the mean score rises by {summary['mean_delta']:+.4f}, no task drops more than "
                  f"{cfg['max_task_drop']}, and the step-contract pass rate does not fall")


# box: promote
def proposal_text(entry: dict, cfg: dict, tools: list[str]) -> str:
    from amoeba.config.prompts import PROMPT, render
    prom = cfg.get("promoted") or {}
    return render(PROMPT.promote, cause=entry["cause"], op=entry["op"], scope=entry["scope"],
                  helped=str(entry["counts"]["helped"]), tasks=str(len(entry["task_ids"])),
                  hurt=str(entry["counts"]["hurt"]), cue=entry.get("cue", ""), lesson=entry.get("lesson", ""),
                  order=json.dumps(((cfg.get("diagnoser") or {}).get("allowed_edits") or {}).get(entry["cause"])),
                  rules=json.dumps(prom.get("planner_rules") or []),
                  guidance=json.dumps(prom.get("tool_guidance") or {}), tools=", ".join(tools),
                  max_chars=str(promote_config()["max_text_chars"]))


# box: promote
def parse_change(raw: str) -> dict | None:
    text = (raw or "").strip()
    if re.fullmatch(r"[`\s]*NO_CHANGE[`.\s]*", text):
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object and no NO_CHANGE")
    return json.loads(m.group(0))


# box: promote
def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# box: promote
def promote(lib: LessonLibrary, entry_id: str, replay: Path, llm, out_dir: Path, config: Path = CONFIG,
            seeds: list[int] | None = None, runner=None, passthrough=(), tools: list[str] | None = None) -> dict:
    """One promotion attempt for one entry. Returns {decision: accepted | rejected | refused | no_change, why,
    report, patch, ...}; nothing is ever applied here."""
    from amoeba.interp.trace import TracedLLM, TraceWriter
    from amoeba.llm.limits import estimate
    pcfg = promote_config()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    name = f"{stamp}_{entry_id}"
    text = Path(config).read_text(encoding="utf-8")
    cfg = yaml.safe_load(text)
    tools = tools or known_tools()
    entry = lib.get(entry_id)
    rec = {"entry": entry_id, "at": stamp, "config": str(config), "config_sha": _sha(text)}

    def done(decision: str, why: str, **more) -> dict:
        rec.update(decision=decision, why=why, **more)
        if decision in ("accepted", "rejected"):
            lib.set_status(entry_id, "promoted" if decision == "accepted" else "promotion_failed")
        report = out_dir / f"{name}.md"
        rec["report"] = str(report)
        if rec.get("new_text"):
            patch = "".join(difflib.unified_diff(text.splitlines(keepends=True),
                                                 rec["new_text"].splitlines(keepends=True),
                                                 f"a/{CONFIG_REL}", f"b/{CONFIG_REL}"))
            (out_dir / f"{name}.patch").write_text(patch, encoding="utf-8")
            rec["patch"] = str(out_dir / f"{name}.patch")
        (out_dir / f"{name}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False, default=str),
                                              encoding="utf-8")
        report.write_text(report_text(rec, entry), encoding="utf-8")
        EvidenceLog(out_dir).append("promotion", {k: v for k, v in rec.items() if k != "new_text"})
        return rec

    if entry is None or entry_id not in {e["id"] for e in candidates(lib)}:
        return done("refused", "the entry is not a candidate (approved, helped often enough on enough tasks, "
                                "never hurt, not tried before)")
    judge0 = judge_hash()["sha256"]
    trace = TraceWriter(out_dir / f"{name}.trace.jsonl", episode_id=name)
    raw = TracedLLM(llm, trace).chat_messages([{"role": "user", "content": proposal_text(entry, cfg, tools)}],
                                             0, agent_name="promoter", role="planner",
                                             max_tokens=int(pcfg["proposal_max_tokens"])).content
    rec["proposal_cost"] = {"tokens": trace.total_tokens,
                            **estimate(trace.spans("chat"), getattr(llm, "model", "") or "")}
    trace.close()
    try:
        change = parse_change(raw)
    except (ValueError, json.JSONDecodeError) as e:
        return done("refused", f"the proposal is unreadable: {e}"[:300], raw=raw[:2000])
    if change is None:
        return done("no_change", "the proposer replied NO_CHANGE")
    rec["change"] = change
    problems = change_problems(change, cfg, tools)
    if problems:
        return done("refused", "; ".join(problems))
    rec["new_text"] = apply_change_text(text, change)
    tmp = out_dir / "configs" / f"{name}.yaml"                          # the changed arm's copy; never the live file
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(rec["new_text"], encoding="utf-8")
    if judge_hash()["sha256"] != judge0:
        return done("refused", "the judge hash changed while the change was written")
    ids = replay_ids(replay)
    if not ids:
        return done("refused", f"{replay} has no task with set: replay")
    seeds = list(seeds) if seeds is not None else list(range(int(pcfg["seeds"])))
    rows = (runner or stage_e_runner)(replay, ids, seeds, out_dir / "arms" / name, tmp, list(passthrough))
    try:
        summary = summarise(rows)
    except JudgeMismatch as e:
        return done("refused", f"the arms were scored by different judges: {e}")
    except ValueError as e:
        return done("refused", str(e))
    if summary["judge_hash"] != judge0:
        return done("refused", "the arms' judge differs from today's judge")
    ok, why = accept(summary, pcfg)
    return done("accepted" if ok else "rejected", why, arms=summary, seeds=seeds, replay=ids)


# box: promote
def report_text(rec: dict, entry: dict | None) -> str:
    c = (entry or {}).get("counts") or {}
    lines = [f"# Promotion of {rec['entry']}: {rec['decision']}", "",
             f"**Decision:** {rec['decision']} — {rec['why']}", "",
             f"**The lesson:** {(entry or {}).get('lesson', '')}", "",
             f"Helped {c.get('helped', 0)} times on {len((entry or {}).get('task_ids') or [])} tasks, hurt "
             f"{c.get('hurt', 0)} times (cause {(entry or {}).get('cause')}, edit {(entry or {}).get('op')}, "
             f"scope {(entry or {}).get('scope')}).", ""]
    if rec.get("change"):
        lines += ["**The proposed change** (adapt.yaml only):", "", "```json", json.dumps(rec["change"], indent=1),
                  "```", ""]
    if rec.get("arms"):
        a = rec["arms"]
        lines += ["**The test** (replay set only, both arms on the same drafts, picks and seeds, lesson writing off; "
                  f"judge {a['judge_hash'][:12]}):", "",
                  "| task | seeds | current | changed | drop |", "|---|---|---|---|---|",
                  *[f"| {t['task']} | {t['seeds']} | {t['current']:.4f} | {t['changed']:.4f} | {t['drop']:+.4f} |"
                    for t in a["per_task"]], "",
                  f"Mean delta {a['mean_delta']:+.4f} over {a['pairs']} pairs; step-contract pass rate "
                  f"{a['contract_current']} → {a['contract_changed']}.", ""]
    if rec["decision"] == "accepted":
        lines += ["**Nothing has been applied.** To apply it, run:", "",
                  f"    python -m scripts.promote --apply {rec['report']}", "",
                  f"The patch is {rec.get('patch')}."]
    return "\n".join(lines) + "\n"


# box: promote
def apply_report(report: str | Path, config: Path = CONFIG) -> dict:
    """The user applies an accepted change: refused unless the live file is still the one the report was made from."""
    rec = json.loads(Path(report).with_suffix(".json").read_text(encoding="utf-8"))
    if rec.get("decision") != "accepted":
        raise ValueError(f"the report's decision is {rec.get('decision')}: only an accepted change can be applied")
    live = Path(config).read_text(encoding="utf-8")
    if _sha(live) != rec["config_sha"]:
        raise ValueError(f"{config} changed since the report was made; promote again")
    Path(config).write_text(rec["new_text"], encoding="utf-8")
    EvidenceLog(Path(report).parent).append("promotion_applied", {"entry": rec["entry"], "report": str(report)})
    return rec


# box: promote
def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    passthrough = argv[argv.index("--") + 1:] if "--" in argv else []
    own = argv[:argv.index("--")] if "--" in argv else argv
    p = argparse.ArgumentParser(prog="python -m scripts.promote", description=__doc__.split("\n\n")[0])
    p.add_argument("--list", action="store_true", help="the candidates (plain-code trigger)")
    p.add_argument("--replay", help="a tasks file; only its set: replay tasks run")
    p.add_argument("--entry", help="the entry to try (default: the most-helped candidate)")
    p.add_argument("--seeds", type=int, default=None, help="sim seeds per task (default: promote.seeds)")
    p.add_argument("--lessons-dir", default=None, help="the lesson library (default: adapt.yaml lessons.library)")
    p.add_argument("--out", default=None, help="the reports folder (default: promote.dir)")
    p.add_argument("--apply", default=None, metavar="REPORT", help="apply an accepted report's change to adapt.yaml")
    a = p.parse_args(own)
    lib = LessonLibrary(a.lessons_dir)
    if a.apply:
        rec = apply_report(a.apply)
        print(f"applied {rec['entry']}: {json.dumps(rec['change'])} → {CONFIG_REL}")
        return 0
    cands = candidates(lib)
    if a.list or not a.replay:
        for e in cands:
            print(f"{e['id']:<48} helped {e['counts']['helped']} on {len(e['task_ids'])} tasks · {e['lesson'][:80]}")
        if not cands:
            print(f"no candidate in {lib.root}")
        return 0
    entry = a.entry or (cands[0]["id"] if cands else None)
    if entry is None:
        print("no candidate to promote")
        return 1
    from scripts.run_task import build_llm, parse_args
    llm = build_llm(parse_args(["promote", *passthrough]))
    out = promote(lib, entry, Path(a.replay), llm, Path(a.out or ROOT / promote_config()["dir"]),
                  seeds=list(range(a.seeds)) if a.seeds else None, passthrough=passthrough)
    print(f"== {out['decision']}: {out['why']}\n   report: {out['report']}")
    return 0 if out["decision"] in ("accepted", "rejected", "no_change") else 2


if __name__ == "__main__":
    raise SystemExit(main())
