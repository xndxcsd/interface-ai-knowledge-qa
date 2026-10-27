"""
Dupaco knowledge Q&A submission for the interface.ai hackathon kit.

Implements build() -> KnowledgeSystem per harness/contract.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "harness" / "contract.py").exists())))
from contract import Answer, Conflict, Snapshot, Source  # noqa: E402

from kb.answer import answer_question
from kb.system import KnowledgeStore


class DupacoKnowledge:
    def __init__(self) -> None:
        self._store = KnowledgeStore()

    def ingest(self, snapshot: Snapshot) -> None:
        self._store.ingest_snapshot(snapshot)

    def answer(self, question: str, as_of: str | None = None) -> Answer:
        return answer_question(self._store, question, as_of)

    def conflicts(self) -> list[Conflict]:
        self._store.finalize()
        out: list[Conflict] = []
        for c in self._store.conflicts_raw():
            srcs = [
                Source(url=u, snapshot_id=sid, quote=q)
                for u, sid, q in c["sources"]
            ]
            out.append(
                Conflict(
                    topic=c["topic"],
                    values=c["values"],
                    sources=srcs,
                    resolution=c.get("resolution"),
                    reason=c.get("reason"),
                )
            )
        return out


def build():
    return DupacoKnowledge()
