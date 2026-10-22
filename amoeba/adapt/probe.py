"""D154 — Box 4's scoped round: two scoped fix proposers, a probe of each edit from the same starting state, and a
plain-code pick.

The gate is unchanged: a step counts as recovered only when its own checks and contract say so. What the round adds:

1. Two proposers, each with a scope. INV (HOW THE TEAM WORKS: procedure, tool use, reading inputs, checking its own
   output, turns) and DOM (WHAT AN EXPERT WOULD KNOW: what the output must contain, domain rules, authoritative
   sources, what "done" means). Each is offered only its scope's edits that the cause allows; each must quote, in
   `because`, the evidence or last attempt it was shown.
2. A snapshot of everything an edit or a re-run can change (the step's agents, an added helper, done_when, run
   options, waived / provided items, counters, the step's artifact and files, the fault state, the workspace files).
3. A probe per candidate: apply the edit, re-run the step, compare its stuck signals with the stuck attempt's
   (cleared, kept, new), then undo everything, files included.
4. Plain code picks: a candidate that ends done (tie: fewer new signals, then fewer tokens); else a work-around that
   finished with limitation; else the candidate that cleared most (fewest new) becomes the base for the next rung, or
   the original state when neither cleared anything. The winner's probed state is put back; the step is not run a
   third time. No LLM composer, no merging of the two edits.

split_step and replan_remaining change the plan graph and are not probed: the other scope is probed first, and the
plan edit is applied only if that probe did not recover the step. A round counts as one try toward the fix limits;
tokens and dollars count per probe. Every probe is recorded with `samples: 1`: one probe proves nothing in general.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from pydantic import ValidationError

from amoeba.adapt.config import adapt_config
from amoeba.adapt.fixes import limits as fix_limits, token_cap
from amoeba.adapt.proposer import D_OPS_SCOPED, fix_problems, parse_fix, quote_found

INV_OPS = ("add_role_rule", "grant_tool", "add_tool_guidance", "add_watch_rule", "split_step")
DOM_OPS = ("add_role_rule", "add_helper_role", "work_around", "replan_remaining")
PLAN_OPS = ("split_step", "replan_remaining")
INV_FIRST = ("tool_error", "format", "max_turns", "claimed_file_missing")   # one probe left: INV for these, else DOM
SKIP_DIRS = ("skills", "sources", "made_tools")        # read-only or not the team's work: never undone


# box: proposer
def scope_config() -> dict:
    """adapt.yaml `proposer` (scoped, stop_on_first_done)."""
    return {"scoped": True, "stop_on_first_done": False, **(adapt_config().get("proposer") or {})}


# box: proposer
def fallback_reason(r) -> str | None:
    """Why a scoped round cannot run for this run (it falls back to single, logged): the workspace files of a probe
    cannot be undone reliably in the OpenShell sandbox (only in-process local tools are undone)."""
    loc = getattr(r, "local", None)
    if loc is None:
        return None
    mode = getattr(getattr(loc, "setup", None), "mode", None)
    if getattr(loc, "box", None) is not None or mode == "sandbox":
        return "the workspace of a probe cannot be undone in the sandbox (local tools not in-process)"
    return None


# ---- the snapshot ----------------------------------------------------------------------------------------------------
# box: proposer
class Snapshot:
    """Everything a proposer edit or a re-run of step n can change, so a probe can be undone (and its result put back
    for the winner)."""

    DICTS = ("step_opts", "waived", "provided", "done_when_kept", "tool_guidance", "watch_rules", "models_tried",
             "attached_ids", "proposer_gave_up", "ledger", "contract_results")

    def __init__(self, r, n: int):
        self.r, self.n = r, n
        self.agents = {aid: a.model_copy(deep=True) for aid, a in r.agents.items()}
        self.cfg_agents = list(r.cfg.agents)
        self.step = r.steps[n].model_copy(deep=True)
        self.dicts = {k: copy.deepcopy(getattr(r, k)) for k in self.DICTS if hasattr(r, k)}
        self.helpers_added = r.helpers_added
        self.fix_keys = set(r.fix_keys)
        self.workarounds = list(r.workarounds)
        self.artifact = copy.deepcopy(r.artifacts.get(n))
        self.faults = r.faults.snapshot() if hasattr(r.faults, "snapshot") else None
        self.faults_probe = (getattr(r, "fault_at_start", {}) or {}).get(n)   # the stuck attempt's starting faults
        self.step_files = {p.name: p.read_bytes() for p in step_files(r, n)}
        loc = getattr(r, "local", None)
        self.ws = workspace_files(loc)
        self.loc_files = copy.deepcopy(loc.files) if loc is not None else None
        self.loc_seen = dict(loc._seen) if loc is not None else None

    @classmethod
    def take(cls, r, n: int) -> "Snapshot":
        return cls(r, n)

    def restore(self, for_probe: bool = False) -> None:
        """Put the state back. for_probe: the faults go back to where they stood when the stuck attempt began, so
        every probe faces exactly the fault the stuck attempt faced."""
        r, n = self.r, self.n
        for aid in [a for a in r.agents if a not in self.agents]:          # a helper the probe added
            r.agents.pop(aid, None)
            r.cfg.agents.pop(aid, None)
        for aid, saved in self.agents.items():
            live = r.agents.get(aid)
            if live is None:
                r.agents[aid] = saved.model_copy(deep=True)
                continue
            for f in type(saved).model_fields:
                setattr(live, f, copy.deepcopy(getattr(saved, f)))
        for aid in self.cfg_agents:
            if aid in r.agents:
                r.cfg.agents[aid] = r.agents[aid]
        for f in type(self.step).model_fields:
            setattr(r.steps[n], f, copy.deepcopy(getattr(self.step, f)))
        for k, v in self.dicts.items():
            setattr(r, k, copy.deepcopy(v))
        r.helpers_added = self.helpers_added
        r.fix_keys = set(self.fix_keys)
        r.workarounds = list(self.workarounds)
        if self.artifact is None:
            r.artifacts.pop(n, None)
        else:
            r.artifacts[n] = copy.deepcopy(self.artifact)
        if self.faults is not None:
            r.faults.put_back(self.faults_probe if for_probe and self.faults_probe is not None else self.faults)
        for p in step_files(r, n):
            if p.name not in self.step_files:
                p.unlink()
        for name, data in self.step_files.items():
            (Path(r.dir) / name).write_bytes(data)
        loc = getattr(r, "local", None)
        if loc is not None:
            put_workspace(loc, self.ws)
            loc.files, loc._seen = copy.deepcopy(self.loc_files), dict(self.loc_seen)


# box: proposer
def step_files(r, n: int) -> list[Path]:
    """Step n's current attempt files (step_N.json / step_N.md), not the kept tries or probes."""
    d = getattr(r, "dir", None)
    return [p for p in (Path(d) / f"step_{n}.json", Path(d) / f"step_{n}.md") if p.exists()] if d else []


