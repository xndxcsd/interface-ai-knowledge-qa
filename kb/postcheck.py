"""Validate model answers against retrieved evidence (staleness / authority)."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from kb.evidence import EvidencePack, is_rate_question

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


def _evidence_numbers(pack: EvidencePack) -> dict[tuple[str, float], float]:
    """Map numeric value -> max authority seen in evidence."""
    auth: dict[tuple[str, float], float] = {}
    for fe in pack.facts:
        for n in _numbers(fe.fact.value):
            auth[n] = max(auth.get(n, 0), fe.fact.authority)
    for ce in pack.chunks:
        if ce.chunk.stale_for_rates:
            continue
        for n in _numbers(ce.chunk.text):
            auth[n] = max(auth.get(n, 0), ce.chunk.authority)
    return auth


def _stale_only_numbers(pack: EvidencePack) -> set[tuple[str, float]]:
    stale_nums: set[tuple[str, float]] = set()
    good_nums: set[tuple[str, float]] = set()
    for ce in pack.chunks:
        nums = _numbers(ce.chunk.text)
        if ce.chunk.stale_for_rates or ce.chunk.authority < 0.85:
            stale_nums |= nums
        else:
            good_nums |= nums
    for fe in pack.facts:
        nums = _numbers(fe.fact.value)
        if fe.fact.authority < 0.85:
            stale_nums |= nums
        else:
            good_nums |= nums
    return stale_nums - good_nums


def postcheck_answer(answer: "Answer", pack: EvidencePack, question: str) -> "Answer":
    from contract import Answer

    if not answer.confident:
        return answer
    if not is_rate_question(question):
        return answer
    ans_nums = _numbers(answer.text)
    if not ans_nums:
        return answer
    stale_only = _stale_only_numbers(pack)
    trap = ans_nums & stale_only
    if trap:
        return Answer(
            text="I don't know — I couldn't confirm a current rate from official Dupaco rate pages.",
            sources=answer.sources,
            confident=False,
            conflict_note=answer.conflict_note,
        )
    ev_auth = _evidence_numbers(pack)
    for n in ans_nums:
        if n not in ev_auth and n[0] == "%":
            return Answer(
                text="I don't know — that rate isn't supported by the retrieved official sources.",
                sources=answer.sources,
                confident=False,
                conflict_note=answer.conflict_note,
            )
        if n in ev_auth and ev_auth[n] < 0.85 and n[0] == "%":
            return Answer(
                text="I don't know — I couldn't verify that rate on an official product page.",
                sources=answer.sources,
                confident=False,
                conflict_note=answer.conflict_note,
            )
    return answer
