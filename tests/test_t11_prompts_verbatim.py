"""T11 — every prompt file body equals the string the source holds at the cited lines."""
import pytest

from amoeba.config.prompts import PROMPT, load_prompt, prompt_source, render
from scripts.extract_prompts import REPOS, SOURCES, header, source_value

pytestmark = pytest.mark.skipif(not REPOS.exists(), reason="run ./clone_sources.sh to get the source repos")


@pytest.mark.parametrize("stem", sorted(SOURCES))
def test_prompt_file_is_verbatim(stem):
    rel, key, (a, b), _lic = SOURCES[stem]
    expected = source_value(rel, key, (a, b))
    assert load_prompt(stem) == expected
    assert prompt_source(stem) == header(stem)
    # the cited line range really holds that text
    cited = (REPOS / rel).read_text(encoding="utf-8").split("\n")[a - 1:b]
    first_line = expected.strip().splitlines()[0]
    assert any(first_line in line for line in cited), (stem, first_line)


def test_derived_solver_append_drops_only_the_code_sentence():
    verbatim = PROMPT.agentverse_solver_append
    assert verbatim.endswith("Write the code step by step.")
    assert PROMPT.agentverse_solver_append_generic == verbatim[: -len(" Write the code step by step.")]


def test_single_format_render_collapses_quadruple_braces():
    rendered = render(PROMPT.autoagents_create_roles, context="c", existing_roles="[]", tools="t", history="h",
                      suggestions="s", format_example=PROMPT.autoagents_create_roles_format)
    assert "{{\n    \"name\": \"ROLE NAME\"" in rendered and "{{{{" not in rendered
    assert "# Question or Task\nc\n" in rendered and "# Suggestions\ns\n" in rendered
    fmt = render(PROMPT.autoagents_custom_action, role="r", context="x", suggestions="", previous="", completed_steps="",
                 tool="['calc']", format_example=PROMPT.autoagents_custom_action_format)
    assert "must be one of [{tool}]" in fmt   # the FORMAT_EXAMPLE's placeholder stays literal, as in the original
