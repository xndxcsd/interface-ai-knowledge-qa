"""Retrieve structured facts and text chunks for a question at a given as_of."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import kb.evidence_weights as W
from kb.places import named_places, newsroom_fact_matches_places
from kb.retrieval_hints import (
    canonical_path_hints,
    expand_list_path_hints,
    is_broad_rate_question,
    is_hours_question,
    is_list_question,
    is_rate_question,
)
from kb.textutil import (
    clean_markdown,
    has_word,
    hint_matches_url,
    question_tokens,
    split_chunks,
    tokenize,
    url_path_segments,
)

if TYPE_CHECKING:
    from kb.facts import ExtractedFact
    from kb.system import ChunkRecord, KnowledgeStore, PageVersion


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


def score_fact(
    f: "ExtractedFact", q_tokens: set[str], question: str, *, rate_question: bool
) -> float:
    blob = " ".join([f.subject, f.field, f.value, f.section, f.url]).lower()
    ftoks = set(tokenize(blob))
    overlap = (len(q_tokens & ftoks) / len(q_tokens)) if q_tokens else 0.0
    auth = f.authority
    if rate_question and f.authority < 0.85:
        auth *= W.LOW_AUTH_RATE_PENALTY
    bonus = 0.0
    for t in q_tokens:
        if has_word(blob, t.rstrip("%")) or has_word(f.subject, t):
            bonus += W.TOKEN_HIT_BONUS
    for m in re.finditer(r"\$?\d[\d,]*", question):
        if m.group(0).replace(",", "") in blob.replace(",", ""):
            bonus += W.QUESTION_NUMBER_BONUS
    if f.field.lower() in ("address", "phone", "routing number", "hours"):
        bonus += W.CONTACT_FIELD_BONUS
    ql = question.lower()
    if f.field.lower() == "hours" and is_hours_question(question):
        bonus += W.HOURS_QUESTION_BONUS
        if has_word(ql, "drive") and has_word(f.value, "drive"):
            bonus += W.DRIVE_HOURS_BONUS
    return (overlap + bonus) * auth


def _chunk_priority(text: str) -> tuple[int, int, int, int]:
    low = text.lower()
    return (
        1 if "|" in text and "%" in text else 0,
        min(text.count("%"), 6),
        1 if "apr" in low or "apy" in low else 0,
        len(text),
    )


def hint_path_score(path_hint: str, url: str, q_tokens: set[str]) -> int:
    if not hint_matches_url(path_hint, url):
        return 0
    url_segs = url_path_segments(url)
    return sum(1 for t in q_tokens if len(t) > 2 and t in url_segs)


def _inject_page_chunks(
    page: "PageVersion",
    chunk_hits: list,
    *,
    extra: bool = False,
    inject_score: float = W.DEFAULT_INJECT_SCORE,
) -> None:
    from kb.system import ChunkRecord

    parts = sorted(split_chunks(page.markdown), key=_chunk_priority, reverse=True)
    n = W.INJECT_CHUNKS_EXTRA if extra else W.INJECT_CHUNKS_NORMAL
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


def _branch_evidence_boost(blob: str, url: str, branch_places: list[str]) -> float:
    if not branch_places:
        return 0.0
    low = blob.lower()
    u = url.lower()
    for place in branch_places:
        if has_word(low, place) or has_word(u, place.replace("-", " ")):
            return W.BRANCH_EVIDENCE_BOOST
        if place in low or place.replace("-", " ") in low:
            return W.BRANCH_EVIDENCE_BOOST
    return 0.0


def _score_facts(
    store: "KnowledgeStore",
    question: str,
    as_of: str | None,
    *,
    q_tokens: set[str],
    rate_q: bool,
    path_hints: list[str],
    list_q: bool,
    branch_places: list[str],
    max_facts: int,
) -> list[FactEvidence]:
    scored: list[FactEvidence] = []
    seen: set[tuple[str, str, str]] = set()
    for f in store.facts_as_of_ranked(as_of):
        s = score_fact(f, q_tokens, question, rate_question=rate_q)
        if rate_q and path_hints and "/newsroom/" in f.url.lower():
            s *= W.NEWSROOM_ON_RATE_PENALTY
        if not newsroom_fact_matches_places(f, branch_places):
            s *= W.NEWSROOM_WRONG_PLACE_PENALTY
        s += _branch_evidence_boost(f"{f.subject} {f.value} {f.section}", f.url, branch_places)
        for hint in path_hints:
            if hint_matches_url(hint, f.url):
                s += W.PATH_HINT_BONUS * f.authority
        if list_q and any(hint_matches_url(h, f.url) for h in path_hints):
            s += W.LIST_HINT_PAGE_BONUS
        if s <= W.MIN_FACT_SCORE and rate_q and not path_hints:
            continue
        if s > 0:
            key = (f.url, f.subject, f.field)
            if key not in seen:
                seen.add(key)
                scored.append(FactEvidence(f, s))
    scored.sort(key=lambda x: x.score, reverse=True)
    if rate_q and path_hints and not list_q:
        scored.sort(
            key=lambda fe: (
                max(hint_path_score(h, fe.fact.url.lower(), q_tokens) for h in path_hints),
                fe.score,
            ),
            reverse=True,
        )
    return scored[:max_facts]


def _collect_bm25_chunks(
    store: "KnowledgeStore", question: str, as_of: str | None, top_k: int
) -> list[tuple["ChunkRecord", float]]:
    return list(store.search_as_of(question, as_of, top_k=top_k))


def _append_newsroom_chunks(
    store: "KnowledgeStore",
    question: str,
    as_of: str | None,
    chunk_hits: list,
) -> None:
    seen_urls = {ch.url.rstrip("/") for ch, _ in chunk_hits}
    for ch, sc in store.search_as_of(question, as_of, top_k=W.NEWSROOM_SEARCH_TOP):
        if "/newsroom/" not in ch.url.lower():
            continue
        key = ch.url.rstrip("/")
        if key in seen_urls:
            continue
        seen_urls.add(key)
        chunk_hits.append((ch, sc + W.NEWSROOM_CHUNK_BONUS))
        if sum(1 for c, _ in chunk_hits if "/newsroom/" in c.url.lower()) >= W.NEWSROOM_CHUNK_CAP:
            break


def _merge_list_facts(
    store: "KnowledgeStore",
    scored_facts: list[FactEvidence],
    as_of: str | None,
    *,
    path_hints: list[str],
    q_tokens: set[str],
    question: str,
    rate_q: bool,
    max_facts: int,
) -> list[FactEvidence]:
    for h in path_hints:
        for f in store.facts_as_of_ranked(as_of):
            if hint_matches_url(h, f.url):
                s = score_fact(f, q_tokens, question, rate_question=rate_q) + W.LIST_EXTRA_FACT_BONUS
                scored_facts.append(FactEvidence(f, s))
    seen_f: set[tuple[str, str, str]] = set()
    merged: list[FactEvidence] = []
    for fe in sorted(scored_facts, key=lambda x: x.score, reverse=True):
        k = (fe.fact.url, fe.fact.subject, fe.fact.field)
        if k not in seen_f:
            seen_f.add(k)
            merged.append(fe)
    return merged[:max_facts]


def _inject_hint_pages(
    hint_pages: list["PageVersion"],
    chunk_hits: list,
    *,
    path_hints: list[str],
    q_tokens: set[str],
    list_q: bool,
    broad_rates: bool,
    rate_q: bool,
) -> None:
    for page in hint_pages:
        rel = max(hint_path_score(h, page.url, q_tokens) for h in path_hints) if path_hints else 0
        if list_q or broad_rates:
            is_card_list = list_q and "credit-cards" in page.url.lower()
            boost = W.HINT_PAGE_INJECT_SCORE if (rel > 0 or is_card_list) else W.DEFAULT_INJECT_SCORE
            _inject_page_chunks(page, chunk_hits, extra=True, inject_score=boost)
        elif rate_q and path_hints and rel > 0:
            _inject_page_chunks(page, chunk_hits, extra=True, inject_score=W.HINT_PAGE_INJECT_SCORE)
        else:
            _inject_page_chunks(page, chunk_hits, extra=False)


def _rank_chunks(
    chunk_hits: list,
    *,
    path_hints: list[str],
    q_tokens: set[str],
    rate_q: bool,
    branch_places: list[str],
    max_chunks: int,
) -> list[ChunkEvidence]:
    chunks: list[ChunkEvidence] = []
    for ch, bm25_score in chunk_hits:
        weight = ch.authority * (W.STALE_CHUNK_WEIGHT if (rate_q and ch.stale_for_rates) else 1.0)
        score = bm25_score * weight + _branch_evidence_boost(ch.text, ch.url, branch_places)
        chunks.append(ChunkEvidence(ch, score))
    if rate_q and path_hints:
        chunks.sort(
            key=lambda c: (
                max(hint_path_score(h, c.chunk.url, q_tokens) for h in path_hints),
                c.score,
                c.chunk.taken_on,
            ),
            reverse=True,
        )
    else:
        chunks.sort(key=lambda c: (c.score, c.chunk.taken_on), reverse=True)
    return chunks[:max_chunks]


def gather_evidence(
    store: "KnowledgeStore",
    question: str,
    as_of: str | None,
    *,
    max_facts: int = W.DEFAULT_MAX_FACTS,
    max_chunks: int = W.DEFAULT_MAX_CHUNKS,
) -> EvidencePack:
    store.finalize()
    list_q = is_list_question(question)
    broad_rates = is_broad_rate_question(question)
    if list_q or broad_rates:
        max_facts, max_chunks = W.LIST_MAX_FACTS, W.LIST_MAX_CHUNKS

    q_tokens = question_tokens(question)
    rate_q = is_rate_question(question)
    path_hints = expand_list_path_hints(canonical_path_hints(question), question)
    branch_places = named_places(question)
    if rate_q and path_hints and not list_q:
        max_facts = max(max_facts, W.RATE_HINT_MAX_FACTS)

    bm25_k = max(max_chunks * W.BM25_TOP_MULT, W.BM25_TOP_MIN)
    chunk_hits = _collect_bm25_chunks(store, question, as_of, bm25_k)
    scored_facts = _score_facts(
        store,
        question,
        as_of,
        q_tokens=q_tokens,
        rate_q=rate_q,
        path_hints=path_hints,
        list_q=list_q,
        branch_places=branch_places,
        max_facts=max_facts,
    )

    hint_pages: list[PageVersion] = []
    seen_pages: set[str] = set()
    for h in path_hints:
        page = store.get_page(h, as_of, prefer_rates=not rate_q)
        if page is not None and page.url not in seen_pages:
            seen_pages.add(page.url)
            hint_pages.append(page)

    if list_q or broad_rates:
        scored_facts = _merge_list_facts(
            store,
            scored_facts,
            as_of,
            path_hints=path_hints,
            q_tokens=q_tokens,
            question=question,
            rate_q=rate_q,
            max_facts=max_facts,
        )
        _inject_hint_pages(
            hint_pages,
            chunk_hits,
            path_hints=path_hints,
            q_tokens=q_tokens,
            list_q=list_q,
            broad_rates=broad_rates,
            rate_q=rate_q,
        )
    else:
        _inject_hint_pages(
            hint_pages,
            chunk_hits,
            path_hints=path_hints,
            q_tokens=q_tokens,
            list_q=list_q,
            broad_rates=False,
            rate_q=rate_q,
        )

    if branch_places or (
        (any("/newsroom/" in ch.url for ch, _ in chunk_hits) or not rate_q)
        and not (rate_q and path_hints and not list_q)
    ):
        _append_newsroom_chunks(store, question, as_of, chunk_hits)
        max_chunks = max(max_chunks, W.PROMPT_MAX_CHUNKS)

    chunks = _rank_chunks(
        chunk_hits,
        path_hints=path_hints,
        q_tokens=q_tokens,
        rate_q=rate_q and not list_q,
        branch_places=branch_places,
        max_chunks=max_chunks,
    )
    return EvidencePack(facts=scored_facts, chunks=chunks, as_of=as_of)


def format_evidence_for_prompt(pack: EvidencePack) -> str:
    lines = [
        "FACTS (each row: page URL, table section, row label, column, value, snapshot_id):"
    ]
    cap = min(len(pack.facts), W.PROMPT_MAX_FACTS)
    for i, fe in enumerate(pack.facts[:cap], 1):
        f = fe.fact
        sec = f.section or "(section)"
        lines.append(
            f"F{i}|snap={f.snapshot_id}|auth={f.authority:.2f}\n"
            f"  page={f.url}\n"
            f"  section={sec}|row={f.subject}|column={f.field}|value={f.value}"
        )
    lines.append("SNIPPETS:")
    cap_c = min(len(pack.chunks), W.PROMPT_MAX_CHUNKS)
    for i, ce in enumerate(pack.chunks[:cap_c], 1):
        c = ce.chunk
        tag = "STALE" if c.stale_for_rates else "OK"
        lines.append(
            f"S{i}|{tag}|snap={c.snapshot_id}|auth={c.authority:.2f}|{c.url}\n"
            f"  {c.text[:W.PROMPT_SNIPPET_CHARS]}"
        )
    return "\n".join(lines)
