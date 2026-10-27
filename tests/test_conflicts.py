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
    conflicts = detect_conflicts(
        facts,
        current_facts=[facts[1]],
        latest_snapshot_date="2026-09-28",
    )
    assert conflicts
    assert "3.5" in conflicts[0]["resolution"]


def test_prose_apr_range_conflict():
    url = "https://www.example.com/personal/credit-cards"
    facts = [
        ExtractedFact(
            subject="Personal Visa",
            field="APR range",
            value="13.00% to 20.00% APR",
            raw_row="prose",
            section="Cards",
            effective_date=None,
            url=url,
            snapshot_id="s1",
            taken_on="2026-02-01",
            authority=1.0,
        ),
        ExtractedFact(
            subject="Personal Visa",
            field="APR range",
            value="12.50% to 19.50% APR",
            raw_row="prose",
            section="Cards",
            effective_date=None,
            url=url,
            snapshot_id="s2",
            taken_on="2026-08-01",
            authority=1.0,
        ),
    ]
    conflicts = detect_conflicts(
        facts,
        current_facts=[facts[1]],
        latest_snapshot_date="2026-08-01",
    )
    assert conflicts
    assert "12.50" in conflicts[0]["resolution"]
