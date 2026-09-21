"""Copy the prompt templates verbatim out of the source clones into amoeba/config/prompts/.

Run once after ./clone_sources.sh:  python -m scripts.extract_prompts
Each file = one source-header line + the exact string the source code holds (AutoAgents: the value of the
named module constant, evaluated from the cited lines; AgentVerse: the YAML block scalar).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REPOS = ROOT / "repos"
OUT = ROOT / "amoeba" / "config" / "prompts"

# stem -> (relative source path, variable/key, (first_line, last_line), license)
AUTOAGENTS = "AutoAgents/autoagents/actions"
AGENTVERSE = "AgentVerse/agentverse/tasks/tasksolving/pythoncalculator/config.yaml"
SOURCES: dict[str, tuple[str, str, tuple[int, int], str]] = {
    "autoagents_create_roles": (f"{AUTOAGENTS}/create_roles.py", "PROMPT_TEMPLATE", (9, 59), "MIT"),
    "autoagents_create_roles_format": (f"{AUTOAGENTS}/create_roles.py", "FORMAT_EXAMPLE", (61, 95), "MIT"),
    "autoagents_check_roles": (f"{AUTOAGENTS}/check_roles.py", "PROMPT_TEMPLATE", (9, 62), "MIT"),
    "autoagents_check_roles_format": (f"{AUTOAGENTS}/check_roles.py", "FORMAT_EXAMPLE", (64, 74), "MIT"),
    "autoagents_check_plans": (f"{AUTOAGENTS}/check_plans.py", "PROMPT_TEMPLATE", (8, 44), "MIT"),
    "autoagents_check_plans_format": (f"{AUTOAGENTS}/check_plans.py", "FORMAT_EXAMPLE", (46, 56), "MIT"),
    "autoagents_custom_action": (f"{AUTOAGENTS}/custom_action.py", "PROMPT_TEMPLATE", (18, 58), "MIT"),
    "autoagents_custom_action_format": (f"{AUTOAGENTS}/custom_action.py", "FORMAT_EXAMPLE", (60, 77), "MIT"),
    "agentverse_solver_prepend": (AGENTVERSE, "prompts.solver_prepend_prompt", (28, 32), "Apache-2.0"),
    "agentverse_solver_append": (AGENTVERSE, "prompts.solver_append_prompt", (34, 35), "Apache-2.0"),
    "agentverse_critic_prepend": (AGENTVERSE, "prompts.critic_prepend_prompt", (37, 42), "Apache-2.0"),
    "agentverse_critic_append": (AGENTVERSE, "prompts.critic_append_prompt", (44, 64), "Apache-2.0"),
}


def source_value(rel: str, key: str, lines: tuple[int, int]) -> str:
    """The exact string the source holds at the cited lines."""
    path = REPOS / rel
    text = path.read_text(encoding="utf-8")
    if rel.endswith(".py"):
        a, b = lines
        snippet = "\n".join(text.split("\n")[a - 1:b])
        ns: dict = {}
        exec(snippet, ns)  # the slice is exactly `NAME = '''...'''`
        return ns[key]
    doc = yaml.safe_load(text)
    node = doc
    for part in key.split("."):
        node = node[part]
    return node


def header(stem: str) -> str:
    rel, key, (a, b), lic = SOURCES[stem]
    return f"# source: repos/{rel}:{a}-{b} {key} ({lic})"


def main() -> int:
    if not REPOS.exists():
        print("repos/ missing — run ./clone_sources.sh first", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for stem, (rel, key, lines, _lic) in SOURCES.items():
        body = source_value(rel, key, lines)
        (OUT / f"{stem}.txt").write_text(header(stem) + "\n" + body, encoding="utf-8", newline="\n")
        print(f"wrote {stem}.txt ({len(body)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
