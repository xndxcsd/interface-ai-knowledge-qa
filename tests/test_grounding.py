import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
from contract import Answer  # noqa: E402

from kb.evidence import EvidencePack, ChunkEvidence, FactEvidence
from kb.facts import ExtractedFact
from kb.grounding import apply_grounding, sanitize_refusal
from kb.system import ChunkRecord


def test_rejects_ungrounded_rate():
    pack = EvidencePack(facts=[], chunks=[], as_of=None)
    ans = Answer(text="The boat loan rate is 4.5% APR.", sources=[], confident=True)
    out = apply_grounding(ans, pack, "What is the boat loan rate?")
    assert not out.confident


def test_allows_grounded_auto_rate():
    f = ExtractedFact(
        subject="2024-27 Model Year | 60 Months",
        field="Annual Percentage Rate (As Low As)",
        value="5.39% APR1",
        raw_row="| 2024-27 | 60 | 5.39% |",
        section="Rates",
        effective_date=None,
        url="https://www.example.com/personal/loans/auto-motorcycle-loans",
        snapshot_id="s1",
        taken_on="2026-09-28",
        authority=1.0,
    )
    pack = EvidencePack(facts=[FactEvidence(f, 1.0)], chunks=[], as_of=None)
    ans = Answer(text="5.39% APR for 60 months.", sources=[], confident=True)
    out = apply_grounding(
        ans,
        pack,
        "What is the APR on a 60-month auto loan for a 2026 model year vehicle?",
    )
    assert out.confident


def test_rejects_wrong_column_for_apy_question():
    f = ExtractedFact(
        subject="10 Month Fixed Jumbo Certificate Special",
        field="Dividend Rate",
        value="3.86%",
        raw_row="| ... |",
        section="Certs",
        effective_date=None,
        url="https://www.example.com/personal/savings-account",
        snapshot_id="s1",
        taken_on="2026-05-12",
        authority=1.0,
    )
    pack = EvidencePack(facts=[FactEvidence(f, 1.0)], chunks=[], as_of=None)
    ans = Answer(text="The APY is 3.86%.", sources=[], confident=True)
    out = apply_grounding(
        ans,
        pack,
        "What APY did the 10-month premium certificate special pay as of May 2026?",
    )
    assert not out.confident


def test_sanitize_refusal_strips_numbers():
    ans = Answer(text="Not sure — month 11 or 12 months.", sources=[], confident=False)
    out = sanitize_refusal(ans)
    assert out.text == "I don't know."
    assert not out.confident


def test_sanitize_refusal_keeps_sources():
    src = [{"url": "https://www.example.com/page", "snapshot_id": "s1"}]
    ans = Answer(text="Maybe 12%.", sources=src, confident=False)
    out = sanitize_refusal(ans)
    assert out.text == "I don't know."
    assert out.sources == src


def test_allows_prose_visa_rate_on_same_page():
    chunk = ChunkRecord(
        chunk_id=1,
        text=(
            "Personal Visa credit card variable APR ranges from 12.50% to 19.50% "
            "based on creditworthiness."
        ),
        url="https://www.example.com/personal/credit-cards",
        snapshot_id="s1",
        taken_on="2026-01-01",
        authority=1.0,
        stale_for_rates=False,
    )
    pack = EvidencePack(
        facts=[],
        chunks=[ChunkEvidence(chunk, 1.0)],
        as_of=None,
    )
    ans = Answer(
        text="Personal Visa APR ranges from 12.50% to 19.50%.",
        sources=[],
        confident=True,
    )
    out = apply_grounding(ans, pack, "What is the personal Visa APR range?")
    assert out.confident


def test_refuses_unknown_branch_hours():
    pack = EvidencePack(
        facts=[
            FactEvidence(
                ExtractedFact(
                    subject="Riverside Branch",
                    field="hours",
                    value="Lobby 9 a.m.–5 p.m.",
                    raw_row="",
                    section="",
                    effective_date=None,
                    url="https://www.example.com/contact",
                    snapshot_id="s1",
                    taken_on="2026-01-01",
                    authority=1.0,
                ),
                1.0,
            )
        ],
        chunks=[],
        as_of=None,
    )
    ans = Answer(
        text="Lobby hours are 8 a.m.–6 p.m.",
        sources=[],
        confident=True,
    )
    out = apply_grounding(
        ans,
        pack,
        "What are the lobby hours at the branch named Oakridge?",
    )
    assert not out.confident
    assert out.text == "I don't know."


def test_named_branch_hours_not_false_refusal():
    pack = EvidencePack(
        facts=[
            FactEvidence(
                ExtractedFact(
                    subject="Riverside Branch",
                    field="hours",
                    value="Lobby 9 a.m.–5 p.m.",
                    raw_row="",
                    section="",
                    effective_date=None,
                    url="https://www.example.com/contact",
                    snapshot_id="s1",
                    taken_on="2026-01-01",
                    authority=1.0,
                ),
                1.0,
            )
        ],
        chunks=[],
        as_of=None,
    )
    ans = Answer(text="Lobby 9 a.m.–5 p.m.", sources=[], confident=True)
    out = apply_grounding(
        ans,
        pack,
        "What are the lobby hours at the Riverside branch?",
    )
    assert out.confident


def test_rewards_visa_prose_range():
    chunk = ChunkRecord(
        chunk_id=1,
        text=(
            "### Rewards Visa Best for earning. Competitive rate if you carry a balance: "
            "12.50%–19.50% APR. Variable rate from 12.50% APR to 19.50% APR."
        ),
        url="https://www.example.com/personal/credit-cards",
        snapshot_id="s1",
        taken_on="2026-01-01",
        authority=1.0,
        stale_for_rates=False,
    )
    pack = EvidencePack(facts=[], chunks=[ChunkEvidence(chunk, 1.0)], as_of=None)
    ans = Answer(text="Rewards Visa APR is 12.50% to 19.50%.", sources=[], confident=True)
    out = apply_grounding(ans, pack, "What is the Example Rewards card APR range?")
    assert out.confident


def test_auto_not_routed_to_recreational_on_substring():
    f = ExtractedFact(
        subject="2024-27 Model Year | 60 Months",
        field="Annual Percentage Rate (As Low As)",
        value="5.39% APR1",
        raw_row="| ... |",
        section="Rates",
        effective_date=None,
        url="https://www.example.com/personal/loans/auto-motorcycle-loans",
        snapshot_id="s1",
        taken_on="2026-09-28",
        authority=1.0,
    )
    pack = EvidencePack(facts=[FactEvidence(f, 1.0)], chunks=[], as_of=None)
    ans = Answer(text="5.39% APR.", sources=[], confident=True)
    out = apply_grounding(
        ans,
        pack,
        "Do you reserve special loan options for member service?",
    )
    assert out.confident


def test_confident_answer_not_sanitized():
    ans = Answer(text="The rate is 5.39% APR.", sources=[], confident=True)
    out = sanitize_refusal(ans)
    assert out.confident and "5.39" in out.text
