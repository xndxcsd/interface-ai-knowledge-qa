import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))

from kb.evidence import EvidencePack
from kb.grounding import _page_product_ok


def test_page_gate_allows_both_sides_when_neither_named():
    assert _page_product_ok(
        "https://www.example.com/business/credit-cards",
        "",
        "What credit cards do you offer?",
        EvidencePack(facts=[], chunks=[], as_of=None),
    )
    assert _page_product_ok(
        "https://www.example.com/personal/credit-cards",
        "",
        "What credit cards do you offer?",
        EvidencePack(facts=[], chunks=[], as_of=None),
    )


def test_page_gate_allows_both_when_personal_and_business_named():
    assert _page_product_ok(
        "https://www.example.com/personal/credit-cards",
        "",
        "What are personal and business card APRs?",
        EvidencePack(facts=[], chunks=[], as_of=None),
    )
    assert _page_product_ok(
        "https://www.example.com/business/credit-cards",
        "",
        "What are personal and business card APRs?",
        EvidencePack(facts=[], chunks=[], as_of=None),
    )


def test_credit_union_does_not_trigger_business_only():
    pack = EvidencePack(facts=[], chunks=[], as_of=None)
    assert _page_product_ok(
        "https://www.example.com/personal/credit-cards",
        "",
        "Tell me about the credit union's Visa cards.",
        pack,
    )
