import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
from contract import Answer  # noqa: E402

from kb.evidence import EvidencePack
from kb.facts import ExtractedFact
from kb.grounding import apply_grounding


def test_rejects_ungrounded_rate():
    pack = EvidencePack(facts=[], chunks=[], as_of=None)
    ans = Answer(text="The boat loan rate is 4.5% APR.", sources=[], confident=True)
    out = apply_grounding(ans, pack, "What is the boat loan rate?")
    assert not out.confident


def test_allows_grounded_auto_rate():
    f = ExtractedFact(
        subject="2024-27 Model Year | 60 Months",
        field="APR",
        value="5.39%",
        raw_row="| 2024-27 | 60 | 5.39% |",
        section="Rates",
        effective_date=None,
        url="https://www.example.com/personal/loans/auto-motorcycle-loans",
        snapshot_id="s1",
        taken_on="2026-09-28",
        authority=1.0,
    )
    from kb.evidence import FactEvidence

    pack = EvidencePack(facts=[FactEvidence(f, 1.0)], chunks=[], as_of=None)
    ans = Answer(text="5.39% APR for 60 months.", sources=[], confident=True)
    out = apply_grounding(
        ans,
        pack,
        "What is the APR on a 60-month auto loan for a 2026 model year vehicle?",
    )
    assert out.confident
