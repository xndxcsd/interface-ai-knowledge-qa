import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
from contract import Snapshot, Page  # noqa: E402

from kb.answer import answer_question
from kb.system import KnowledgeStore


def _minimal_store():
    store = KnowledgeStore()
    snap = Snapshot(
        snapshot_id="t",
        taken_on="2026-09-28",
        pages=[
            Page(
                url="https://www.dupaco.com/personal/loans/home-loans",
                title="Home Loans",
                markdown="Build and buy homes. Construction loans available.",
                fetched_at="2026-09-28",
            )
        ],
    )
    store.ingest_snapshot(snap)
    return store


def test_construction_loan_refusal():
    store = _minimal_store()
    ans = answer_question(store, "What interest rate do you charge on a construction loan?", None)
    assert not ans.confident
    assert "don't know" in ans.text.lower() or "does not publish" in ans.text.lower()


def test_mullan_hours_refusal():
    store = _minimal_store()
    ans = answer_question(
        store, "Can you give me the lobby hours for the Mullan Avenue branch?", None
    )
    assert not ans.confident
