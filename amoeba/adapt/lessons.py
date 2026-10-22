"""D163 — verdicts, the reflector and the lesson library (spec/BUILD_SPEC_BOX4_RSI.md, stage 2).

Plain code gives every edit of a Box 4 round (D162's row) one verdict:

    composed (only tried together with another edit, D165)  -> confounded
    the probe ended done, or finished with limitation       -> helped
    it cleared a signal and added a new one                 -> confounded
    it cleared a signal and added none                      -> helped
    it added a new signal and cleared none                  -> hurt
    nothing cleared, nothing new (and not done)             -> no_effect

Every verdict updates the library's counts, `hurt` included. When an edit helped, one LLM call (the reflector,
prompts/reflector.txt) may write a lesson for it: a cue (the shape of the situation, with no task facts) and the
lesson (the operation, naming the op and the scope). Plain code refuses a lesson over the character cap, with denied
wording, or with a number or proper noun from the task prompt; a refused lesson is asked for once more, then dropped.

The library (`adapt.yaml lessons.library`, data/lessons/) is one for every task: entries are keyed by
(cause, op, scope). The niche of each count is recorded (`by_niche`), never used to split. `index.jsonl` holds one
row per entry; each entry's folder holds `edit.json` (the op and the params that helped), `evidence.jsonl` (one line
per verdict: run, task, niche, verdict, the probe's signals) and `EXPERIENCE.md` (the cue, the lesson and the evidence
for a person to read). New entries are `unreviewed`; only the user approves one (scripts/lessons.py). Writes take a
file lock and replace files atomically, so runs may write at once.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from amoeba.adapt.config import adapt_config

ROOT = Path(__file__).resolve().parents[2]
VERDICTS = ("helped", "hurt", "no_effect", "confounded")
STATUSES = ("unreviewed", "approved", "rejected", "promoted", "promotion_failed")
WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*|\d[\d.,]*")


# box: lessons
def lessons_config() -> dict:
    """adapt.yaml `lessons` with its defaults."""
    return {"library": "data/lessons", "max_chars": 300, "reflector_max_tokens": 1024, "lock_timeout_s": 30,
            "max_entries": 5, "max_section_chars": 1500, "evidence_kept": 20,
            **(adapt_config().get("lessons") or {})}


# box: lessons
def verdict(probe: dict) -> str:
    """The plain-code verdict of one probe (see the module docstring)."""
    if probe.get("composed_of"):
        return "confounded"
    if probe.get("status") == "done" or probe.get("limited"):
        return "helped"
    cleared, new = bool(probe.get("cleared")), bool(probe.get("new"))
    if cleared and new:
        return "confounded"
    if cleared:
        return "helped"
    if new:
        return "hurt"
    return "no_effect"


# box: lessons
def key_of(cause: str, op: str, scope: str) -> str:
    """The entry id of (cause, op, scope)."""
    return "__".join(re.sub(r"[^\w-]+", "_", x or "none") for x in (cause, op, scope))


# box: lessons
def round_verdicts(row: dict) -> list[dict]:
    """[{id, cause, op, scope, verdict, probe}] for every probe of a D162 round row; a composed probe gives a
    confounded verdict to each edit it combined."""
    out = []
    for p in row.get("probes") or []:
        parts = p.get("composed_of") or [{"scope": p["scope"], "op": p["op"], "params": p.get("params") or {}}]
        v = verdict(p)
        for part in parts:
            out.append({"id": key_of(row["cause"], part["op"], part["scope"]), "cause": row["cause"],
                        "op": part["op"], "scope": part["scope"], "params": part.get("params") or {}, "verdict": v,
                        "probe": {k: p.get(k) for k in ("status", "cleared", "kept", "new", "tokens", "samples")}})
    return out


# box: lessons
def task_facts(task_prompt: str) -> tuple[set[str], set[str]]:
    """The numbers and the proper nouns of a task prompt (a capitalised word not at a sentence start)."""
    numbers = {m.group(0).rstrip(".,") for m in re.finditer(r"\d[\d.,]*", task_prompt or "")}
    nouns = set()
    for sent in re.split(r"(?<=[.!?:])\s+|\n+", task_prompt or ""):
        words = WORD.findall(sent)
        nouns |= {w for w in words[1:] if w[0].isupper() and len(w) > 1}
    return {n for n in numbers if n}, nouns


# box: lessons
def lesson_problems(cue: str, lesson: str, task_prompt: str, cfg: dict | None = None) -> list[str]:
    """Why plain code refuses a lesson ([] = accepted): over the cap, denied wording, or a task fact in it."""
    cfg = cfg or lessons_config()
    deny = (adapt_config().get("limits") or {}).get("denylist") or []
    out = []
    for where, text in (("cue", cue), ("lesson", lesson)):
        if not (text or "").strip():
            out.append(f"{where}: empty")
            continue
        if len(text) > int(cfg["max_chars"]):
            out.append(f"{where}: {len(text)} characters > {cfg['max_chars']}")
        low = " ".join(text.lower().split())
        hits = [w for w in deny if re.search(r"(?<![a-z0-9])" + re.escape(w), low)]
        if hits:
            out.append(f"{where}: denied wording {hits}")
        numbers, nouns = task_facts(task_prompt)
        words = set(WORD.findall(text))
        facts = sorted((words & nouns) | {w.rstrip(".,") for w in words if w[0].isdigit()} & numbers)
        if facts:
            out.append(f"{where}: names facts of this task {facts}; describe the shape of the situation instead")
    return out


# box: lessons
class LessonLibrary:
    """data/lessons/: index.jsonl (one row per (cause, op, scope)) and one folder per entry. Safe for several
    writers: every change holds an exclusive file lock and replaces files atomically."""

    def __init__(self, root: str | Path | None = None):
        cfg = lessons_config()
        self.root = Path(root) if root is not None else ROOT / cfg["library"]
        self.timeout = float(cfg["lock_timeout_s"])
        self.kept = int(cfg["evidence_kept"])

    # ---- storage -----------------------------------------------------------------------------------------------
    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / ".lock", "a+") as fh:
            t0 = time.monotonic()
            while True:
                try:
                    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() - t0 > self.timeout:
                        raise TimeoutError(f"the lesson library {self.root} stayed locked for {self.timeout} s")
                    time.sleep(0.02)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def _write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)

    def _rows(self) -> dict[str, dict]:
        p = self.root / "index.jsonl"
        rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
        return {r["id"]: r for r in rows}

    def _save(self, rows: dict[str, dict]) -> None:
        self._write(self.root / "index.jsonl",
                    "".join(json.dumps(rows[k], ensure_ascii=False) + "\n" for k in sorted(rows)))

    # ---- reading -----------------------------------------------------------------------------------------------
    def entries(self) -> list[dict]:
        return list(self._rows().values())

    def get(self, entry_id: str) -> dict | None:
        return self._rows().get(entry_id)

    def evidence(self, entry_id: str) -> list[dict]:
        p = self.root / entry_id / "evidence.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []

    # ---- writing -----------------------------------------------------------------------------------------------
    def record(self, v: dict, niche: str, task_id: str, run_id: str) -> dict:
        """Count one verdict (D163: every verdict counts, hurt included); a new key starts an unreviewed entry."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.locked():
            rows = self._rows()
            row = rows.get(v["id"]) or {"id": v["id"], "cause": v["cause"], "op": v["op"], "scope": v["scope"],
                                        "counts": dict.fromkeys(VERDICTS, 0), "by_niche": {}, "task_ids": [],
                                        "run_ids": [], "status": "unreviewed", "cue": "", "lesson": "",
                                        "confidence": None, "created_at": now}
            row["counts"][v["verdict"]] += 1
            row["by_niche"].setdefault(niche, dict.fromkeys(VERDICTS, 0))[v["verdict"]] += 1
            for k, x in (("task_ids", task_id), ("run_ids", run_id)):
                if x and x not in row[k]:
                    row[k].append(x)
            row["updated_at"] = now
            rows[v["id"]] = row
            self._save(rows)
            folder = self.root / v["id"]
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / "evidence.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"run_id": run_id, "task_id": task_id, "niche": niche, "verdict": v["verdict"],
                                     "probe": v["probe"], "at": now}, ensure_ascii=False) + "\n")
            if v["verdict"] == "helped":
                edit = json.loads((folder / "edit.json").read_text()) if (folder / "edit.json").exists() else \
                    {"cause": v["cause"], "op": v["op"], "scope": v["scope"], "params_that_helped": []}
                edit["params_that_helped"] = (edit["params_that_helped"] + [v["params"]])[-self.kept:]
                self._write(folder / "edit.json", json.dumps(edit, indent=2, ensure_ascii=False) + "\n")
            self._experience(row)
            return row

    def add_lesson(self, entry_id: str, cue: str, lesson: str, confidence, run_id: str) -> dict:
        """Write (or replace) the entry's cue and lesson; its status and counts are kept."""
        with self.locked():
            rows = self._rows()
            row = rows[entry_id]
            row.update(cue=cue.strip(), lesson=lesson.strip(), confidence=confidence, lesson_run=run_id,
                       updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            self._save(rows)
            self._experience(row)
            return row

    def set_status(self, entry_id: str, status: str) -> dict:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        with self.locked():
            rows = self._rows()
            if entry_id not in rows:
                raise KeyError(f"no lesson {entry_id!r} in {self.root}")
            rows[entry_id]["status"] = status
            rows[entry_id][f"{status}_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._save(rows)
            self._experience(rows[entry_id])
            return rows[entry_id]

    def _experience(self, row: dict) -> None:
        c = row["counts"]
        ev = self.evidence(row["id"])[-self.kept:]
        lines = [f"# {row['op']} ({row['scope']}) for {row['cause']}", "",
                 f"Status: {row['status']}. Helped {c['helped']}, hurt {c['hurt']}, no effect {c['no_effect']}, "
                 f"confounded {c['confounded']}; tasks: {len(row['task_ids'])}.", "",
                 f"**Cue:** {row.get('cue') or '(no lesson written yet)'}", "",
                 f"**Lesson:** {row.get('lesson') or '(no lesson written yet)'}", "",
                 "## Evidence (latest first)", "",
                 *[f"- {e['at']} · {e['verdict']} · run {e['run_id']} · task {e['task_id']} · niche {e['niche']} · "
                   f"cleared {e['probe'].get('cleared')} new {e['probe'].get('new')} status {e['probe'].get('status')}"
                   for e in reversed(ev)]]
        self._write(self.root / row["id"] / "EXPERIENCE.md", "\n".join(lines) + "\n")


# ---- the reflector (one LLM call, only when an edit helped) ------------------------------------------------------
# box: lessons
def reflector_text(r, row: dict, helped: dict, refused: list[str] | None) -> str:
    from amoeba.config.prompts import PROMPT, render
    step = r.steps.get(row["step"]) if hasattr(r, "steps") else None
    card = "\n".join(x for x in ((step.text if step else ""), f"output: {getattr(step, 'output', '')}",
                                 f"done_when: {getattr(step, 'done_when', '')}") if x and not x.endswith(": "))
    tools = ", ".join(sorted(r.i.tools.names())) if hasattr(r.i.tools, "names") else "none"
    skills = sorted({p["name"] for a in r.agents.values() for p in a.pool if p["kind"] == "skill"})
    rounds = json.dumps({k: row[k] for k in ("cause", "signals", "edits", "probes", "pick", "pick_reason",
                                             "step_status")}, ensure_ascii=False, default=str)
    user = render(PROMPT.reflector, card=card or "(none)", rounds=rounds[:6000], op=helped["op"],
                  scope=helped["scope"], cause=row["cause"], tools=f"tools: {tools}\nskills: {', '.join(skills) or 'none'}",
                  max_chars=str(lessons_config()["max_chars"]))
    if refused:
        user += ("\n\n# Your previous reply was refused by plain code\n" + "\n".join(f"- {x}" for x in refused)
                 + "\nReply again, or reply NO_ENTRY.")
    return user


# box: lessons
def parse_reflection(raw: str) -> dict | None:
    """{"cue", "lesson", "confidence"} from the reflector's reply, None for NO_ENTRY; ValueError if unreadable."""
    text = (raw or "").strip()
    if re.fullmatch(r"[`\s]*NO_ENTRY[`.\s]*", text):
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object and no NO_ENTRY")
    obj = json.loads(m.group(0))
    if obj.get("entry") is False or obj.get("no_entry"):
        return None
    if not isinstance(obj.get("cue"), str) or not isinstance(obj.get("lesson"), str):
        raise ValueError("cue and lesson must be strings")
    conf = obj.get("confidence")
    return {"cue": obj["cue"], "lesson": obj["lesson"],
            "confidence": conf if isinstance(conf, (int, float, str)) else None}


# box: lessons
def reflector_affordable(r, est: int) -> str | None:
    """Why the reflector may not be called now (None: it may): the run's token cap or the task's fix allowance would
    not hold an estimated `est` tokens, or the step has used its share of the run cap (D151)."""
    from amoeba.adapt.fixes import limits as fix_limits, token_cap
    lim = getattr(getattr(r.i.trace, "limits", None), "max_tokens", None)
    if lim and r.billed_now() + est > lim:
        return f"the run cap ({lim:,} tokens) would not hold the reflector"
    avg = r.avg_attempt()
    if avg > 0 and r.adapt_tokens + est > token_cap(fix_limits(), avg):
        return "the task's fix allowance would not hold the reflector"
    share = r.over_share() if hasattr(r, "over_share") else None
    return share


# box: lessons
def learn_from_round(r, row: dict) -> dict:
    """D163, after a round is written: every verdict is counted in the library; when an edit helped and the run cap
    and the fix allowance hold it, the reflector is asked for a lesson (twice at most). Never fails the run: any error
    is logged and the round goes on. Returns {"verdicts": [...], "lesson": id | None, "skipped": why | None}."""
    out = {"verdicts": [], "lesson": None, "skipped": None}
    opt = r.opt
    if getattr(opt, "lessons_write", "off") != "on":
        return out
    try:
        lib = LessonLibrary(getattr(opt, "lessons_dir", None))
        run_id = Path(r.run_dir).name if getattr(r, "run_dir", None) else r.ep.episode_id
        for v in round_verdicts(row):
            lib.record(v, row["niche"], row["task_id"], run_id)
            out["verdicts"].append({k: v[k] for k in ("id", "op", "scope", "verdict")})
        helped = [v for v in round_verdicts(row) if v["verdict"] == "helped"]
        if not helped:
            return out
        pick = next((v for v in helped if v["scope"] == row.get("pick")), helped[0])
        cfg = lessons_config()
        est = int(cfg["reflector_max_tokens"]) + 2000
        why = reflector_affordable(r, est)
        if why:
            out["skipped"] = why
            r.i.trace.event("reflector_skipped", {"amoeba.box": "lessons", "amoeba.step": row["step"],
                                                  "amoeba.why": why})
            r.log_event("reflector_skipped", {"step": row["step"], "why": why})
            return out
        refused = None
        for attempt in (1, 2):
            raw = reflector_call(r, reflector_text(r, row, pick, refused), int(cfg["reflector_max_tokens"]))
            try:
                got = parse_reflection(raw)
                problems = [] if got is None else lesson_problems(got["cue"], got["lesson"], r.task.prompt, cfg)
            except (ValueError, json.JSONDecodeError) as e:
                got, problems = {}, [f"unreadable reply: {e}"[:300]]
            r.i.trace.event("reflector_reply", {"amoeba.box": "lessons", "amoeba.step": row["step"],
                                                "amoeba.attempt": attempt, "amoeba.entry": got is not None,
                                                "amoeba.problems": problems[:4]})
            if got is None:
                return out
            if not problems:
                lib.add_lesson(pick["id"], got["cue"], got["lesson"], got["confidence"], run_id)
                out["lesson"] = pick["id"]
                r.log_event("lesson", {"id": pick["id"], "step": row["step"], "cue": got["cue"],
                                       "lesson": got["lesson"]})
                return out
            refused = problems
        out["skipped"] = "the lesson was refused twice: " + "; ".join(refused or [])[:300]
        return out
    except Exception as e:                       # the library is evidence, never a reason to fail the run
        out["skipped"] = f"{type(e).__name__}: {e}"[:300]
        r.i.trace.event("reflector_skipped", {"amoeba.box": "lessons", "amoeba.why": out["skipped"]})
        return out


# box: lessons
def reflector_call(r, user: str, max_tokens: int) -> str:
    """One traced, counted call (its tokens go to the round's fix tokens and to the run's totals)."""
    with r.i.trace.span("invoke_agent", {"gen_ai.agent.name": "reflector", "amoeba.box": "lessons"}):
        resp = r.i.llm.chat_messages([{"role": "user", "content": user}], r.ep.seed, agent_name="reflector",
                                     role="planner", max_tokens=max_tokens)
    r.ep.total_tokens += resp.input_tokens + resp.output_tokens
    r.ep.n_llm_calls += 1
    return resp.content or ""