# box: proposer
def workspace_files(loc) -> dict[str, bytes]:
    """The team's files in the local workspace (not skills/, sources/, made_tools/), by relative path."""
    if loc is None or not loc.workspace.is_dir():
        return {}
    out = {}
    for f in loc.workspace.rglob("*"):
        rel = f.relative_to(loc.workspace)
        if f.is_file() and not f.is_symlink() and rel.parts[0] not in SKIP_DIRS:
            out[str(rel)] = f.read_bytes()
    return out


# box: proposer
def put_workspace(loc, saved: dict[str, bytes]) -> list[str]:
    """Undo a probe's file changes: files it added are deleted, files it changed or deleted are written back.
    Returns the paths that were touched."""
    now = workspace_files(loc)
    touched = []
    for rel in now:
        if rel not in saved:
            (loc.workspace / rel).unlink()
            touched.append(rel)
    for rel, data in saved.items():
        if now.get(rel) != data:
            p = loc.workspace / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            touched.append(rel)
    return touched


# ---- one round -------------------------------------------------------------------------------------------------------
# box: proposer
def signal_names(meta: dict | None) -> list[str]:
    """The stuck signals of an attempt (step_signals() as the watch stored them; none when the step is not stuck)."""
    st = (meta or {}).get("stuck") or {}
    return [s["signal"] for s in st.get("signals_detail") or []] or list(st.get("signals") or [])


