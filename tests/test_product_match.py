from kb.facts import ExtractedFact
from kb.product_match import product_aligns


def _fact(url: str, subject: str) -> ExtractedFact:
    return ExtractedFact(
        subject=subject,
        field="APR",
        value="8.34%",
        raw_row="",
        section="",
        effective_date=None,
        url=url,
        snapshot_id="s",
        taken_on="2026-09-28",
        authority=1.0,
    )


def test_auto_question_rejects_recreational_row():
    f = _fact(
        "https://www.dupaco.com/personal/loans/recreational-loans",
        "2024-27 Model Year | 60 Months",
    )
    q = "What is the APR on a 60-month new auto loan for a 2026 model year vehicle?"
    assert not product_aligns(q, f)


def test_auto_question_accepts_auto_page():
    f = _fact(
        "https://www.dupaco.com/personal/loans/auto-motorcycle-loans",
        "2024-27 Model Year | 60 Months",
    )
    q = "What is the APR on a 60-month new auto loan for a 2026 model year vehicle?"
    assert product_aligns(q, f)
