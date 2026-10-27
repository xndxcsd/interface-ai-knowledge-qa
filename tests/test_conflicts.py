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
    import json
    from pathlib import Path

    import pytest

    from kb.prose_rates import extract_prose_apr_facts

    cards_url = "https://www.dupaco.com/personal/credit-cards"
    snap_root = Path(__file__).resolve().parents[1] / "snapshots"
    snap_dirs = (
        sorted(
            (d for d in snap_root.iterdir() if d.is_dir() and (d / "manifest.json").is_file()),
            key=lambda d: json.loads((d / "manifest.json").read_text(encoding="utf-8"))["taken_on"],
        )
        if snap_root.is_dir()
        else []
    )
    if len(snap_dirs) < 2:
        pytest.skip(
            "Unpack snapshots_zip/ at the repo root (or run the harness once) so ./snapshots/ has kit crawl folders."
        )

    def _cards_page(snap_dir: Path) -> Path | None:
        manifest = json.loads((snap_dir / "manifest.json").read_text(encoding="utf-8"))
        for page in manifest.get("pages", []):
            if str(page.get("url", "")).rstrip("/") == cards_url:
                rel = page.get("file")
                if rel:
                    return snap_dir / rel
        return None

    oldest, latest = snap_dirs[0], snap_dirs[-1]
    page_old, page_new = _cards_page(oldest), _cards_page(latest)
    if not page_old or not page_new or not page_old.is_file() or not page_new.is_file():
        pytest.skip(
            "Unpack snapshots_zip/ at the repo root (or run the harness once) so ./snapshots/ has kit crawl folders."
        )

    facts = []
    latest_taken = ""
    for snap_dir, page_path in ((oldest, page_old), (latest, page_new)):
        manifest = json.loads((snap_dir / "manifest.json").read_text(encoding="utf-8"))
        taken = manifest["taken_on"]
        if snap_dir == latest:
            latest_taken = taken
        facts.extend(
            extract_prose_apr_facts(
                page_path.read_text(encoding="utf-8"),
                url=cards_url,
                snapshot_id=manifest["snapshot_id"],
                taken_on=taken,
                authority=1.0,
            )
        )
    platinum = [f for f in facts if f.subject.lower() == "platinum visa"]
    assert any("13.00" in f.value and "20.00" in f.value for f in platinum)
    assert any("12.50" in f.value and "19.50" in f.value for f in platinum)
    current = [f for f in facts if f.taken_on == latest_taken]
    conflicts = detect_conflicts(
        facts,
        current_facts=current,
        latest_snapshot_date=latest_taken,
    )
    assert any(
        "platinum" in c["topic"].lower() and "12.50" in c["resolution"] for c in conflicts
    )