# box: proposer
def probes_affordable(r, n: int, lim: dict) -> int:
    """How many probes the remaining allowance holds (2 or 1): each probe is estimated at one average step attempt
    (D151); the fixes' token allowance and the step's share of a run cap must hold that many."""
    avg = r.avg_attempt()
    if avg <= 0:
        return 2
    left = [token_cap(lim, avg) - r.adapt_tokens]
    share = (getattr(r, "step_share", {}) or {}).get(getattr(r, "cur_step", None))
    if share:
        left.append(share["share"] - (r.billed_now() - r.step_t0[r.cur_step]))
    return 2 if min(left) >= 2 * avg else 1


# box: proposer
def propose(r, n: int, d: dict, scope: str, allowed: list[str]) -> dict:
    """One scoped proposer: up to two calls (the second sees what plain code refused), the reply checked by the same
    rules as single mode (fix_problems, _d_live) plus the scope's own: its `because` quote must be in what it was
    shown. Returns {scope, reply, change, replies, refusals}; reply None means no candidate."""
    tools = r.i.tools.descriptions() if hasattr(r.i.tools, "descriptions") else {}
    roles = [r.agents[a].name for a in r.steps[n].agent_ids]
    held = {t for a in r.steps[n].agent_ids for t in r.agents[a].tools}
    tried_here = r.tried_kinds(n)
    refused, reply, change, replies = None, None, None, []
    for attempt in (1, 2):
        raw = r._proposer_call(n, d, allowed, refused, scope=scope)
        try:
            reply = parse_fix(raw, scoped=True)
            problems = fix_problems(reply, d["cause"], allowed, tools, r.fix_keys, roles, tried_here, step=n,
                                    held=held)
            if not quote_found(reply.because, r._proposer_shown):
                problems.append(f"because: the quote {reply.because[:80]!r} is not in the evidence or the last "
                                "attempt you were shown")
            if not problems and reply.edit.op in PLAN_OPS + ("add_helper_role",):
                problems, change = r._d_live(reply, n)
        except (ValueError, ValidationError) as e:
            reply, problems = None, [f"unreadable reply: {e}"[:400]]
        replies.append({"attempt": attempt, "op": reply.edit.op if reply else None, "problems": problems})
        r.i.trace.event("proposer_reply", {"amoeba.step": n, "amoeba.scope": scope, "amoeba.attempt": attempt,
                                           "amoeba.op": reply.edit.op if reply else None,
                                           "amoeba.problems": problems[:6]})
        if not problems:
            break
        refused, reply = problems, None
        if r.typed and replies[-1]["op"] is None:        # D141: ask() already made the repair call
            break
    return {"scope": scope, "reply": reply, "change": change, "replies": replies,
            "refusals": [p for x in replies for p in x["problems"]]}


