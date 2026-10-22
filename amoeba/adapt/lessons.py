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

The library (`adapt.yaml lessons.library`, data/lessons/) is one for every task. D167: a *family* is (cause, op,
scope) and counts every verdict, for reports (`index.jsonl`; its folder holds `edit.json`, the params that helped,
`evidence.jsonl` and `EXPERIENCE.md`). Every lesson the reflector writes is its own entry in `lessons.jsonl`
(`<family>__L<k>`), with its own text, which never changes, its own status and its own counts. A lesson gains
evidence only when it is used: the round that wrote it, then probes whose proposer cited it (`from_lesson`). The niche
of each count is recorded (`by_niche`), never used to split. New lessons are `unreviewed`; only the user approves one
(scripts/lessons.py). Writes take a file lock and replace files atomically, so runs may write at once.
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
VERDICTS = ("helped", "hurt", "no_effect", "confounded")    # D168: a verdict without a control is "uncontrolled"
STATUSES = ("unreviewed", "approved", "rejected", "promoted", "promotion_failed")
LESSONS = "lessons.jsonl"                                       # D167: one row per lesson
OLD_KEYS = ("status", "cue", "lesson", "confidence", "lesson_run")   # D167: what a pre-D167 index row held
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


# box: control
def controlled_verdict(probe: dict, control: dict) -> str:
    """D168: the verdict of an edit against the control (the same start, no edit, re-run once): helped only when it did
    better than doing nothing; as well as the control is no_effect."""
    if probe.get("composed_of"):
        return "confounded"
    done = probe.get("status") == "done" or bool(probe.get("limited"))
    c_done = control.get("status") == "done"
    if done:
        return "no_effect" if c_done else "helped"
    if c_done:                                    # doing nothing finished the step; the edit did not
        return "hurt"
    more = set(probe.get("cleared") or []) - set(control.get("cleared") or [])
    worse = set(probe.get("new") or []) - set(control.get("new") or [])
    if more and worse:
        return "confounded"
    return "helped" if more else "hurt" if worse else "no_effect"


# box: lessons
def key_of(cause: str, op: str, scope: str) -> str:
    """The entry id of (cause, op, scope)."""
    return "__".join(re.sub(r"[^\w-]+", "_", x or "none") for x in (cause, op, scope))


