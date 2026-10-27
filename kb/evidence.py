"""Retrieve structured facts and text chunks for a question at a given as_of."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kb.retrieval_hints import canonical_path_hints, is_list_question
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
    stop = {
        "what", "the", "is", "are", "do", "does", "a", "an", "for", "on", "to",
        "you", "your", "me", "tell", "can", "how", "when", "where", "dupaco",
        "s", "i", "and", "or", "of", "in", "at", "be", "any", "our", "their",
    }
    return {t for t in toks if t not in stop and len(t) > 1}


def score_fact(
    f: "ExtractedFact", q_tokens: set[str], question: str, *, rate_question: bool
) -> float:
    blob = " ".join([f.subject, f.field, f.value, f.section, f.url]).lower()
    ftoks = set(tokenize(blob))
    overlap = (len(q_tokens & ftoks) / len(q_tokens)) if q_tokens else 0.0
    auth = f.authority
    if rate_question and f.authority < 0.85:
        auth *= 0.2
    bonus = 0.0
    for t in q_tokens:
        if t.rstrip("%") in blob or t in f.subject.lower():
            bonus += 0.12
    for m in re.finditer(r"\$?\d[\d,]*", question):
        if m.group(0).replace(",", "") in blob.replace(",", ""):
            bonus += 0.2
    if f.field.lower() in ("address", "phone", "routing number", "lobby or drive-up"):
        bonus += 0.15
    return (overlap + bonus) * auth


def is_rate_question(question: str) -> bool:
    q = question.lower()
    return any(
        k in q
        for k in (
            "rate", "apy", "apr", "dividend", "interest", "yield", "percent",
            "%", "loan", "mortgage", "certificate", "cd", "checking", "savings",
        )
    )


def _inject_page_chunks(page, chunk_hits: list, *, extra: bool = False) -> None:
    from kb.textutil import clean_markdown, split_chunks
    from kb.system import ChunkRecord

    for part in split_chunks(page.markdown)[:3 if extra else 2]:
        text = clean_markdown(part)
        if len(text) < 50:
            continue
        cr = ChunkRecord(
            chunk_id=-1,
            text=text,
            url=page.url,
            snapshot_id=page.snapshot_id,
            taken_on=page.taken_on,
            authority=page.authority,
            stale_for_rates=page.stale_for_rates,
        )
        chunk_hits.append((cr, 2.0 * page.authority))
        break


def gather_evidence(
    store: "KnowledgeStore",
    question: str,
    as_of: str | None,
    *,
    max_facts: int = 10,
    max_chunks: int = 5,
) -> EvidencePack:
    store.finalize()
    list_q = is_list_question(question)
    if list_q:
        max_facts, max_chunks = 36, 8

    q_tokens = _question_tokens(question)
    rate_q = is_rate_question(question)
    path_hints = canonical_path_hints(question)

    def score_all_facts():
        facts_raw = store.facts_as_of_ranked(as_of)
        scored: list[FactEvidence] = []
        seen: set[tuple[str, str, str]] = set()
        for f in facts_raw:
            s = score_fact(f, q_tokens, question, rate_question=rate_q)
            for hint in path_hints:
                if hint in f.url.lower():
                    s += 0.5 * f.authority
            if list_q and any(h in f.url.lower() for h in path_hints):
                s += 0.35
            if s <= 0.02 and rate_q and not path_hints:
                continue
            if s > 0:
                key = (f.url, f.subject, f.field)
                if key not in seen:
                    seen.add(key)
                    scored.append(FactEvidence(f, s))
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:max_facts]

    def search_chunks():
        return store.search_as_of(question, as_of, top_k=max_chunks * 2)

    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_f = ex.submit(score_all_facts)
        fut_c = ex.submit(search_chunks)
        scored_facts = fut_f.result()
        chunk_hits = list(fut_c.result())

    hint_pages = []
    for h in path_hints:
        page = store.get_page(h, as_of, prefer_rates=not rate_q)
        if page is not None:
            hint_pages.append(page)

    if list_q:
        for h in path_hints:
            for f in store.facts_as_of_ranked(as_of):
                if h in f.url.lower():
                    s = score_fact(f, q_tokens, question, rate_question=rate_q) + 0.65
                    scored_facts.append(FactEvidence(f, s))
        for page in hint_pages:
            _inject_page_chunks(page, chunk_hits, extra=True)
        seen_f = set()
        merged: list[FactEvidence] = []
        for fe in sorted(scored_facts, key=lambda x: x.score, reverse=True):
            k = (fe.fact.url, fe.fact.subject, fe.fact.field)
            if k not in seen_f:
                seen_f.add(k)
                merged.append(fe)
        scored_facts = merged[:max_facts]
    else:
        for page in hint_pages:
            _inject_page_chunks(page, chunk_hits)

    chunks: list[ChunkEvidence] = []
    for ch, bm25_score in chunk_hits:
        weight = ch.authority * (0.15 if (rate_q and ch.stale_for_rates) else 1.0)
        chunks.append(ChunkEvidence(ch, bm25_score * weight))
    chunks.sort(key=lambda x: x.score, reverse=True)
    return EvidencePack(facts=scored_facts, chunks=chunks[:max_chunks], as_of=as_of)


def normalize_url_match(a: str, b: str) -> bool:
    from kb.authority import normalize_url

    return normalize_url(a) == normalize_url(b)


def format_evidence_for_prompt(pack: EvidencePack) -> str:
    lines = ["FACTS (use snapshot_id on each row; prefer highest authority / newest snapshot):"]
    for i, fe in enumerate(pack.facts[:10], 1):
        f = fe.fact
        lines.append(
            f"F{i}|snap={f.snapshot_id}|auth={f.authority:.2f}|{f.url}\n"
            f"  {f.subject}|{f.field}={f.value}"
        )
    lines.append("SNIPPETS:")
    for i, ce in enumerate(pack.chunks[:5], 1):
        c = ce.chunk
        tag = "STALE" if c.stale_for_rates else "OK"
        lines.append(
            f"S{i}|{tag}|snap={c.snapshot_id}|auth={c.authority:.2f}|{c.url}\n  {c.text[:420]}"
        )
    return "\n".join(lines)
