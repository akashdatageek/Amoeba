"""D74 — citation check by code: what a step cites a source for must be in that source.

Every [S#] tag in a step's output backs the words in front of it (from the previous tag, or the start of the line,
up to the tag). In that stretch plain code picks out the claims it can check without a model:

- a quoted phrase ("…" or “…”, at least 3 words or 12 characters)
- a time of day (8:00 AM, 4:30 p.m., 08:30)
- a number: a price, a percentage, a count, a date part (list markers, labels such as "step 3" or "R2", numbers
  given in the task and numbers the step computed with calc or a local tool are left out)
- an identifier (D78): a phone number, a ZIP or ZIP+4 code, a street number — matched as a whole token, digits only,
  never as a rounded or partial number; a 5-digit ZIP is in a source that prints its ZIP+4 run together
  ("463243348") or hyphenated

Each must appear in the text the team was really shown for that source (search snippet, fetched page, tool output),
after normalising: case, dashes, "a.m."/"AM", spaces and thousands separators; a number also matches when the
source has it at more precision ($6.47 against 6.4709). A claim that is missing is a mislabelled citation; if another
source has it, that source is named. A tag whose source text is unknown (a pool tool with no output, a hallucinated
id) is not checked here — D33 already reports hallucinated ids.

D104 (arithmetic=True): a number the line shows as the result of a calculation ("350 + 1,428.00 = 1,778.00 [S3]",
"≈ 1.05 million"), the base and exponent of a power ("4¹⁰", "4^10"), and the years of a range ("2016–2019",
"2016 … 2019") are not claims of their own: the operands of the calculation are still checked.
"""
from __future__ import annotations

import re

from amoeba.interp.provenance import IDS, LIST_MARKER, NUM, equals_computed

TAG = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]", re.I)
QUOTE = re.compile(r"[\"“]([^\"”\n]{3,200})[\"”]")
TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?\s?m\.?|p\.?\s?m\.?)(?![a-z])|\b(\d{1,2}):(\d{2})\b", re.I)
URL = re.compile(r"https?://\S+")
# D78: identifiers, taken out before the number scan and matched as whole tokens
PHONE = re.compile(r"(?<![\d-])(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s])\d{3}[-.]\d{4}(?![\d-])")
ZIP = re.compile(r"(?:(?<=\b[A-Z]{2} )|(?<=\b[A-Z]{2}, ))\d{5}(?:-?\d{4})?(?!\d)|"
                 r"(?<![\d-])\d{5}-\d{4}(?![\d-])")
STREET = re.compile(r"(?<![\d,.$])\d{1,6}(?=\s+(?:[NSEW]\.?\s+)?(?:[A-Z][\w.']*\s+){1,3}"
                    r"(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way|Hwy|Highway|Pkwy|Parkway|"
                    r"Ct|Court|Pl|Place)\b)")


def norm(text: str) -> str:
    t = (text or "").lower().replace(" ", " ")
    t = re.sub(r"[‐-―−]", "-", t)
    t = re.sub(r"\ba\.\s?m\.?", "am", t)
    t = re.sub(r"\bp\.\s?m\.?", "pm", t)
    t = re.sub(r"[“”\"'’`*_]", "", t)
    t = re.sub(r"\s*-\s*", " - ", t)
    return re.sub(r"\s+", " ", t).strip()


def times_in(text: str) -> set[str]:
    """Times of day as 'H:MM' plus am/pm when written ('8:00am', '16:30' -> '4:30pm', '08:30' -> '8:30')."""
    out = set()
    for m in TIME.finditer(norm(text)):
        if m.group(3):
            h, mm, ap = int(m.group(1)), m.group(2) or "00", "am" if m.group(3).startswith("a") else "pm"
            if h <= 12:
                out.add(f"{h}:{mm}{ap}")
        else:
            h, mm = int(m.group(4)), m.group(5)
            if h <= 23:
                out.add(f"{h % 12 or 12}:{mm}{'pm' if h >= 12 else 'am'}" if h > 12 else f"{h}:{mm}")
    return out


def _time_match(t: str, source: set[str]) -> bool:
    if t in source:
        return True
    bare = re.sub(r"(am|pm)$", "", t)
    return bare in source or any(re.sub(r"(am|pm)$", "", s) == bare for s in source if not s.endswith(("am", "pm")))


def numbers(text: str) -> list[float]:
    out = []
    for m in NUM.finditer(URL.sub(" ", text or "")):
        try:
            out.append(float(m.group(0).strip("$€£%").replace(",", "")))
        except ValueError:
            pass
    return out


def digits(tok: str) -> str:
    return re.sub(r"\D", "", tok)


def identifiers(body: str) -> tuple[list[tuple[str, str]], str]:
    """D78: (kind, digits) for every phone number, ZIP and street number in `body`, and `body` with them blanked
    out, so their digits are not also read as numbers."""
    found = []

    def take(kind):
        def sub(m):
            found.append((kind, digits(m.group(0))))
            return " " * len(m.group(0))
        return sub
    body = PHONE.sub(take("phone"), body)
    body = ZIP.sub(take("zip"), body)
    body = STREET.sub(take("street"), body)
    return found, body


