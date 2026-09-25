"""The words on the as-built page that code cannot extract: each box's one-line `sentence` and its `what` lines.

They start hand-written in tools/arch_extract.py BOXES. docs/arch/box_text.json keeps, per box, the text in use and a
hash of that box's extracted facts (signatures, docstrings, fields, guards, checks, prompts, callees; no line numbers,
no numeric values). On a rebuild:
- same facts hash                → the cached text is used; no model call;
- the hand text in BOXES changed → the new hand text is used and re-hashed; no model call;
- the facts changed              → one call to a cheap model with the new facts, the diff of the facts and the old text:
                                   "still true? keep / rewrite". Without a model (no key, or --no-llm) the old text is
                                   kept and the box is marked stale; it is checked on the next rebuild that has one.
Numbers never enter the text as digits: they are {NAME} placeholders filled from the extracted constants on every
build, so a changed constant updates the page without a model call. Every rebuild appends one line (calls and tokens)
to docs/arch/text_log.jsonl.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "arch"
CACHE = OUT / "box_text.json"
LOG = OUT / "text_log.jsonl"
PROFILE = "arch-text"                  # amoeba/config/models.yaml: a cheap model; ARCH_TEXT_PROFILE overrides
NUM = re.compile(r"(?<![\w{.$/])\d{1,3}(?:,\d{3})+(?![\w}])|(?<![\w{.$/])\d+(?:\.\d+)?(?![\w}%])")
PLACEHOLDER = re.compile(r"\{([A-Za-z_][\w.]*)\}")
MAX_REPLY_TOKENS = 700

SYSTEM = ("You keep one box of an architecture page up to date. The page is read by a non-programmer: plain words, "
          "no code names unless the old text used them. Reply with JSON only.")
ASK = """Box "{title}" ({kind}).

Current text, numbered:
{lines}

How the code facts changed since that text was checked:
{diff}

The box's facts now:
{facts}

Numbers you may use, only as the placeholder in braces and only for exactly the quantity its name says: {consts}

Is every numbered line still true? Most code changes leave the text true: answer keep unless the diff makes a line
FALSE. New detail is not a reason to change anything.
- still true: {{"verdict": "keep"}}
- a line is now false: {{"verdict": "rewrite", "changes": [{{"line": <number>, "text": "<the corrected line>"}}]}}
  List only the false lines; every other line stays exactly as it is. Line 0 is the one-sentence summary (at most
  25 words). "text": null deletes a line; "line": "new" adds one. Write no digits outside placeholders."""


# ------------------------------------------------------------------------------------------------ numbers
def numeric_facts(F, box: dict, C: list[dict]) -> dict[str, float | int]:
    """The numbers this box's code names: module constants it uses, and the numeric defaults of the fields and
    parameters it defines or reads (Class.field, function.param). Name -> value."""
    idents: set[str] = set()
    own: dict[str, float | int] = {}
    for a in box["anchors"]:
        d = F.defs.get(a["key"])
        if not d:
            continue
        lo, hi = a.get("range", [a["line"], a.get("end_line", a["line"])])
        for n in ast.walk(d["node"]):
            ln = getattr(n, "lineno", lo)
            if not lo <= ln <= hi:
                continue
            if isinstance(n, ast.Name):
                idents.add(n.id)
            elif isinstance(n, ast.Attribute):
                idents.add(n.attr)
            elif isinstance(n, ast.keyword) and n.arg:
                idents.add(n.arg)
        node = d["node"]
        if isinstance(node, ast.FunctionDef):
            args = node.args.args + node.args.kwonlyargs
            defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + list(node.args.defaults) \
                + list(node.args.kw_defaults)
            for arg, dv in zip(args, defaults):
                v = _number(dv)
                if v is not None:
                    own[f"{d['qual'].split('.')[-1]}.{arg.arg}"] = v
    out: dict[str, float | int] = {}
    for c in C:
        if c["name"] in idents and isinstance(c["value"], (int, float)) and not isinstance(c["value"], bool):
            out[c["name"]] = c["value"]
    for key, d in F.defs.items():                      # class fields: the box's own classes, or fields it reads
        if d["kind"] != "class":
            continue
        mine = any(a["key"] == key for a in box["anchors"])
        for st in d["node"].body:
            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and (mine or st.target.id in idents):
                v = _number(st.value)
                if v is not None:
                    out[f"{d['node'].name}.{st.target.id}"] = v
    out.update(own)
    return out


def _number(node) -> float | int | None:
    try:
        v = ast.literal_eval(node) if node is not None else None
    except Exception:
        return None
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _num(tok: str) -> float:
    return float(tok.replace(",", ""))


def templatize(text: str, consts: dict) -> tuple[str, list[str], list[str]]:
    """Digits that equal exactly one of the box's numbers become {NAME}. Returns (text, replaced, left as digits)."""
    replaced, left = [], []

    def sub(m):
        tok = m.group(0)
        names = [k for k, v in consts.items() if _num(tok) == float(v)]
        if len(names) == 1:
            replaced.append(f"{tok}->{{{names[0]}}}")
            return "{" + names[0] + "}"
        left.append(tok)
        return tok
    return NUM.sub(sub, text), replaced, left


