"""Optional OpenAI-backed answer synthesis."""
from __future__ import annotations

import os
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
            max_tokens=500,
        )
        return (resp.choices[0].message.content or "").strip()


def get_llm_client() -> ChatClient | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        return OpenAIChatClient()
    except Exception:
        return None


SYSTEM_PROMPT = """You answer credit-union member questions using ONLY the provided evidence snippets.
Rules:
- Use current official rate pages over blogs, calculators, or old press releases.
- Distinguish rate vs APY, standard vs intro APR, personal vs business, jumbo vs standard tiers.
- If evidence is insufficient, reply with exactly: I don't know.
- Be concise (2-4 sentences). Include specific numbers only when supported.
- Do not invent branch hours, rates, or URLs."""
