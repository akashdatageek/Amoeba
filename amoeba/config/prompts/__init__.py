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

# DEVIATION D19 (spec §11): the planner may REQUEST capabilities we lack instead of being told never to invent
# tools; both observers see and critique those requests. The copied files stay verbatim (T11); these variants are
# the verbatim text with the exact replacements below, and a replacement whose source text is gone fails loudly.
CAPABILITY_REQUEST_KEYS = ("name, kind (tool|skill), for_role, what_it_does, input, output, "
                           "example_input, example_output")
CAPABILITY_EDITS: dict[str, list[tuple[str, str]]] = {
    "autoagents_create_roles": [
        ("tools (from {tools} only)",
         "tools (prefer existing tools from {tools}; a tool or skill we lack goes under Capability Requests)"),
        ("2. Use only existing tools {tools}; do NOT invent new tools.",
         "2. Prefer existing tools {tools}. If a role needs a tool or skill we don't have, list it under a section "
         "'## Capability Requests' as one JSON blob per request with keys: " + CAPABILITY_REQUEST_KEYS
         + ". Write None there when the existing tools are enough."),
    ],
    "autoagents_create_roles_format": [
        ("## RoleFeedback",
         "## Capability Requests:\n```\nJSON BLOB 1,\nJSON BLOB 2\n```\n\n## RoleFeedback"),
    ],
    "autoagents_check_roles": [
        ("# Created Roles List\n{created_roles}\n",
         "# Created Roles List\n{created_roles}\n\n# Capability Requests\n{capability_requests}\n"),
        ("tools (from {tools} only)",
         "tools (prefer {tools}; anything else must appear under Capability Requests)"),
        ("4. Ensure no tool outside ({tools}) is referenced; remove any that are.",
         "4. A tool outside ({tools}) may appear only if it is listed under Capability Requests. For each request, "
         "say whether it is really needed and whether an existing tool is enough."),
        ("4. Only use existing tools ({tools}); do NOT create new tools.",
         "4. Prefer existing tools ({tools}); a missing tool or skill is requested under Capability Requests, "
         "never invented silently."),
    ],
    "autoagents_check_plans": [
        ("# Execution Plan\n{plan}\n",
         "# Execution Plan\n{plan}\n\n# Capability Requests\n{capability_requests}\n"),
        ("1. Only use existing tools {tools}; do NOT create new tools.",
         "1. Prefer existing tools {tools}. For each Capability Request, say whether the plan really needs it or "
         "whether an existing tool is enough."),
    ],
}


def _with_capability_requests(stem: str) -> str:
    text = getattr(PROMPT, stem)
    for old, new in CAPABILITY_EDITS[stem]:
        if text.count(old) != 1:
            raise ValueError(f"D19 edit for {stem}: expected exactly one {old!r} in the verbatim prompt")
        text = text.replace(old, new)
    return text


for _stem in CAPABILITY_EDITS:
    _DERIVED[f"{_stem}_d19"] = (lambda s=_stem: _with_capability_requests(s))


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
