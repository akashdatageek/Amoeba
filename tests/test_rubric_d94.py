"""D94 — rubric content checks: a required section with `entities` passes only if its body (up to the next heading)
names at least one task-specific entity; an empty heading fails. Items without entities score as before."""
from amoeba.task.evaluate import rubric_score, section_entity
from amoeba.task.models import Rubric

PATTERNS = ["(?im)^\\s*#{1,6}\\s*(?:\\d+[.)]\\s*)?(?:key\\s+|main\\s+)?assumptions?\\b",
            "(?im)^\\s*\\*\\*\\s*(?:\\d+[.)]\\s*)?(?:key\\s+|main\\s+)?assumptions?\\b[^\\n]{0,30}\\*\\*",
            "(?im)^\\s*assumptions?\\s*(?:made|used)?\\s*:?\\s*$"]
ENT = ["overtime", "medicare", "47 hours", "tax"]
RUBRIC = Rubric.model_validate({"expected_numbers": [{"name": "gross pay", "value": 1333.2, "unit": "USD",
                                                      "tolerance": 0.005}],
                                "required_deliverables": [{"name": "assumptions section", "any_of": PATTERNS,
                                                           "entities": ENT}]})


def item(answer):
    return next(i for i in rubric_score(answer, RUBRIC)["items"] if i["name"] == "assumptions section")


def test_a_section_naming_an_entity_passes():
    it = item("Gross pay $1,333.20.\n\n## Assumptions\n- Overtime is paid for hours beyond 40.\n")
    assert it["pass"] and it["evidence"] == "## Assumptions … Overtime"


def test_an_empty_heading_fails():
    it = item("Gross pay $1,333.20.\n\n## Assumptions\n\n## Limitations\n- overtime rules vary\n")
    assert not it["pass"] and it["detail"] == "heading without a task-specific entity"


def test_an_entity_only_in_the_heading_line_or_after_the_next_heading_fails():
    assert not item("## Assumptions about overtime\n\n## Notes\nnone\n")["pass"]
    assert not item("## Assumptions\n- none\n**Result**\n47 hours\n")["pass"]


def test_bold_and_plain_labels_count_their_own_line():
    assert item("**Assumptions:** Medicare at 1.45%\n")["pass"]
    assert item("Assumptions:\n- 47 hours in one week\n\n# Next\n")["pass"]


def test_entities_match_whole_words_only():
    assert not item("## Assumptions\n- a taxi fare is not included\n")["pass"]
    assert item("## Assumptions\n- no other tax applies\n")["pass"]


def test_no_heading_fails_and_a_later_section_can_pass():
    assert not item("Overtime and Medicare were assumed.")["pass"]
    assert item("## Assumptions\n\n## Main assumptions\n- withholding uses the Medicare rate\n")["pass"]


def test_items_without_entities_score_as_before():
    r = Rubric.model_validate({"required_deliverables": [{"name": "assumptions section", "any_of": PATTERNS}]})
    assert rubric_score("## Assumptions\n\n## Next\n", r)["items"][0]["pass"]
    assert section_entity("no heading", PATTERNS, ENT) == (None, None)
