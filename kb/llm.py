"""OpenAI-backed answer synthesis (no response cache)."""
from __future__ import annotations

import json
import os
import re
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
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "320")),
        )
        return (resp.choices[0].message.content or "").strip()


def get_llm_client() -> ChatClient | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        return OpenAIChatClient()
    except Exception:
        return None


SYSTEM_PROMPT = """You answer member questions using ONLY the evidence block.

Rules:
- Match the product, tier, term, and qualifiers named in the question. Do not substitute a different product or tier.
- Prefer the newest snapshot_id and highest-authority rows when rows disagree.
- Quote numbers, times, phones, addresses, and URLs exactly as they appear in the evidence you use.
- For broad list requests, include items from every relevant product page represented in the evidence.
- Ignore STALE-tagged snippets for current-rate questions unless no newer row exists.
- If the evidence does not contain the answer, set confident=false and say you don't know.

JSON only:
{"text":"...", "source_urls":["https://..."], "confident":true|false}"""


def _parse_llm_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    return json.loads(raw)


def llm_answer_from_evidence(
    question: str, evidence_block: str, as_of: str | None
) -> dict:
    as_of_line = (
        f"Answer as the website stood on {as_of} (evidence at or before that date)."
        if as_of
        else "Answer using the latest snapshot versions in the evidence."
    )
    user = f"{as_of_line}\n\nQuestion: {question}\n\n{evidence_block}"
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAIChatClient(model=model)
    raw = client.complete(SYSTEM_PROMPT, user)
    return _parse_llm_json(raw)