def _identifier_in(kind: str, d: str, text: str) -> bool:
    """A whole-token match, digits only: a phone with any separators; a ZIP alone, as ZIP+4 hyphenated or run
    together; a street number not inside a longer number."""
    t = text or ""
    if kind == "phone":
        d = d[-10:]
        return re.search(rf"(?<!\d)(?:\+?1[-.\s]?)?\(?{d[:3]}\)?[-.\s]*{d[3:6]}[-.\s]*{d[6:]}(?!\d)", t) is not None
    if kind == "zip":
        if len(d) == 9:
            return re.search(rf"(?<!\d){d[:5]}-?{d[5:]}(?!\d)", t) is not None
        return re.search(rf"(?<!\d){d}(?:-?\d{{4}})?(?!\d)", t) is not None
    return re.search(rf"(?<![\d,.]){d}(?!\d|[,.]\d)", t) is not None


RESULT = re.compile(r"[=≈]\s*~?\s*[$€£]?(\d(?:[\d,]*\d)?(?:\.\d+)?)")
POWER = re.compile(r"(?<![\w.])(\d+)\s*(?:\^\s*\(?(\d+)|[⁰¹²³⁴⁵⁶⁷⁸⁹]+)")
YEAR_RANGE = re.compile(r"\b((?:19|20)\d{2})\s*(?:-|–|—|…|\.\.\.?|to|through)\s*((?:19|20)\d{2})\b", re.I)


# box: step_check
def derived_tokens(body: str) -> set[str]:
    """D104: the numbers of a stretch that are not claims of their own — calculation results, powers, year ranges."""
    out = {m.group(1).replace(",", "") for m in RESULT.finditer(body)}
    for m in POWER.finditer(body):
        out.add(m.group(1))
        if m.group(2):
            out.add(m.group(2))
    for m in YEAR_RANGE.finditer(body):
        out.update({m.group(1), m.group(2)})
    return out


def claims(segment: str, exempt: set[str], exact: list[float], arithmetic: bool = False) -> list[tuple[str, str]]:
    """(kind, claim) pairs a code check can test in the words an [S#] tag backs."""
    body = URL.sub(" ", LIST_MARKER.sub("", segment))
    out = [("quote", q.strip()) for q in QUOTE.findall(body) if len(q.split()) >= 3 or len(q.strip()) >= 12]
    ids, body = identifiers(QUOTE.sub(lambda m: " " * len(m.group(0)), body))
    out += [(kind, d) for kind, d in ids if d not in exempt]
    times = times_in(body)
    out += [("time", t) for t in sorted(times)]
    rest = TIME.sub(" ", norm(QUOTE.sub(" ", body)))   # a quote's and a time's digits are not claims of their own
    rest = IDS.sub(" ", rest)
    skip = derived_tokens(rest) if arithmetic else set()                      # D104
    for m in NUM.finditer(rest):
        tok = m.group(0)
        bare = tok.strip("$€£%").replace(",", "")
        if bare in exempt or equals_computed(tok, exact) or bare in skip:
            continue
        out.append(("number", tok))
    return out


def _has(kind: str, claim: str, text: str) -> bool:
    if kind == "quote":
        return norm(claim).strip(" .,;:") in norm(text)
    if kind == "time":
        return _time_match(claim, times_in(text))
    if kind in ("phone", "zip", "street"):
        return _identifier_in(kind, claim, text)
    if re.fullmatch(r"\d{5}", claim) and _identifier_in("zip", claim, text):
        return True        # D78: a bare 5-digit number is in a source's ZIP+4 run together ("463243348")
    return equals_computed(claim, numbers(text))


# box: step_check
def mislabelled_citations(text: str, contents: dict[str, str], exempt: set[str] | None = None,
                          exact: list[float] | None = None, arithmetic: bool = False) -> list[dict]:
    """D74: every checkable claim tagged [S#] whose source text does not contain it. `contents`: S# -> the text the
    team was shown for it; `exempt`: numbers given in the task; `exact`: values the step computed."""
    found, seen = [], set()
    exempt, exact = exempt or set(), exact or []
    for line in (text or "").splitlines():
        start = 0
        for m in TAG.finditer(line):
            ids = [x.strip().upper() for x in m.group(1).split(",")]
            known = [i for i in ids if i in contents]
            segment, start = line[start:m.start()], m.end()
            if not known:
                continue
            for kind, claim in claims(segment, exempt, exact, arithmetic):
                if any(_has(kind, claim, contents[i]) for i in known) or (tuple(ids), claim) in seen:
                    continue
                seen.add((tuple(ids), claim))
                elsewhere = [i for i, t in contents.items() if i not in ids and _has(kind, claim, t)]
                found.append({"source": ",".join(ids), "claim": claim, "kind": kind, "found_in": elsewhere[:3],
                              "line": line.strip()[:200]})
    return found
