import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
from contract import Snapshot, Page  # noqa: E402

from kb.answer import answer_question
from kb.system import KnowledgeStore


def test_as_of_picks_older_snapshot_page():
    store = KnowledgeStore()
    old_md = """
| Certificate | APY |
| --- | --- |
| 10 Month Fixed Jumbo Certificate Special | 3.90% |
"""
    new_md = """
| Certificate | APY |
| --- | --- |
| 10 Month Fixed Jumbo Certificate Special | 4.00% |
"""
    store.ingest_snapshot(
        Snapshot(
            "01",
            "2026-05-19",
            [
                Page(
                    "https://www.dupaco.com/personal/savings-account",
                    "Savings",
                    old_md,
                    "2026-05-19",
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
                    "https://www.dupaco.com/personal/savings-account",
                    "Savings",
                    new_md,
                    "2026-09-28",
                )
            ],
        )
    )
    ans = answer_question(
        store,
        "What was the rate on the 10-month fixed jumbo special certificate as of May 2026?",
        "2026-05-31",
    )
    assert "3.90" in ans.text
    assert "4.00" not in ans.text
