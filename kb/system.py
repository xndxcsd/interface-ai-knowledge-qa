"""Snapshot ingestion, corpus selection, and indexing."""
from __future__ import annotations

from dataclasses import dataclass, field

from kb.authority import authority_score, is_likely_stale_for_rates, normalize_url
from kb.conflicts import detect_conflicts
from kb.contact_extract import extract_contact_facts
from kb.hours_extract import extract_hours_facts
from kb.facts import ExtractedFact, extract_table_facts
from kb.normalize import fact_key
from kb.retrieve import BM25Index
from kb.textutil import clean_markdown, split_chunks, tokenize


@dataclass
class PageVersion:
    url: str
    canonical: str
    title: str
    markdown: str
    snapshot_id: str
    taken_on: str
    fetched_at: str
    authority: float
    stale_for_rates: bool


@dataclass
class ChunkRecord:
    chunk_id: int
    text: str
    url: str
    snapshot_id: str
    taken_on: str
    authority: float
    stale_for_rates: bool


@dataclass
class KnowledgeStore:
    snapshots: list[tuple[str, str]] = field(default_factory=list)  # id, taken_on
    pages: list[PageVersion] = field(default_factory=list)
    facts: list[ExtractedFact] = field(default_factory=list)
    _bm25_by_asof: dict[str, tuple[list[ChunkRecord], BM25Index]] = field(
        default_factory=dict
    )
    _conflicts_raw: list[dict] | None = None
    _finalized: bool = False

    def ingest_snapshot(self, snapshot) -> None:
        sid = snapshot.snapshot_id
        taken = snapshot.taken_on
        self.snapshots.append((sid, taken))
        for p in snapshot.pages:
            auth = authority_score(p.url, p.title)
            stale = is_likely_stale_for_rates(p.url, p.markdown)
            pv = PageVersion(
                url=p.url,
                canonical=normalize_url(p.url),
                title=p.title or "",
                markdown=p.markdown,
                snapshot_id=sid,
                taken_on=taken,
                fetched_at=p.fetched_at,
                authority=auth,
                stale_for_rates=stale,
            )
            self.pages.append(pv)
            self.facts.extend(
                extract_table_facts(
                    p.markdown,
                    url=p.url,
                    snapshot_id=sid,
                    taken_on=taken,
                    authority=auth,
                )
            )
            self.facts.extend(
                extract_hours_facts(
                    p.markdown,
                    url=p.url,
                    snapshot_id=sid,
                    taken_on=taken,
                    authority=auth,
                    page_title=p.title or "",
                )
            )
            if "/contact" in normalize_url(p.url) or auth >= 0.9 and "contact" in p.url.lower():
                self.facts.extend(
                    extract_contact_facts(
                        p.markdown,
                        url=p.url,
                        snapshot_id=sid,
                        taken_on=taken,
                        authority=auth,
                    )
                )

    def finalize(self) -> None:
        if self._finalized:
            return
        self._conflicts_raw = detect_conflicts(
            [f for f in self.facts if f.authority >= 0.9],
            current_facts=self.facts_for_conflicts(None),
            latest_snapshot_date=self.latest_taken_on(),
        )
        self._finalized = True

    def latest_taken_on(self) -> str:
        if not self.snapshots:
            return ""
        return max(t for _, t in self.snapshots)

    def _current_pages(self, as_of: str | None) -> dict[str, PageVersion]:
        cutoff = self._cutoff(as_of)
        by_url: dict[str, PageVersion] = {}
        for pv in sorted(self.pages, key=lambda x: x.taken_on):
            if cutoff and pv.taken_on > cutoff:
                continue
            by_url[pv.canonical] = pv
        return by_url

    def _cutoff(self, as_of: str | None) -> str | None:
        if not as_of:
            return None
        return as_of[:10]

    def corpus_as_of(self, as_of: str | None, *, for_rates: bool) -> list[PageVersion]:
        by_url = self._current_pages(as_of)
        if for_rates:
            return [p for p in by_url.values() if not p.stale_for_rates]
        return list(by_url.values())

    def get_page(
        self, path_fragment: str, as_of: str | None, *, prefer_rates: bool = True
    ) -> PageVersion | None:
        frag = path_fragment.lower().rstrip("/")
        corpus = self.corpus_as_of(as_of, for_rates=prefer_rates)
        matches = [p for p in corpus if frag in p.canonical.lower()]
        if not matches:
            matches = [
                p
                for p in self.corpus_as_of(as_of, for_rates=False)
                if frag in p.canonical.lower()
            ]
        if not matches:
            return None
        return max(matches, key=lambda p: (p.authority, p.taken_on))

    def _asof_key(self, as_of: str | None) -> str:
        return self._cutoff(as_of) or "latest"

    def _build_bm25_for(self, as_of: str | None) -> tuple[list[ChunkRecord], BM25Index]:
        corpus = self.corpus_as_of(as_of, for_rates=False)
        chunks: list[ChunkRecord] = []
        tokens: list[list[str]] = []
        cid = 0
        for page in corpus:
            is_news = "/newsroom/" in page.canonical.lower()
            max_chars = 520 if is_news else 900
            prefix = ""
            if is_news:
                title = (page.title or "").strip()
                prefix = f"Title: {title} Date: {page.taken_on}\n\n" if title else f"Date: {page.taken_on}\n\n"
            for ch in split_chunks(page.markdown, max_chars=max_chars):
                body = clean_markdown(ch)
                text = f"{prefix}{body}".strip()
                if len(body) < 40:
                    continue
                chunks.append(
                    ChunkRecord(
                        chunk_id=cid,
                        text=text,
                        url=page.url,
                        snapshot_id=page.snapshot_id,
                        taken_on=page.taken_on,
                        authority=page.authority,
                        stale_for_rates=page.stale_for_rates,
                    )
                )
                tokens.append(tokenize(text))
                cid += 1
        return chunks, BM25Index(tokens)

    def search_as_of(
        self, query: str, as_of: str | None, top_k: int = 8
    ) -> list[tuple[ChunkRecord, float]]:
        self.finalize()
        key = self._asof_key(as_of)
        if key not in self._bm25_by_asof:
            self._bm25_by_asof[key] = self._build_bm25_for(as_of)
        chunks, bm25 = self._bm25_by_asof[key]
        hits = bm25.query(query, top_k=top_k)
        out: list[tuple[ChunkRecord, float]] = []
        for h in hits:
            if h.chunk_id < len(chunks):
                out.append((chunks[h.chunk_id], h.score))
        return out

    def search(self, query: str, as_of: str | None, top_k: int = 6) -> list[ChunkRecord]:
        return [c for c, _ in self.search_as_of(query, as_of, top_k=top_k)]

    def facts_for_conflicts(self, as_of: str | None) -> list[ExtractedFact]:
        current = self._current_pages(as_of)
        out: list[ExtractedFact] = []
        for f in self.facts:
            if f.authority < 0.9:
                continue
            canon = normalize_url(f.url)
            page = current.get(canon)
            if page is None or f.snapshot_id != page.snapshot_id:
                continue
            out.append(f)
        return out

    def _facts_as_of(self, as_of: str | None) -> list[ExtractedFact]:
        current = self._current_pages(as_of)
        by_key: dict[tuple[str, str, str], ExtractedFact] = {}
        for f in self.facts:
            if f.authority < 0.5:
                continue
            canon = normalize_url(f.url)
            page = current.get(canon)
            if page is None or f.snapshot_id != page.snapshot_id:
                continue
            key = fact_key(f.url, f.subject, f.field)
            by_key[key] = f
        return list(by_key.values())

    def facts_as_of_ranked(self, as_of: str | None) -> list[ExtractedFact]:
        return self._facts_as_of(as_of)

    def conflicts_raw(self) -> list[dict]:
        self.finalize()
        return self._conflicts_raw or []
