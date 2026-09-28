"""D64 — shorten a text for a later reader without cutting away its result.

Where a step's output (or a program's output) must be shortened, plain code keeps its head AND its tail, marks the
cut with "[… N characters omitted …]", and always keeps the lines that carry a final result: a count, a total, a
result or answer, an "=" line, a "label: number" line, and the last 20 lines of each program output block. A single
line longer than a quarter of the limit (a printed list of 1,229 primes) is itself shortened to its head and tail.
"""
from __future__ import annotations

import re

KEY_LINE = re.compile(
    r"\b(count|counts|total|totals|sum|result|results|answer|largest|smallest|max|maximum|min|minimum|average|mean|"
    r"final|grand total|verdict|pass|fail)\b|=|^\s*[-*]?\s*[A-Za-z][\w ()/%$.-]{0,40}:\s*[-+$€£]?\d", re.I)
OUTPUT_TAIL = 20          # lines kept from the end of each program output block
MARK = "[… {n:,} characters omitted …]"


def _cut_line(line: str, limit: int) -> str:
    if len(line) <= limit:
        return line
    half = max(20, limit // 2 - 20)
    return f"{line[:half].rstrip()} {MARK.format(n=len(line) - 2 * half)} {line[-half:].lstrip()}"


def _output_tails(lines: list[str]) -> set[int]:
    """Line numbers of the last OUTPUT_TAIL lines of each fenced block that is program output (```text, ```output,
    ```console, a bare ``` right after a line naming output / stdout / result), and of a [local:...] tool result."""
    keep: set[int] = set()
    start, is_output = None, False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("```"):
            if start is None:
                lang = s[3:].strip().lower()
                prev = lines[i - 1].lower() if i else ""
                is_output = lang in ("text", "output", "console", "stdout", "shell-session", "") and (
                    lang != "" or bool(re.search(r"output|stdout|result|printed|prints", prev)))
                start = i
            else:
                if is_output:
                    keep.update(range(max(start + 1, i - OUTPUT_TAIL), i))
                start = None
        elif s.startswith("[local:"):
            keep.update(range(i, min(len(lines), i + 1)))
    if start is not None and is_output:                      # an unclosed output block runs to the end
        keep.update(range(max(start + 1, len(lines) - OUTPUT_TAIL), len(lines)))
    return keep


# box: plan_step, plan_summary
def shorten(text: str, limit: int) -> str:
    """The text within about `limit` characters: head, the result lines of the middle, tail. Unchanged when it
    fits."""
    text = text or ""
    if len(text) <= limit:
        return text
    if limit < 400:                                          # too small for lines: characters, head and tail
        half = max(1, limit // 2)
        return f"{text[:half]}{MARK.format(n=len(text) - 2 * half)}{text[-half:]}"
    lines = [_cut_line(l, max(200, limit // 4)) for l in text.split("\n")]
    if sum(len(l) + 1 for l in lines) <= limit:
        return "\n".join(lines)
    must = _output_tails(lines) | {i for i, l in enumerate(lines) if KEY_LINE.search(l)}
    head_room, tail_room = int(limit * 0.4), int(limit * 0.3)
    head, used = [], 0
    for i, l in enumerate(lines):
        if used + len(l) + 1 > head_room:
            break
        head.append(i)
        used += len(l) + 1
    tail, used = [], 0
    for i in range(len(lines) - 1, head[-1] if head else -1, -1):
        if used + len(lines[i]) + 1 > tail_room:
            break
        tail.append(i)
        used += len(lines[i]) + 1
    tail.reverse()
    first_tail = tail[0] if tail else len(lines)
    last_head = head[-1] if head else -1
    room = limit - sum(len(lines[i]) + 1 for i in head + tail)
    middle = []
    for i in sorted(must):
        if last_head < i < first_tail:
            line = _cut_line(lines[i], 300)
            if room - len(line) - 1 < 0:
                break
            middle.append(i)
            room -= len(line) + 1
    out, prev = [], -1
    for i in [*head, *middle, *tail]:
        if i != prev + 1:
            skipped = sum(len(lines[j]) + 1 for j in range(prev + 1, i))
            out.append(MARK.format(n=skipped))
        out.append(_cut_line(lines[i], 300) if i in middle else lines[i])
        prev = i
    if prev != len(lines) - 1:
        out.append(MARK.format(n=sum(len(lines[j]) + 1 for j in range(prev + 1, len(lines)))))
    return "\n".join(out)
