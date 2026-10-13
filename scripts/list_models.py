"""D54: print the models an OpenAI-compatible endpoint offers, to check a profile's model names before a run.

    python -m scripts.list_models --profile gemma-api
    python -m scripts.list_models --profile gemma-openrouter --filter gemma

The endpoint and key come from the profile (amoeba/config/models.yaml), with the same overrides as run_task
(--base-url / AMOEBA_BASE_URL, --api-key / AMOEBA_API_KEY). One request to the endpoint's model list; no model is
called. Models the profile uses are marked with '*'; a profile model the endpoint does not list is reported.
"""
from __future__ import annotations

import argparse
import sys

from amoeba.llm.profiles import get_profile
from scripts.run_task import endpoint


def model_ids(client) -> list[str]:
    return sorted(m.id for m in client.models.list())


def bare(model_id: str) -> str:
    """Gemini's OpenAI-compatible list names models 'models/<id>'; requests take '<id>'."""
    return model_id.removeprefix("models/")


def anthropic_headers(base_url: str | None) -> dict:
    """Claude's model list is the native endpoint: it needs an anthropic-version header and the key as x-api-key
    (chat completions take the OpenAI-style bearer key)."""
    return {"anthropic-version": "2023-06-01"} if "api.anthropic.com" in (base_url or "") else {}


def main(argv: list[str] | None = None, make_client=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--profile", default=None, help="default: the default profile of amoeba/config/models.yaml")
    p.add_argument("--base-url", default=None)
    p.add_argument("--api-key", default=None)
    p.add_argument("--filter", default="", help="show only ids containing this text (case-insensitive)")
    args = p.parse_args(argv)
    profile = get_profile(args.profile)
    base_url, api_key = endpoint(args, profile)
    if make_client is None:
        from openai import OpenAI
        headers = anthropic_headers(base_url)
        make_client = lambda: OpenAI(base_url=base_url, api_key=api_key, max_retries=0, default_headers=headers)
    ids = model_ids(make_client())
    used = {profile.model, *(r["model"] for r in profile.roles.values() if r.get("model"))}
    shown = [i for i in ids if args.filter.lower() in i.lower()]
    print(f"== {len(shown)} of {len(ids)} models at {base_url} (profile {profile.name})")
    for i in shown:
        print(("* " if bare(i) in used else "  ") + i)
    missing = sorted(m for m in used if m not in {bare(i) for i in ids})
    if missing:
        print(f"!! not offered here: {', '.join(missing)} — fix the profile's model name")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
