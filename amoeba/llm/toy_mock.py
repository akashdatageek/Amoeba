"""A scripted stand-in for a model on the toy tasks, so `scripts/run_task.py --toy` runs offline.

It behaves the way a well-behaved model would: the planner drafts a two-role team, observers approve, the
worker uses `calc` for arithmetic and then says `Final Output`, the solver answers directly, critics agree.
Nothing here is used by the acceptance tests' scripted fixtures; it exists so the end-to-end path can run.
"""
from __future__ import annotations

import re

from amoeba.llm.client import Messages, MockLLMClient
from amoeba.task.source import solve_toy

DRAFT = '''## Thought
The task is small: one role works it out, one language expert states the answer.

## Question or Task:
{task}

## Selected Roles List:
```
```

## Created Roles List:
```
{{
    "name": "Solver",
    "description": "Works out the answer to the task, using the calc tool for any arithmetic.",
    "tools": ["calc"],
    "suggestions": "Use calc for arithmetic. Reply with only the final value.",
    "prompt": "You are a careful problem solver. Do exactly what the task asks and report only the result."
}},
{{
    "name": "Language Expert",
    "description": "A language expert with no tools who states the final result.",
    "tools": [],
    "suggestions": "Copy the final result exactly; add nothing.",
    "prompt": "You are a language expert. Restate the final result exactly as given, in one line."
}}
```

## Execution Plan:
1. [Solver]: Solve the task and report the result.
2. [Language Expert]: Restate the Solver's result as the final answer.

## RoleFeedback
None yet.

## PlanFeedback
None yet.
'''

NO_SUGGESTIONS = "## Thought\nThe roles and the plan are adequate for this task.\n\n## Suggestions\nNo Suggestions\n"

WORKER = "## Thought\n{thought}\n\n## Task\n{task}\n\n## CurrentStep\n{step}\n\n## Action\n{action}\n\n## ActionInput\n{inp}\n"

OFFLINE = "(offline mock) no answer"


def _planner(messages: Messages, seed: int) -> str:
    m = re.search(r"\[Question/Task: (.*?)\]\n", messages[-1]["content"], re.S)
    return DRAFT.format(task=m.group(1) if m else "")


def _worker(messages: Messages, seed: int) -> str:
    user = messages[-1]["content"]
    task = re.search(r"\[Question/Task: (.*?)(?:, user: |\])", user, re.S)
    task = task.group(1) if task else ""
    step = re.search(r"# Task (.*?)\n", user)
    step = step.group(1) if step else ""
    done = re.search(r"# Completed Steps and Responses (.*?)\n\nYou have access", user, re.S)
    done = done.group(1) if done else ""
    if "Language Expert" in step:
        finals = re.findall(r">>>> Final Output\n\n(.*?)\n\n>>>>", user, re.S)
        answer = finals[-1].strip() if finals else (solve_toy(task) or OFFLINE)
        return WORKER.format(thought="Restate the established result.", task=task, step="State the final answer.",
                             action="Final Output", inp=answer)
    expr = re.search(r"Compute (.+?)\. Reply", task)
    if expr:
        results = re.findall(r">Subresponse:\n(.*?)\n", done)
        if not results:
            return WORKER.format(thought="Arithmetic — use the calculator.", task=task, step="Evaluate the expression.",
                                 action="calc", inp=expr.group(1))
        return WORKER.format(thought="The calculator answered; report it.", task=task, step="Report the result.",
                             action="Final Output", inp=results[-1].strip())
    return WORKER.format(thought="Work it out directly.", task=task, step="Compute the result.",
                         action="Final Output", inp=solve_toy(task) or OFFLINE)


def _solver(messages: Messages, seed: int) -> str:
    m = re.search(r"You are faced with the task:\n(.*?)\n\nBelow", messages[0]["content"], re.S)
    return solve_toy(m.group(1) if m else "") or OFFLINE


def toy_mock_client() -> MockLLMClient:
    return MockLLMClient(script={
        "planner": _planner,
        "agent_observer": [NO_SUGGESTIONS],
        "plan_observer": [NO_SUGGESTIONS],
        "worker": _worker,
        "solver": _solver,
        "critic": ["Action: Agree\nAction Input: Agree."],
    }, model="toy-mock")
