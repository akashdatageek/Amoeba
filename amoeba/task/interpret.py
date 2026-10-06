"""D77 — task understanding before planning (Box 1 → Box 2).

One LLM call lists the readings of the task's key entities and terms (names, abbreviations, acronyms, likely
voice-input errors such as "P and W" for "PNW"), each with a one-line justification and a confidence; it reads the
user context (--context, the Memory stub) when there is one. Plain code then decides, per entity:

- one reading clearly dominant (its confidence beats the next by at least DOMINANCE_GAP, or it is the only one)
  → it is the working interpretation;
- otherwise the task's subject is ambiguous:
    - with --interactive the user gets ONE multiple-choice question (the readings + "other") before planning;
    - without it the top reading is used as an assumption: the final answer must open with "I read X as Y; if you
      meant Z, …" and its Limitations list the other readings (plain code checks both and adds what is missing).

The working interpretation travels with the task text (Planner, observers, every Box 3 helper), and an open
question the Planner writes about one of these entities is answered from it, never by the Planner's guess.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Mapping

import yaml

from amoeba.config.prompts import PROMPT, render
from amoeba.interp.trace import TracedLLM
from amoeba.memory.context import context_text
from amoeba.task.parsers import parse_sections

FAMILIES = Path(__file__).resolve().parents[1] / "config" / "families.yaml"
DOMINANCE_GAP = 0.3          # confidence lead a reading needs over the next to be taken without asking
MAX_TOKENS = 4096
OTHER = "other (type what you meant)"


# box: interpret
def parse_entities(raw: str) -> list[dict]:
    """The Entities section as [{entity, readings: [{reading, why, confidence}]}], readings sorted by confidence."""
    body = parse_sections(raw).get("Entities", "") or raw
    m = re.search(r"\[[\s\S]*\]", body)
    try:
        items = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        items = []
    out = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict) or not str(it.get("entity", "")).strip():
            continue
        readings = []
        for r in it.get("readings") or []:
            if isinstance(r, dict) and str(r.get("reading", "")).strip():
                try:
                    conf = max(0.0, min(1.0, float(r.get("confidence", 0))))
                except (TypeError, ValueError):
                    conf = 0.0
                readings.append({"reading": str(r["reading"]).strip(), "why": str(r.get("why", "")).strip(),
                                 "confidence": round(conf, 3)})
        if readings:
            readings.sort(key=lambda r: -r["confidence"])
            out.append({"entity": str(it["entity"]).strip(), "readings": readings})
    return out


# box: interpret
def decide(entities: list[dict], gap: float = DOMINANCE_GAP) -> dict:
    """Plain code: per entity, the working reading and how it was settled ("dominant" / "only" / "assumed")."""
    working, ambiguous = [], []
    for e in entities:
        top, rest = e["readings"][0], e["readings"][1:]
        lead = top["confidence"] - (rest[0]["confidence"] if rest else 0.0)
        how = "only" if not rest else ("dominant" if lead >= gap else "assumed")
        working.append({"entity": e["entity"], "reading": top["reading"], "why": top["why"],
                        "confidence": top["confidence"], "lead": round(lead, 3), "settled": how,
                        "alternatives": [r["reading"] for r in rest]})
        if how == "assumed":
            ambiguous.append(e["entity"])
    return {"entities": entities, "working": working, "ambiguous": ambiguous, "gap": gap, "question": None}


# box: interpret
def read_task(task_text: str, llm: TracedLLM, context: Mapping[str, str] | None = None, seed: int = 0,
              gap: float = DOMINANCE_GAP, environment: str = "") -> dict:
    """The interpretation step: one call, then plain code decides. environment: D102's Environment section of the
    niche profile ("" for general: the prompt is unchanged)."""
    user = render(PROMPT.interpret, task=task_text, context=context_text(context or {})) + environment
    raw = llm.chat_messages([{"role": "user", "content": user}], seed=seed, max_tokens=MAX_TOKENS,
                            agent_name="interpreter", role="planner").content
    out = decide(parse_entities(raw), gap)
    out["context"] = dict(context or {})
    llm.trace.event("task_interpretation", {
        "amoeba.box": "interpret", "amoeba.entities": [w["entity"] for w in out["working"]],
        "amoeba.working": {w["entity"]: w["reading"] for w in out["working"]},
        "amoeba.settled": {w["entity"]: w["settled"] for w in out["working"]}, "amoeba.ambiguous": out["ambiguous"],
        "amoeba.context_keys": sorted(out["context"])})
    return out


# box: interpret
def options_of(interp: dict, w: dict) -> list[str]:
    """The choices put to the user for one entity: its readings, most confident first, then "other"."""
    e = next(x for x in interp["entities"] if x["entity"] == w["entity"])
    return [r["reading"] for r in e["readings"]] + [OTHER]


# box: interpret
def settle(interp: dict, w: dict, options: list[str], reply: str) -> dict:
    """Reads one reply (an option number or the user's own words) and, when it names a reading, makes it the entity's
    working reading ("user"). A blank reply or "other" without words leaves the assumption as it was."""
    reply = (reply or "").strip()
    chosen = None
    if reply.isdigit() and 1 <= int(reply) <= len(options) - 1:
        chosen = options[int(reply) - 1]
    elif reply and not (reply.isdigit() and int(reply) == len(options)):
        chosen = reply
    q = {"entity": w["entity"], "options": options, "reply": reply, "chosen": chosen}
    if chosen:
        w.update(reading=chosen, settled="user", alternatives=[])
        interp["ambiguous"] = [a for a in interp["ambiguous"] if a != w["entity"]]
    return q


# box: interpret
def _ask(w: dict, options: list[str], ask: Callable[[str], str]) -> str:
    lines = [f'What did you mean by "{w["entity"]}"?'] + [f"  {i}. {o}" for i, o in enumerate(options, 1)]
    try:
        return ask("\n".join(lines) + f"\nChoose 1-{len(options)} (or type your meaning): ")
    except EOFError:
        return ""


# box: interpret
def ask_one(interp: dict, ask: Callable[[str], str]) -> dict:
    """--interactive: ONE multiple-choice question about the least certain ambiguous entity (its readings + other),
    before planning. The answer becomes that entity's working reading ("user"); any other ambiguous entity stays an
    assumption."""
    if not interp["ambiguous"]:
        return interp
    rows = [w for w in interp["working"] if w["settled"] == "assumed"]
    w = min(rows, key=lambda x: x["lead"])
    options = options_of(interp, w)
    interp["question"] = settle(interp, w, options, _ask(w, options, ask))
    return interp


# box: interpret
def ask_all(interp: dict, ask: Callable[[str], str]) -> dict:
    """D116: every entity whose reading would be assumed (no reading leads the next by DOMINANCE_GAP, a tie
    included) is asked about before planning, least certain first, one multiple-choice question each. A blank
    reply keeps that one assumption, which the answer then states (D77)."""
    rows = sorted((w for w in interp["working"] if w["settled"] == "assumed"), key=lambda x: x["lead"])
    asked = []
    for w in rows:
        options = options_of(interp, w)
        asked.append(settle(interp, w, options, _ask(w, options, ask)))
    if asked:
        interp["question"], interp["questions"] = asked[0], asked
    return interp


# box: interpret
def apply_clarify(interp: dict, answers: Mapping[str, str]) -> dict:
    """D116 --clarify ENTITY=READING: answers given on the command line (an option number or words) settle those
    entities as the user's choice, with no question; entity names match case-insensitively."""
    given = {k.strip().strip('"').lower(): v for k, v in answers.items()}
    done = []
    for w in interp["working"]:
        reply = given.get(w["entity"].lower())
        if reply is not None and w["settled"] == "assumed":
            done.append(settle(interp, w, options_of(interp, w), reply))
    if done:
        interp["clarified"] = done
    return interp


# box: interpret
class NeedsClarification(Exception):
    """D116: a reading would be assumed and nobody can be asked (no terminal, no --interactive); the run stops before
    Box 2 instead of guessing. `questions` are what the user is asked to answer with --clarify."""

    def __init__(self, questions: list[dict]):
        self.questions = questions
        super().__init__("; ".join(f'"{q["entity"]}": ' + " | ".join(q["options"][:-1]) for q in questions))


# box: interpret
def open_questions(interp: dict) -> list[dict]:
    """D116: the questions a run that cannot ask leaves for the user, least certain first."""
    rows = sorted((w for w in interp["working"] if w["settled"] == "assumed"), key=lambda x: x["lead"])
    return [{"entity": w["entity"], "options": options_of(interp, w), "lead": w["lead"]} for w in rows]


# box: interpret
def assumed(interp: dict | None) -> list[dict]:
    return [w for w in (interp or {}).get("working", []) if w["settled"] == "assumed"]


# box: interpret
def opening_line(interp: dict | None) -> str | None:
    """The sentence the answer must open with when the subject was assumed: "I read X as Y; if you meant Z, …"."""
    rows = assumed(interp)
    if not rows:
        return None
    parts = []
    for w in rows:
        alts = " or ".join(w["alternatives"][:3])
        parts.append(f'I read "{w["entity"]}" as {w["reading"]}; if you meant {alts}, the answer below may not apply.')
    return " ".join(parts)


# box: interpret
def task_note(interp: dict | None) -> str:
    """What the Planner, the observers and every helper are told: the working interpretation, and when it was
    assumed, the opening line the answer must carry."""
    rows = (interp or {}).get("working", [])
    if not rows:
        return ""
    how = {"only": "", "dominant": "", "user": " (the user chose this)", "assumed": " (an assumption)"}
    lines = ["Working interpretation (settled before planning; do not re-interpret it or guess otherwise):"]
    lines += [f'- "{w["entity"]}" means {w["reading"]}{how[w["settled"]]}' for w in rows]
    line = opening_line(interp)
    if line:
        lines.append(f"The final answer must open with this line: {line}")
    return "\n".join(lines)


# box: interpret
def with_note(prompt: str, interp: dict | None) -> str:
    note = task_note(interp)
    return f"{prompt}\n\n{note}" if note and note not in prompt else prompt


# box: interpret
def route_open_questions(open_questions: list[dict], interp: dict | None) -> tuple[list[dict], list[str]]:
    """The Planner may not settle a question about the task's subject by guessing: an open question that names an
    interpreted entity is answered from the working interpretation. Returns the questions and the ones routed."""
    rows = (interp or {}).get("working", [])
    routed, out = [], []
    for q in open_questions:
        text = f"{q.get('question', '')}"
        hit = next((w for w in rows if w["entity"].lower() in text.lower()
                    or w["reading"].lower() in text.lower()), None)
        if hit:
            q = {**q, "assumption": f'settled before planning: "{hit["entity"]}" means {hit["reading"]}'
                                    + (" (an assumption; the answer states it)" if hit["settled"] == "assumed" else "")}
            routed.append(text)
        out.append(q)
    return out, routed


# box: interpret
def enforce_opening(answer: str | None, interp: dict | None) -> tuple[str | None, dict]:
    """Plain code: when the subject was assumed, the answer opens with the stated assumption and its Limitations
    list the other readings; whatever is missing is added (and recorded)."""
    line, rows = opening_line(interp), assumed(interp)
    if not answer or not line:
        return answer, {}
    added = {"opening_line_added": False, "alternatives_added": []}
    first = next((l for l in answer.splitlines() if l.strip()), "")
    if not (re.match(r"^\W*I read\b", first, re.I) and all(w["entity"].lower() in first.lower() for w in rows)):
        answer = f"{line}\n\n{answer.lstrip()}"
        added["opening_line_added"] = True
    m = re.search(r"^\s*#+\s*limitations\b.*$", answer, re.I | re.M)
    section = answer[m.end():].lower() if m else ""
    missing = [(w["entity"], a) for w in rows for a in w["alternatives"] if a.lower() not in section]
    if missing:
        body = "\n".join(f'- Other reading of "{e}": {a} (not researched; added by plain code)' for e, a in missing)
        answer = f"{answer.rstrip()}\n\n{body}\n" if m else f"{answer.rstrip()}\n\n## Limitations\n{body}\n"
        added["alternatives_added"] = [a for _, a in missing]
    return answer, added


# ---- D101: the task family of a free-text task (warm start) ---------------------------------------------------------
# box: interpret
def load_families(path: str | Path = FAMILIES) -> dict[str, dict]:
    return (yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}).get("families") or {}


