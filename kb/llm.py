"""OpenAI-backed answer synthesis (no response cache)."""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

LLM_TIMEOUT_S = float(os.getenv("OPENAI_TIMEOUT_S", "15"))
_DEFAULT_MAX_TOKENS = 768

_openai_client: Any | None = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            timeout=LLM_TIMEOUT_S,
            max_retries=0,
        )
    return _openai_client


def llm_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


SYSTEM_PROMPT = """You answer member questions using ONLY the evidence block.

Rules:
- Match row= labels to the term, tier, model year, or product wording the question specifies; do not borrow a nearby row.
- If no evidence row matches what was asked for, set confident=false and say it is not listed.
- If the question asks for APY or yield, use the APY/yield column—not dividend rate alone. If it asks APR, use the APR column.
- Prefer the newest snapshot_id and highest-authority rows when rows disagree.
- Quote numbers, times, phones, addresses, and URLs exactly as they appear in the evidence you use.
- For broad list requests, include items from every relevant product page represented in the evidence.
- Ignore STALE-tagged snippets for current-rate questions unless no newer row exists.
- If asked for a specific branch's hours and evidence only shows general hours, say branch-specific hours are not listed and label any general schedule as general—not that branch's.
- If the evidence does not contain the answer, set confident=false and say you don't know.

Respond with JSON: {"text":"...", "source_urls":["https://..."], "confident":true|false}"""


def _parse_llm_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    return json.loads(raw)


def _llm_call_once(question: str, evidence_block: str, as_of: str | None) -> dict:
    as_of_line = (
        f"Answer as the website stood on {as_of} (evidence at or before that date)."
        if as_of
        else "Answer using the latest snapshot versions in the evidence."
    )
    user = f"{as_of_line}\n\nQuestion: {question}\n\n{evidence_block}"
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = _get_openai_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        temperature=0,
        max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", str(_DEFAULT_MAX_TOKENS))),
        response_format={"type": "json_object"},
    )
    raw = (resp.choices[0].message.content or "").strip()
    return _parse_llm_json(raw)


def llm_answer_from_evidence(
    question: str, evidence_block: str, as_of: str | None
) -> dict:
    wall = float(os.getenv("LLM_WALL_S", "20"))
    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(_llm_call_once, question, evidence_block, as_of)
    try:
        return fut.result(timeout=wall)
    except FuturesTimeout as e:
        ex.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError("LLM wall-clock deadline exceeded") from e
    finally:
        if fut.done():
            ex.shutdown(wait=False)
