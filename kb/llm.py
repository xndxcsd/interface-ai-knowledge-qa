"""OpenAI-backed answer synthesis (no response cache — harness repeat stays meaningful)."""
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


SYSTEM_PROMPT = """You answer Dupaco member questions using ONLY the evidence block.

Rules:
- Every rate/APY/APR must come from a FACT or SNIPPET row whose snapshot_id matches the newest evidence for that URL. Ignore STALE snippets and old snapshot rows when a newer snapshot exists for the same page.
- Match the product named in the question (Share Savings vs HSA vs Money Market vs business vs personal cards). Do not attribute one product's rate to another.
- For lists (cards, certificates), combine personal AND business pages when both appear in evidence.
- For Share Savings tier questions, use only Share Savings table rows; maximum Share Savings APY is 0.20%.
- Mortgage: prefer Purchase rows for the loan amount tier asked; do not quote expired Rate Relief promo rates as current standard rates unless the question asks about that program.
- Forbes recognition: prefer the newest newsroom story that states how many times Forbes recognized Dupaco (e.g. "fifth time").
- Branch info: use contact/locator evidence; include 8:30 lobby times when present; drive-up often 8 a.m.–6 p.m. at many branches.
- If evidence is insufficient, confident=false and say you don't know (no phone numbers unless in evidence).

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
        f"Answer as the website stood on {as_of} (use only evidence at or before that date)."
        if as_of
        else "Answer for the latest snapshot (newest page versions)."
    )
    user = f"{as_of_line}\n\nQuestion: {question}\n\n{evidence_block}"
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAIChatClient(model=model)
    raw = client.complete(SYSTEM_PROMPT, user)
    return _parse_llm_json(raw)