# box: proposer
def probe(r, n: int, wave: int, cand: dict, start: Snapshot, s0: list[str]) -> dict:
    """Apply one candidate edit from the starting state, re-run step n, record what changed, keep the probe's files
    as step_N.probe-<scope>.*, take the probed state (for a winner) and undo everything."""
    from amoeba.interp.plan_runner import dependencies
    start.restore(for_probe=True)
    reply, scope = cand["reply"], cand["scope"]
    op, p = reply.edit.op, reply.edit.params
    t0 = r.billed_now()
    rec = {}
    note = r.apply_edit(n, op, p, cand["change"], rec)
    r.i.trace.event("fix_try", {"amoeba.step": n, "amoeba.cause": cand.get("cause"), "amoeba.fix": op,
                                "amoeba.rung": "D", "amoeba.scope": scope, "amoeba.target": n,
                                "amoeba.params": json.dumps(p, default=str)[:2000]})
    r.run_step(r.steps[n], wave, dependencies(r.cfg.plan)[n],
               fixing={"kind": op, "rung": "D", "target": n, "params": p, "note": note, "scope": scope})
    return measure(r, n, start, s0, t0, scope, op, p, {"because": reply.because, "reason": reply.reason},
                   rec, limited_ops=("work_around",))


# box: proposer
def measure(r, n: int, start: Snapshot, s0: list[str], t0: int, scope: str, op: str, p: dict, extra: dict,
            rec: dict, limited_ops: tuple = ()) -> dict:
    """After a probe's re-run: what changed (cleared, kept, new), the probed state for a winner, the probe's files
    kept as step_N.probe-<scope>.*, then everything undone."""
    meta = r.artifacts[n]["meta"]
    s1 = signal_names(meta)
    limited = op in limited_ops and not meta.get("stuck")
    after = Snapshot.take(r, n)
    now = workspace_files(getattr(r, "local", None))
    files = sorted(k for k in set(now) | set(start.ws) if now.get(k) != start.ws.get(k))
    for path in step_files(r, n):                        # keep the probe's attempt beside the tries
        path.rename(path.with_name(path.name.replace(f"step_{n}.", f"step_{n}.probe-{scope}.")))
    out = {"scope": scope, "op": op, "params": p, **extra,
           "status": meta["status"], "limited": limited, "tokens": r.billed_now() - t0, "turns": meta.get("turns"),
           "cleared": [x for x in s0 if x not in s1], "kept": [x for x in s0 if x in s1],
           "new": [x for x in s1 if x not in s0], "files_changed": files, "samples": 1,
           "text": (r.artifacts[n].get("text") or "")[:4000], **({"helper": rec["helper"]} if "helper" in rec else {})}
    start.restore()
    out["_after"] = after
    return out


# box: proposer
def scopes_for(allowed: list[str]) -> dict[str, list[str]]:
    """Each scope's edits: its own ∩ the edits the cause allows (after propose_fix's filters); an empty scope is not
    called."""
    out = {s: [a for a in ops if a in allowed] for s, ops in (("inv", INV_OPS), ("dom", DOM_OPS))}
    return {s: ops for s, ops in out.items() if ops}


# box: proposer
def round_flags(probes: list[dict]) -> dict:
    """complementary: the two probes cleared different signals; shared_failure: both failed with the same new
    signal."""
    out = {}
    if len(probes) == 2:
        a, b = (set(x["cleared"]) for x in probes)
        if a and b and a != b:
            out["complementary"] = True
        shared = set(probes[0]["new"]) & set(probes[1]["new"])
        if shared and all(x["status"] != "done" and not x["limited"] for x in probes):
            out["shared_failure"] = sorted(shared)[0]
    return out


# box: compose
def compose_config() -> dict:
    """adapt.yaml `compose` (D165): enabled, default false."""
    return {"enabled": False, **(adapt_config().get("compose") or {})}


# box: compose
def composable(cands: list[dict]) -> bool:
    """Two candidates and neither changes the plan graph (split_step and replan_remaining are never composed)."""
    return len(cands) == 2 and all(c["reply"].edit.op not in PLAN_OPS for c in cands)


# box: compose
def keep_composed(comp: dict, probes: list[dict]) -> bool:
    """The composed state is kept when it ends done, or clears more signals than either probe alone and adds none."""
    if comp["status"] == "done":
        return True
    return not comp["new"] and len(comp["cleared"]) > max((len(x["cleared"]) for x in probes), default=0)


