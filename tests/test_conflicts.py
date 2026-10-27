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


def test_prose_apr_range_conflict_on_real_credit_card_snapshots():
    from pathlib import Path

    from kb.prose_rates import extract_prose_apr_facts

    base = Path("/tmp/dupaco-snapshots/extracted")
    page = base / "01_2026-05-12_baseline" / "pages" / "personal-credit-cards-8b78fb.md"
    latest = base / "05_2026-09-28_latest" / "pages" / "personal-credit-cards-8b78fb.md"
    if not page.is_file() or not latest.is_file():
        import pytest

        pytest.skip("dupaco snapshot tree not on this machine")

    url = "https://www.dupaco.com/personal/credit-cards"
    facts = []
    for snap_dir, taken in (
        ("01_2026-05-12_baseline", "2026-05-12"),
        ("05_2026-09-28_latest", "2026-09-28"),
    ):
        md = (base / snap_dir / "pages" / "personal-credit-cards-8b78fb.md").read_text()
        facts.extend(
            extract_prose_apr_facts(
                md, url=url, snapshot_id=snap_dir, taken_on=taken, authority=1.0
            )
        )
    platinum = [f for f in facts if f.subject.lower() == "platinum visa"]
    assert any("13.00" in f.value and "20.00" in f.value for f in platinum)
    assert any("12.50" in f.value and "19.50" in f.value for f in platinum)
    current = [f for f in facts if f.taken_on == "2026-09-28"]
    conflicts = detect_conflicts(
        facts,
        current_facts=current,
        latest_snapshot_date="2026-09-28",
    )
    assert any(
        "platinum" in c["topic"].lower() and "12.50" in c["resolution"] for c in conflicts
    )
