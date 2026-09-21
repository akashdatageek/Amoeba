"""Prompt files copied verbatim from the source repos (spec §7), one source-header line each.

``PROMPT.<stem>`` returns the body of ``<stem>.txt`` with its header line removed.
``render(template, **kw)`` fills either ``{x}`` placeholders (AutoAgents, ``str.format`` applied exactly once so
the ``{{{{ }}}}`` in the templates collapse the way the original code does) or ``${x}`` placeholders (AgentVerse,
``string.Template.safe_substitute``).
"""
from __future__ import annotations

from pathlib import Path
from string import Template

PROMPT_DIR = Path(__file__).parent

# AutoAgents role.py:17 PREFIX_TEMPLATE, filled for the two static roles. Sent as the system message of
# every call the Manager makes (action.py:60; manager.py:17) and of every Group worker call (group.py:23).
MANAGER_PREFIX = ("You are a Manager, named Ethan, your goal is Efficiently to finish the tasks or solve the "
                  "problem, and the constraint is . ")
GROUP_PREFIX = ("You are a Group, named Alex, your goal is Effectively delivering information according to "
                "plan., and the constraint is . ")

# Prompts we derive from a verbatim file (kept out of the files so T11 can compare those byte for byte).
# DEVIATION (spec §7): the AgentVerse solver append prompt ends "Write the code step by step." — dropped for
# non-code tasks.
_DERIVED = {
    "agentverse_solver_append_generic": lambda: PROMPT.agentverse_solver_append.replace(
        " Write the code step by step.", ""),
}


def prompt_path(stem: str) -> Path:
    return PROMPT_DIR / f"{stem}.txt"


def prompt_source(stem: str) -> str:
    """The header line naming where the prompt was copied from."""
    return prompt_path(stem).read_text(encoding="utf-8").split("\n", 1)[0]


def load_prompt(stem: str) -> str:
    if stem in _DERIVED:
        return _DERIVED[stem]()
    text = prompt_path(stem).read_text(encoding="utf-8")
    head, _, body = text.partition("\n")
    if not head.startswith("#"):
        raise ValueError(f"prompt {stem} lacks its source header line")
    return body


class _Prompts:
    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def __getattr__(self, stem: str) -> str:
        if stem.startswith("_"):
            raise AttributeError(stem)
        if stem not in self._cache:
            self._cache[stem] = load_prompt(stem)
        return self._cache[stem]


PROMPT = _Prompts()


def render(template: str, **kw) -> str:
    if "${" in template:
        return Template(template).safe_substitute(**kw)
    return template.format(**kw)


def resolve(ref: str) -> str:
    """A PromptRef field: ``seed:<stem>`` loads a prompt file; anything else is literal text."""
    if ref.startswith("seed:"):
        return getattr(PROMPT, ref[len("seed:"):])
    return ref
