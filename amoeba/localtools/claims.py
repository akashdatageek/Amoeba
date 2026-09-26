"""D59 — a step that says it made a file must have made it (plain code, with --local-tools on only).

A sentence of a step's output that names a file (chart.png, totals.xlsx, report.docx …) together with a claim verb
(saved, created, wrote, generated, exported …) and no negation or future ("could not", "will be", "BLOCKED") is a
claim. Code blocks are not read. A claimed file that is not in the workspace makes the step "incomplete" with the
reason claimed_file_missing.
"""
from __future__ import annotations

import re

FILE = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w-][\w.-]*\.(?:png|jpe?g|gif|svg|pdf|xlsx|xlsm|xls|csv|tsv|docx|pptx|"
                  r"txt|md|json|html?|py|zip))(?![\w-]|\.\w)", re.I)
CLAIM = re.compile(r"\b(saved|created|written|wrote|generated|exported|produced|attached|stored|rendered|"
                   r"has been made|is ready)\b", re.I)
NEGATION = re.compile(r"\b(not|cannot|can't|couldn't|unable|failed|fail|no|never|without|blocked|would|will|"
                      r"should|shall|to be|planned|if|once)\b|n't\b", re.I)
FENCE = re.compile(r"```.*?```", re.S)


# box: localtools
def claimed_files(text: str) -> list[str]:
    """File names the text says were made, in order of first mention."""
    out: list[str] = []
    for line in FENCE.sub(" ", text or "").splitlines():
        if line.strip().upper().startswith("BLOCKED"):
            continue
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z*#\-])", line):
            if not CLAIM.search(sentence) or NEGATION.search(sentence):
                continue
            for f in FILE.findall(sentence):
                if f not in out:
                    out.append(f)
    return out