# box: compose
def third_affordable(r, n: int, lim: dict) -> bool:
    """One more probe (estimated at one average step attempt, D151) fits the fixes' token allowance and the step's
    share of a run cap."""
    avg = r.avg_attempt()
    if avg <= 0:
        return True
    left = [token_cap(lim, avg) - r.adapt_tokens]
    share = (getattr(r, "step_share", {}) or {}).get(getattr(r, "cur_step", None))
    if share:
        left.append(share["share"] - (r.billed_now() - r.step_t0[r.cur_step]))
    return min(left) >= avg


# box: compose
def compose_probe(r, n: int, wave: int, cands: list[dict], start: Snapshot, s0: list[str]) -> dict:
    """D165: both edits applied from the same starting state, the step re-run once, measured and undone like a
    probe. Its record names the edits it combined (composed_of); D163 judges it confounded for both."""
    from amoeba.interp.plan_runner import dependencies
    start.restore(for_probe=True)
    t0, rec = r.billed_now(), {}
    parts = [{"scope": c["scope"], "op": c["reply"].edit.op, "params": c["reply"].edit.params} for c in cands]
    notes = [r.apply_edit(n, c["reply"].edit.op, c["reply"].edit.params, c["change"], rec) for c in cands]
    r.i.trace.event("fix_try", {"amoeba.step": n, "amoeba.cause": cands[0].get("cause"), "amoeba.fix": "compose",
                                "amoeba.rung": "D", "amoeba.scope": "compose", "amoeba.target": n,
                                "amoeba.params": json.dumps(parts, default=str)[:2000]})
    r.run_step(r.steps[n], wave, dependencies(r.cfg.plan)[n],
               fixing={"kind": "compose", "rung": "D", "target": n, "params": {"edits": parts},
                       "note": "; ".join(x for x in notes if x), "scope": "compose"})
    return measure(r, n, start, s0, t0, "compose", "compose", {"edits": parts},
                   {"composed_of": parts, "because": " | ".join(c["reply"].because for c in cands),
                    "reason": "the two edits together (D165)"}, rec, limited_ops=())


# box: proposer
def pick(probes: list[dict]) -> tuple[dict | None, str, dict | None]:
    """Plain code's pick: (winner or None, reason, base for the next rung or None)."""
    done = [x for x in probes if x["status"] == "done"]
    if done:
        w = min(done, key=lambda x: (len(x["new"]), x["tokens"]))
        why = "the only candidate that ends done" if len(done) == 1 else \
            "both end done: fewer new signals, then fewer tokens"
        return w, why, None
    lim = [x for x in probes if x["limited"]]
    if lim:
        return lim[0], "no candidate ends done; the work-around finished with limitation", None
    best = max(probes, key=lambda x: (len(x["cleared"]), -len(x["new"])), default=None)
    if best is not None and best["cleared"]:
        return None, "none recovered: the candidate that cleared most signals (fewest new) is the base", best
    return None, "none recovered and neither cleared a signal: the original state is kept", None


# box: proposer
def llm_pick(r, n: int, probes: list[dict]) -> str | None:
    """--fix-pick llm (ablation only): one call sees the task, the step's card and the two probe outputs as A and B,
    and picks one. Returns the scope picked, or None when the reply names neither."""
    from amoeba.config.prompts import PROMPT, render
    step = r.steps[n]
    card = "\n".join(x for x in (step.text, f"output: {step.output}", f"done_when: {step.done_when}") if x)
    user = render(PROMPT.fix_picker, task=r.task.prompt[:1500], card=card, a=probes[0]["text"][:3000],
                  b=probes[1]["text"][:3000])
    resp = r.i.llm.chat_messages([{"role": "user", "content": user}], r.ep.seed, agent_name="fix_picker",
                                 role="planner", max_tokens=200)
    m = re.search(r"PICK:\s*([AB])\b", resp.content or "", re.I)
    return probes["AB".index(m.group(1).upper())]["scope"] if m else None


