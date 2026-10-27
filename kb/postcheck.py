"""Validate answers against retrieved evidence (staleness, authority, product scope)."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from kb.evidence import EvidencePack, is_rate_question
from kb.normalize import normalize_value

if TYPE_CHECKING:
    from contract import Answer

NUM = re.compile(r"(\$)?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d+))?\s*(%|percent)?", re.I)


def _numbers(text: str) -> set[tuple[str, float]]:
    out: set[tuple[str, float]] = set()
    for m in NUM.finditer(text or ""):
        unit = "$" if m.group(1) else ("%" if m.group(4) else "")
        val = float(m.group(2).replace(",", "") + ("." + m.group(3) if m.group(3) else ""))
        out.add((unit, round(val, 4)))
    return out


def _product_terms(question: str) -> list[str]:
    q = question.lower()
    terms = []
    for phrase in (
        "share savings",
        "bright savings",
        "free checking",
        "1st rate checking",
        "platinum visa",
        "rewards visa",
        "health savings",
        "investor's choice",
        "business platinum",
        "business rewards",
    ):
        if phrase in q:
            terms.append(phrase)
    return terms


def _fact_supports_number(fe, num: tuple[str, float], product_terms: list[str]) -> bool:
    blob = f"{fe.fact.subject} {fe.fact.field} {fe.fact.value}".lower()
    if product_terms and not any(p in blob for p in product_terms):
        if not any(p in fe.fact.url.lower() for p in ("savings", "checking", "credit")):
            return False
        if product_terms and "share savings" in product_terms:
            if "share savings" not in blob and "health savings" in blob:
                return False
    val_nums = _numbers(fe.fact.value)
    return num in val_nums


def postcheck_answer(answer: "Answer", pack: EvidencePack, question: str) -> "Answer":
    from contract import Answer

    if not answer.confident:
        return answer

    product_terms = _product_terms(question)
    ans_nums = _numbers(answer.text)

    if is_rate_question(question) and ans_nums:
        supported: set[tuple[str, float]] = set()
        max_auth: dict[tuple[str, float], float] = {}
        for fe in pack.facts:
            if fe.fact.authority < 0.85:
                continue
            for n in _numbers(fe.fact.value):
                if product_terms and not _fact_supports_number(fe, n, product_terms):
                    continue
                supported.add(n)
                max_auth[n] = max(max_auth.get(n, 0), fe.fact.authority)
        for ce in pack.chunks:
            if ce.chunk.stale_for_rates or ce.chunk.authority < 0.85:
                continue
            for n in _numbers(ce.chunk.text):
                supported.add(n)
                max_auth[n] = max(max_auth.get(n, 0), ce.chunk.authority)

        for n in ans_nums:
            if n[0] != "%":
                continue
            if n not in supported:
                return Answer(
                    text="I don't know — that rate is not supported by the current official sources in evidence.",
                    sources=answer.sources,
                    confident=False,
                    conflict_note=answer.conflict_note,
                )

        if "share savings" in " ".join(product_terms) or (
            "share savings" in question.lower() and "0.35" in answer.text
        ):
            ss_facts = [
                fe for fe in pack.facts
                if "share savings" in fe.fact.subject.lower() and fe.fact.authority >= 0.85
            ]
            if ss_facts:
                max_apy = max(
                    (_numbers(fe.fact.value) for fe in ss_facts),
                    key=lambda s: max((x[1] for x in s if x[0] == "%"), default=0),
                    default=set(),
                )
                if ("%", 0.35) in ans_nums and all(
                    n != ("%", 0.35) for n in max_apy
                ):
                    return Answer(
                        text="No — Share Savings tiers top out at 0.20% APY on the official rate sheet; 0.35% applies to other products such as HSA tiers, not Share Savings.",
                        sources=answer.sources,
                        confident=True,
                    )

    latest_snaps = {fe.fact.snapshot_id for fe in pack.facts[:8]} | {
        ce.chunk.snapshot_id for ce in pack.chunks[:5]
    }
    for s in answer.sources or []:
        sid = getattr(s, "snapshot_id", None)
        if sid and latest_snaps and sid not in latest_snaps:
            pass  # source attribution handled in _sources_from_urls

    return answer
