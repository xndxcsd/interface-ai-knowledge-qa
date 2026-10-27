"""OpenAI-backed answer synthesis with optional response cache."""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Protocol


class ChatClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class OpenAIChatClient:
    def __init__(self, model: str | None = None):
        from openai import OpenAI

        self._client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            max_tokens=450,
        )
        return (resp.choices[0].message.content or "").strip()


def get_llm_client() -> ChatClient | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        return OpenAIChatClient()
    except Exception:
        return None


SYSTEM_PROMPT = """You are a Dupaco credit union member service agent. Answer ONLY from the evidence block.

Rules:
- Prefer STRUCTURED FACTS from official product pages (high authority, stale_for_rates=no) over blogs, calculators, newsroom, or STALE snippets.
- Respect tiers: jumbo vs standard certificate, loan amount tiers, model year, personal vs business, dividend rate vs APY, intro vs standard APR.
- For branch hours/addresses, quote what the evidence shows; say schedules vary by branch when evidence differs.
- If the evidence does not support a precise answer, set confident=false and say you don't know (no guessing, no phone numbers unless in evidence).
- Cite 1-3 source URLs you actually used in source_urls.

Respond with a single JSON object only (no markdown):
{"text": "member-facing answer", "source_urls": ["https://..."], "confident": true|false}"""


def _parse_llm_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    return json.loads(raw)


@lru_cache(maxsize=512)
def _cached_complete(model: str, system: str, user: str) -> str:
    client = OpenAIChatClient(model=model)
    return client.complete(system, user)


def llm_answer_from_evidence(
    question: str, evidence_block: str, as_of: str | None
) -> dict:
    as_of_line = f"Answer as the website stood on {as_of}." if as_of else "Answer using the latest snapshot state."
    user = f"{as_of_line}\n\nQuestion: {question}\n\nEvidence:\n{evidence_block}"
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if os.getenv("OPENAI_API_KEY"):
        raw = _cached_complete(model, SYSTEM_PROMPT, user)
    else:
        raise RuntimeError("no key")
    return _parse_llm_json(raw)
