"""Retrieve structured facts and text chunks for a question at a given as_of."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kb.retrieval_hints import canonical_path_hints
from kb.textutil import tokenize

if TYPE_CHECKING:
    from kb.facts import ExtractedFact
    from kb.system import ChunkRecord, KnowledgeStore


@dataclass(frozen=True)
class FactEvidence:
    fact: "ExtractedFact"
    score: float


@dataclass(frozen=True)
class ChunkEvidence:
    chunk: "ChunkRecord"
    score: float


@dataclass
class EvidencePack:
    facts: list[FactEvidence]
    chunks: list[ChunkEvidence]
    as_of: str | None


def _question_tokens(question: str) -> set[str]:
    toks = set(tokenize(question))
    stop = {"what", "the", "is", "are", "do", "does", "a", "an", "for", "on", "to", "you", "your", "me", "tell", "can", "how", "when", "where", "dupaco", "s", "i"}
    return {t for t in toks if t not in stop and len(t) > 1}


def score_fact(
    f: "ExtractedFact", q_tokens: set[str], question: str, *, rate_question: bool
) -> float:
    blob = " ".join([f.subject, f.field, f.value, f.section, f.url]).lower()
    ftoks = set(tokenize(blob))
    if not q_tokens:
        overlap = 0.0
    else:
        overlap = len(q_tokens & ftoks) / len(q_tokens)
    auth = f.authority
    if rate_question and f.authority < 0.85:
        auth *= 0.35
    bonus = 0.0
    for t in q_tokens:
        if t.rstrip("%") in blob or t in f.subject.lower():
            bonus += 0.15
    for m in re.finditer(r"\$?\d[\d,]*", question):
        if m.group(0).replace(",", "") in blob.replace(",", ""):
            bonus += 0.25
    return (overlap + bonus) * auth


def is_rate_question(question: str) -> bool:
    q = question.lower()
    return any(
        k in q
        for k in (
            "rate",
            "apy",
            "apr",
            "dividend",
            "interest",
            "yield",
            "percent",
            "%",
            "loan",
            "mortgage",
            "certificate",
            "cd",
            "checking",
            "savings",
        )
    )


def gather_evidence(
    store: "KnowledgeStore", question: str, as_of: str | None, *, max_facts: int = 16, max_chunks: int = 8
) -> EvidencePack:
    store.finalize()
    q_tokens = _question_tokens(question)
    rate_q = is_rate_question(question)
    path_hints = canonical_path_hints(question)
    facts_raw = store.facts_as_of_ranked(as_of)
    scored_facts: list[FactEvidence] = []
    seen_fact: set[tuple[str, str, str]] = set()
    for f in facts_raw:
        s = score_fact(f, q_tokens, question, rate_question=rate_q)
        for hint in path_hints:
            if hint in f.url.lower():
                s += 0.45 * f.authority
        if s <= 0.02 and rate_q and not path_hints:
            continue
        if s > 0:
            key = (f.url, f.subject, f.value)
            if key not in seen_fact:
                seen_fact.add(key)
                scored_facts.append(FactEvidence(f, s))
    scored_facts.sort(key=lambda x: x.score, reverse=True)
    scored_facts = scored_facts[:max_facts]

    chunk_hits = store.search_as_of(question, as_of, top_k=max_chunks * 3)
    hint_pages: list = []
    for h in path_hints:
        page = store.get_page(h, as_of, prefer_rates=not rate_q)
        if page is not None:
            hint_pages.append(page)
    for page in hint_pages:
        for ch in store.search_as_of(page.title or question, as_of, top_k=2):
            chunk_hits.append(ch)
        # inject first chunk from hinted page
        from kb.textutil import clean_markdown, split_chunks

        for part in split_chunks(page.markdown)[:2]:
            text = clean_markdown(part)
            if len(text) < 50:
                continue
            from kb.system import ChunkRecord

            cr = ChunkRecord(
                chunk_id=-1,
                text=text,
                url=page.url,
                snapshot_id=page.snapshot_id,
                taken_on=page.taken_on,
                authority=page.authority,
                stale_for_rates=page.stale_for_rates,
            )
            chunk_hits.append((cr, 1.5 * page.authority))
            break
    chunks: list[ChunkEvidence] = []
    for ch, bm25_score in chunk_hits:
        weight = ch.authority * (0.25 if (rate_q and ch.stale_for_rates) else 1.0)
        chunks.append(ChunkEvidence(ch, bm25_score * weight))
    chunks.sort(key=lambda x: x.score, reverse=True)
    chunks = chunks[:max_chunks]
    return EvidencePack(facts=scored_facts, chunks=chunks, as_of=as_of)


def format_evidence_for_prompt(pack: EvidencePack) -> str:
    lines = ["STRUCTURED FACTS (prefer higher authority; ignore stale_for_rates for current rates):"]
    for i, fe in enumerate(pack.facts[:12], 1):
        f = fe.fact
        stale = "stale_for_rates=yes" if f.authority < 0.85 else "stale_for_rates=no"
        lines.append(
            f"F{i} authority={f.authority:.2f} {stale} snapshot={f.snapshot_id} url={f.url}\n"
            f"  {f.subject} | {f.field} = {f.value} (section: {f.section})"
        )
    lines.append("\nTEXT SNIPPETS:")
    for i, ce in enumerate(pack.chunks[:6], 1):
        c = ce.chunk
        flag = "STALE" if c.stale_for_rates else "ok"
        lines.append(
            f"S{i} [{flag}] authority={c.authority:.2f} url={c.url} snapshot={c.snapshot_id}\n"
            f"  {c.text[:650]}"
        )
    return "\n".join(lines)
