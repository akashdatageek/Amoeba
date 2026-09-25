"""A readable Markdown transcript of Box 2 attempts from an eval_draft output folder (drafts/<task>.<n>.json).

    python -m scripts.draft_transcript runs/draft_eval/<name> --task db-choice [--out docs/real_runs/x.md]

Each round: the Planner's roles and plan, what each observer said (and, for d24, its verdict), then the three full
replies in collapsible blocks; after the rounds, the final plan plain code accepted, its draft_quality checks and
capability requests. d24 drafts also show requirements, givens, risks and each step's detail.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _roles_line(roles: list[dict]) -> str:
    return ", ".join(f"{r.get('name')} (tools: {', '.join(r.get('tools') or []) or 'none'})" for r in roles)


def _full(who: str, text: str) -> list[str]:
    return [f"<details><summary><b>{who}</b>: full reply</summary>", "", "````text", (text or "").strip(), "````", "",
            "</details>", ""]


def _step_detail(s: dict, indent: str = "   ") -> list[str]:
    out = []
    for k in ("covers", "depends_on", "do", "output", "done_when"):
        v = s.get(k)
        if v:
            v = ", ".join(map(str, v)) if isinstance(v, list) else str(v).replace("\n", " / ")
            out.append(f"{indent}- *{k}*: {v}")
    return out


def attempt_md(d: dict, n: int) -> list[str]:
    if "rounds" not in d or ("created_roles" not in d and "error" in d):
        head = [f"## Attempt {n}: failed ({d.get('error', 'unknown')})", ""]
    else:
        head = [f"## Attempt {n}: {d['rounds_used']} rounds, consensus: {'yes' if d['consensus'] else 'no'}", ""]
    out = ["---", ""] + head
    for r in d.get("rounds", []):
        out += [f"### Round {r['index']}", "", "**Planner roles:** " + _roles_line(r.get("roles", [])), "",
                "**Planner plan:**", ""]
        for i, s in enumerate(r.get("plan", [])):
            out += [f"{i + 1}. {s['text']}"] + _step_detail(s)
        reqs = [q.get("name") for q in r.get("capability_requests", [])]
        out += ["", f"**Capability requests this round:** {', '.join(reqs) or 'none'}", ""]
        out += _full("Planner", r.get("planner_raw", "")) + _full("Agent Observer", r.get("agent_observer_raw", "")) \
            + _full("Plan Observer", r.get("plan_observer_raw", ""))
        av, pv = r.get("agent_verdict"), r.get("plan_verdict")
        out += [f"**Agent Observer said:** {(r.get('agent_observer') or '').strip()}", ""]
        if av:
            out += [f"**Agent Observer verdict:** {av}", ""]
        out += [f"**Plan Observer said:** {(r.get('plan_observer') or '').strip()}", ""]
        if pv:
            out += [f"**Plan Observer verdict:** {pv}", ""]
        out += [f"**Consensus this round:** {'yes' if r.get('consensus') else 'no'}", ""]
    if "created_roles" not in d:
        return out
    out += [f"### Final plan accepted by plain code (attempt {n})", ""]
    if d.get("requirements"):
        out += ["**Requirements:**", ""] + [f"- {k}: {v}" for k, v in d["requirements"].items()] + [""]
    if d.get("givens"):
        out += ["**Givens and assumptions:**", ""] + [f"- {g}" for g in d["givens"]] + [""]
    if d.get("open_questions"):   # D53
        out += ["**Open questions (settled by assumption):**", ""] + [
            f"- {q['question']} — *assumed:* {q['assumption'] or '(none given)'}" for q in d["open_questions"]] + [""]
    out += ["| role | tools | missing tools | skills | covers | summariser |", "|---|---|---|---|---|---|"]
    out += [f"| {x['name']} | {', '.join(x['tools']) or 'none'} | {', '.join(x.get('missing_tools') or []) or ''} | "
            f"{'; '.join(x.get('skills') or [])} | {', '.join(x.get('covers') or [])} | {'yes' if x['is_summariser'] else ''} |"
            for x in d["created_roles"]]
    out += [""]
    for i, s in enumerate(d["plan"]):
        out += [f"{i + 1}. **{', '.join(s['agent_names'])}**: {s['text']}"] + _step_detail(s)
    out += ["", f"Capability requests: {', '.join(q['name'] for q in d['capability_requests']) or 'none'}", ""]
    if d.get("risks"):
        out += ["**Risks and decisions:**", ""] + [f"- {x}" for x in d["risks"]] + [""]
    q = d.get("quality") or {}
    if q:
        out += [f"**draft_quality:** {q['passed']} passed, {q['failed']} failed, {q['na']} n/a"
                + (f" (failed: {', '.join(q['failed_checks'])})" if q["failed_checks"] else ""), ""]
    return out


def transcript(folder: Path, task_id: str, title: str = "") -> str:
    tasks_dir = Path(__file__).resolve().parents[1] / "tasks"
    task = next((json.loads(l) for p in sorted(tasks_dir.glob("*.jsonl")) for l in p.read_text().splitlines()
                 if l.strip() and json.loads(l)["id"] == task_id), None)
    rows = [json.loads(l) for l in (folder / "attempts.jsonl").read_text().splitlines() if l.strip()]
    meta = next((r for r in rows if r["task_id"] == task_id), {})
    out = [f"# {title or 'Box 2 transcript'}: `{task_id}` ({meta.get('model', '?')}, prompts {meta.get('prompts', '?')})",
           "", f"Source: `{folder}/drafts/` ({sum(r['task_id'] == task_id for r in rows)} attempts). Each round shows "
           "the Planner's roles and plan, what each observer said, and the three full replies; the **final plan** "
           "is what plain code accepted.", ""]
    if task:
        out += ["**Task:** " + task["prompt"], ""]
    for p in sorted((folder / "drafts").glob(f"{task_id}.*.json"), key=lambda p: int(p.stem.rsplit(".", 1)[1])):
        out += attempt_md(json.loads(p.read_text()), int(p.stem.rsplit(".", 1)[1]) + 1)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder")
    p.add_argument("--task", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)
    text = transcript(Path(a.folder), a.task, a.title)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
