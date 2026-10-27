import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
from contract import Page, Snapshot  # noqa: E402

from kb.system import KnowledgeStore


def test_facts_as_of_uses_latest_page_version_only():
    store = KnowledgeStore()
    table = """
| Loan | Rate |
| --- | --- |
| 30-Year | {rate} |
"""
    store.ingest_snapshot(
        Snapshot(
            "01",
            "2026-05-12",
            [
                Page(
                    "https://www.dupaco.com/personal/loans/home-loans",
                    "HL",
                    table.format(rate="6.125%"),
                    "2026-05-12",
                )
            ],
        )
    )
    store.ingest_snapshot(
        Snapshot(
            "05",
            "2026-09-28",
            [
                Page(
                    "https://www.dupaco.com/personal/loans/home-loans",
                    "HL",
                    table.format(rate="7.13%"),
                    "2026-09-28",
                )
            ],
        )
    )
    facts = store.facts_as_of_ranked(None)
    rates = {f.value for f in facts if "30" in f.subject}
    assert rates == {"7.13%"}
    assert all(f.snapshot_id == "05" for f in facts if "7.13" in f.value)