# box: lessons
def round_verdicts(row: dict) -> list[dict]:
    """[{id, cause, op, scope, verdict, raw, controlled, probe}] for every probe of a D162 round row; a composed probe
    gives a confounded verdict to each edit it combined. D168: with the round's control, `verdict` is the controlled
    verdict; without one it is `uncontrolled` (`raw`: the rule without a control, kept for the family's counts)."""
    out = []
    control = row.get("control")
    for p in row.get("probes") or []:
        parts = p.get("composed_of") or [{"scope": p["scope"], "op": p["op"], "params": p.get("params") or {},
                                          "from_lesson": p.get("from_lesson")}]
        raw = verdict(p)
        v = controlled_verdict(p, control) if control else "uncontrolled"
        for part in parts:
            out.append({"id": key_of(row["cause"], part["op"], part["scope"]), "cause": row["cause"],
                        "op": part["op"], "scope": part["scope"], "params": part.get("params") or {}, "verdict": v,
                        "raw": raw, "controlled": bool(control),
                        "from_lesson": part.get("from_lesson"),
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
    """data/lessons/ (D167): `index.jsonl` holds one row per family (cause, op, scope) with every verdict counted, for
    reports; `lessons.jsonl` one row per lesson the reflector wrote, with its own id, text, status and counts. A
    lesson's text never changes (new text is a new lesson). Each family and each lesson has a folder (evidence.jsonl,
    EXPERIENCE.md; a family also edit.json). Safe for several writers: every change holds an exclusive file lock and
    replaces files atomically. A library written before D167 is migrated when opened."""

    def __init__(self, root: str | Path | None = None):
        cfg = lessons_config()
        self.root = Path(root) if root is not None else ROOT / cfg["library"]
        self.timeout = float(cfg["lock_timeout_s"])
        self.kept = int(cfg["evidence_kept"])
        if any(k in r for r in self._rows().values() for k in OLD_KEYS):
            self.migrate()

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

    def _rows(self, name: str = "index.jsonl") -> dict[str, dict]:
        p = self.root / name
        rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
        return {r["id"]: r for r in rows}

    def _save(self, rows: dict[str, dict], name: str = "index.jsonl") -> None:
        self._write(self.root / name, "".join(json.dumps(rows[k], ensure_ascii=False) + "\n" for k in sorted(rows)))

    def _append(self, entry_id: str, line: dict) -> None:
        folder = self.root / entry_id
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "evidence.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    @staticmethod
    def _count(row: dict, v: dict, niche: str, task_id: str, run_id: str, now: str, lesson: bool = False) -> None:
        """D168: a family counts every verdict by the rule without a control (`raw`, today's counts) and keeps the
        controlled ones apart (`controlled`) and how many had no control (`uncontrolled`); a lesson's `counts` hold
        only controlled verdicts, its `uncontrolled` the raw verdicts of uses without a control."""
        raw, controlled = v.get("raw", v["verdict"]), v.get("controlled", v["verdict"] != "uncontrolled")
        if lesson:
            if controlled:
                row["counts"][v["verdict"]] += 1
                row["by_niche"].setdefault(niche, dict.fromkeys(VERDICTS, 0))[v["verdict"]] += 1
            else:
                row.setdefault("uncontrolled", dict.fromkeys(VERDICTS, 0))[raw] += 1
        else:
            row["counts"][raw] += 1
            row["by_niche"].setdefault(niche, dict.fromkeys(VERDICTS, 0))[raw] += 1
            if controlled:
                row.setdefault("controlled", dict.fromkeys(VERDICTS, 0))[v["verdict"]] += 1
            else:
                row["uncontrolled"] = row.get("uncontrolled", 0) + 1
        for k, x in (("task_ids", task_id), ("run_ids", run_id)):
            if x and x not in row[k]:
                row[k].append(x)
        row["updated_at"] = now

    # ---- reading -----------------------------------------------------------------------------------------------
    def entries(self) -> list[dict]:
        """The families (every verdict counted; for reports only)."""
        return list(self._rows().values())

    def lessons(self, family: str | None = None) -> list[dict]:
        """The lessons, of one family or of all."""
        return [x for x in self._rows(LESSONS).values() if family is None or x["family"] == family]

    def lesson(self, lesson_id: str) -> dict | None:
        return self._rows(LESSONS).get(lesson_id)

    def get(self, entry_id: str) -> dict | None:
        """A family or a lesson by its id."""
        return self._rows().get(entry_id) or self.lesson(entry_id)

    def evidence(self, entry_id: str) -> list[dict]:
        p = self.root / entry_id / "evidence.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []

    # ---- writing -----------------------------------------------------------------------------------------------
    def record(self, v: dict, niche: str, task_id: str, run_id: str) -> dict:
        """Count one verdict in its family (D163: every verdict counts, hurt included); a new key starts a family."""
        now = _now()
        with self.locked():
            rows = self._rows()
            row = rows.get(v["id"]) or {"id": v["id"], "cause": v["cause"], "op": v["op"], "scope": v["scope"],
                                        "counts": dict.fromkeys(VERDICTS, 0), "by_niche": {}, "task_ids": [],
                                        "run_ids": [], "created_at": now}
            self._count(row, v, niche, task_id, run_id, now)
            rows[v["id"]] = row
            self._save(rows)
            self._append(v["id"], {"run_id": run_id, "task_id": task_id, "niche": niche, "verdict": v["verdict"],
                                   "raw": v.get("raw", v["verdict"]), "probe": v["probe"], **({"from_lesson": v["from_lesson"]}
                                                           if v.get("from_lesson") else {}), "at": now})
            folder = self.root / v["id"]
            if v.get("raw", v["verdict"]) == "helped":
                edit = json.loads((folder / "edit.json").read_text()) if (folder / "edit.json").exists() else \
                    {"cause": v["cause"], "op": v["op"], "scope": v["scope"], "params_that_helped": []}
                edit["params_that_helped"] = (edit["params_that_helped"] + [v["params"]])[-self.kept:]
                self._write(folder / "edit.json", json.dumps(edit, indent=2, ensure_ascii=False) + "\n")
            self._experience_family(row)
            return row

    def add_lesson(self, family_id: str, cue: str, lesson: str, confidence, run_id: str, first: dict | None = None,
                   niche: str = "general", task_id: str = "") -> dict:
        """A new lesson in the family, `unreviewed`; `first` (the verdict of the round that wrote it) is its first
        sample. A lesson whose text is already in the family is that lesson (returned unchanged, nothing counted):
        a lesson's text never changes."""
        now = _now()
        with self.locked():
            fam = self._rows()[family_id]
            rows = self._rows(LESSONS)
            same = next((x for x in rows.values() if x["family"] == family_id and x["lesson"] == lesson.strip()), None)
            if same is not None:
                return same
            k = 1 + max((int(x["id"].rsplit("__L", 1)[1]) for x in rows.values() if x["family"] == family_id),
                        default=0)
            row = {"id": f"{family_id}__L{k}", "family": family_id, **{x: fam[x] for x in ("cause", "op", "scope")},
                   "cue": cue.strip(), "lesson": lesson.strip(), "confidence": confidence, "status": "unreviewed",
                   "counts": dict.fromkeys(VERDICTS, 0), "uncontrolled": dict.fromkeys(VERDICTS, 0), "by_niche": {},
                   "task_ids": [], "run_ids": [], "written_by": run_id, "created_at": now, "updated_at": now}
            if first is not None:
                self._use(row, first, niche, task_id, run_id, now, "the round that wrote it")
            rows[row["id"]] = row
            self._save(rows, LESSONS)
            self._experience_lesson(row)
            self._experience_family(fam)
            return row

    def record_use(self, lesson_id: str, v: dict, niche: str, task_id: str, run_id: str) -> dict:
        """D167: a probe whose edit cited this lesson (`from_lesson`, checked by plain code) counts for it."""
        now = _now()
        with self.locked():
            rows = self._rows(LESSONS)
            if lesson_id not in rows:
                raise KeyError(f"no lesson {lesson_id!r} in {self.root}")
            self._use(rows[lesson_id], v, niche, task_id, run_id, now, "cited by the proposer")
            self._save(rows, LESSONS)
            self._experience_lesson(rows[lesson_id])
            return rows[lesson_id]

    def _use(self, row: dict, v: dict, niche: str, task_id: str, run_id: str, now: str, how: str) -> None:
        self._count(row, v, niche, task_id, run_id, now, lesson=True)
        self._append(row["id"], {"run_id": run_id, "task_id": task_id, "niche": niche, "verdict": v["verdict"],
                                 "raw": v.get("raw", v["verdict"]), "probe": v.get("probe") or {}, "how": how,
                                 "at": now})

    def set_status(self, lesson_id: str, status: str) -> dict:
        """A lesson's status (families have none)."""
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        with self.locked():
            rows = self._rows(LESSONS)
            if lesson_id not in rows:
                raise KeyError(f"no lesson {lesson_id!r} in {self.root}")
            rows[lesson_id]["status"] = status
            rows[lesson_id][f"{status}_at"] = _now()
            self._save(rows, LESSONS)
            self._experience_lesson(rows[lesson_id])
            return rows[lesson_id]

    def migrate(self) -> list[str]:
        """D167: a pre-D167 library (one row per key, holding the latest lesson and a status) becomes families; each
        written lesson moves into its family as one lesson, `unreviewed` (its counts start at 0: the old counts were
        the family's). Returns the lesson ids made."""
        made = []
        with self.locked():
            fams, rows = self._rows(), self._rows(LESSONS)
            for f in fams.values():
                text = (f.get("lesson") or "").strip()
                if text and not any(x["family"] == f["id"] and x["lesson"] == text for x in rows.values()):
                    lid = f"{f['id']}__L{1 + sum(x['family'] == f['id'] for x in rows.values())}"
                    rows[lid] = {"id": lid, "family": f["id"], **{x: f[x] for x in ("cause", "op", "scope")},
                                 "cue": (f.get("cue") or "").strip(), "lesson": text,
                                 "confidence": f.get("confidence"), "status": "unreviewed",
                                 "counts": dict.fromkeys(VERDICTS, 0), "uncontrolled": dict.fromkeys(VERDICTS, 0),
                                 "by_niche": {}, "task_ids": [], "run_ids": [],
                                 "written_by": f.get("lesson_run"), "migrated_from_status": f.get("status"),
                                 "created_at": f.get("updated_at") or f.get("created_at") or _now(),
                                 "updated_at": _now()}
                    made.append(lid)
                for k in OLD_KEYS:
                    f.pop(k, None)
            self._save(fams)
            self._save(rows, LESSONS)
            for lid in made:
                self._experience_lesson(rows[lid])
            for f in fams.values():
                self._experience_family(f)
        return made

    def _experience_family(self, row: dict) -> None:
        c = row["counts"]
        ev = self.evidence(row["id"])[-self.kept:]
        les = self.lessons(row["id"])
        lines = [f"# {row['op']} ({row['scope']}) for {row['cause']}: the family", "",
                 f"Every verdict of this edit, for reports only (a lesson counts only its own uses). Helped "
                 f"{c['helped']}, hurt {c['hurt']}, no effect {c['no_effect']}, confounded {c['confounded']}; tasks: "
                 f"{len(row['task_ids'])}.", "", "## Lessons", "",
                 *([f"- {x['id']} · {x['status']} · helped {x['counts']['helped']} hurt {x['counts']['hurt']} · "
                    f"{x['lesson']}" for x in les] or ["(no lesson written yet)"]), "",
                 "## Evidence (latest first)", "",
                 *[f"- {e['at']} · {e['verdict']} · run {e['run_id']} · task {e['task_id']} · niche {e['niche']} · "
                   f"cleared {e['probe'].get('cleared')} new {e['probe'].get('new')} status {e['probe'].get('status')}"
                   for e in reversed(ev)]]
        self._write(self.root / row["id"] / "EXPERIENCE.md", "\n".join(lines) + "\n")

    def _experience_lesson(self, row: dict) -> None:
        c = row["counts"]
        ev = self.evidence(row["id"])[-self.kept:]
        lines = [f"# Lesson {row['id']}", "", f"Edit {row['op']} ({row['scope']}) for {row['cause']}.", "",
                 f"Status: {row['status']}. Helped {c['helped']}, hurt {c['hurt']}, no effect {c['no_effect']}, "
                 f"confounded {c['confounded']} (against a control); without a control: "
                 f"{json.dumps(row.get('uncontrolled') or {})}; tasks: {len(row['task_ids'])}. Counted only when this "
                 "lesson was used: the round that wrote it, and probes whose edit cited it.", "",
                 f"**Cue:** {row['cue']}", "", f"**Lesson:** {row['lesson']}", "",
                 "## Evidence (latest first)", "",
                 *[f"- {e['at']} · {e['verdict']} · {e.get('how', '')} · run {e['run_id']} · task {e['task_id']} · "
                   f"niche {e['niche']}" for e in reversed(ev)]]
        self._write(self.root / row["id"] / "EXPERIENCE.md", "\n".join(lines) + "\n")


# box: lessons
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
            if v.get("from_lesson") and lib.lesson(v["from_lesson"]):      # D167: a cited use counts for the lesson
                lib.record_use(v["from_lesson"], v, row["niche"], row["task_id"], run_id)
        helped = [v for v in round_verdicts(row) if v["verdict"] == "helped" or       # D168: against the control,
                  (v["verdict"] == "uncontrolled" and v["raw"] == "helped")]           # or by the rule without one
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
                les = lib.add_lesson(pick["id"], got["cue"], got["lesson"], got["confidence"], run_id, first=pick,
                                     niche=row["niche"], task_id=row["task_id"])                # D167
                out["lesson"] = les["id"]
                r.log_event("lesson", {"id": les["id"], "family": pick["id"], "step": row["step"], "cue": got["cue"],
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
