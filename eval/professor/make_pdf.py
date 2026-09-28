"""docs/eval/professor/REPORT.md → REPORT.pdf (Markdown → HTML with python-markdown → PDF with the preinstalled
headless Chromium via Playwright, offline; LibreOffice cannot load files in this container).

    python eval/professor/make_pdf.py

Mermaid diagrams are not rendered offline; each is replaced in the PDF by its step list as plain text (the
GitHub page shows the drawn diagram).
"""
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/eval/professor/REPORT.md"
OUT = ROOT / "docs/eval/professor/REPORT.pdf"
CSS = """
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; line-height: 1.4; margin: 0; color: #111; }
h1 { font-size: 19pt; } h2 { font-size: 15pt; border-bottom: 1px solid #999; margin-top: 1.4em; }
h3 { font-size: 12.5pt; margin-top: 1.1em; } h4 { font-size: 11pt; }
table { border-collapse: collapse; width: 100%; margin: .6em 0; font-size: 9.5pt; }
th, td { border: 1px solid #999; padding: 3px 6px; vertical-align: top; text-align: left; }
th { background: #eee; } code { font-family: 'DejaVu Sans Mono', monospace; font-size: 9pt; }
pre { background: #f4f4f4; padding: 6px; font-size: 8.5pt; white-space: pre-wrap; }
blockquote { border-left: 3px solid #bbb; margin: .5em 0; padding-left: .8em; color: #333; }
.diagram { background: #f7f7f7; border: 1px dashed #aaa; padding: 6px; font-size: 9pt; white-space: pre-wrap; }
"""


def mermaid_to_text(m: re.Match) -> str:
    out = []
    for l in (x.strip() for x in m.group(1).splitlines()):
        if not l or l == "end" or l.startswith(("flowchart", "graph", "classDef", "class ")):
            continue
        if l.startswith("subgraph"):
            out.append(re.sub(r'subgraph\s+\w+\["?(.*?)"?\]', r"\1:", l))
        elif "-->" in l:
            out.append("  order: " + re.sub(r"S(\d+)", r"step \1", l).replace("-->", "→"))
        else:
            out.append("  " + re.sub(r'^\w+\["?(.*?)"?\]$', r"\1", l))
    return "<div class='diagram'><b>Step graph</b> (drawn on the GitHub page)\n" + "\n".join(out) + "</div>"


def blank_before_lists(text: str) -> str:
    """python-markdown needs a blank line before a list (GitHub does not); add one after any non-list line, and
    indent nested items to 4 spaces, which python-markdown needs for nesting."""
    out, prev = [], ""
    item = re.compile(r"^(\s*)([-*]|\d+\.)\s")
    for line in text.splitlines():
        m = item.match(line)
        if m:
            line = " " * (len(m.group(1)) * 2) + line.lstrip()        # GitHub's 2-space nesting → 4 spaces
            if prev.strip() and not item.match(prev) and not prev.startswith(" "):
                out.append("")
        elif line.startswith("  ") and out and (item.match(out[-1]) or out[-1].startswith("    ")):
            line = "    " + line.lstrip()                          # continuation of a list item
        out.append(line)
        prev = line
    return "\n".join(out)


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    text = re.sub(r"```mermaid\n(.*?)```", lambda m: mermaid_to_text(m), text, flags=re.S)
    text = blank_before_lists(text)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>Professor benchmark</title><style>{CSS}</style></head><body>{body}</body></html>"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = b.new_page()
        page.set_content(html, wait_until="load")
        page.pdf(path=str(OUT), format="Letter", print_background=True,
                 margin={"top": "1.2cm", "bottom": "1.2cm", "left": "1.2cm", "right": "1.2cm"})
        b.close()
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
