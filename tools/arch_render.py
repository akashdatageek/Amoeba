"""Render docs/arch/phase1.html from docs/arch/architecture.json (never hand-edit the HTML).

    python tools/arch_render.py            # render, then check every file:line against the commit it names
    python tools/arch_render.py --no-check

Layout (box positions, arrows) lives here; every word about the code comes from architecture.json.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCH = ROOT / "docs" / "arch"
TITLE = "Amoeba Phase 1 As-Built"

# ------------------------------------------------------------------------------------------------ layout
VIEWS = {
    "overview": {"h": 330, "label": "Phase 1 overview", "heading": "PHASE 1 · THREE BOXES, AS BUILT",
                 "note": "Click a box to open it. Colour says who decides; the badge says whether the code matches the plan."},
    "task": {"h": 350, "label": "1 · Task", "heading": "INSIDE BOX 1 · TASK",
             "note": "Nothing in this box calls an AI. The known answer is only used for scoring after Box 3."},
    "plan": {"h": 640, "label": "2 · Plan a new team", "heading": "INSIDE BOX 2 · PLAN A NEW TEAM",
             "note": "At most three rounds of three AI calls. Everything after the loop is plain code, and it is what keeps a sloppy draft out."},
    "run": {"h": 700, "label": "3 · Team runs the task", "heading": "INSIDE BOX 3 · TEAM RUNS THE TASK",
            "note": "Two runners, chosen when the run starts. Both write the same log and the same result record."},
}
L = {  # id: (x, y, w, h)
    "ov_task": (30, 60, 250, 150), "ov_plan": (365, 60, 300, 150), "ov_run": (750, 60, 300, 150),
    "ov_leave": (30, 245, 1125, 68),
    "toy_source": (30, 60, 240, 130), "free_text": (30, 210, 240, 100), "task_record": (370, 105, 230, 120),
    "handoff": (670, 115, 210, 100), "scoring": (930, 95, 230, 140),
    "planner": (50, 96, 215, 140), "split": (295, 96, 185, 140), "agent_obs": (510, 84, 270, 96),
    "plan_obs": (510, 196, 270, 110), "envelope": (50, 420, 270, 110), "checks": (830, 70, 330, 150),
    "instantiate": (830, 290, 330, 130), "teamconfig": (440, 470, 250, 110),
    "teamconfig@run": (30, 60, 190, 90), "interpreter": (250, 60, 200, 98),
    "each_step": (510, 110, 180, 130), "helper": (715, 110, 215, 140), "read_action": (955, 110, 195, 140),
    "solver": (510, 400, 195, 130), "critics": (730, 400, 205, 140), "disagree": (960, 400, 190, 140),
    "trace": (30, 175, 420, 95), "runresult": (30, 290, 420, 90),
    "tools": (30, 400, 420, 80), "client": (30, 530, 205, 128), "toymock": (245, 530, 205, 128),
}
DECOR = {  # static enclosures, captions and loop arrows (text filled from data where it states a fact)
    "plan": [("group", 30, 56, 770, 320), ("lbl", 44, 76, "loop_plan"),
             ("loop", "M645 306 V338 H157 V236", "loop_plan_cap", 400, 358)],
    "run": [("group", 490, 60, 670, 270), ("hd", 505, 82, "STEP BY STEP (flat) · AutoAgents Group"),
            ("loop", "M1052 250 V290 H822 V250", "loop_flat_cap", 830, 310),
            ("group", 490, 350, 670, 290), ("hd", 505, 372, "ONE WRITER WITH REVIEWERS (boss + reviewers) · AgentVerse"),
            ("loop", "M1055 540 V580 H607 V530", "loop_boss_cap", 830, 600),
            ("hd", 30, 518, "SHARED PARTS")],
}
EDGES = [  # (view, from, to, path, label, data key, label x, label y)
    ("overview", "ov_task", "ov_plan", "M280 135 H365", "Task", "Task", 322, 127),
    ("overview", "ov_plan", "ov_run", "M665 135 H750", "TeamConfig", "TeamConfig", 707, 127),
    ("overview", "ov_run", "answer", "M1050 135 H1085", "", "answer", 0, 0),
    ("task", "toy_source", "task_record", "M270 125 H320 V150 H370", "has an answer", "Task", 276, 117),
    ("task", "free_text", "task_record", "M270 260 H320 V185 H370", "no answer", "FreeTask", 276, 280),
    ("task", "task_record", "handoff", "M600 165 H670", "Task", "Task", 622, 157),
    ("plan", "planner", "split", "M265 166 H295", "", "raw_text", 0, 0),
    ("plan", "split", "agent_obs", "M480 150 H495 V132 H510", "", "sections", 0, 0),
    ("plan", "split", "plan_obs", "M480 182 H495 V251 H510", "", "sections", 0, 0),
    ("plan", "plan_obs", "checks", "M800 200 H830", "", "sections", 0, 0),
    ("plan", "envelope", "checks", "M320 440 H815 V205 H830", "allowed tools", "Envelope", 560, 432),
    ("plan", "envelope", "planner", "M110 420 V236", "tool list", "Envelope", 116, 400),
    ("plan", "checks", "instantiate", "M995 220 V290", "Draft", "Draft", 1003, 262),
    ("plan", "instantiate", "teamconfig", "M995 420 V525 H690", "TeamConfig", "TeamConfig", 860, 517),
    ("run", "teamconfig@run", "interpreter", "M220 105 H250", "", "TeamConfig", 0, 0),
    ("run", "interpreter", "each_step", "M450 90 H475 V175 H510", "flat", "PlanStep", 482, 168),
    ("run", "interpreter", "solver", "M450 120 H468 V465 H510", "boss", "AgentSpec", 474, 458),
    ("run", "each_step", "helper", "M690 175 H715", "", "step_input", 0, 0),
    ("run", "helper", "read_action", "M930 180 H955", "", "worker_sections", 0, 0),
    ("run", "solver", "critics", "M705 465 H730", "", "_Msg", 0, 0),
    ("run", "critics", "disagree", "M935 470 H960", "", "reviews", 0, 0),
]
KIND_WHO = {"llm": "AI writes text", "code": "Plain code decides", "data": "Record passed along",
            "plain": "Input / output", "top": "See inside"}
STATUS = {"built": ("✓", "built"), "differs": ("≠", "differs"), "missing": ("✗", "missing"), "extra": ("+", "extra")}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def wrap(text: str, width_px: float, px: float) -> list[str]:
    per = max(8, int(width_px / px))
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + (1 if cur else 0) > per:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(cur)
    return lines


def short(path: str) -> str:
    return path[len("amoeba/"):] if path.startswith("amoeba/") else path


def trimj(v, n=420) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1, default=str)
    return s if len(s) <= n else s[:n] + f" … [+{len(s) - n} chars]"


# ------------------------------------------------------------------------------------------------ cards
def dl(pairs) -> str:
    code_cls = ' class="c"'
    return "<dl>" + "".join(f"<dt>{esc(k)}</dt><dd{code_cls if k == 'Code' else ''}>{esc(v)}</dd>"
                            for k, v in pairs if v) + "</dl>"


def box_card(b: dict, A: dict) -> str:
    a0 = b["anchors"][0] if b["anchors"] else None
    inp = out = code = ""
    if a0 and a0["kind"] == "function":
        m = re.match(r"\w+\((.*)\)(?: -> (.*))?$", a0["signature"])
        inp = ", ".join(p.split(":")[0].split("=")[0].strip() for p in re.split(r",\s*(?![^\[]*\])", m.group(1))
                        if p.strip() and p.strip() not in ("self", "*")) if m else ""
        out = (m.group(2) or "") if m else ""
        code = a0["signature"]
    elif a0:
        inp = ""
        out = "fields: " + ", ".join(f["name"] for f in a0["fields"])
        code = f"class {a0['name']}({', '.join(a0['bases'])})"
    limits = "; ".join(c["msg"].split(" (")[0] for c in b["checks"] if c["level"] == "ok" and ":" in c["msg"]
                       and re.search(r":\s*\d", c["msg"]))
    fails = "; ".join(f"{g['code'][:60]} → {g['effect'][:40]}" for g in (b["guards"] + b.get("output_guards", []))
                      if g["kind"] in ("reject", "fallback") and g["effect"] != "choose value")[:260]
    cost = ""
    for topo in ("flat", "boss_reviewers"):
        pb = A["sample"]["runs"][topo]["per_box"].get(b["id"])
        if pb and pb["calls"]:
            cost += f"{topo}: {pb['calls']} call(s), {pb['tokens']} tokens · "
    files = " · ".join(dict.fromkeys(f"{short(a['path'])}:{a['line']}" for a in b["anchors"]))
    later = (b.get("plan_card") or {}).get("Later", "")
    return dl([("Description", b["sentence"]), ("Input", inp), ("Output", out), ("Who decides", KIND_WHO.get(b["kind"], "")),
               ("Limits", limits), ("If it fails", fails), ("Files", files), ("Code", code),
               ("Cost (sample run)", cost.rstrip(" ·")), ("Later (plan)", later)])


def shield_card(b: dict) -> str:
    rows = b["guards"] + b.get("output_guards", [])
    items = "".join(f"<li><code>{esc(g['code'][:90])}</code> → {esc(g['effect'][:50])} "
                    f"<span class='fl'>{esc(short(g['path']))}:{g['line']}</span></li>" for g in rows[:9])
    more = f"<li>… and {len(rows) - 9} more in the drawer (Code tab)</li>" if len(rows) > 9 else ""
    return f"<b>Plain-code checks on AI output here</b><ul class='gl'>{items}{more}</ul>"


def edge_card(key: str, A: dict) -> str:
    S = A["sample"]
    flat, boss = S["runs"]["flat"], S["runs"]["boss_reviewers"]
    worker = next((c for c in flat["calls"] if c["kind"] == "worker"), None)
    step_input = ""
    if worker:
        u = worker["messages"][-1]["content"]
        step_input = "\n".join(l for l in u.split("\n") if l.startswith(("# Task", "# Execution Result")))
    special = {
        "answer": ("str (the answer)", "", flat["result"]["answer"]),
        "raw_text": ("str (the planner's whole reply)", "", flat["examples"]["raw_text"]),
        "sections": ("dict[str, str] (section title → text)", "", flat["examples"]["sections"]),
        "step_input": ("str (step text + everything earlier steps published)", "", step_input),
        "worker_sections": ("dict[str, str] (CurrentStep, Action, ActionInput …)", "", (flat["examples"]["worker_sections"] or [{}])[0]),
        "reviews": ("list of (agree, reason) per reviewer", "", boss["examples"]["critic_verdicts"]),
        "FreeTask": ("Task", "family='freeform', ground_truth=None", S.get("free_text_task", "unknown")),
    }
    examples = {"Task": S["task"], "TeamConfig": flat["team_trimmed"], "Draft": {k: v for k, v in flat["plan_trimmed"].items() if k != "raw_draft"},
                "PlanStep": (flat["team_trimmed"]["plan"] or [None])[0], "AgentSpec": boss["examples"]["solver_agent"],
                "Envelope": flat["examples"]["envelope"],
                "_Msg": {"sender": next((a["name"] for a in boss["team_trimmed"]["agents"].values() if a["role"] == "solver"), "?"),
                         "content": boss["result"]["answer"]}}
    if key in special:
        typ, fields, ex = special[key]
        if key == "FreeTask":
            fields = ", ".join(f["name"] for f in A["data_types"]["Task"]["fields"]) + " (" + special[key][1] + ")"
    else:
        dt = A["data_types"].get(key)
        typ = f"{key}  ({short(dt['path'])}:{dt['line']})" if dt else key
        fields = ", ".join(f"{f['name']}: {f['type']}" for f in dt["fields"]) if dt else "unknown"
        ex = examples.get(key, "unknown")
    return (f"<b>Carries: {esc(typ)}</b>" + (f"<div class='ef'>{esc(fields)}</div>" if fields else "")
            + f"<div class='ex'><span>example from the sample run</span><pre>{esc(trimj(ex, 380))}</pre></div>")


# ------------------------------------------------------------------------------------------------ svg
def box_svg(b: dict, A: dict, changed: set) -> str:
    x, y, w, h = L[b["id"]]
    ref = b.get("ref")
    src_b = next(bb for bb in A["boxes"] if bb["id"] == ref) if ref else b
    status = src_b["status"]
    sym, word = STATUS.get(status, ("", ""))
    top = b["kind"] == "top"
    badge_w = int(len(word) * 6.1 + 22)
    parts = []
    cls = "boxg tip" + (" hit" if top else "") + (" guarded" if src_b.get("shield") else "") + \
          (" changed" if src_b["id"] in changed else "") + (" ai" if b["kind"] == "llm" else "")
    attrs = (f'class="{cls}" id="b-{esc(b["id"])}" data-id="{esc(src_b["id"])}" data-view="{esc(b.get("opens", ""))}" '
             f'tabindex="0" role="button" data-card="{esc(box_card(src_b, A))}" aria-label="{esc(b["title"])}"')
    rect_cls = "big" if top else f"box {b['kind']}"
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{8 if top else 6}" class="{rect_cls}"/>')
    # badge (top-right), shield and ✦ to its left
    bx = x + w - badge_w - 6
    parts.append(f'<g class="badge st-{status}"><rect x="{bx}" y="{y + 7}" width="{badge_w}" height="17" rx="8.5"/>'
                 f'<text x="{bx + badge_w / 2}" y="{y + 19.5}" text-anchor="middle">{sym} {word}</text></g>')
    ix = bx - 6
    if src_b.get("shield"):
        ix -= 16
        parts.append(f'<g class="shield tip2" tabindex="0" data-card="{esc(shield_card(src_b))}" aria-label="guards">'
                     f'<path d="M{ix + 7} {y + 7} l6 2.4 v4.4 c0 3.8 -2.7 6.4 -6 7.6 c-3.3 -1.2 -6 -3.8 -6 -7.6 v-4.4 z"/></g>')
    if src_b["id"] in changed:
        ix -= 14
        parts.append(f'<text x="{ix + 2}" y="{y + 20}" class="star" aria-label="changed since last build">✦</text>')
    title_room = (ix - (x + 10)) if not top else w - 2 * badge_w - 20
    if top:
        tl = wrap(b["title"], w - 40, 7.8)
        ty = y + 44
        for i, t in enumerate(tl):
            parts.append(f'<text x="{x + w / 2}" y="{ty + i * 18}" text-anchor="middle" class="t">{esc(t)}</text>')
        sl = wrap(b["sentence"], w - 36, 5.9)
        for i, t in enumerate(sl):
            parts.append(f'<text x="{x + w / 2}" y="{ty + len(tl) * 18 + 4 + i * 14}" text-anchor="middle" class="s">{esc(t)}</text>')
        parts.append(f'<text x="{x + w / 2}" y="{y + h - 12}" text-anchor="middle" class="open">CLICK TO OPEN ▸</text>')
        parts.append(f'<text x="{x + 12}" y="{y + h - 11}" class="glyph info" role="button" aria-label="Details">ⓘ</text>')
        need = 44 + len(tl) * 18 + 4 + len(sl) * 14 + 20
    else:
        tl = wrap(b["title"], title_room, 7.0)
        for i, t in enumerate(tl):
            parts.append(f'<text x="{x + 10}" y="{y + 20 + i * 16}" class="t2">{esc(t)}</text>')
        sy = y + 20 + len(tl) * 16 + 2
        sl = wrap(b["sentence"], w - 20, 5.75)
        for i, t in enumerate(sl):
            parts.append(f'<text x="{x + 10}" y="{sy + i * 14}" class="s">{esc(t)}</text>')
        src = f"{short(src_b['src'])}" if src_b.get("src") and src_b["src"] != "unknown" else "unknown"
        parts.append(f'<text x="{x + 10}" y="{y + h - 9}" class="src">{esc(src)}</text>')
        parts.append(f'<text x="{x + 10}" y="{y + h - 9}" class="cost" id="cost-{esc(b["id"])}"></text>')
        need = 20 + len(tl) * 16 + 2 + len(sl) * 14 + 14
    parts.append(f'<text x="{x + w - 17}" y="{y + h - 8}" class="glyph edit" role="button" aria-label="Request a change">✎</text>')
    if need > h:
        print(f"  ! box {b['id']} needs {need}px, has {h}px", file=sys.stderr)
    return f'<g {attrs}>' + "".join(parts) + "</g>"


def edge_svg(e, A) -> str:
    view, a, b, d, label, key, lx, ly = e
    card = edge_card(key, A)
    anchor = ' text-anchor="middle"' if view == "overview" else ""
    lab = f'<text x="{lx}" y="{ly}" class="lbl"{anchor}>{esc(label)}</text>' if label else ""
    return (f'<g class="edge tip" tabindex="0" data-card="{esc(card)}" data-from="{a}" data-to="{b}" aria-label="arrow {esc(label or key)}">'
            f'<path d="{d}" class="arrow" marker-end="url(#ah)"/><path d="{d}" class="hitline"/>{lab}</g>')


def decor_svg(view, A) -> str:
    consts = {c["name"]: c for c in A["constants"]}
    fields = {f"{c['name']}.{f['name']}": f for c in A["classes"] for f in c["fields"]}
    mr = consts.get("MAX_ROUNDS")
    mt = fields.get("Limits.max_turns")
    mi = fields.get("TeamConfig.max_inner_turns")
    texts = {
        "loop_plan": f"repeat up to {mr['value'] if mr else 'unknown'} rounds; stop early when both checkers say "
                     f"'No Suggestions' in the same round ({short(mr['path'])}:{mr['line']})" if mr else "unknown",
        "loop_plan_cap": "the checkers' latest suggestions go back to the planner for the next round",
        "loop_flat_cap": f"up to {mt['default'] if mt else 'unknown'} turns per step (config/schema.py:{mt['line'] if mt else '?'}); "
                         "the last turn adds a 'please synthesize' hint",
        "loop_boss_cap": f"up to {mi['default'] if mi else 'unknown'} review rounds (config/schema.py:{mi['line'] if mi else '?'}); "
                         "unreadable reviews count as agreement",
    }
    out = []
    for item in DECOR.get(view, []):
        if item[0] == "group":
            out.append(f'<rect x="{item[1]}" y="{item[2]}" width="{item[3]}" height="{item[4]}" rx="8" class="group"/>')
        elif item[0] == "lbl":
            out.append(f'<text x="{item[1]}" y="{item[2]}" class="lbl">{esc(texts[item[3]])}</text>')
        elif item[0] == "hd":
            out.append(f'<text x="{item[1]}" y="{item[2]}" class="hd">{esc(item[3])}</text>')
        elif item[0] == "loop":
            out.append(f'<path d="{item[1]}" class="arrow loop" marker-end="url(#ahp)"/>'
                       f'<text x="{item[3]}" y="{item[4]}" text-anchor="middle" class="lbl loopl">{esc(texts[item[2]])}</text>')
    if view == "overview":
        out.append('<rect x="1085" y="110" width="75" height="50" rx="6" class="box plain"/>'
                   '<text x="1122" y="139" text-anchor="middle" class="t2">Answer</text>')
    # one caption naming the deliberate deviations marked in this view's code
    ids = sorted({d["id"] for b in A["boxes"] if b["view"] == view for d in b.get("deviations", []) if d["id"]},
                 key=lambda s: int(s[1:]))
    n = len({(d["path"], d["line"]) for b in A["boxes"] if b["view"] == view for d in b.get("deviations", [])})
    if view != "overview":
        cap = (f"Deliberate departures from AutoAgents / AgentVerse marked in this view's code: {n} note(s)"
               + (f" ({', '.join(ids)})" if ids else "") + " — open a box's “Plan vs built” tab for each.") if n else \
              "No departures from the source projects are marked in this view's code."
        out.append(f'<text x="30" y="{VIEWS[view]["h"] - 14}" class="s cap">{esc(cap)}</text>')
    return "".join(out)


# ------------------------------------------------------------------------------------------------ page
CSS = r"""
:root{--bg:#f7f8f6;--ink:#1d221f;--muted:#5d665f;--line:#8c948e;--llm-fill:#ece8f7;--llm-line:#6b5bb5;--code-fill:#e3f1e8;--code-line:#2f7d57;
--data-fill:#fff7e3;--data-line:#b8860b;--person-fill:#fbeedd;--person-line:#c47a1f;--plain-fill:#fff;--plain-line:#8c948e;--p1:#1f5fbf;--p1-fill:#e3ecfa;--hover:#d7e4fa;
--ok:#2f7d57;--ok-fill:#e3f1e8;--warn:#9a5b00;--warn-fill:#fdf0d8;--bad:#b3261e;--bad-fill:#fbe4e2;--ext:#1f5fbf;--ext-fill:#e3ecfa;--panel:#fff;--mark:#fff1a8}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15181a;--ink:#e8ebe7;--muted:#a3aba5;--line:#6b736d;--llm-fill:#2b2544;--llm-line:#a798e8;
--code-fill:#1d3328;--code-line:#6cc596;--data-fill:#3a3115;--data-line:#e2b94a;--person-fill:#3a2a16;--person-line:#e0a45c;--plain-fill:#20252a;--plain-line:#6b736d;
--p1:#8fb6f5;--p1-fill:#1c2a40;--hover:#26385a;--ok:#6cc596;--ok-fill:#1d3328;--warn:#e2b94a;--warn-fill:#3a3115;--bad:#f2a49c;--bad-fill:#44201d;--ext:#8fb6f5;--ext-fill:#1c2a40;--panel:#1b1f22;--mark:#5a4a00}}
:root[data-theme="dark"]{--bg:#15181a;--ink:#e8ebe7;--muted:#a3aba5;--line:#6b736d;--llm-fill:#2b2544;--llm-line:#a798e8;
--code-fill:#1d3328;--code-line:#6cc596;--data-fill:#3a3115;--data-line:#e2b94a;--person-fill:#3a2a16;--person-line:#e0a45c;--plain-fill:#20252a;--plain-line:#6b736d;
--p1:#8fb6f5;--p1-fill:#1c2a40;--hover:#26385a;--ok:#6cc596;--ok-fill:#1d3328;--warn:#e2b94a;--warn-fill:#3a3115;--bad:#f2a49c;--bad-fill:#44201d;--ext:#8fb6f5;--ext-fill:#1c2a40;--panel:#1b1f22;--mark:#5a4a00}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:"IBM Plex Sans",system-ui,sans-serif;margin:0;padding:24px 16px}
.wrap{max-width:1180px;margin:0 auto}
h1{font-size:22px;font-weight:600;margin:0 0 4px}
h2{font-size:15px;margin:22px 0 8px}
.sub{color:var(--muted);font-size:14px;margin:0 0 10px;max-width:80ch}
code,.mono{font-family:"IBM Plex Mono",monospace;font-size:12px}
.summary{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;font-size:13.5px;padding:8px 12px;border:1px solid var(--line);border-radius:6px;background:var(--panel);margin:0 0 10px}
.summary b{font-weight:600}
.pill{display:inline-block;border-radius:9px;padding:1px 8px;font-size:12px;font-weight:600}
.pill.built{background:var(--ok-fill);color:var(--ok)}.pill.differs{background:var(--warn-fill);color:var(--warn)}
.pill.missing,.pill.failed,.pill.none{background:var(--bad-fill);color:var(--bad)}.pill.extra{background:var(--ext-fill);color:var(--ext)}
.pill.passed{background:var(--ok-fill);color:var(--ok)}.pill.muted{background:var(--p1-fill);color:var(--muted)}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:12.5px;margin:0 0 10px;align-items:center}
.legend span{display:inline-flex;align-items:center;gap:6px}
.sw{width:20px;height:13px;border-radius:3px;border:1.5px solid;display:inline-block}
.sw.llm{background:var(--llm-fill);border-color:var(--llm-line)}.sw.code{background:var(--code-fill);border-color:var(--code-line)}
.sw.data{background:var(--data-fill);border-color:var(--data-line)}.sw.plain{background:var(--plain-fill);border-color:var(--plain-line)}
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 10px;font-size:13px}
.btn{font:inherit;font-size:13px;font-weight:600;border-radius:6px;padding:5px 12px;cursor:pointer;border:1.5px solid var(--p1);background:var(--p1-fill);color:var(--p1)}
.btn[aria-pressed="true"],.btn.primary{background:var(--p1);color:#fff}
.btn:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--p1);outline-offset:2px}
select,input[type=search]{font:inherit;font-size:13px;padding:5px 8px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink)}
input[type=search]{min-width:220px}
.crumb{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:0 0 8px;font-size:13.5px;min-height:32px}
.crumb .here{color:var(--muted)}
.panel{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--plain-fill)}
svg{display:block;min-width:900px;width:100%;height:auto;font-family:"IBM Plex Sans",system-ui,sans-serif}
[hidden]{display:none!important}
.box{stroke-width:1.5}.box.llm{fill:var(--llm-fill);stroke:var(--llm-line)}.box.code{fill:var(--code-fill);stroke:var(--code-line)}
.box.data{fill:var(--data-fill);stroke:var(--data-line)}.box.plain{fill:var(--plain-fill);stroke:var(--plain-line)}
rect.big{fill:var(--p1-fill);stroke:var(--p1);stroke-width:3}
.hit{cursor:pointer}.hit:hover rect.big,.hit:focus-visible rect.big{fill:var(--hover)}
.t{fill:var(--ink);font-size:14px;font-weight:600}.t2{fill:var(--ink);font-size:12.5px;font-weight:600}
.s{fill:var(--muted);font-size:11px}.src{fill:var(--muted);font-size:10px;font-family:"IBM Plex Mono",monospace}
.cost{fill:var(--llm-line);font-size:10.5px;font-weight:600;display:none}
body.costmode .cost{display:inline}body.costmode .boxg.ai .src{display:none}
.open{fill:var(--p1);font-size:10.5px;font-weight:600;letter-spacing:.05em}
.arrow{stroke:var(--line);stroke-width:1.6;fill:none}.arrow.loop{stroke:var(--llm-line)}
.hitline{stroke:transparent;stroke-width:12;fill:none;pointer-events:stroke}
.edge{cursor:help}.edge:hover .arrow,.edge:focus-visible .arrow{stroke:var(--p1);stroke-width:2.4}
.lbl{fill:var(--muted);font-size:11px}.loopl{fill:var(--llm-line)}.hd{fill:var(--muted);font-size:11px;font-weight:600;letter-spacing:.06em}
.group{fill:none;stroke:var(--line);stroke-dasharray:6 4;stroke-width:1.2}
.cap{font-style:italic}
.badge rect{stroke-width:1}.badge text{font-size:10.5px;font-weight:600}
.st-built rect{fill:var(--ok-fill);stroke:var(--ok)}.st-built text{fill:var(--ok)}
.st-differs rect{fill:var(--warn-fill);stroke:var(--warn)}.st-differs text{fill:var(--warn)}
.st-missing rect{fill:var(--bad-fill);stroke:var(--bad)}.st-missing text{fill:var(--bad)}
.st-extra rect{fill:var(--ext-fill);stroke:var(--ext)}.st-extra text{fill:var(--ext)}
.shield path{fill:var(--code-line);stroke:var(--code-line)}.shield{cursor:help}
.star{fill:var(--warn);font-size:13px}
.glyph{fill:var(--p1);font-size:13px;cursor:pointer}.glyph:hover{font-weight:700}
.boxg{cursor:pointer;transition:opacity .2s}.boxg:hover rect.box,.boxg:focus-visible rect.box{stroke-width:2.6}.boxg:focus-visible{outline:none}
body.guardsonly .boxg:not(.guarded),body.guardsonly .edge{opacity:.22}
.boxg.flash rect.box,.boxg.flash rect.big,.boxg.replay rect.box,.boxg.replay rect.big{stroke:var(--p1)!important;stroke-width:4!important}
.boxg.sel rect.box{stroke-width:3}
.notes{margin:10px 0 0;font-size:13.5px;line-height:1.5;color:var(--muted);max-width:95ch}
.tt{position:fixed;z-index:50;max-width:440px;background:var(--panel);color:var(--ink);border:1.5px solid var(--p1);border-radius:8px;padding:10px 12px;font-size:12.5px;line-height:1.45;box-shadow:0 6px 18px rgba(0,0,0,.16);opacity:0;pointer-events:none;transition:opacity .18s}
.tt.on{opacity:1}
.tt b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--p1);margin-bottom:4px}
.tt dl{margin:0;display:grid;grid-template-columns:max-content 1fr;gap:3px 10px}
.tt dt{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--p1);font-weight:600;padding-top:1px}
.tt dd{margin:0;overflow-wrap:anywhere}.tt dd.c{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--code-line)}
.tt pre{font-family:"IBM Plex Mono",monospace;font-size:11px;white-space:pre-wrap;margin:4px 0 0;max-height:220px;overflow:hidden}
.tt .ef{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted)}.tt .ex span{font-size:10.5px;text-transform:uppercase;color:var(--p1)}
.tt ul.gl{margin:0;padding-left:16px}.tt .fl{color:var(--muted);font-family:"IBM Plex Mono",monospace;font-size:10.5px}
.drawer{position:fixed;top:0;right:0;bottom:0;width:min(580px,100vw);background:var(--panel);border-left:1.5px solid var(--p1);box-shadow:-8px 0 24px rgba(0,0,0,.18);z-index:40;display:flex;flex-direction:column}
.drawer header{padding:12px 14px 8px;border-bottom:1px solid var(--line)}
.drawer h3{margin:0 0 4px;font-size:16px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.drawer .one{margin:0;color:var(--muted);font-size:13px}
.drawer .x{position:absolute;right:10px;top:8px}
.tabs{display:flex;flex-wrap:wrap;gap:4px;padding:8px 14px 0;border-bottom:1px solid var(--line)}
.tabs button{font:inherit;font-size:12.5px;padding:6px 10px;border:1px solid var(--line);border-bottom:none;border-radius:6px 6px 0 0;background:var(--bg);color:var(--ink);cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--p1);color:#fff;border-color:var(--p1)}
.tabbody{padding:12px 14px 40px;overflow:auto;font-size:13px;line-height:1.5;flex:1}
.tabbody h4{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--p1);margin:14px 0 6px}
.tabbody pre{font-family:"IBM Plex Mono",monospace;font-size:11.5px;white-space:pre-wrap;overflow-wrap:anywhere;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px;margin:4px 0 10px;max-height:420px;overflow:auto}
.tabbody table{border-collapse:collapse;width:100%;font-size:12px;margin:4px 0 10px}
.tabbody td,.tabbody th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
.tabbody th{font-size:11px;color:var(--muted);font-weight:600}
mark{background:var(--mark);color:inherit;border-radius:3px;padding:0 1px}
.lpcd{display:grid;grid-template-columns:1fr;gap:8px;margin:10px 0}
.lpcd div{border:1px solid var(--line);border-radius:6px;padding:8px 10px}.lpcd .ai{border-color:var(--llm-line);background:var(--llm-fill)}.lpcd .cd{border-color:var(--code-line);background:var(--code-fill)}
.warnline{color:var(--bad);font-weight:600}
.timeline{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--panel);max-height:320px;overflow-y:auto}
.timeline table{border-collapse:collapse;width:100%;font-size:12.5px;min-width:720px}
.timeline th,.timeline td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.timeline th{position:sticky;top:0;background:var(--panel);font-size:11.5px;color:var(--muted)}
.timeline tr.row{cursor:pointer}.timeline tr.row:hover{background:var(--hover)}.timeline tr.on{background:var(--p1-fill);outline:2px solid var(--p1)}
.timeline tr.det td{background:var(--bg)}.timeline pre{margin:0;font-family:"IBM Plex Mono",monospace;font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}
.changes{font-size:13px}.changes li{margin:2px 0}
.gloss{display:grid;grid-template-columns:minmax(0,16em) minmax(0,1fr);gap:4px 14px;font-size:13px;margin:0}
@media (max-width:640px){.gloss{grid-template-columns:minmax(0,1fr)}.gloss dd{margin-bottom:6px}input[type=search]{min-width:0;width:100%}}
.legend svg{min-width:0;width:14px;height:16px;display:inline-block}
.gloss dt{font-weight:600}.gloss dd{margin:0;color:var(--muted)}
.ov{position:fixed;inset:0;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;z-index:60;padding:16px}
.ed{background:var(--panel);color:var(--ink);border:1.5px solid var(--p1);border-radius:10px;width:min(560px,100%);padding:16px 18px}
.ed h2{margin:0 0 4px}.ed .box-id{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--muted);margin:0 0 10px}
.ed textarea{width:100%;min-height:120px;font:inherit;font-size:13.5px;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink);resize:vertical}
.ed .row{display:flex;gap:10px;justify-content:flex-end;margin-top:10px;align-items:center;flex-wrap:wrap}.ed .st{margin-right:auto;font-size:12.5px;color:var(--muted)}
.queue{display:inline-flex;gap:8px;align-items:center;font-size:12.5px;color:var(--muted);margin-left:auto}
.foot{margin-top:18px;font-size:12px;color:var(--muted)}
@media (prefers-reduced-motion: reduce){.tt,.boxg{transition:none}}
"""

JS = r"""
(function(){
var A = JSON.parse(document.getElementById('data').textContent);
var BOX = {}; A.boxes.forEach(function(b){ BOX[b.id] = b; });
var VIEWS = A.__views, cur = 'overview', topo = 'flat';
function $(s, r){ return (r||document).querySelector(s); }
function $$(s, r){ return Array.prototype.slice.call((r||document).querySelectorAll(s)); }
function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function j(v, n){ var s = typeof v === 'string' ? v : JSON.stringify(v, null, 1); if(s === undefined) s = 'unknown'; n = n || 2400; return s.length > n ? s.slice(0, n) + ' … [+' + (s.length - n) + ' chars]' : s; }
function short(p){ return (p||'').replace(/^amoeba\//, ''); }
function fl(o){ return o ? esc(o.path) + ':' + o.line : 'unknown'; }
// ---------------- views
function show(name){
  if(!VIEWS[name]) name = 'overview'; cur = name;
  Object.keys(VIEWS).forEach(function(k){ var el = document.getElementById('v-' + k); if(k === name) el.removeAttribute('hidden'); else el.setAttribute('hidden',''); });
  var c = $('#crumb'); c.innerHTML = '';
  if(name !== 'overview'){ var b = document.createElement('button'); b.type = 'button'; b.className = 'btn'; b.textContent = '◂ Back to overview'; b.onclick = function(){ go('overview'); }; c.appendChild(b); }
  var h = document.createElement('span'); h.className = 'here'; h.textContent = name === 'overview' ? 'Overview: click a box to open it' : 'Inside: ' + VIEWS[name].label; c.appendChild(h);
  $('#note').textContent = VIEWS[name].note; renderQueue();
}
function go(name){ try { history.replaceState(null, '', '#' + name); } catch(e){} show(name); }
window.addEventListener('hashchange', function(){ show(location.hash.slice(1)); });
// ---------------- hover cards
var tt = $('#tt'), hideT = null, curEl = null;
function place(x, y){ var p = 14, w = tt.offsetWidth, h = tt.offsetHeight, l = x + p, t = y + p;
  if(l + w > innerWidth - 8) l = x - w - p; if(l < 8) l = 8; if(t + h > innerHeight - 8) t = y - h - p; if(t < 8) t = 8;
  tt.style.left = l + 'px'; tt.style.top = t + 'px'; }
function showFor(el, x, y){ clearTimeout(hideT); curEl = el; tt.innerHTML = el.getAttribute('data-card') || ''; tt.classList.add('on'); tt.setAttribute('aria-hidden','false'); place(x, y); }
function hide(){ hideT = setTimeout(function(){ tt.classList.remove('on'); tt.setAttribute('aria-hidden','true'); curEl = null; }, 60); }
$$('.tip, .tip2').forEach(function(el){
  el.addEventListener('mouseenter', function(e){ if(el.classList.contains('tip2')) e.stopPropagation(); showFor(el, e.clientX, e.clientY); });
  el.addEventListener('mousemove', function(e){ if(el.classList.contains('tip2')) e.stopPropagation(); if(curEl !== el && el.classList.contains('tip') && curEl && curEl.classList.contains('tip2')) return; if(curEl === el) place(e.clientX, e.clientY); });
  el.addEventListener('mouseleave', function(e){ if(el.classList.contains('tip2')){ var box = el.closest('.boxg'); if(box){ showFor(box, e.clientX, e.clientY); return; } } hide(); });
  el.addEventListener('focus', function(){ var r = el.getBoundingClientRect(); showFor(el, r.left + r.width/2, r.bottom); });
  el.addEventListener('blur', hide);
});
document.addEventListener('scroll', hide, {passive:true});
// ---------------- drawer
var dr = $('#drawer'), drBox = null, drTab = 'what';
var TABS = [['what','What it does'],['code','Code'],['prompt','Prompt'],['example','Example'],['tests','Tests'],['plan','Plan vs built']];
function statusPill(s){ var m = {built:'✓ built', differs:'≠ differs', missing:'✗ missing', extra:'+ extra'}; return '<span class="pill ' + s + '">' + (m[s]||s) + '</span>'; }
function openDrawer(id, tab){
  var b = BOX[id]; if(b && b.ref) b = BOX[b.ref]; if(!b) return; drBox = b; drTab = tab || drTab;
  if(drTab === 'prompt' && !(b.prompts||[]).length) drTab = 'what';
  $$('.boxg.sel').forEach(function(e){ e.classList.remove('sel'); }); var g = document.getElementById('b-' + b.id); if(g) g.classList.add('sel');
  $('#drt').innerHTML = esc(b.title) + ' ' + statusPill(b.status) + (b.shield ? ' <span class="pill muted">shield: guarded</span>' : '');
  $('#dro').textContent = b.sentence;
  var tb = $('#drtabs'); tb.innerHTML = '';
  TABS.forEach(function(t){ if(t[0] === 'prompt' && !(b.prompts||[]).length) return; var bt = document.createElement('button'); bt.type='button'; bt.setAttribute('role','tab'); bt.textContent = t[1]; bt.setAttribute('aria-selected', t[0] === drTab ? 'true' : 'false'); bt.onclick = function(){ drTab = t[0]; openDrawer(b.id, t[0]); }; tb.appendChild(bt); });
  $('#drbody').innerHTML = RENDER[drTab](b); dr.removeAttribute('hidden');
}
function closeDrawer(){ dr.setAttribute('hidden',''); $$('.boxg.sel').forEach(function(e){ e.classList.remove('sel'); }); }
$('#drx').onclick = closeDrawer;
document.addEventListener('keydown', function(e){ if(e.key === 'Escape'){ if(!$('#ov').hasAttribute('hidden')) closeEditor(); else closeDrawer(); } });
function guardsTable(rows){ if(!rows.length) return '<p class="warnline">No plain-code check found here.</p>';
  return '<table><tr><th>kind</th><th>condition (exact code)</th><th>what happens</th><th>file:line</th></tr>' + rows.map(function(g){ return '<tr><td>' + esc(g.kind) + '</td><td><code>' + esc(g.code) + '</code></td><td>' + esc(g.effect) + '</td><td class="mono">' + fl(g) + '</td></tr>'; }).join('') + '</table>'; }
function shortKey(k){ return k.split('::').pop(); }
var RENDER = {
 what: function(b){
  var h = (b.what||[]).map(function(s){ return '<p>' + esc(s) + '</p>'; }).join('');
  h += '<h4>LLM proposes / code disposes</h4><div class="lpcd"><div class="ai"><b>The AI may suggest:</b> ' + esc(b.proposes||'unknown') + '</div><div class="cd"><b>Plain code checks before accepting:</b> ' + esc(b.disposes||'unknown') + '</div></div>';
  var g = (b.guards||[]).concat(b.output_guards||[]);
  h += '<h4>Checks on AI output here (' + g.length + ')</h4>' + (g.length ? '<ul>' + g.slice(0, 12).map(function(x){ return '<li><code>' + esc(x.code) + '</code> → ' + esc(x.effect) + '</li>'; }).join('') + (g.length > 12 ? '<li>… ' + (g.length - 12) + ' more in the Code tab</li>' : '') + '</ul>' : '<p class="muted">None: ' + (b.kind === 'llm' ? '<span class="warnline">nothing in this box checks the AI reply</span>' : 'no AI output is handled here') + '.</p>');
  var pb = A.sample.runs[topo].per_box[b.id]; if(pb) h += '<h4>Sample run (' + topo + ')</h4><p>' + pb.calls + ' AI call(s), ' + pb.tokens + ' tokens, ' + pb.ms + ' ms (time rounds to whole milliseconds; the stand-in AI answers instantly).</p>';
  return h; },
 code: function(b){
  var h = '';
  if(!b.anchors.length) h += '<p class="warnline">unknown: no code pointer resolved for this box.</p>';
  b.anchors.forEach(function(a){
   h += '<h4>' + (a.kind === 'class' ? 'class' : 'function') + ' · <span class="mono">' + esc(a.path) + ':' + a.line + '–' + a.end_line + '</span></h4>';
   if(a.kind === 'class'){ h += '<pre>class ' + esc(a.name) + '(' + esc(a.bases.join(', ')) + ')' + (a.decorators.length ? '   # @' + esc(a.decorators.join(' @')) : '') + '</pre>' + (a.doc ? '<p>' + esc(a.doc) + '</p>' : '');
     if(a.fields.length) h += '<table><tr><th>field</th><th>type</th><th>default</th><th>line</th></tr>' + a.fields.map(function(f){ return '<tr><td class="mono">' + esc(f.name) + '</td><td class="mono">' + esc(f.type) + '</td><td class="mono">' + esc(f.default == null ? '(required)' : f.default) + '</td><td class="mono">' + f.line + '</td></tr>'; }).join('') + '</table>';
     if(a.methods.length) h += '<table><tr><th>method</th><th>what it says</th></tr>' + a.methods.map(function(m){ return '<tr><td class="mono">' + esc(m.signature) + ' <span class="muted">:' + m.line + '</span></td><td>' + esc(m.doc) + '</td></tr>'; }).join('') + '</table>';
   } else { h += '<pre>def ' + esc(a.signature) + '</pre>' + (a.doc ? '<p>' + esc(a.doc) + '</p>' : '') + (a.range_note ? '<p class="muted">This box covers ' + esc(a.range_note) + ' of it.</p>' : '');
     h += '<p><b>Called by</b> ' + (a.callers.length ? a.callers.map(function(k){ return '<code>' + esc(shortKey(k)) + '</code>'; }).join(', ') : 'nothing in the repo (entry point or unused)') + '<br><b>Calls</b> ' + (a.callees.length ? a.callees.map(function(k){ return '<code>' + esc(shortKey(k)) + '</code>'; }).join(', ') : 'no repo functions') + '</p>'; }
  });
  h += '<h4>Guards: every check in this box\'s code</h4>' + guardsTable(b.guards||[]);
  if((b.output_guards||[]).length) h += '<h4>Checks applied to this AI\'s reply (in shared code)</h4>' + guardsTable(b.output_guards);
  if((b.ai_sites||[]).length) h += '<h4>AI call path (every call site on the way to the service)</h4><table><tr><th>call</th><th>in</th><th>seed</th><th>file:line</th></tr>' + b.ai_sites.map(function(s){ return '<tr><td class="mono">' + esc(s.call) + '</td><td class="mono">' + esc(shortKey(s.key)) + '</td><td class="mono">' + esc(s.seed) + '</td><td class="mono">' + fl(s) + '</td></tr>'; }).join('') + '</table>';
  return h; },
 prompt: function(b){
  var h = '', P = {}; A.prompts.forEach(function(p){ P[p.stem] = p; });
  var stems = [b.system].concat(b.prompts||[], b.derived_prompts||[]).filter(Boolean);
  stems.forEach(function(s){ var p = P[s]; if(!p){ h += '<h4>' + esc(s) + '</h4><p class="warnline">unknown: prompt not found</p>'; return; }
   var t = esc(p.text).replace(/\$\{(\w+)\}/g, '<mark>${$1}</mark>').replace(/(^|[^{])\{(\w+)\}(?!\})/g, '$1<mark>{$2}</mark>');
   h += '<h4>' + esc(s) + '</h4><p class="muted mono">' + esc(p.header) + '</p><p>Placeholders: ' + (p.placeholders.length ? p.placeholders.map(function(x){ return '<mark class="mono">' + esc(x) + '</mark>'; }).join(' ') : 'none') + ' · ' + esc(p.style) + (p.note ? ' · ' + esc(p.note) : '') + '</p>';
   h += '<p class="muted">Loaded by: ' + (p.loaded_by.length ? p.loaded_by.map(function(l){ return '<code>' + esc(shortKey(l.key)) + '</code> (' + fl(l) + ')'; }).join(', ') : 'nothing') + '</p><pre>' + t + '</pre>'; });
  var kind = b.ai, call = null; ['flat','boss_reviewers'].forEach(function(tp){ if(!call) (A.sample.runs[tp].calls||[]).forEach(function(c){ if(!call && c.kind === kind) call = c; }); });
  h += '<h4>Filled in, as sent in the sample run (first ' + esc(kind) + ' call)</h4>';
  if(call){ call.messages.forEach(function(m){ h += '<p class="muted mono">' + esc(m.role) + '</p><pre>' + esc(j(m.content, 6000)) + '</pre>'; }); h += '<p class="muted mono">reply</p><pre>' + esc(j(call.response, 3000)) + '</pre>'; }
  else h += '<p class="warnline">unknown: this role made no call in the sample run.</p>';
  var ai = A.ai; h += '<h4>Model settings</h4><table><tr><th>setting</th><th>value in the code</th></tr>'
   + '<tr><td>model</td><td class="mono">sample run: ' + esc(ai.stand_in_model) + ' (offline stand-in)<br>command line: ' + esc(ai.cli_model) + '</td></tr>'
   + '<tr><td>temperature</td><td class="mono">' + esc(ai.client_defaults.temperature) + ' (connection default, ' + esc(ai.client_defaults.where) + ')</td></tr>'
   + '<tr><td>max tokens</td><td class="mono">' + esc(ai.client_defaults.max_tokens) + ' (connection default)</td></tr>'
   + '<tr><td>seed</td><td class="mono">' + esc(((b.ai_sites||[])[0]||{}).seed || 'unknown') + '</td></tr></table>'
   + (ai.per_helper_settings_read_by_runtime.length < 3 ? '<p class="warnline">Each helper\'s own model / temperature / max tokens in team.yaml are not read by the runner; the connection settings above apply to every call.</p>' : '');
  return h; },
 example: function(b){
  var ex = (A.__examples[b.id] || {}), h = '<p class="muted">From the sample run: one practice job (' + esc(A.sample.task.prompt) + '), offline stand-in AI, seed 0. Topology shown where it matters: <b>' + esc(topo) + '</b> (switch above the timeline).</p>';
  var items = typeof ex === 'function' ? ex() : (ex[topo] || ex.any || []);
  if(!items.length) return h + '<p class="warnline">unknown: this box has no recorded input or output in the ' + esc(topo) + ' sample run.</p>';
  items.forEach(function(it){ h += '<h4>' + esc(it[0]) + '</h4><pre>' + esc(j(it[1], 3000)) + '</pre>'; }); return h; },
 tests: function(b){
  var t = b.tests||[]; if(!t.length) return '<p class="warnline">no test</p><p>No test calls this box\'s code, directly or through anything it calls.</p>';
  var dn = t.filter(function(x){ return x.how !== 'indirect'; }).length;
  var h = (dn ? '' : '<p class="warnline">No test targets this code directly; it is only reached through larger tests.</p>') + '<table><tr><th>test</th><th>result</th><th>how</th></tr>';
  t.forEach(function(x){ h += '<tr><td class="mono">' + esc(x.test) + ':' + x.line + '</td><td><span class="pill ' + (x.outcome.indexOf('passed') === 0 ? 'passed' : 'failed') + '">' + esc(x.outcome) + '</span></td><td>' + esc(x.how) + '</td></tr>'; });
  return h + '</table><p class="muted">direct = the test uses this box\'s class or function by name; indirect = reached through the call graph; run: ' + esc(A.tests.summary) + '</p>'; },
 plan: function(b){
  var h = '<p>' + statusPill(b.status) + '</p>';
  var ch = (b.checks||[]); h += '<h4>Plan vs code</h4>' + (ch.length ? '<ul>' + ch.map(function(c){ return '<li><span class="pill ' + (c.level === 'ok' ? 'built' : c.level) + '">' + esc(c.level) + '</span> ' + esc(c.msg) + '</li>'; }).join('') + '</ul>' : (b.status === 'extra' ? '<p>The plan page never mentions this part; it exists in the code.</p>' : '<p>Every pointer the plan names exists; no difference found by the checks.</p>'));
  if(b.plan_card){ h += '<h4>What the plan page says (' + esc(A.plan_source) + ')</h4><table>' + Object.keys(b.plan_card).map(function(k){ return '<tr><th>' + esc(k) + '</th><td>' + esc(b.plan_card[k]) + '</td></tr>'; }).join('') + '</table>'; }
  var d = b.deviations||[], T = {}; A.deviations.spec_table.forEach(function(r){ T[r.id] = r; });
  h += '<h4>Departures from the source projects marked in this code (' + d.length + ')</h4>';
  h += d.length ? '<table><tr><th>note in the code</th><th>why (spec §11)</th><th>file:line</th></tr>' + d.map(function(x){ var r = x.id && T[x.id]; return '<tr><td>' + esc(x.text) + '</td><td>' + (r ? esc(x.id + ': ' + r.why) : '') + '</td><td class="mono">' + fl(x) + '</td></tr>'; }).join('') + '</table>' : '<p>None marked here.</p>';
  return h; }
};
// ---------------- box interactions
$$('.boxg').forEach(function(g){
  var id = g.getAttribute('data-id');
  var ed = g.querySelector('.edit'); if(ed) ed.addEventListener('click', function(e){ e.stopPropagation(); openEditor(g); });
  var inf = g.querySelector('.info'); if(inf) inf.addEventListener('click', function(e){ e.stopPropagation(); openDrawer(id, 'what'); });
  g.addEventListener('click', function(){ if(g.classList.contains('hit')) go(g.getAttribute('data-view')); else openDrawer(id); });
  g.addEventListener('keydown', function(e){ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); g.click(); } });
});
// ---------------- toggles
function toggle(btn, cls, on){ var v = on == null ? btn.getAttribute('aria-pressed') !== 'true' : on; btn.setAttribute('aria-pressed', v ? 'true' : 'false'); document.body.classList.toggle(cls, v); return v; }
$('#guards').onclick = function(){ toggle(this, 'guardsonly'); };
function paintCost(){
  var pb = A.sample.runs[topo].per_box, tot = 0; Object.keys(pb).forEach(function(k){ tot += pb[k].tokens; });
  $$('.boxg.ai').forEach(function(g){ var id = g.getAttribute('data-id'), r = g.querySelector('rect.box'), c = document.getElementById('cost-' + id), p = pb[id];
    if(!document.body.classList.contains('costmode')){ r.style.fill = ''; if(c) c.textContent = ''; return; }
    var share = p && tot ? p.tokens / tot : 0; r.style.fill = 'color-mix(in srgb, var(--llm-line) ' + Math.round(8 + share * 80) + '%, var(--llm-fill))';
    if(c) c.textContent = p ? (p.calls + ' call' + (p.calls === 1 ? '' : 's') + ' · ' + p.tokens + ' tok · ' + Math.round(share * 100) + '%') : 'not called in ' + topo; });
}
$('#cost').onclick = function(){ toggle(this, 'costmode'); paintCost(); };
$('#topo').onchange = function(){ topo = this.value; buildTimeline(); paintCost(); if(!dr.hasAttribute('hidden') && drBox) openDrawer(drBox.id, drTab); };
// ---------------- timeline + replay
var rows = [], replayT = null, replayI = 0;
function buildTimeline(){
  var tl = A.sample.runs[topo].timeline, tb = $('#tlbody'); tb.innerHTML = '';
  $('#tlmeta').textContent = 'Sample run ' + A.sample.runs[topo].run_id.slice(0, 8) + ' · ' + A.sample.runs[topo].dir + ' · ' + tl.length + ' trace lines · answer ' + JSON.stringify(A.sample.runs[topo].result.answer) + ' · score ' + A.sample.runs[topo].result.score + '. Only traced steps appear: plain-code steps between them are not logged in Phase 1.';
  rows = tl.map(function(r){ var b = BOX[r.box]; var tr = document.createElement('tr'); tr.className = 'row'; tr.tabIndex = 0;
    tr.innerHTML = '<td>' + (r.i + 1) + '</td><td>' + esc(b ? b.title : r.box) + '</td><td>' + esc(r.helper || '—') + '</td><td class="mono">' + esc(r.span) + '</td><td>' + (r.tokens || '') + '</td><td>' + esc(r.result) + '</td>';
    var det = document.createElement('tr'); det.className = 'det'; det.setAttribute('hidden','');
    det.innerHTML = '<td></td><td colspan="5"><div class="muted">trace.jsonl line ' + r.file_line + '</div><pre>' + esc(JSON.stringify(r.raw, null, 1)) + '</pre></td>';
    tr.onclick = function(){ if(det.hasAttribute('hidden')) det.removeAttribute('hidden'); else det.setAttribute('hidden',''); highlight(r, tr); };
    tr.onkeydown = function(e){ if(e.key === 'Enter'){ e.preventDefault(); tr.onclick(); } };
    tb.appendChild(tr); tb.appendChild(det); return {r: r, tr: tr}; });
}
function highlight(r, tr){
  $$('.boxg.replay').forEach(function(e){ e.classList.remove('replay'); }); $$('.timeline tr.on').forEach(function(e){ e.classList.remove('on'); });
  var b = BOX[r.box]; if(b && b.view !== cur) go(b.view); var g = document.getElementById('b-' + r.box); if(g) g.classList.add('replay'); if(tr){ tr.classList.add('on'); var box = $('.timeline'); box.scrollTop = tr.offsetTop - 40; }
}
function stopReplay(){ clearInterval(replayT); replayT = null; $$('.boxg.replay').forEach(function(e){ e.classList.remove('replay'); }); $$('.timeline tr.on').forEach(function(e){ e.classList.remove('on'); }); $('#replay').textContent = '▶ Replay sample run'; $('#replay').setAttribute('aria-pressed','false'); }
$('#replay').onclick = function(){
  if(replayT){ stopReplay(); return; } replayI = 0; this.textContent = '■ Stop replay'; this.setAttribute('aria-pressed','true');
  var step = function(){ if(replayI >= rows.length){ stopReplay(); return; } highlight(rows[replayI].r, rows[replayI].tr); replayI++; };
  step(); replayT = setInterval(step, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 1400 : 850);
};
// ---------------- search
var IDX = A.boxes.filter(function(b){ return !b.ref; }).map(function(b){ var s = [b.title, b.sentence, (b.what||[]).join(' ')].concat(b.anchors.map(function(a){ return a.name + ' ' + a.path; }), b.prompts||[], b.derived_prompts||[], [b.system||'']); return {id: b.id, s: s.join(' ').toLowerCase()}; });
function search(q){ q = (q||'').trim().toLowerCase(); if(!q) return; var hit = IDX.filter(function(x){ return x.s.indexOf(q) >= 0; });
  var st = $('#sst'); if(!hit.length){ st.textContent = 'no box mentions “' + q + '”'; return; }
  var b = BOX[hit[0].id]; st.textContent = hit.length + ' box' + (hit.length > 1 ? 'es' : '') + ' · showing ' + b.title; go(b.view);
  var g = document.getElementById('b-' + b.id); if(g){ g.classList.add('flash'); setTimeout(function(){ g.classList.remove('flash'); }, 1600); } openDrawer(b.id, 'code'); }
$('#q').addEventListener('keydown', function(e){ if(e.key === 'Enter'){ e.preventDefault(); search(this.value); } });
$('#q').addEventListener('change', function(){ search(this.value); });
// ---------------- change requests (✎) → local server or a copyable queue
var ENDPOINT = /^(localhost|127\.0\.0\.1)/.test(location.host) ? '/edit' : null, queue = [], edBox = null;
try { queue = JSON.parse(localStorage.getItem('amoeba_asbuilt_edits') || '[]'); } catch(e){ queue = []; }
function saveQ(){ try { localStorage.setItem('amoeba_asbuilt_edits', JSON.stringify(queue)); } catch(e){} renderQueue(); }
function openEditor(g){ var id = g.getAttribute('data-id'), b = BOX[id]; edBox = {view: g.closest('svg').id.replace(/^v-/, ''), box: b ? b.title : id, box_id: id};
  $('#edbox').textContent = 'view: ' + edBox.view + '   box: ' + edBox.box; $('#edtxt').value = '';
  $('#edst').textContent = ENDPOINT ? 'Will be sent to Claude Code (' + ENDPOINT + ').' : 'Queued in this browser; use “Copy edits” and paste them to Claude Code with “apply pending edits”.';
  $('#ov').removeAttribute('hidden'); $('#edtxt').focus(); }
function closeEditor(){ $('#ov').setAttribute('hidden',''); edBox = null; }
window.closeEditor = closeEditor;
$('#edcancel').onclick = closeEditor; $('#ov').onclick = function(e){ if(e.target.id === 'ov') closeEditor(); };
$('#edsend').onclick = function(){ var t = $('#edtxt').value.trim(); if(!t){ $('#edtxt').focus(); return; }
  var rec = {view: edBox.view, box: edBox.box, box_id: edBox.box_id, request: t, ts: new Date().toISOString(), page: document.title, commit: A.repo.short};
  if(ENDPOINT){ fetch(ENDPOINT, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(rec)}).then(function(r){ if(!r.ok) throw 0; closeEditor(); }).catch(function(){ queue.push(rec); saveQ(); closeEditor(); }); }
  else { queue.push(rec); saveQ(); closeEditor(); } };
function renderQueue(){ var w = $('#queue'); if(!w){ w = document.createElement('span'); w.id = 'queue'; w.className = 'queue'; } $('#crumb').appendChild(w); w.innerHTML = '';
  if(!queue.length) return; var n = document.createElement('span'); n.textContent = queue.length + ' pending edit' + (queue.length > 1 ? 's' : ''); w.appendChild(n);
  var c = document.createElement('button'); c.type = 'button'; c.className = 'btn'; c.textContent = 'Copy edits';
  c.onclick = function(){ var t = queue.map(function(q){ return JSON.stringify(q); }).join('\n'); if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(function(){ c.textContent = 'Copied'; setTimeout(function(){ c.textContent = 'Copy edits'; }, 1200); }); else window.prompt('Copy these lines:', t); };
  var x = document.createElement('button'); x.type = 'button'; x.className = 'btn'; x.textContent = 'Clear'; x.onclick = function(){ queue = []; saveQ(); };
  w.appendChild(c); w.appendChild(x); }
buildTimeline(); show((location.hash || '#overview').slice(1));
})();
"""


def examples(A: dict) -> dict:
    S = A["sample"]
    R = S["runs"]
    out = {}

    def call(tp, kind):
        return next((c for c in R[tp]["calls"] if c["kind"] == kind), None)

    for tp in ("flat", "boss_reviewers"):
        r = R[tp]
        ex = r["examples"]
        w = call(tp, "worker")
        steps = r["team_trimmed"]["plan"]
        E = {
            "ov_task": [("input", "ToyTaskSource(seed=0, n=1)"), ("output: Task", S["task"])],
            "task_record": [("the sample job", S["task"])],
            "toy_source": [("input", "ToyTaskSource(seed=0, n=3)"), ("output: first three jobs", S["toy_tasks"])],
            "free_text": [("input", "a sentence on the command line"), ("output: Task (built by the code)", S.get("free_text_task", "unknown"))],
            "handoff": [("what the planner receives", S["task"]["prompt"])],
            "scoring": [("answer", r["result"]["answer"]), ("known answer", S["task"]["ground_truth"]), ("score", r["result"]["score"])],
            "ov_plan": [("input", S["task"]["prompt"]), ("output: the team (trimmed)", r["team_trimmed"])],
            "planner": [("reply (trimmed; full text in the Prompt tab)", ex["raw_text"])],
            "split": [("input: the planner's reply", ex["raw_text"]), ("output: its sections (trimmed)", ex["sections"])],
            "agent_obs": [("reply", (call(tp, "agent_observer") or {}).get("response", "unknown"))],
            "plan_obs": [("reply", (call(tp, "plan_observer") or {}).get("response", "unknown")),
                         ("round result", {"draft_rounds": r["result"]["draft_rounds"], "consensus": r["result"]["consensus"]})],
            "envelope": [("the rules used in the sample run", ex["envelope"])],
            "checks": [("input: sections read", {k: ex["sections"].get(k, "unknown") for k in ("Created Roles List", "Execution Plan")}),
                       ("output: cleaned draft", {k: v for k, v in r["plan_trimmed"].items() if k != "raw_draft"})],
            "instantiate": [("input: helpers", [x["name"] for x in r["plan_trimmed"].get("created_roles", [])]),
                            ("output: team (trimmed)", r["team_trimmed"])],
            "teamconfig": [("team.yaml (trimmed)", r["team_trimmed"])],
            "interpreter": [("team shape", r["team_trimmed"]["topology"]), ("result", {k: r["result"][k] for k in ("answer", "error")})],
            "ov_run": [("result.json", r["result"])],
            "ov_leave": [("files in " + r["dir"], r["files"])],
            "trace": [(f"first 3 of {r['n_trace_lines']} lines of trace.jsonl", "\n".join(r["trace_lines"]))],
            "runresult": [("result.json", r["result"])],
            "tools": [("calc input", S["calc_example"]["input"]), ("calc output", S["calc_example"]["output"])],
            "client": [("one chat line from the log (token counts as reported)",
                        next((t["raw"] for t in r["timeline"] if t["span"] == "chat"), "unknown"))],
            "toymock": [("roles it answered in this run", sorted({c["kind"] for c in r["calls"]}))],
        }
        if tp == "flat":
            E["each_step"] = [("the plan's steps", steps)]
            if w:
                E["helper"] = [("reply of the first helper turn", w["response"])]
            E["read_action"] = [("actions read from the helper replies", ex["worker_sections"])]
        else:
            s = call(tp, "solver")
            c = call(tp, "critic")
            if s:
                E["solver"] = [("reply", s["response"])]
            if c:
                E["critics"] = [("reply", c["response"]), ("verdicts read by the code", ex["critic_verdicts"])]
            E["disagree"] = [("verdicts", ex["critic_verdicts"]),
                             ("decision", "no objection with a reason → stop, answer = " + json.dumps(r["result"]["answer"]))]
        for k, v in E.items():
            out.setdefault(k, {})[tp] = v
    return out


def diff_prev(A: dict) -> tuple[list[str], set]:
    p = ARCH / "architecture.prev.json"
    if not p.exists():
        return ["First build: there is no previous architecture.json to compare with."], set()
    P = json.loads(p.read_text())
    prev = {b["id"]: b for b in P["boxes"]}
    now = {b["id"]: b for b in A["boxes"]}
    lines, changed = [], set()
    for i in now:
        if i not in prev:
            lines.append(f"added: {now[i]['title']}"); changed.add(i)
        elif prev[i].get("fingerprint") != now[i].get("fingerprint"):
            what = [k for k in ("anchors", "guards", "checks", "tests", "status", "sentence")
                    if json.dumps(prev[i].get(k), sort_keys=True, default=str) != json.dumps(now[i].get(k), sort_keys=True, default=str)]
            lines.append(f"changed: {now[i]['title']} ({', '.join(what) or 'prompt text'})"); changed.add(i)
    for i in prev:
        if i not in now:
            lines.append(f"removed: {prev[i]['title']}")
    head = f"Compared with the previous build (commit {P['repo']['short']}, extracted {P.get('generated_at', 'unknown')}):"
    return [head] + (lines or ["no box was added, removed or changed."]), changed


def render() -> Path:
    A = json.loads((ARCH / "architecture.json").read_text())
    changes, changed = diff_prev(A)
    views_svg = []
    for v, meta in VIEWS.items():
        items = [box_svg(b, A, changed) for b in A["boxes"] if b["view"] == v]
        edges = [edge_svg(e, A) for e in EDGES if e[0] == v]
        views_svg.append(f'<svg id="v-{v}" viewBox="0 0 1180 {meta["h"]}" role="img" aria-label="{esc(meta["label"])}"'
                         f'{"" if v == "overview" else " hidden"}><text x="30" y="36" class="hd">{esc(meta["heading"])}</text>'
                         + decor_svg(v, A) + "".join(edges) + "".join(items) + "</svg>")
    counts = A["status_counts"]
    date = datetime.fromisoformat(A["repo"]["commit_date"]).strftime("%-d %b")
    summary = (f'<span class="pill built">{counts.get("built", 0)} built</span>'
               f'<span class="pill differs">{counts.get("differs", 0)} differ</span>'
               f'<span class="pill missing">{counts.get("missing", 0)} missing</span>'
               f'<span class="pill extra">{counts.get("extra", 0)} extra</span>'
               f'<span>commit <b class="mono">{esc(A["repo"]["short"])}</b> · {esc(date)}'
               f'{" · <b>uncommitted changes</b>" if A["repo"]["dirty"] else ""} · branch <span class="mono">{esc(A["repo"]["branch"])}</span></span>'
               f'<span>tests: {esc(A["tests"]["summary"])}</span>')
    data = dict(A)
    data["__views"] = {k: {"label": v["label"], "note": v["note"]} for k, v in VIEWS.items()}
    data["__examples"] = examples(A)
    for k in ("functions", "modules", "classes", "constants", "guards"):   # shown per box already; keep the page light
        data.pop(k, None)
    blob = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    gloss = "".join(f"<dt>{esc(t)}</dt><dd>{esc(d)}</dd>" for t, d in A["glossary"])
    changes_html = "<ul class='changes'>" + "".join(f"<li>{esc(l)}</li>" for l in changes) + "</ul>"
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style></head><body>
<div class="wrap">
<h1>{TITLE}</h1>
<p class="sub">Task → Plan a new team → Team runs the task, read from the code at the commit below, not from the plan. Every box says in one sentence what it does; click it for the exact code, prompt, example and tests.</p>
<div class="summary" id="summary">{summary}</div>
<div class="legend">
<span><i class="sw llm"></i>an AI writes text</span><span><i class="sw code"></i>plain code decides</span><span><i class="sw data"></i>a record passed along</span><span><i class="sw plain"></i>input / output</span>
<span><svg width="14" height="16" style="min-width:0;display:inline"><path d="M7 1 l6 2.4 v4.4 c0 3.8 -2.7 6.4 -6 7.6 c-3.3 -1.2 -6 -3.8 -6 -7.6 v-4.4 z" fill="var(--code-line)"/></svg>plain code checks AI output here</span>
<span>✦ changed since last build</span><span><code>task/draft.py:39</code> = where it lives in the code</span></div>
<div class="tools">
<button type="button" class="btn" id="replay" aria-pressed="false">▶ Replay sample run</button>
<label>sample: <select id="topo"><option value="flat">step by step (flat)</option><option value="boss_reviewers">writer + reviewers</option></select></label>
<button type="button" class="btn" id="cost" aria-pressed="false">Cost overlay</button>
<button type="button" class="btn" id="guards" aria-pressed="false">Show only guards</button>
<input type="search" id="q" placeholder="Search a class, prompt file or word…" aria-label="Search boxes" list="qlist">
<datalist id="qlist">{"".join(f'<option value="{esc(b["title"])}">' for b in A["boxes"] if not b.get("ref"))}{"".join(f'<option value="{esc(p["stem"])}">' for p in A["prompts"])}</datalist>
<span id="sst" class="sub" style="margin:0"></span></div>
<div class="crumb" id="crumb"></div>
<svg width="0" height="0" style="position:absolute;min-width:0" aria-hidden="true"><defs>
<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="var(--line)"/></marker>
<marker id="ahp" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="var(--llm-line)"/></marker>
</defs></svg>
<div class="panel">{"".join(views_svg)}</div>
<p class="notes" id="note"></p>
<h2>Sample run timeline</h2>
<p class="sub" id="tlmeta"></p>
<div class="timeline"><table><thead><tr><th>#</th><th>step</th><th>helper</th><th>log line</th><th>tokens</th><th>result</th></tr></thead><tbody id="tlbody"></tbody></table></div>
<h2>What changed since the last build</h2>
{changes_html}
<h2>Glossary</h2>
<dl class="gloss">{gloss}</dl>
<p class="foot">Generated by tools/arch_render.py from docs/arch/architecture.json (tools/arch_extract.py) at {esc(A.get("generated_at", "unknown"))}. Plan compared against: <a href="{esc(A["plan_page"])}">Amoeba Phase 1 (plan)</a>, saved as {esc(A["plan_source"])}. Nothing on this page is hand-written about the code; boxes with no fact available say “unknown”.</p>
</div>
<div class="tt" id="tt" role="tooltip" aria-hidden="true"></div>
<aside class="drawer" id="drawer" hidden aria-label="Box details"><header><button type="button" class="btn x" id="drx" aria-label="Close">✕</button><h3 id="drt"></h3><p class="one" id="dro"></p></header>
<div class="tabs" id="drtabs" role="tablist"></div><div class="tabbody" id="drbody"></div></aside>
<div class="ov" id="ov" hidden><div class="ed" role="dialog" aria-modal="true" aria-labelledby="edh"><h2 id="edh">Request a change</h2><p class="box-id" id="edbox"></p>
<textarea id="edtxt" placeholder="What should change? e.g. “this cap should be 3”"></textarea>
<div class="row"><span class="st" id="edst"></span><button type="button" class="btn" id="edcancel">Cancel</button><button type="button" class="btn primary" id="edsend">Send</button></div></div></div>
<script type="application/json" id="data">{blob}</script>
<script>{JS}</script>
</body></html>
"""
    out = ARCH / "phase1.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(page) // 1024} KB)")
    return out


