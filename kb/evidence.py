"""Retrieve structured facts and text chunks for a question at a given as_of."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kb.retrieval_hints import (
    canonical_path_hints,
    expand_list_path_hints,
    is_broad_rate_question,
    is_hours_question,
    is_list_question,
)
from kb.textutil import (
    has_any_word,
    has_word,
    hint_matches_url,
    tokenize,
    url_path_segments,
)

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
        if has_word(blob, t.rstrip("%")) or has_word(f.subject, t):
            bonus += 0.12
    for m in re.finditer(r"\$?\d[\d,]*", question):
        if m.group(0).replace(",", "") in blob.replace(",", ""):
            bonus += 0.2
    if f.field.lower() in ("address", "phone", "routing number", "hours"):
        bonus += 0.15
    ql = question.lower()
    if f.field.lower() == "hours" and is_hours_question(question):
        bonus += 0.85
        if has_word(ql, "drive") and has_word(f.value, "drive"):
            bonus += 0.5
    return (overlap + bonus) * auth


def is_rate_question(question: str) -> bool:
    q = question
    if has_any_word(
        q,
        ("rate", "rates", "apy", "apr", "dividend", "interest", "yield", "percent"),
    ):
        return True
    if has_word(q, "cd") or has_word(q, "certificate"):
        return True
    return "%" in q


def _chunk_priority(text: str) -> tuple[int, int, int, int]:
    low = text.lower()
    return (
        1 if "|" in text and "%" in text else 0,
        min(text.count("%"), 6),
        1 if "apr" in low or "apy" in low else 0,
        len(text),
    )


def _hint_path_score(path_hint: str, url: str, q_tokens: set[str]) -> int:
    if not hint_matches_url(path_hint, url):
        return 0
    url_segs = url_path_segments(url)
    return sum(1 for t in q_tokens if len(t) > 2 and t in url_segs)


def _inject_page_chunks(
    page, chunk_hits: list, *, extra: bool = False, inject_score: float = 2.0
) -> None:
    from kb.textutil import clean_markdown, split_chunks
    from kb.system import ChunkRecord

    parts = sorted(split_chunks(page.markdown), key=_chunk_priority, reverse=True)
    n = 4 if extra else 2
    added = 0
    for part in parts:
        if added >= n:
            break
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
        chunk_hits.append((cr, inject_score * page.authority))
        added += 1


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
    broad_rates = is_broad_rate_question(question)
    if list_q or broad_rates:
        max_facts, max_chunks = 40, 10

    q_tokens = _question_tokens(question)
    rate_q = is_rate_question(question)
    path_hints = expand_list_path_hints(canonical_path_hints(question), question)
    branch_places: list[str] = []
    if is_hours_question(question):
        from kb.grounding import _named_places

        branch_places = _named_places(question)
    if rate_q and path_hints and not list_q:
        max_facts = max(max_facts, 16)

    def _branch_evidence_boost(blob: str, url: str) -> float:
        if not branch_places:
            return 0.0
        low = blob.lower()
        u = url.lower()
        for place in branch_places:
            if has_word(low, place) or has_word(u, place.replace("-", " ")):
                return 2.0
            if place in low or place.replace("-", " ") in low:
                return 2.0
        return 0.0

    def score_all_facts():
        facts_raw = store.facts_as_of_ranked(as_of)
        scored: list[FactEvidence] = []
        seen: set[tuple[str, str, str]] = set()
        for f in facts_raw:
            s = score_fact(f, q_tokens, question, rate_question=rate_q)
            if rate_q and path_hints and "/newsroom/" in f.url.lower():
                s *= 0.05
            s += _branch_evidence_boost(
                f"{f.subject} {f.value} {f.section}", f.url
            )
            for hint in path_hints:
                if hint_matches_url(hint, f.url):
                    s += 0.5 * f.authority
            if list_q and any(hint_matches_url(h, f.url) for h in path_hints):
                s += 0.35
            if s <= 0.02 and rate_q and not path_hints:
                continue
            if s > 0:
                key = (f.url, f.subject, f.field)
                if key not in seen:
                    seen.add(key)
                    scored.append(FactEvidence(f, s))
        scored.sort(key=lambda x: x.score, reverse=True)
        if rate_q and path_hints and not list_q:

            def fact_hint_rank(fe: FactEvidence) -> tuple[int, float]:
                url = fe.fact.url.lower()
                rel = max(_hint_path_score(h, url, q_tokens) for h in path_hints)
                return (rel, fe.score)

            scored.sort(key=fact_hint_rank, reverse=True)
        return scored[:max_facts]

    def search_chunks():
        return store.search_as_of(question, as_of, top_k=max(max_chunks * 3, 15))

    def _append_newsroom_chunks(chunk_hits: list) -> None:
        seen_urls = {ch.url.rstrip("/") for ch, _ in chunk_hits}
        for ch, sc in store.search_as_of(question, as_of, top_k=30):
            if "/newsroom/" not in ch.url.lower():
                continue
            key = ch.url.rstrip("/")
            if key in seen_urls:
                continue
            seen_urls.add(key)
            chunk_hits.append((ch, sc + 18.0))
            if sum(1 for c, _ in chunk_hits if "/newsroom/" in c.url.lower()) >= 4:
                break

    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_f = ex.submit(score_all_facts)
        fut_c = ex.submit(search_chunks)
        scored_facts = fut_f.result()
        chunk_hits = list(fut_c.result())

    hint_pages = []
    seen_pages: set[str] = set()
    for h in path_hints:
        page = store.get_page(h, as_of, prefer_rates=not rate_q)
        if page is not None and page.url not in seen_pages:
            seen_pages.add(page.url)
            hint_pages.append(page)

    if list_q or broad_rates:
        for h in path_hints:
            for f in store.facts_as_of_ranked(as_of):
                if hint_matches_url(h, f.url):
                    s = score_fact(f, q_tokens, question, rate_question=rate_q) + 0.65
                    scored_facts.append(FactEvidence(f, s))
        for page in hint_pages:
            rel = max(_hint_path_score(h, page.url, q_tokens) for h in path_hints)
            is_card_list = list_q and "credit-cards" in page.url.lower()
            boost = 24.0 if (rel > 0 or is_card_list) else 2.0
            _inject_page_chunks(page, chunk_hits, extra=True, inject_score=boost)
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
            if list_q:
                rel = max(_hint_path_score(h, page.url, q_tokens) for h in path_hints)
                _inject_page_chunks(
                    page, chunk_hits, extra=True, inject_score=24.0 if rel > 0 else 2.0
                )
            elif rate_q and path_hints:
                rel = max(_hint_path_score(h, page.url, q_tokens) for h in path_hints)
                if rel > 0:
                    _inject_page_chunks(page, chunk_hits, extra=True, inject_score=24.0)
            else:
                _inject_page_chunks(page, chunk_hits, extra=False)

    if branch_places or (
        (any("/newsroom/" in ch.url for ch, _ in chunk_hits) or not rate_q)
        and not (rate_q and path_hints and not list_q)
    ):
        _append_newsroom_chunks(chunk_hits)
        max_chunks = max(max_chunks, 8)

    chunks: list[ChunkEvidence] = []
    for ch, bm25_score in chunk_hits:
        weight = ch.authority * (0.15 if (rate_q and ch.stale_for_rates) else 1.0)
        score = bm25_score * weight + _branch_evidence_boost(ch.text, ch.url)
        chunks.append(ChunkEvidence(ch, score))
    if rate_q and path_hints and not list_q:
        chunks.sort(
            key=lambda c: (
                max(_hint_path_score(h, c.chunk.url, q_tokens) for h in path_hints),
                c.score,
                c.chunk.taken_on,
            ),
            reverse=True,
        )
    else:
        chunks.sort(key=lambda c: (c.score, c.chunk.taken_on), reverse=True)
    return EvidencePack(facts=scored_facts, chunks=chunks[:max_chunks], as_of=as_of)


def normalize_url_match(a: str, b: str) -> bool:
    from kb.authority import normalize_url

    return normalize_url(a) == normalize_url(b)


def format_evidence_for_prompt(pack: EvidencePack) -> str:
    lines = [
        "FACTS (each row: page URL, table section, row label, column, value, snapshot_id):"
    ]
    cap = min(len(pack.facts), 28)
    for i, fe in enumerate(pack.facts[:cap], 1):
        f = fe.fact
        sec = f.section or "(section)"
        lines.append(
            f"F{i}|snap={f.snapshot_id}|auth={f.authority:.2f}\n"
            f"  page={f.url}\n"
            f"  section={sec}|row={f.subject}|column={f.field}|value={f.value}"
        )
    lines.append("SNIPPETS:")
    cap_c = min(len(pack.chunks), 8)
    for i, ce in enumerate(pack.chunks[:cap_c], 1):
        c = ce.chunk
        tag = "STALE" if c.stale_for_rates else "OK"
        lines.append(
            f"S{i}|{tag}|snap={c.snapshot_id}|auth={c.authority:.2f}|{c.url}\n  {c.text[:420]}"
        )
    return "\n".join(lines)
