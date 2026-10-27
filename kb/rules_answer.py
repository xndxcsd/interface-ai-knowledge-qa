"""Deterministic answers when no LLM key is available."""
from __future__ import annotations

import re

from kb.evidence import EvidencePack
from kb.retrieval_hints import is_rate_question
from kb.retrieval_hints import is_list_question
from kb.textutil import has_word


def _src(url, snapshot_id, quote=None):
    from contract import Source

    return Source(url=url, snapshot_id=snapshot_id, quote=quote)


def _ans(text, sources, confident=True, conflict_note=None):
    from contract import Answer

    return Answer(text=text, sources=sources, confident=confident, conflict_note=conflict_note)


IDK = "I don't know — I couldn't find that on the website based on the available pages."


def _wants_list(question: str) -> bool:
    return is_list_question(question)


def rules_answer(question: str, pack: EvidencePack) -> "Answer":
    rate_q = is_rate_question(question)
    if not pack.facts and not pack.chunks:
        return _ans(IDK, [], confident=False)

    best_score = max(
        [pack.facts[0].score if pack.facts else 0.0]
        + [pack.chunks[0].score if pack.chunks else 0.0]
    )
    min_score = 0.22 if rate_q else 0.12
    if best_score < min_score:
        return _ans(IDK, [], confident=False)

    # Rate question with no authoritative facts -> abstain (general refusal)
    auth_facts = [fe for fe in pack.facts if fe.fact.authority >= 0.85]
    if rate_q and not auth_facts:
        top = pack.chunks[0].chunk if pack.chunks else None
        if not top or top.stale_for_rates or top.authority < 0.85:
            return _ans(IDK, [], confident=False)

    sources = []
    if _wants_list(question) or (rate_q and has_word(question, "certificate")):
        lines = []
        for fe in auth_facts[:14]:
            f = fe.fact
            if rate_q and "%" not in f.value:
                continue
            line = f"{f.subject}: {f.value} ({f.field})"
            if line not in lines:
                lines.append(line)
            sources.append(_src(f.url, f.snapshot_id, f.raw_row[:140]))
        if lines:
            text = "From current rate information: " + "; ".join(lines[:12])
            return _ans(text, sources[:3])

    parts: list[str] = []
    for fe in (auth_facts or pack.facts)[:4]:
        f = fe.fact
        parts.append(f"{f.subject}: {f.value} ({f.field})")
        sources.append(_src(f.url, f.snapshot_id, f.raw_row[:160]))
    if parts:
        lead = "Per the website, " + "; ".join(parts) + "."
        return _ans(lead, sources[:3])

    ch = pack.chunks[0].chunk
    if rate_q and (ch.stale_for_rates or ch.authority < 0.7):
        return _ans(IDK, [], confident=False)
    snippet = re.sub(r"\s+", " ", ch.text)[:520]
    return _ans(snippet, [_src(ch.url, ch.snapshot_id, snippet[:180])])
