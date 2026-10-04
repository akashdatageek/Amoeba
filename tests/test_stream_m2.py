"""Stream m2 (D92, D94): 16 practice tasks (stream_m1's, post-shift rubrics with entity lists), a gate set of 15 post +
3 pre retention tasks, a final-audit set of 10 in tasks/audit/; every new task has 5–6 rubric items; "assumptions
section" is in every post-shift rubric (with 4–8 entities) and the word is in no prompt; the loader keeps the audit
set out. Skipped until the approved files are committed."""
import json

import pytest

from amoeba.adapt.stream import load_stream
from tests.conftest import ROOT

STREAM = ROOT / "tasks" / "stream_m2.jsonl"
AUDIT = ROOT / "tasks" / "audit" / "stream_m2.audit.jsonl"
pytestmark = pytest.mark.skipif(not STREAM.exists(), reason="stream m2 not committed yet")


def audit_rows():
    return [json.loads(l) for l in AUDIT.read_text().splitlines() if l.strip()]


def test_the_three_sets():
    s = load_stream("m2")
    assert len(s.practice()) == 16 and len(s.heldout("calc", "post")) == 15 and len(s.heldout("calc", "pre")) == 3
    assert {t.split for t in s.tasks} == {"practice", "gate"}
    a = audit_rows()
    assert len(a) == 10 and {r["split"] for r in a} == {"audit"} and {r["phase"] for r in a} == {"post"}
    ids = {t.id for t in s.tasks}
    assert not ids & {r["id"] for r in a}


def test_rubrics_and_prompts():
    s = load_stream("m2")
    rows = [t.model_dump() for t in s.tasks] + audit_rows()
    for r in rows:
        assert "assum" not in r["prompt"].lower(), r["id"]
        if r["phase"] != "post":
            continue
        rub = r["rubric"]
        [sec] = [d for d in rub["required_deliverables"] if d["name"] == "assumptions section"]
        assert 4 <= len(sec["entities"]) <= 8, r["id"]
        if r["id"].startswith("m2-"):                                     # the new tasks
            n = len(rub["expected_numbers"]) + len(rub["required_deliverables"])
            assert n in (5, 6), r["id"]
