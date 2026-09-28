"""D64 — outputs are never cut before the key result: head and tail kept, result lines kept, marks for what is left
out. The bench5 primes case: step 1's output (8,087 characters, the printed list of 1,229 primes on one line) was cut
at 6,000 characters before its count line, so the checker and the writer never saw 1,229 and 9,973."""
import re
from pathlib import Path

from amoeba.interp.plan_runner import PlanOptions
from amoeba.interp.runtime import Interpreter
from amoeba.interp.shorten import shorten
from tests.test_plan_runner import BODY, plan_team, scripted, step_no

PRIMES = (Path(__file__).parent / "fixtures" / "bench5_primes_step1.md").read_text(encoding="utf-8")


def test_the_primes_output_keeps_its_count_and_largest_prime():
    assert len(PRIMES) > 8000
    out = shorten(PRIMES, 6000)
    assert len(out) <= 6300
    for line in ("Count: 1229", "Max Prime: 9973", "Total primes found below 10,000: 1229 [S1]",
                 "Largest prime found: 9973 [S1]"):
        assert line in out
    assert "characters omitted …]" in out and "9967, 9973]" in out          # the long list line keeps its tail
    assert out.startswith(PRIMES[:40])                                        # and the head is kept


def test_head_tail_and_result_lines_of_a_long_text():
    middle = "\n".join(f"line {i}: nothing to see here, just words and more words" for i in range(400))
    text = "HEAD first line\n" + middle.replace("line 200: nothing", "grand total = 4,950.30 nothing") + "\nLAST line\n"
    out = shorten(text, 3000)
    assert out.startswith("HEAD first line") and out.rstrip().endswith("LAST line")
    assert "grand total = 4,950.30" in out and re.search(r"\[… [\d,]+ characters omitted …\]", out)
    assert shorten("short", 3000) == "short"


def test_program_output_keeps_its_last_twenty_lines():
    rows = "\n".join(f"row {i}" for i in range(500))
    text = "Output:\n```\n" + rows + "\n```\n" + "notes " * 400
    out = shorten(text, 2000)
    assert all(f"row {i}" in out for i in range(480, 500))


def test_the_checker_and_the_writer_see_the_count(task, envelope, trace, tools):
    w = scripted(lambda n, k, p: PRIMES if n == "1" else f"OUT-{n}\n{BODY}")
    llm, cfg = plan_team(task, envelope, trace, plan_worker=w)
    Interpreter(llm, tools, trace, plan_options=PlanOptions(max_input_chars=6000)).run(cfg, task, seed=0)
    for n in ("2", "3"):
        prompt = [c for c in llm.calls_of("plan_worker") if step_no(c["messages"]) == n][0]["messages"][-1]["content"]
        assert "Count: 1229" in prompt and "Max Prime: 9973" in prompt
    summ = llm.calls_of("plan_summariser")[0]["messages"][-1]["content"]
    assert "Count: 1229" in summ and "Max Prime: 9973" in summ
    [ev] = [e for e in trace.events("input_truncated") if e["amoeba.what"] == "input"][:1]
    assert ev["amoeba.chars"] > 8000 and ev["amoeba.chars_passed"] <= 6300