def fill(text: str, consts: dict) -> tuple[str, list[str]]:
    """{NAME} -> the value extracted now (thousands with commas). Returns (text, unknown placeholder names)."""
    unknown = []

    def sub(m):
        name = m.group(1)
        if name not in consts:
            unknown.append(name)
            return m.group(0)
        v = consts[name]
        return f"{v:,}" if isinstance(v, int) and abs(v) >= 1000 else f"{v:g}" if isinstance(v, float) else str(v)
    return PLACEHOLDER.sub(sub, text), unknown


# ------------------------------------------------------------------------------------------------ facts
def text_facts(box: dict, prompts: dict[str, str], consts: dict) -> dict:
    """What the box's words depend on, with every line number and number value left out, so a change elsewhere in
    a file or a changed constant does not count as a change to the box."""
    strip = lambda s: re.sub(r"\s*\((?:[\w./-]+\.(?:py|txt|md)):\d+\)|:\d+\b", "", str(s))

    def anchor(a):
        r = {"key": a["key"], "signature": a.get("signature"), "doc": a.get("doc"),
             "callees": sorted(a.get("callees", []))}
        if a.get("kind") == "class":
            r["fields"] = [(f["name"], f["type"]) for f in a.get("fields", [])]
            r["methods"] = [m["signature"] for m in a.get("methods", [])]
        return r
    return {"title": box["title"], "kind": box["kind"],
            "anchors": [anchor(a) for a in box["anchors"]],
            "guards": sorted({(g["kind"], g["code"], g["effect"]) for g in box.get("guards", [])}),
            "checks": sorted({(c["level"], NUM.sub("#", strip(c["msg"]))) for c in box.get("checks", [])}),
            "prompts": {s: hashlib.sha256(prompts.get(s, "").encode()).hexdigest()[:12]
                        for s in box.get("prompts", []) + box.get("alt_prompts", [])},
            "numbers": sorted(consts)}


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def facts_diff(old: dict | None, new: dict) -> str:
    a = json.dumps(old or {}, indent=1, sort_keys=True, default=str).splitlines()
    b = json.dumps(new, indent=1, sort_keys=True, default=str).splitlines()
    return "\n".join(l for l in difflib.unified_diff(a, b, "before", "now", n=1, lineterm="")
                     if not l.startswith(("---", "+++")))[:6000]


# ------------------------------------------------------------------------------------------------ model
def make_llm():
    """The cheap model of the arch-text profile, or None (no key, or ARCH_TEXT_LLM=off)."""
    if os.environ.get("ARCH_TEXT_LLM", "").lower() in ("off", "0", "no"):
        return None
    sys.path.insert(0, str(ROOT))
    from amoeba.llm.client import OpenAICompatibleClient
    from amoeba.llm.profiles import get_profile
    p = get_profile(os.environ.get("ARCH_TEXT_PROFILE") or PROFILE)
    key = os.environ.get("AMOEBA_API_KEY") or (os.environ.get(p.api_key_env) if p.api_key_env else None)
    if not key:
        return None
    return OpenAICompatibleClient(base_url=os.environ.get("AMOEBA_BASE_URL") or p.base_url, api_key=key, model=p.model,
                                  temperature=0.0, max_tokens=p.max_tokens or MAX_REPLY_TOKENS,
                                  merge_system=p.merge_system, reasoning_effort=p.reasoning_effort)


def ask_model(llm, box: dict, old: dict, diff: str, facts: dict, consts: dict):
    lines = "\n".join(f"{i}. {t}" for i, t in enumerate([old["sentence"], *old["what"]]))
    user = ASK.format(title=box["title"], kind=box["kind"], lines=lines, diff=diff or "(none)",
                      facts=json.dumps(facts, sort_keys=True, default=str)[:6000],
                      consts=", ".join(f"{{{k}}}={v}" for k, v in sorted(consts.items())) or "none")
    return llm.chat_messages([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], seed=0)


def parse_reply(content: str) -> dict | None:
    m = re.search(r"\{.*\}", content or "", re.S)
    try:
        r = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None
    if not isinstance(r, dict) or r.get("verdict") not in ("keep", "rewrite"):
        return None
    if r["verdict"] == "rewrite":
        ch = r.get("changes")
        if not isinstance(ch, list) or not ch or not all(
                isinstance(c, dict) and (c.get("line") == "new" or isinstance(c.get("line"), int))
                and (c.get("text") is None or isinstance(c.get("text"), str)) for c in ch):
            return None
    return r


