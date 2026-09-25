"""D46 — a response cache for LLM replies and web tool results, so a run can be recorded once and replayed free.

Modes: "record" answers from the cache when it can and otherwise calls the real service and stores the reply;
"replay" answers only from the cache — a miss raises CacheMiss and never reaches the network; "off" passes every
call through. A reply is keyed by a hash of (model, messages, max_tokens, temperature) plus an optional
namespace (for example the repeat number, so repeats of the same prompt are not collapsed into one reply);
the seed is not part of the key. Files: <dir>/llm/<k[:2]>/<k>.json and <dir>/web/<k[:2]>/<k>.json, each
holding the request next to the reply so a cache can be read by eye.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from amoeba.llm.client import ChatResponse, LLMClient, Messages

MODES = ("record", "replay", "off")


class CacheMiss(RuntimeError):
    """Replay mode found no stored reply. Deliberately not a WebToolError, so it is never turned into a tool
    error string: the run stops with error "cache_miss" instead of falling back to a live call."""


def cache_key(parts: dict) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class _Store:
    def __init__(self, folder: str | Path, kind: str, mode: str, namespace: str = ""):
        if mode not in MODES:
            raise ValueError(f"cache mode must be one of {MODES}, not {mode!r}")
        self.dir, self.mode, self.namespace = Path(folder) / kind, mode, namespace
        self.hits = self.misses = self.stored = 0

    def path(self, k: str) -> Path:
        return self.dir / k[:2] / f"{k}.json"

    def get(self, k: str) -> dict | None:
        p = self.path(k)
        if self.mode != "off" and p.exists():
            self.hits += 1
            return json.loads(p.read_text(encoding="utf-8"))
        self.misses += 1
        return None

    def put(self, k: str, record: dict) -> None:
        if self.mode != "record":
            return
        p = self.path(k)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        self.stored += 1


# box: client
class CachedLLM(LLMClient):
    """Wraps any LLMClient. The wrapped client is only called on a miss in record (or off) mode."""

    def __init__(self, inner: LLMClient, folder: str | Path, mode: str = "record", namespace: str = ""):
        self.inner, self.model = inner, inner.model
        self.store = _Store(folder, "llm", mode, namespace)

    def key(self, messages: Messages, max_tokens: int | None) -> str:
        parts = {"model": self.model, "messages": messages, "max_tokens": max_tokens,
                 "temperature": getattr(self.inner, "temperature", None), "namespace": self.store.namespace}
        opts = getattr(self.inner, "request_options", None)
        if opts and any(opts.values()):      # D49: --merge-system / --reasoning-effort change the request
            parts["options"] = opts
        return cache_key(parts)

    def chat_messages(self, messages: Messages, seed: int = 0, max_tokens: int | None = None) -> ChatResponse:
        if self.store.mode == "off":
            return self.inner.chat_messages(messages, seed, max_tokens=max_tokens)
        k = self.key(messages, max_tokens)
        hit = self.store.get(k)
        if hit is not None:
            return ChatResponse(**{**hit["response"], "cached": True})
        if self.store.mode == "replay":
            raise CacheMiss(f"no cached reply (model {self.model}, key {k[:12]}) in {self.store.dir}")
        resp = self.inner.chat_messages(messages, seed, max_tokens=max_tokens)
        self.store.put(k, {"key": k, "model": self.model, "max_tokens": max_tokens,
                           "temperature": getattr(self.inner, "temperature", None),
                           "namespace": self.store.namespace, "messages": messages, "response": asdict(resp)})
        return resp


class CachedProvider:
    """Wraps a web SearchProvider (D32). The real provider is built only when a live call is needed, so replay
    works without its API key."""

    def __init__(self, make_inner: Callable[[], object], folder: str | Path, mode: str = "record",
                 namespace: str = "", name: str = "tavily"):
        self._make, self._inner = make_inner, None
        self.name = name
        self.store = _Store(folder, "web", mode, namespace)

    @property
    def inner(self):
        if self._inner is None:
            self._inner = self._make()
        return self._inner

    def _call(self, parts: dict, live: Callable[[], object]):
        if self.store.mode == "off":
            return live()
        k = cache_key({**parts, "provider": self.name, "namespace": self.store.namespace})
        hit = self.store.get(k)
        if hit is not None:
            return hit["result"]
        if self.store.mode == "replay":
            raise CacheMiss(f"no cached {parts['op']} result ({self.name}, key {k[:12]}) in {self.store.dir}")
        result = live()
        self.store.put(k, {"key": k, **parts, "provider": self.name, "result": result})
        return result

    def search(self, query: str, max_results: int) -> list[dict]:
        return self._call({"op": "search", "query": query, "max_results": max_results},
                          lambda: self.inner.search(query, max_results))

    def fetch(self, url: str) -> dict:
        return self._call({"op": "fetch", "url": url}, lambda: self.inner.fetch(url))
