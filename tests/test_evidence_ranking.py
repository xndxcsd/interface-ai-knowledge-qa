"""Regression: URL token matching uses whole path segments, not substrings."""

from kb.authority import normalize_url
from kb.evidence import _hint_path_score, gather_evidence
from kb.facts import ExtractedFact
from kb.system import KnowledgeStore, PageVersion


def test_hint_path_score_does_not_match_rate_inside_celebrate():
    url = "https://www.example.com/newsroom/dupaco-celebrates-branch-opening"
    q_tokens = {"rate", "dividend", "checking", "free"}
    score_celebrate = _hint_path_score("personal/checking-accounts", url, q_tokens)
    url_product = "https://www.example.com/personal/checking-accounts/free-checking"
    score_product = _hint_path_score("personal/checking-accounts", url_product, q_tokens)
    assert score_product > score_celebrate
    assert score_celebrate == 0


def test_rate_question_prefers_product_page_facts_over_newsroom_hours():
    store = KnowledgeStore()
    news_hours = ExtractedFact(
        subject="Lobby",
        field="hours",
        value="Monday through Friday 9:00 a.m. to 5:00 p.m.",
        raw_row="",
        section="Hours",
        effective_date=None,
        url="https://www.example.com/newsroom/celebrates-new-branch",
        snapshot_id="s1",
        taken_on="2026-01-01",
        authority=0.55,
    )
    rate_row = ExtractedFact(
        subject="Free Checking",
        field="Dividend Rate",
        value="0.05%",
        raw_row="| Free Checking | 0.05% |",
        section="Rates",
        effective_date=None,
        url="https://www.example.com/personal/checking-accounts",
        snapshot_id="s1",
        taken_on="2026-01-01",
        authority=1.0,
    )
    store.snapshots.append(("s1", "2026-01-01"))
    store.facts.extend([news_hours, rate_row])
    canon = normalize_url(rate_row.url)
    store.pages.append(
        PageVersion(
            url=rate_row.url,
            canonical=canon,
            title="Checking",
            markdown="| Free Checking | Dividend Rate | 0.05% |\n|---|---|\n| Free Checking | 0.05% |",
            snapshot_id="s1",
            taken_on="2026-01-01",
            fetched_at="2026-01-01",
            authority=1.0,
            stale_for_rates=False,
        )
    )
    pack = gather_evidence(
        store,
        "What is the dividend rate on Free Checking?",
        None,
        max_facts=8,
    )
    assert pack.facts
    top_url = pack.facts[0].fact.url
    assert "checking-accounts" in top_url
    assert "/newsroom/" not in top_url
