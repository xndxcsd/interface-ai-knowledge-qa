from kb.conflicts import detect_conflicts
from kb.facts import ExtractedFact


def test_detect_rate_conflict():
    facts = [
        ExtractedFact(
            subject="6 Month",
            field="APY",
            value="2.95%",
            raw_row="| 6 Month | 2.95% |",
            section="Certs",
            effective_date="2026-06-01",
            url="https://www.dupaco.com/personal/savings-account",
            snapshot_id="a",
            taken_on="2026-05-12",
            authority=1.0,
        ),
        ExtractedFact(
            subject="6 Month",
            field="APY",
            value="3.50%",
            raw_row="| 6 Month | 3.50% |",
            section="Certs",
            effective_date="2026-09-01",
            url="https://www.dupaco.com/personal/savings-account",
            snapshot_id="a",
            taken_on="2026-09-28",
            authority=1.0,
        ),
    ]
    conflicts = detect_conflicts(facts, latest_snapshot_date="2026-09-28")
    assert conflicts
    assert "3.50%" in conflicts[0]["resolution"]
