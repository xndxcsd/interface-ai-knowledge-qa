"""End-to-end answer() with stub LLM and synthetic fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "harness"))

from contract import Answer  # noqa: E402

from kb.authority import normalize_url
from kb.facts import ExtractedFact
from kb.system import KnowledgeStore, PageVersion
from solution import DupacoKnowledge


def _store_with_facts(*facts: ExtractedFact) -> KnowledgeStore:
    store = KnowledgeStore()
    taken = min((f.taken_on for f in facts), default="2026-06-01")
    store.snapshots.append(("s1", taken))
    seen: set[str] = set()
    for f in facts:
        canon = normalize_url(f.url)
        if canon in seen:
            continue
        seen.add(canon)
        store.pages.append(
            PageVersion(
                url=f.url,
                canonical=canon,
                title="Fixture",
                markdown="fixture",
                snapshot_id="s1",
                taken_on=f.taken_on,
                fetched_at="2026-06-01",
                authority=1.0,
                stale_for_rates=False,
            )
        )
    store.facts.extend(facts)
    return store


@pytest.fixture
def stub_llm(monkeypatch):
    def _fake(question: str, block: str, as_of: str | None) -> dict:
        q = question.lower()
        if "drive-up" in q or "drive up" in q:
            return {
                "text": "Drive-up hours are 8 a.m. to 6 p.m.",
                "source_urls": ["https://www.example.com/newsroom/riverside-opening"],
                "confident": True,
            }
        if "apr" in q:
            return {
                "text": "The APR range is 12.50% to 19.50%.",
                "source_urls": ["https://www.example.com/personal/credit-cards"],
                "confident": True,
            }
        if as_of:
            return {
                "text": "The dividend rate was 0.05% on that date.",
                "source_urls": ["https://www.example.com/personal/checking-accounts"],
                "confident": True,
            }
        return {"text": "I don't know.", "source_urls": [], "confident": False}

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("kb.answer.llm_answer_from_evidence", _fake)


def test_branch_hours_through_answer_no_nameerror(stub_llm):
    """Regression: newsroom place match must not raise during grounding."""
    news = ExtractedFact(
        subject="Riverside | Drive-up",
        field="hours",
        value="Drive-up Monday through Friday 8 a.m. to 6 p.m.",
        raw_row="",
        section="article-places:riverside",
        effective_date=None,
        url="https://www.example.com/newsroom/riverside-opening",
        snapshot_id="s1",
        taken_on="2026-06-01",
        authority=0.55,
    )
    wrong = ExtractedFact(
        subject="Other City | Drive-up",
        field="hours",
        value="Saturday 9 a.m. to 1 p.m.",
        raw_row="",
        section="article-places:other city",
        effective_date=None,
        url="https://www.example.com/newsroom/other-opening",
        snapshot_id="s1",
        taken_on="2026-06-01",
        authority=0.55,
    )
    sys = DupacoKnowledge()
    sys._store = _store_with_facts(news, wrong)
    out = sys.answer(
        "What are the drive-up hours at the Riverside branch?",
        None,
    )
    assert isinstance(out, Answer)
    assert out.confident


def test_rate_grounded_through_answer(stub_llm):
    rate = ExtractedFact(
        subject="Rewards Visa",
        field="APR range",
        value="12.50% to 19.50% APR",
        raw_row="",
        section="Cards",
        effective_date=None,
        url="https://www.example.com/personal/credit-cards",
        snapshot_id="s1",
        taken_on="2026-06-01",
        authority=1.0,
    )
    sys = DupacoKnowledge()
    sys._store = _store_with_facts(rate)
    out = sys.answer("What is the Rewards Visa APR range?", None)
    assert out.confident
    assert "12.50" in out.text


def test_refusal_when_ungrounded(stub_llm, monkeypatch):
    monkeypatch.setattr(
        "kb.answer.llm_answer_from_evidence",
        lambda q, b, a: {
            "text": "The rate is 99.99%.",
            "source_urls": [],
            "confident": True,
        },
    )
    sys = DupacoKnowledge()
    sys._store = _store_with_facts()
    out = sys.answer("What is the boat loan APR?", None)
    assert not out.confident


def test_as_of_answer(stub_llm):
    fact = ExtractedFact(
        subject="Free Checking",
        field="Dividend Rate",
        value="0.05%",
        raw_row="| ... |",
        section="Rates",
        effective_date=None,
        url="https://www.example.com/personal/checking-accounts",
        snapshot_id="s1",
        taken_on="2026-05-01",
        authority=1.0,
    )
    sys = DupacoKnowledge()
    sys._store = _store_with_facts(fact)
    out = sys.answer("What was the dividend rate?", "2026-05-15")
    assert out.confident
    assert "0.05" in out.text
