"""BM25 retrieval over page chunks."""
from __future__ import annotations

from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from kb.textutil import tokenize


@dataclass
class ChunkHit:
    chunk_id: int
    score: float


class BM25Index:
    def __init__(self, corpus_tokens: list[list[str]]):
        self._bm25 = BM25Okapi(corpus_tokens) if corpus_tokens else None
        self._empty = not corpus_tokens

    def query(self, text: str, top_k: int = 8) -> list[ChunkHit]:
        if self._empty or self._bm25 is None:
            return []
        q = tokenize(text)
        if not q:
            return []
        scores = self._bm25.get_scores(q)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [ChunkHit(i, float(s)) for i, s in ranked[:top_k] if s > 0]
