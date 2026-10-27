from kb.authority import normalize_url
from kb.evidence import gather_evidence
from kb.prose_rates import extract_prose_apr_facts
from kb.system import KnowledgeStore, PageVersion


def test_extract_prose_apr_range_with_heading():
    md = (
        "### Rewards Visa\n"
        "Best for earning. Variable rate from 12.50% APR to 19.50% APR.\n"
    )
    facts = extract_prose_apr_facts(
        md,
        url="https://www.example.com/personal/credit-cards",
        snapshot_id="s1",
        taken_on="2026-01-01",
        authority=1.0,
    )
    assert facts
    assert any("12.50" in f.value and "19.50" in f.value for f in facts)
    assert any("Rewards" in f.subject for f in facts)


def test_gather_includes_prose_apr_facts():
    url = "https://www.example.com/personal/credit-cards"
    md = "### Personal Visa\nAPR ranges from 12.50% to 19.50% APR based on credit.\n"
    store = KnowledgeStore()
    store.snapshots.append(("s1", "2026-01-01"))
    store.pages.append(
        PageVersion(
            url=url,
            canonical=normalize_url(url),
            title="Cards",
            markdown=md,
            snapshot_id="s1",
            taken_on="2026-01-01",
            fetched_at="2026-01-01",
            authority=1.0,
            stale_for_rates=False,
        )
    )
    store.facts.extend(
        extract_prose_apr_facts(
            md, url=url, snapshot_id="s1", taken_on="2026-01-01", authority=1.0
        )
    )
    pack = gather_evidence(store, "What is the Example Rewards card APR range?", None, max_facts=10)
    assert any("apr range" in fe.fact.field.lower() for fe in pack.facts)