# ------------------------------------------------------------------------------------------------ check
def check(out: Path) -> int:
    """Every file:line on the page must exist in the commit the page names."""
    A = json.loads((ARCH / "architecture.json").read_text())
    commit = A["repo"]["commit"]
    cache: dict[str, list[str] | None] = {}

    def lines_of(path):
        if path not in cache:
            r = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, text=True)
            cache[path] = r.stdout.split("\n") if r.returncode == 0 else None
        return cache[path]

    bad, n = [], 0
    def visit(o):
        nonlocal n
        if isinstance(o, dict):
            if isinstance(o.get("path"), str) and isinstance(o.get("line"), int) and re.search(r"\.(py|txt|md)$", o["path"]):
                n += 1
                ls = lines_of(o["path"])
                if ls is None or not (0 < o["line"] <= len(ls)):
                    bad.append(f"{o['path']}:{o['line']} (not in {commit[:7]})")
                elif o.get("kind") in ("class", "function"):
                    name = o["name"].split(".")[-1]
                    if f"def {name}" not in ls[o["line"] - 1] and f"class {name}" not in ls[o["line"] - 1]:
                        bad.append(f"{o['path']}:{o['line']} does not define {name}")
            for v in o.values():
                visit(v)
        elif isinstance(o, list):
            for v in o:
                visit(v)
    visit(A)
    # every path:line written into the page text (hover cards, box provenance, captions)
    text = html.unescape(html.unescape(out.read_text(encoding="utf-8").split('<script type="application/json"')[0]))
    for m in set(re.findall(r"\b((?:amoeba/|scripts/|tests/|spec/)?(?:[\w-]+/)*[\w-]+\.(?:py|txt|md)):(\d+)", text)):
        path, line = m[0], int(m[1])
        cand = [path, "amoeba/" + path]
        found = next((c for c in cand if lines_of(c) is not None), None)
        n += 1
        if found is None:
            src = [p for p in (ROOT / "repos").rglob(Path(path).name)] if (ROOT / "repos").exists() else []
            if not any(line <= len(p.read_text(errors="ignore").split("\n")) for p in src):
                bad.append(f"{path}:{line} (not in the repo, nor in the source clones)")
        elif not (0 < line <= len(lines_of(found))):
            bad.append(f"{found}:{line} (beyond end of file)")
    print(f"check: {n} file:line references against commit {commit[:7]}: {len(bad)} bad")
    for b in bad:
        print("  BAD", b)
    return 1 if bad else 0


if __name__ == "__main__":
    o = render()
    sys.exit(0 if "--no-check" in sys.argv else check(o))
