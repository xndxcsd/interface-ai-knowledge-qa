import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
from contract import Page, Snapshot  # noqa: E402

from kb.evidence import gather_evidence, is_rate_question
from kb.system import KnowledgeStore


def test_is_rate_question():
    assert is_rate_question("What is the APY on savings?")
    assert not is_rate_question("How do I join?")


def test_gather_evidence_finds_table_fact():
    store = KnowledgeStore()
    md = """
| Account Type | APY |
| --- | --- |
| Bright Savings | 2.25% |
"""
    store.ingest_snapshot(
        Snapshot(
            "s1",
            "2026-09-28",
            [
                Page(
                    "https://www.dupaco.com/personal/savings-account",
                    "Savings",
                    md,
                    "2026-09-28",
                )
            ],
        )
    )
    pack = gather_evidence(store, "What APY does Bright Savings pay?", None)
    assert any("2.25" in fe.fact.value for fe in pack.facts)
