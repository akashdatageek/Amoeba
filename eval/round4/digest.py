"""Rounds 3b and 4 — one digest per run for the observer to score C1–C6, plus the contract facts.

    python eval/round4/digest.py            # every run in eval/round4/ledger_*.jsonl → eval/round4/digests/, facts.json

Read-only on the run folders. For each run: the answer, every step's latest status with the reason, the step contract
(needs, attached items, what was left missing or unused), every tool call, every NOT NEEDED line as the helper wrote
it (from the logged model replies), the toolbox outcome per request, local calls and files, and the cost of the
contract's refine turns (calls whose prompt carries a refine note with a contract finding).
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CONTRACT_FINDING = re.compile(r"asked for .*? which this run could not provide|was given .*? for this step but|"
                              r"the team made these files but the answer|were cited from a source by a step but")
NN = re.compile(r"NOT\s+NEEDED\s*[:：].*", re.I)


def lines(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def messages(v) -> list[dict]:
    if isinstance(v, list):
        return v
    try:
        return ast.literal_eval(v)
    except Exception:
        try:
            return json.loads(v)
        except Exception:
            return []


def latest_steps(run: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((run / "artifacts").glob("step_*.json"),
                                                                      key=lambda p: int(re.findall(r"\d+", p.stem)[0]))
            if p.stem.count("_") == 1]


def changed_by_contract(m: dict) -> bool:
    """The step is not done only because of the contract: no declared gap, no failed check, no turn cap, no missing
    file — its only causes are an undeclared missing capability or an unused attached item."""
    if m.get("status") == "done" or "causes" not in m:
        return False
    declared = set(m.get("blocked", [])) - set(m.get("contract_missing", []))
    failed = [c for c in m.get("checks", []) if not c["pass"]]
    return not declared and not failed and set(m["causes"]) <= {"capability", "unused_tool"} and \
        bool(m.get("contract_missing") or m.get("unused"))


def digest(rec: dict) -> tuple[str, dict]:
    run = ROOT / rec["run"]
    res = json.loads((run / "result.json").read_text(encoding="utf-8"))
    trace = lines(run / "trace.jsonl")
    steps = latest_steps(run)
    chats = [t for t in trace if t["name"] == "chat"]
    # NOT NEEDED lines as written, and the contract refine turns' cost
    nn, contract_calls = [], {"calls": 0, "input": 0, "output": 0, "reasoning": 0, "pure_calls": 0}
    for c in chats:
        msgs = messages(c.get("gen_ai.input.messages", "[]"))
        user = next((m["content"] for m in reversed(msgs) if m.get("role") == "user"), "") if msgs else ""
        out = messages(c.get("gen_ai.output.messages", "[]"))
        text = "\n".join(m.get("content", "") for m in out if isinstance(m, dict))
        step = re.search(r"# Your step \(step (\d+)\)", user)
        for m in NN.finditer(text.split("## ActionInput")[-1] if "## ActionInput" in text else ""):
            nn.append({"step": int(step.group(1)) if step else None, "agent": c.get("gen_ai.agent.name"),
                       "line": m.group(0).strip()[:300]})
        note = user.split("Plain code checked this step's output and found:", 1)
        if len(note) == 2 and CONTRACT_FINDING.search(note[1].split("Fix exactly these")[0]):
            findings = note[1].split("Fix exactly these")[0]
            contract_calls["calls"] += 1
            contract_calls["input"] += int(c.get("gen_ai.usage.input_tokens") or 0)
            contract_calls["output"] += int(c.get("gen_ai.usage.output_tokens") or 0)
            contract_calls["reasoning"] += int(c.get("amoeba.usage.reasoning_tokens") or 0)
            items = [x for x in re.findall(r"^\d+\. (.+)$", findings, re.M)]
            if items and all(CONTRACT_FINDING.search(x) for x in items):
                contract_calls["pure_calls"] += 1
    # dedupe NOT NEEDED lines (a helper repeats its Final Output in later turns)
    seen, nn_u = set(), []
    for x in nn:
        k = (x["step"], x["agent"], x["line"])
        if k not in seen:
            seen.add(k)
            nn_u.append(x)
    ev = lambda n: [{k: v for k, v in t.items() if k.startswith("amoeba.") and k not in ("amoeba.profile", "amoeba.box")}
                    for t in trace if t["name"] == n]
    answer = res.get("answer") or ""
    facts = {"round": rec["round"], "repeat": rec["repeat"], "task": rec["task"], "run": rec["run"],
             "error": res.get("error"), "usage": res.get("usage"), "calls": res.get("n_llm_calls"),
             "refinement": res.get("refinement"), "summary_check": res.get("summary_check"),
             "blocked_capabilities": res.get("blocked_capabilities"), "provenance": res.get("provenance"),
             "files_created": res.get("files_created"), "local_tool_calls": res.get("local_tool_calls"),
             "local_refusals": res.get("local_refusals"),
             "requests": [{k: q.get(k) for k in ("name", "for_role", "status", "reason", "pool_id")}
                          for q in res.get("requested_capabilities", [])],
             "attached": (res.get("pool") or {}).get("attached"),
             "steps": [{k: m.get(k) for k in ("step", "roles", "status", "status_reason", "blocked", "contract_missing",
                                              "unused", "not_needed", "causes", "refine_reason", "verdict", "verification",
                                              "contract")}
                       | {"tool_calls": [(c["agent"], c["tool"], c["ok"], c["input"][:100]) for c in m.get("tool_calls", [])],
                          "files_made": [f["path"] for f in m.get("files_made", [])],
                          "failed_checks": [c["name"] for c in m.get("checks", []) if not c["pass"]],
                          "changed_by_contract": changed_by_contract(m),
                          "reworked": bool(m.get("rework_of"))} for m in steps],
             "not_needed_lines": nn_u, "contract_refine_cost": contract_calls,
             "rework": ev("rework"), "rework_skipped": ev("rework_skipped"), "limitations_added": ev("limitations_added"),
             "local_calls": [(t.get("amoeba.step"), t.get("gen_ai.tool.name"), t.get("amoeba.input"), t.get("amoeba.is_error"))
                             for t in trace if t["name"] == "local_call"],
             "local_refused": [(t.get("amoeba.step"), t.get("amoeba.reason"), t.get("amoeba.input"))
                               for t in trace if t["name"] == "local_refused"],
             "pool_calls": [(t.get("amoeba.step"), t.get("gen_ai.tool.name"), t.get("amoeba.source_id"), t.get("amoeba.is_error"))
                            for t in trace if t["name"] == "pool_call"],
             "web_calls": sum(1 for t in trace if t["name"] == "execute_tool" and t.get("gen_ai.tool.name") in
                              ("web_search", "fetch_url")),
             "answer_chars": len(answer)}
    md = [f"# {rec['round']} rep{rec['repeat']} {rec['task']} — {rec['run']}",
          f"error: {facts['error']} · calls {facts['calls']} · usage {facts['usage']}",
          f"requests: " + "; ".join(f"{q['name']}→{q['for_role']}: {q['status']} {q['reason']} {q['pool_id']}"
                                    for q in facts["requests"]),
          f"attached: {facts['attached']}",
          f"local calls: {facts['local_calls']}", f"local refused: {facts['local_refused']}",
          f"pool calls: {facts['pool_calls']} · web calls: {facts['web_calls']}",
          f"files_created: {facts['files_created']}",
          f"provenance: {facts['provenance']}", f"summary_check: {facts['summary_check']}",
          f"rework: {facts['rework']} · rework_skipped: {facts['rework_skipped']}",
          f"limitations_added: {facts['limitations_added']}",
          f"contract refine cost: {contract_calls}", "", "## Steps"]
    for s in facts["steps"]:
        md.append(f"- step {s['step']} {s['roles']}: **{s['status']}** ({s['status_reason']}) blocked={s['blocked']} "
                  f"missing={s['contract_missing']} unused={s['unused']} not_needed={s['not_needed']} "
                  f"causes={s['causes']} refine={s['refine_reason']} verdict={s['verdict']} "
                  f"failed={s['failed_checks']} changed_by_contract={s['changed_by_contract']} reworked={s['reworked']}"
                  f"\n  contract={s['contract']}\n  tools={s['tool_calls']} files={s['files_made']}")
    md += ["", "## NOT NEEDED lines"] + [f"- step {x['step']} {x['agent']}: {x['line']}" for x in nn_u]
    for m in steps:
        md += ["", f"## Step {m['step']} output (first 1500 chars)", (run / "artifacts" / f"step_{m['step']}.md")
               .read_text(encoding="utf-8")[:1500]]
    md += ["", "## Answer", answer]
    return "\n".join(md), facts


def main() -> None:
    out = HERE / "digests"
    out.mkdir(exist_ok=True)
    allf = []
    for led in sorted(HERE.glob("ledger_*.jsonl")):
        for rec in lines(led):
            if not rec.get("ok") or not rec.get("run"):
                continue
            md, facts = digest(rec)
            (out / f"{rec['round']}_rep{rec['repeat']}_{rec['task']}.md").write_text(md, encoding="utf-8")
            allf.append(facts)
    (HERE / "facts.json").write_text(json.dumps(allf, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"{len(allf)} run(s) digested")


if __name__ == "__main__":
    main()