# box: interpret
def family_by_rule(text: str, families: dict[str, dict]) -> tuple[str | None, list[str]]:
    """The family whose keywords match the task most often (whole words, case-insensitive); a tie or no match is
    None. Returns (family, the keywords that matched it)."""
    hits = {}
    for name, f in families.items():
        found = [k for k in f.get("keywords") or [] if re.search(rf"(?<![\w-]){k}(?![\w-])", text, re.I)]
        if found:
            hits[name] = found
    if not hits:
        return None, []
    best = max(len(v) for v in hits.values())
    top = [n for n, v in hits.items() if len(v) == best]
    return (top[0], hits[top[0]]) if len(top) == 1 else (None, sorted(k for n in top for k in hits[n]))


# box: interpret
def classify_family(task_text: str, llm: TracedLLM | None, families: dict[str, dict] | None = None,
                    seed: int = 0) -> dict:
    """Box 1 (D101): {family, how, ...} for a free-text task. Rules first; only if none decides, one routed call
    (role family_classifier) choosing from the list or "new", validated by code (anything else → "new")."""
    families = load_families() if families is None else families
    fam, kws = family_by_rule(task_text, families)
    if fam:
        return {"family": fam, "how": "rule", "keywords": kws}
    if llm is None:
        return {"family": "new", "how": "no_rule_no_call", "keywords": kws}
    listing = "\n".join(f"- {n}: {f.get('description', '')}" for n, f in families.items()) + \
        "\n- new: none of the above fits"
    raw = llm.chat_messages([{"role": "user", "content": render(PROMPT.family_classify, task=task_text,
                                                                families=listing)}],
                            seed=seed, max_tokens=200, agent_name="family_classifier", role="planner").content
    m = re.search(r"\{[\s\S]*\}", raw or "")
    try:
        answer = str(json.loads(m.group(0)).get("family", "")).strip() if m else ""
    except (json.JSONDecodeError, AttributeError):
        answer = ""
    if answer in families or answer == "new":
        return {"family": answer, "how": "llm", "keywords": kws}
    return {"family": "new", "how": "llm_invalid", "answer": answer[:80], "keywords": kws}