def apply_changes(sentence: str, what: list[str], changes: list[dict]) -> tuple[str, list[str]] | None:
    """The model's line edits on the old text; everything it did not name stays word for word. None if an edit
    points at a line that does not exist or deletes the summary."""
    lines: list[str | None] = [sentence, *what]
    added = []
    for c in changes:
        text = re.sub(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", "", c["text"]).strip() if c.get("text") is not None else None
        if c["line"] == "new":
            if text:
                added.append(text)
        elif 0 <= c["line"] < len(lines) and not (c["line"] == 0 and not text):
            lines[c["line"]] = text
        else:
            return None
    return lines[0], [l for l in lines[1:] if l] + added


# ------------------------------------------------------------------------------------------------ update
def _publish(b: dict, e: dict, consts: dict, h: str) -> None:
    """The box record the page shows: the text with its numbers filled in, and where the text came from."""
    b["sentence_tpl"], b["what_tpl"] = e["sentence"], e["what"]
    b["sentence"] = fill(e["sentence"], consts)[0]
    b["what"] = [fill(w, consts)[0] for w in e["what"]]
    b["numbers"] = consts
    b["text_source"] = e["source"]
    b["text_stale"] = e.get("stale")
    b["text_hash"] = h


def update_texts(boxes: list[dict], F, C: list[dict], prompts: dict[str, str], hand: dict[str, dict],
                 llm="auto", commit: str = "") -> dict:
    """Fill each box's sentence/what from the cache, the hand text or the model; returns this rebuild's log line."""
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    log = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "commit": commit, "boxes": 0,
           "unchanged": 0, "hand": 0, "checked": 0, "kept": 0, "rewritten": 0, "stale": 0, "rejected": 0,
           "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "model": None,
           "rewritten_boxes": [], "stale_boxes": []}
    client = None
    for b in boxes:
        if b.get("status") == "ref":
            continue
        log["boxes"] += 1
        consts = numeric_facts(F, b, C)
        facts = text_facts(b, prompts, consts)
        h = digest(facts)
        seed = hand[b["id"]]
        s_tpl, _, _ = templatize(seed["sentence"], consts)
        w_tpl = [templatize(w, consts)[0] for w in seed["what"]]
        seed_hash = digest([seed["sentence"], seed["what"]])
        e = cache.get(b["id"])
        if e is None or e.get("seed_hash") != seed_hash:           # new box, or its hand text was edited
            e = {"seed_hash": seed_hash, "facts_hash": h, "facts": facts, "sentence": s_tpl, "what": w_tpl,
                 "source": "hand", "checked_at": commit}
            log["hand"] += 1
        elif e["facts_hash"] == h:
            log["unchanged"] += 1
        else:                                                        # the code under the box changed
            if client is None:
                client = make_llm() if llm == "auto" else llm or False
            if not client:
                e["stale"] = "the code under this box changed; no model was available to re-check the text"
                log["stale"] += 1
                log["stale_boxes"].append(b["id"])
            else:
                log["checked"] += 1
                log["model"] = client.model
                try:
                    resp = ask_model(client, b, e, facts_diff(e.get("facts"), facts), facts, consts)
                except Exception as ex:                              # an API error never breaks the build
                    e["stale"] = f"re-check failed: {type(ex).__name__}: {str(ex)[:120]}"
                    log["stale"] += 1
                    log["stale_boxes"].append(b["id"])
                    cache[b["id"]] = e
                    _publish(b, e, consts, h)
                    continue
                log["llm_calls"] += 1
                log["input_tokens"] += resp.input_tokens
                log["output_tokens"] += resp.output_tokens
                log["reasoning_tokens"] += resp.reasoning_tokens
                r = parse_reply(resp.content)
                new = None
                edited = apply_changes(e["sentence"], e["what"], r["changes"]) if r and r["verdict"] == "rewrite" else None
                if r and r["verdict"] == "rewrite" and edited is None:
                    r = None
                if r and r["verdict"] == "rewrite":
                    s2, _, left_s = templatize(edited[0], consts)
                    w2 = [templatize(w, consts) for w in edited[1]]
                    left = left_s + [x for _, _, l in w2 for x in l]
                    unknown = fill(s2 + " ".join(w for w, _, _ in w2), consts)[1]
                    if left or unknown:                              # a figure the code does not hold: not accepted
                        r = None
                    else:
                        new = (s2, [w for w, _, _ in w2])
                if r is None:
                    e["stale"] = "the model's reply was unusable or wrote a number the code does not hold"
                    log["rejected"] += 1
                    log["stale_boxes"].append(b["id"])
                else:
                    if new:
                        e["sentence"], e["what"], e["source"] = new[0], new[1], "model: rewritten"
                        log["rewritten"] += 1
                        log["rewritten_boxes"].append(b["id"])
                    else:
                        e["source"] = "model: kept" if e["source"] != "hand" else "hand (model: still true)"
                        log["kept"] += 1
                    e.update(facts_hash=h, facts=facts, checked_at=commit, model=client.model)
                    e.pop("stale", None)
        cache[b["id"]] = e
        _publish(b, e, consts, h)
    for gone in set(cache) - {b["id"] for b in boxes}:
        cache.pop(gone)
    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True, ensure_ascii=False, default=str) + "\n",
                     encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(log, ensure_ascii=False) + "\n")
    return log
