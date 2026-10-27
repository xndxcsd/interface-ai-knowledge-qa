"""Snapshot ingestion, corpus selection, and indexing."""
from __future__ import annotations

from dataclasses import dataclass, field

from kb.authority import authority_score, is_likely_stale_for_rates, normalize_url
from kb.conflicts import detect_conflicts
from kb.facts import ExtractedFact, extract_table_facts
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
    chunks: list[ChunkRecord] = field(default_factory=list)
    _chunk_tokens: list[list[str]] = field(default_factory=list)
    _bm25: BM25Index | None = None
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

    def finalize(self) -> None:
        if self._finalized:
            return
        self._build_latest_index()
        self._conflicts_raw = detect_conflicts(self._facts_as_of(None))
        self._finalized = True

    def _build_latest_index(self) -> None:
        corpus = self.corpus_as_of(None, for_rates=False)
        self.chunks = []
        self._chunk_tokens = []
        cid = 0
        for page in corpus:
            for ch in split_chunks(page.markdown):
                text = clean_markdown(ch)
                if len(text) < 40:
                    continue
                self.chunks.append(
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
                self._chunk_tokens.append(tokenize(text))
                cid += 1
        self._bm25 = BM25Index(self._chunk_tokens)

    def _cutoff(self, as_of: str | None) -> str | None:
        if not as_of:
            return None
        return as_of[:10]

    def corpus_as_of(self, as_of: str | None, *, for_rates: bool) -> list[PageVersion]:
        cutoff = self._cutoff(as_of)
        by_url: dict[str, PageVersion] = {}
        for pv in sorted(self.pages, key=lambda x: x.taken_on):
            if cutoff and pv.taken_on > cutoff:
                continue
            if for_rates and pv.stale_for_rates:
                continue
            by_url[pv.canonical] = pv
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
            for ch in split_chunks(page.markdown):
                text = clean_markdown(ch)
                if len(text) < 40:
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

    def _facts_as_of(self, as_of: str | None) -> list[ExtractedFact]:
        cutoff = self._cutoff(as_of)
        by_key: dict[tuple[str, str, str, str], ExtractedFact] = {}
        for f in sorted(self.facts, key=lambda x: x.taken_on):
            if cutoff and f.taken_on > cutoff:
                continue
            if f.authority < 0.5:
                continue
            key = (f.url, f.subject, f.field, f.value)
            by_key[key] = f
        return list(by_key.values())

    def facts_as_of_ranked(self, as_of: str | None) -> list[ExtractedFact]:
        return self._facts_as_of(as_of)

    def facts_matching(
        self, as_of: str | None, subject_contains: str = "", url_fragment: str = ""
    ) -> list[ExtractedFact]:
        sub = subject_contains.lower()
        frag = url_fragment.lower()
        out = []
        for f in self._facts_as_of(as_of):
            if sub and sub not in f.subject.lower():
                continue
            if frag and frag not in f.url.lower():
                continue
            out.append(f)
        return out

    def conflicts_raw(self) -> list[dict]:
        self.finalize()
        return self._conflicts_raw or []
