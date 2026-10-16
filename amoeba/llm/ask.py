"""D141 — `ask`: one structured call under protocol v2, in the output mode the model passed (D135/D140's model check).

    schema       the provider enforces the JSON schema (Claude's output_config.format; OpenAI-style response_format)
    submit_tool  a tool submit_<kind> whose parameters are the schema; the model is asked to call it, never forced
    json_prompt  the schema is shown in the prompt; the reply's JSON is validated by pydantic

Every mode validates the reply in code (`validate_reply`), and an invalid reply gets one repair call that quotes the
exact validation error. A blocked reply, or a second invalid one, raises `Unreadable`. A schema Claude's structured
outputs cannot take (a free-form dict, too many optional fields) goes as json_prompt.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from amoeba.llm.anthropic_client import AnthropicClient, SchemaTooComplex, is_anthropic, to_claude_schema
from amoeba.llm.cache import is_blocked
from amoeba.llm.client import MockLLMClient, parse_schema_reply, tool_fn_name, validate_reply

MODES = ("schema", "submit_tool", "json_prompt")
SUBMIT_NOTE = ("When your answer is ready, call the tool {name} once with it as its arguments. Do not write the answer "
               "as text.")
JSON_NOTE = ("Reply with only one JSON object that matches this JSON schema, nothing else:\n{schema}")
REPAIR_NOTE = "That reply did not validate: {error}\nReply again with the corrected answer only."
# D141: a schema the provider refused to compile (Claude: "The compiled grammar is too large"); it goes as json_prompt
SCHEMA_REJECTED = re.compile(r"(?i)grammar is too large|schema is too complex|too many (?:optional|properties)|"
                             r"invalid (?:json[_ ])?schema|response_format")
REJECTED: set[str] = set()           # schema names refused this process (no second 400 per call)


# box: client
class Unreadable(ValueError):
    """No valid structured reply after the repair call (or a blocked reply). raw: the last reply's text;
    blocked/category: the provider blocked it (D128/D134)."""

    def __init__(self, why: str, raw: str = "", blocked: bool = False, category: str | None = None):
        super().__init__(why)
        self.why, self.raw, self.blocked, self.category = why, raw, blocked, category


# box: client
def output_mode_of(llm) -> str:
    """The output mode the model behind `llm` passed in the model check (models.yaml supports.output_mode). The
    mock answers schema calls; Claude's own API is `schema`; a router uses its models' common mode; anything
    unknown is `json_prompt`, which every model can do."""
    from amoeba.llm.router import load_registry
    inner = getattr(llm, "llm", llm) if hasattr(llm, "trace") else llm
    for _ in range(6):
        if isinstance(inner, MockLLMClient):
            return getattr(inner, "output_mode", "schema")
        if isinstance(inner, AnthropicClient):
            return "schema"
        if hasattr(inner, "registry") and hasattr(inner, "route"):             # D97 ModelRouter
            names = [inner.fixed] if inner.mode == "fixed" else \
                [n for n in (inner.profile_allowed or inner.allowed or list(inner.registry)) if n in inner.registry]
            modes = {(inner.registry[n].supports or {}).get("output_mode") for n in names if n in inner.registry}
            return modes.pop() if len(modes) == 1 and None not in modes else "json_prompt"
        nxt = getattr(inner, "inner", None) or getattr(inner, "default", None)  # CachedLLM, RoleRouter
        if nxt is None:
            break
        inner = nxt
    model = getattr(inner, "model", None)
    try:
        reg, _ = load_registry()
    except Exception:
        return "json_prompt"
    e = next((e for e in reg.values() if e.model == model and not is_anthropic(e.provider)), None)
    mode = (e.supports or {}).get("output_mode") if e else None
    return mode if mode in MODES else "json_prompt"


# box: client
def validation_error(schema, content: str) -> str:
    """The exact reason a JSON reply does not validate (pydantic's first errors, or the JSON error)."""
    text = (content or "").strip()
    m = re.search(r"(?s)```(?:json)?\s*(.*?)```", text)
    text = m.group(1).strip() if m else text
    try:
        schema.model_validate_json(text)
    except ValidationError as e:
        return "; ".join(f"{'.'.join(map(str, x['loc'])) or 'reply'}: {x['msg']}" for x in e.errors()[:4])
    except ValueError as e:
        return f"not JSON ({str(e)[:120]})"
    return "no error"


def _with_note(messages: list[dict], note: str) -> list[dict]:
    out = [dict(m) for m in messages]
    for m in reversed(out):
        if m.get("role") == "user":
            m["content"] = f"{m.get('content') or ''}\n\n{note}"
            return out
    return out + [{"role": "user", "content": note}]


def submit_spec(kind: str, schema: type[BaseModel]) -> dict:
    name = tool_fn_name(f"submit_{kind}")
    return {"type": "function", "function": {"name": name, "description": f"submit the {kind} answer (call it once)",
                                             "parameters": to_claude_schema(schema)}}


# box: client
def ask(llm, kind: str, messages: list[dict], schema: type[BaseModel], max_tokens: int | None = None,
        seed: int = 0, **ids) -> BaseModel:
    """One structured call (TracedLLM `llm`) in the model's output mode; the validated model instance. Raises
    Unreadable after one repair call, or at once on a blocked reply."""
    mode = output_mode_of(llm)
    if mode in ("schema", "submit_tool"):
        try:
            to_claude_schema(schema)
        except SchemaTooComplex:
            mode = "json_prompt"
        if schema.__name__ in REJECTED:
            mode = "json_prompt"
    try:
        return _ask(llm, kind, messages, schema, mode, max_tokens, seed, ids)
    except Exception as e:
        if mode == "json_prompt" or isinstance(e, Unreadable) or not SCHEMA_REJECTED.search(str(e)):
            raise
        REJECTED.add(schema.__name__)       # the provider would not compile it: the same call once more as json_prompt
        llm.trace.event("ask_schema_rejected", {"amoeba.box": "client", "amoeba.kind": kind, "amoeba.mode": mode,
                                                "amoeba.schema": schema.__name__, "amoeba.error": str(e)[:300]})
        return _ask(llm, kind, messages, schema, "json_prompt", max_tokens, seed, ids)


def _ask(llm, kind: str, messages: list[dict], schema, mode: str, max_tokens, seed: int, ids: dict) -> BaseModel:
    llm.trace.event("ask", {"amoeba.box": "client", "amoeba.kind": kind, "amoeba.mode": mode,
                            "amoeba.schema": schema.__name__, "gen_ai.agent.name": ids.get("agent_name")})
    msgs, kw = list(messages), {}
    if mode == "schema":
        kw["schema"] = schema
    elif mode == "submit_tool":
        spec = submit_spec(kind, schema)
        kw["tools"] = [spec]
        msgs = _with_note(msgs, SUBMIT_NOTE.format(name=spec["function"]["name"]))
    else:
        try:
            shown = to_claude_schema(schema)
        except SchemaTooComplex:
            shown = schema.model_json_schema()
        msgs = _with_note(msgs, JSON_NOTE.format(schema=json.dumps(shown, ensure_ascii=False)))
    resp, data, raw = None, None, ""
    for attempt in (1, 2):
        resp = llm.chat_messages(msgs, seed, max_tokens=max_tokens, **kw, **ids)
        if is_blocked(resp):
            raise Unreadable("blocked by the provider", blocked=True, category=resp.refusal_category)
        data, raw = _read(resp, mode, schema, kind)
        if data is not None:
            break
        if attempt == 1:                     # one repair call quoting the exact error
            msgs = msgs + [{"role": "assistant", "content": raw or "(no answer)"},
                           {"role": "user", "content": REPAIR_NOTE.format(error=validation_error(schema, raw))}]
    if data is None:
        llm.trace.event("ask_unreadable", {"amoeba.box": "client", "amoeba.kind": kind, "amoeba.mode": mode,
                                           "amoeba.error": validation_error(schema, raw)[:300]})
        raise Unreadable(f"no valid {schema.__name__} after one repair call: {validation_error(schema, raw)}", raw=raw)
    out = schema.model_validate(data)
    if getattr(out, "rationale", None):
        llm.trace.event("ask_rationale", {"amoeba.box": "client", "amoeba.kind": kind, "amoeba.rationale": out.rationale})
    return out


def _read(resp, mode: str, schema, kind: str) -> tuple[dict | None, str]:
    if mode == "schema":
        data = resp.parsed if resp.parsed is not None else parse_schema_reply(schema, resp.content)
        return (validate_reply(schema, data) if isinstance(data, dict) else None), resp.content or ""
    if mode == "submit_tool":
        name = tool_fn_name(f"submit_{kind}")
        call = next((c for c in resp.tool_calls or [] if c.get("name") == name), None)
        if call is not None:
            try:
                args = json.loads(call.get("input") or "{}")
            except ValueError:
                return None, call.get("input") or ""
            return validate_reply(schema, args), call.get("input") or ""
        return parse_schema_reply(schema, resp.content), resp.content or ""
    return parse_schema_reply(schema, resp.content), resp.content or ""


# box: client
def protocol_of(trace) -> str:
    """D141: the run's protocol ("legacy" | "v2"), carried on its TraceWriter so every call site can see it."""
    return getattr(trace, "protocol", "legacy") or "legacy"
