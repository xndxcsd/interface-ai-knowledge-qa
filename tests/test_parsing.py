from kb.facts import extract_table_facts
from kb.textutil import clean_markdown, tokenize


SAMPLE_MD = """
## Savings Account Rates

| Account Type | Balance Tier | Dividend Rate | APY |
| --- | --- | --- | --- |
| Share Savings | $10,000 – $24,999.99 | 0.15% | 0.15% |

Rates are effective as of 06/15/2026 and are subject to change without notice.
"""


def test_clean_markdown_strips_links():
    raw = "See [rates](https://example.com/rates) today."
    assert "example.com" not in clean_markdown(raw)
    assert "rates" in clean_markdown(raw)


def test_tokenize_keeps_percentages():
    assert "3.5%" in tokenize("The APY is 3.5% today.")


def test_extract_table_facts():
    facts = extract_table_facts(
        SAMPLE_MD,
        url="https://www.dupaco.com/personal/savings-account",
        snapshot_id="test",
        taken_on="2026-09-28",
        authority=1.0,
    )
    assert any("0.15%" in f.value for f in facts)
    assert facts[0].effective_date == "2026-06-15"