# box: proposer
def scoped_round(r, n: int, wave: int, d: dict) -> str:
    """One scoped round for stuck step n (called by PlanRunner.propose_fix under --proposer scoped). Returns what
    propose_fix returns: "applied", "replanned" or "none"."""
    t0, sp0 = r.i.trace.total_tokens, len(r.i.trace.spans("chat"))
    lim, cfg = fix_limits(), scope_config()
    allowed = r.allowed_edits(n, d, D_OPS_SCOPED)
    scopes = scopes_for(allowed)
    if not scopes:
        r.proposer_gave_up[n] = f"fix proposer: no edit allowed for {d['cause']}"
        return "none"
    if len(scopes) == 2 and probes_affordable(r, n, lim) < 2:
        keep = "inv" if d["cause"] in INV_FIRST else "dom"
        scopes = {keep: scopes[keep]}
    s0 = signal_names(r.artifacts[n]["meta"]) or list(d.get("signals") or [])
    cands = [dict(propose(r, n, d, s, ops), cause=d["cause"]) for s, ops in scopes.items()]
    valid = [c for c in cands if c["reply"] is not None]
    rnd = {"step": n, "cause": d["cause"], "signals": s0, "scopes": list(scopes),
           "candidates": [{"scope": c["scope"], "op": c["reply"].edit.op if c["reply"] else None,
                           "params": c["reply"].edit.params if c["reply"] else {},
                           "because": c["reply"].because if c["reply"] else "", "refusals": c["refusals"]}
                          for c in cands], "probes": [], "pick": None, "pick_reason": "", "samples": 1}
    rec = {"step": n, "try": len(r.step_fixes(n)) + 1, "cause": d["cause"], "kind": "scoped_round", "rung": "D",
           "target": n, "params": {}, "evidence": d["evidence"][:4], "round": rnd,
           "proposer": [x for c in cands for x in c["replies"]]}
    for c in valid:
        r.fix_keys.add(c["reply"].edit.key(n))           # a candidate is never proposed again for this step
    if not valid:
        rec["kind"] = "fix_proposer"
        why = "fix proposer: no valid edit in two replies from either scope (" + "; ".join(
            f"{c['scope']}: {'; '.join(c['refusals'])[:200]}" for c in cands) + ")"
        r.proposer_gave_up[n] = why
        rec.update(status_after=r.artifacts[n]["meta"]["status"], result=f"failed: {why}")
        return finish(r, n, rec, rnd, t0, sp0, "none")
    plan = [c for c in valid if c["reply"].edit.op in PLAN_OPS]
    probeable = [c for c in valid if c["reply"].edit.op not in PLAN_OPS]
    start = Snapshot.take(r, n)
    for c in probeable:
        rnd["probes"].append(probe(r, n, wave, c, start, s0))
        if cfg.get("stop_on_first_done") and rnd["probes"][-1]["status"] == "done":
            break
    winner, why, base = pick(rnd["probes"]) if rnd["probes"] else (None, "", None)
    if getattr(r.opt, "fix_pick", "code") == "llm" and len(rnd["probes"]) == 2:    # the ablation arm
        chosen = llm_pick(r, n, rnd["probes"])
        picked = next((x for x in rnd["probes"] if x["scope"] == chosen), None)
        rnd["llm_pick"] = {"picked": chosen, "code_pick": winner["scope"] if winner else None,
                           "verdict": "done" if picked and picked["status"] == "done" else
                           (picked["status"] if picked else "no pick")}
        if picked is not None:
            winner, why = (picked, "picked by the LLM (ablation)") if picked["status"] == "done" or picked["limited"] \
                else (None, "picked by the LLM (ablation); its checks did not pass")
            base = None if winner else picked
    rnd.update(round_flags(rnd["probes"][:2]))
    if (winner is None and rnd.get("complementary") and compose_config().get("enabled") and composable(probeable)
            and third_affordable(r, n, lim)):                                        # D165
        comp = compose_probe(r, n, wave, probeable, start, s0)
        rnd["probes"].append(comp)
        if keep_composed(comp, rnd["probes"][:2]):
            winner, base = comp, None
            why = ("the two edits together end done" if comp["status"] == "done" else
                   "the two edits together clear more signals than either alone and add none")
    if winner is None and plan:                          # a plan edit only if the probes did not recover the step
        c = plan[0] if len(plan) == 1 else next((x for x in plan if x["scope"] == (
            "inv" if d["cause"] in INV_FIRST else "dom")), plan[0])
        rnd["pick"], rnd["pick_reason"] = c["scope"], (why + "; " if why else "") + \
            f"the plan edit {c['reply'].edit.op} is applied (not probed)"
        start.restore()
        r.artifacts.pop(n)
        r.keep_try(n)
        r.apply_decision({"reason": c["reply"].reason}, c["change"])
        rec.update(kind=c["reply"].edit.op, params=c["reply"].edit.params,
                   checks_carried=c["change"].get("checks_carried") or [], applied=c["reply"].edit.op,
                   replaced_by=sorted(s["number"] for s in c["change"]["steps"]), dropped=c["change"]["drop"],
                   result="applied: the plan changed; judged when its steps have run")
        return finish(r, n, rec, rnd, t0, sp0, "replanned")
    target = winner or base
    if target is not None:
        target["_after"].restore()
        for ext in ("json", "md"):                       # the winner's attempt is the step's current one
            src = Path(r.dir) / f"step_{n}.probe-{target['scope']}.{ext}" if getattr(r, "dir", None) else None
            if src is not None and src.exists():
                (Path(r.dir) / f"step_{n}.{ext}").write_bytes(src.read_bytes())
    rnd["pick"], rnd["pick_reason"] = (winner or {}).get("scope"), why
    rnd["base"] = base["scope"] if base else None
    m = r.artifacts[n]["meta"]
    rec["status_after"] = m["status"]
    if winner is not None:
        rec.update(kind=winner["op"], applied=winner["op"], params=winner["params"],
                   **({"helper": winner["helper"]} if winner.get("helper") else {}),
                   result="finished with limitation" if winner["op"] == "work_around" else "recovered")
        if winner["op"] == "work_around":
            r.workarounds.append({"step": n, **winner["params"]})
        for part in winner.get("composed_of") or []:                              # D165
            if part["op"] == "work_around":
                r.workarounds.append({"step": n, **part["params"]})
    else:
        if len(probes := rnd["probes"]) == 1:         # one edit was tried: the fix is of that kind (D150, D124 read it)
            rec.update(kind=probes[0]["op"], params=probes[0]["params"])
        rec["result"] = f"failed: {why}" + (f" (base: {base['scope']} {base['op']})" if base else "")
    return finish(r, n, rec, rnd, t0, sp0, "applied")


# box: proposer
def finish(r, n: int, rec: dict, rnd: dict, t0: int, sp0: int, outcome: str) -> str:
    """Record the round once: one fixes entry (one try toward the limits), the trace and one events.jsonl row."""
    for x in rnd["probes"]:
        x.pop("_after", None)
    r.i.trace.event("box4_round", {"amoeba.step": n, "amoeba.pick": rnd.get("pick"),
                                   "amoeba.reason": rnd.get("pick_reason"), "amoeba.probes": len(rnd["probes"])})
    r.log_event("box4_round", {k: v for k, v in rnd.items() if k != "probes"} |
                {"probes": [{k: v for k, v in x.items() if k != "text"} for x in rnd["probes"]]})
    from amoeba.adapt.rounds import round_row, write_round
    write_round(r, round_row(r, n, rnd, "scoped", outcome))                     # D162
    r._fix_done(rec, t0, sp0)
    return outcome
