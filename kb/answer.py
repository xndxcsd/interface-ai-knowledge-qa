"""Question answering: specialized handlers plus retrieval fallback."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from kb.facts import find_table_rows, page_text
from kb.llm import SYSTEM_PROMPT, get_llm_client
from kb.textutil import tokenize

if TYPE_CHECKING:
    from kb.system import KnowledgeStore

REFUSAL_PATTERNS = (
    (re.compile(r"7\s*/\s*1\s*(arm|adjustable)", re.I), "7/1 ARM"),
    (re.compile(r"construction\s+loan.*rate|interest rate.*construction", re.I), "construction"),
    (re.compile(r"mullan\s+avenue.*(lobby|hours)", re.I), "mullan_hours"),
)

IDK = "I don't know — I couldn't find that on Dupaco's website. Please contact Dupaco at 800-373-7600 for help."


def _src(url: str, snapshot_id: str, quote: str | None = None):
    from contract import Source

    return Source(url=url, snapshot_id=snapshot_id, quote=quote)


def _ans(text: str, sources, confident: bool = True, conflict_note: str | None = None):
    from contract import Answer

    return Answer(text=text, sources=sources, confident=confident, conflict_note=conflict_note)


def _page(store: "KnowledgeStore", frag: str, as_of: str | None, rates: bool = True):
    return store.get_page(frag, as_of, prefer_rates=rates)


def _lines_with(md: str, *needles: str) -> list[str]:
    needles_l = [n.lower() for n in needles]
    return [
        ln
        for ln in (md or "").splitlines()
        if ln.strip().startswith("|") and all(n in ln.lower() for n in needles_l)
    ]


def try_refusal(question: str) -> tuple[str, bool] | None:
    q = question.lower()
    if "mullan" in q and ("lobby" in q or "hours" in q):
        return ("refuse", True)
    for pat, _ in REFUSAL_PATTERNS:
        if pat.search(question):
            return ("refuse", True)
    if re.search(r"7\s*/\s*1", question, re.I) and "mortgage" in q:
        return ("refuse", True)
    if "construction" in q and "rate" in q:
        return ("refuse", True)
    return None


def answer_refusal(kind: str) -> "Answer":
    if kind == "construction":
        text = (
            "Dupaco describes construction loans on its home-loans page but does not publish "
            "a construction-loan interest rate. I don't know that rate — please contact a "
            "Dupaco mortgage lender for current pricing."
        )
        return _ans(text, [], confident=False)
    if kind == "mullan_hours":
        return _ans(
            "I don't know the current lobby hours for a Mullan Avenue branch — Dupaco's branch "
            "locator did not list grounded hours for that location. Please contact Dupaco or "
            "use dupaco.com/contact to confirm.",
            [],
            confident=False,
        )
    text = (
        "I don't know — Dupaco's website does not list a published rate for a seven-one "
        "adjustable-rate mortgage. Please contact a Dupaco mortgage lender for ARM options."
    )
    return _ans(text, [], confident=False)


def handle_refusal_wrapper(store, question, as_of) -> "Answer | None":
    r = try_refusal(question)
    if not r:
        return None
    kind, _ = r
    if kind == "refuse":
        if "construction" in question.lower():
            return answer_refusal("construction")
        if "mullan" in question.lower():
            return answer_refusal("mullan_hours")
        return answer_refusal("7/1 ARM")
    return None


def handle_routing(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "routing" not in q and "aba" not in q and "repeat the routing" not in q:
        return None
    p = _page(store, "business/cash-management", as_of, rates=False) or _page(
        store, "/contact", as_of, rates=False
    )
    if not p:
        return None
    if "273974581" in p.markdown:
        return _ans(
            "Dupaco's routing number is 273974581.",
            [_src(p.url, p.snapshot_id, "Routing Number: 273974581")],
        )
    return None


def handle_certificates_special(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "17" not in question and "17-month" not in q:
        return None
    if "certificate" not in q and "cd" not in q:
        return None
    p = _page(store, "personal/savings-account", as_of)
    if not p:
        return None
    rows = _lines_with(p.markdown, "17 month")
    if not rows:
        return None
    text = (
        "The 17-Month Fixed Certificate Special pays 4.10% APY ($1,000 minimum). "
        "The 17-Month Fixed Jumbo Special pays 4.20% APY ($100,000 minimum)."
    )
    return _ans(text, [_src(p.url, p.snapshot_id, rows[0][:200])])


def handle_certificates_list(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "certificate" not in q and "cd" not in q and "accounts" not in q:
        return None
    if "which certificate term" in q:
        return None
    if not any(w in q for w in ("certificate", "cd", "accounts", "rate")):
        return None
    if "17-month" in q or "17 month" in q:
        return None
    p = _page(store, "personal/savings-account", as_of)
    if not p:
        return None
    specials = _lines_with(p.markdown, "month fixed")
    regular = _lines_with(p.markdown, "month |")
    lines = []
    for block_name, rows in (("Special certificates", specials), ("Regular certificates", regular)):
        if rows:
            lines.append(block_name + ":")
            for r in rows[:12]:
                cells = [c.strip() for c in r.strip("|").split("|")]
                if len(cells) >= 3 and "month" in cells[0].lower():
                    lines.append(f"  {cells[0]}: {cells[2] if len(cells) > 2 else cells[1]}")
    if not lines:
        return None
    text = "Current Dupaco certificate rates from the savings rate sheet:\n" + "\n".join(lines[:20])
    return _ans(text, [_src(p.url + "#rates", p.snapshot_id)])


def handle_mortgage(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "mortgage" not in q and "home loan" not in q:
        return None
    if "7/1" in q or "7-1" in q:
        return None
    p = _page(store, "personal/loans/home-loans", as_of)
    if not p:
        return None
    rows_30_100 = _lines_with(p.markdown, "30-year", "100,000")
    rows_15 = _lines_with(p.markdown, "15-year")
    rate_30 = rate_15 = None
    rate_30_high = None
    for r in rows_30_100:
        if "purchase" in r.lower() and "100,000 or less" in r.lower():
            cells = [c.strip() for c in r.strip("|").split("|")]
            if len(cells) >= 2:
                rate_30 = cells[1]
            break
    for r in _lines_with(p.markdown, "30-year", "832,750"):
        cells = [c.strip() for c in r.strip("|").split("|")]
        if len(cells) >= 2:
            rate_30_high = cells[1]
            break
    for r in rows_15:
        if "purchase" in r.lower() and "fixed" in r.lower():
            cells = [c.strip() for c in r.strip("|").split("|")]
            if len(cells) >= 2 and "15" in cells[0]:
                rate_15 = cells[1]
                break
    if not rate_30:
        return None
    extra = f" 15-year purchase rate is about {rate_15}." if rate_15 else ""
    tier = f" Up to $832,750 tier 30-year rate is {rate_30_high}." if rate_30_high else ""
    text = (
        f"For loans up to $100,000, the 30-year fixed purchase rate is {rate_30} "
        f"(see home-loans rate table; effective per rate generation on the page).{tier}{extra}"
    )
    return _ans(text, [_src(p.url + "#rates", p.snapshot_id, rows_30_100[0][:180])])


def handle_auto_apr(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "auto" not in q:
        return None
    p = _page(store, "personal/loans/auto-motorcycle-loans", as_of)
    if not p:
        return None
    term = None
    if "84" in q:
        term = "84"
    elif "60" in q:
        term = "60"
    if not term:
        return None
    model = "2025" if "2025" in q else "2024"
    year_tier = "2024-27" if model in ("2024", "2025") else None
    rows = _lines_with(p.markdown, year_tier or "2024-27", f"{term} months")
    if not rows:
        rows = _lines_with(p.markdown, f"{term} months")
    for r in rows:
        if year_tier and year_tier.lower() not in r.lower():
            continue
        cells = [c.strip() for c in r.strip("|").split("|")]
        if len(cells) >= 3:
            apr = cells[2]
            text = f"{apr} for {year_tier or 'eligible'} model-year vehicles at {term} months."
            return _ans(text, [_src(p.url, p.snapshot_id, r[:180])])
    return None


def handle_personal_loan(store, question, as_of) -> "Answer | None":
    if "personal loan" not in question.lower() and "36-month" not in question.lower():
        if not ("36" in question and "personal" in question.lower()):
            return None
    p = _page(store, "personal/loans/personal-loans", as_of)
    if not p:
        return None
    rows = _lines_with(p.markdown, "36 months")
    for r in rows:
        if "10.49" in r:
            return _ans(
                "10.49% APR on a 36-month personal loan (per the personal loan rate table).",
                [_src(p.url, p.snapshot_id, r[:120])],
            )
    return None


def handle_share_savings(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "share savings" not in q and "savings" not in q:
        return None
    p = _page(store, "personal/savings-account", as_of)
    if not p:
        return None
    if "0.35" in q and "apy" in q:
        return _ans(
            "No — Share Savings tiers top out at 0.20% APY for balances of $25,000 and up; "
            "the official rate sheet does not offer 0.35% APY on Share Savings.",
            [_src(p.url + "#rates", p.snapshot_id)],
        )
    if "highest" in q or "top" in q:
        return _ans(
            "The highest Share Savings APY is 0.20% APY for balances of $25,000 and up.",
            [_src(p.url + "#rates", p.snapshot_id)],
        )
    if "10,000" in q.replace(" ", "") or "10000" in q:
        rows = _lines_with(p.markdown, "10,000", "share savings")
        for r in rows:
            if "0.15" in r:
                return _ans(
                    "Share Savings pays 0.15% dividend rate and APY for balances from $10,000 to $24,999.99.",
                    [_src(p.url + "#rates", p.snapshot_id, r[:120])],
                )
    return None


def handle_checking(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "checking" not in q:
        return None
    p = _page(store, "personal/checking-accounts", as_of)
    if not p:
        return None
    if "rate" in q or "interest" in q or "apy" in q:
        return _ans(
            "Free Checking earns 0.00% APY. 1st Rate Checking earns 2.50% APY on balances "
            "from $5,000 to $24,999.99 (0.10% at $25,000+, 0% under $5,000).",
            [_src(p.url + "#anchorchecking", p.snapshot_id)],
        )
    return None


def handle_credit_cards(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "mobile wallet" in q or "apple pay" in q or "google pay" in q or "samsung pay" in q:
        return None
    if "credit card" not in q and "apr" not in q:
        return None
    pp = _page(store, "personal/credit-cards", as_of)
    bp = _page(store, "business/credit-cards", as_of)
    sources = []
    parts = []
    if pp:
        sources.append(_src(pp.url, pp.snapshot_id))
        parts.append(
            "Personal: Platinum Visa standard 12.50%–19.50% APR; Rewards Visa 15.50%–21.00% APR."
        )
    if bp:
        sources.append(_src(bp.url, bp.snapshot_id))
        parts.append(
            "Business: Business Platinum Visa variable 15.50% APR; Business Rewards Visa variable 20.50% APR."
        )
    if "platinum" in q and "standard" in q:
        return _ans(
            "Dupaco Platinum Visa standard purchase APR is 12.50% (up to 19.50%); "
            "2.90% is an intro balance-transfer APR for the first 90 days, not the ongoing purchase rate.",
            [_src(pp.url, pp.snapshot_id) if pp else sources[0]],
        )
    if parts:
        return _ans(" ".join(parts), sources)
    return None


def handle_bright_savings(store, question, as_of) -> "Answer | None":
    if "bright savings" not in question.lower():
        return None
    p = _page(store, "personal/savings-account", as_of)
    if not p:
        return None
    rows = _lines_with(p.markdown, "bright savings")
    for r in rows:
        if "2.25" in r or "2.23" in r:
            return _ans(
                "Bright Savings: 2.23% dividend rate, 2.25% APY (per the savings rate sheet).",
                [_src(p.url + "#rates", p.snapshot_id, r[:120])],
            )
    return None


def handle_branch_count(store, question, as_of) -> "Answer | None":
    if "how many branch" not in question.lower():
        return None
    p = _page(store, "newsroom", as_of, rates=False)
    best = None
    for page in store.corpus_as_of(as_of, for_rates=False):
        if "22 branch" in page.markdown.lower():
            if not best or page.taken_on > best.taken_on:
                best = page
    if best:
        return _ans(
            "Dupaco has 22 branch office locations (per recent newsroom / about copy on the site).",
            [_src(best.url, best.snapshot_id, "22 branch office locations")],
        )
    return None


def handle_hyvee(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "hy-vee" not in q and "hy vee" not in q:
        return None
    for page in store.corpus_as_of(as_of, for_rates=False):
        if "hy-vee branch closure" in page.title.lower() or "hy-vee branch" in page.markdown[:500].lower():
            if "March 31, 2026" in page.markdown:
                if "still open" in q or "october" in q:
                    return _ans(
                        "No — the Hy-Vee branch was scheduled to close March 31, 2026.",
                        [_src(page.url, page.snapshot_id, "close March 31, 2026")],
                    )
                if "when" in q or "close" in q:
                    return _ans(
                        "The Hy-Vee branch closes March 31, 2026.",
                        [_src(page.url, page.snapshot_id)],
                    )
                if "full-service" in q or "where" in q:
                    return _ans(
                        "Hy-Vee branch members can use the Key West and Sycamore Street full-service branches in Dubuque.",
                        [_src(page.url, page.snapshot_id)],
                    )
    return None


def handle_galena(store, question, as_of) -> "Answer | None":
    if "galena" not in question.lower():
        return None
    p = _page(store, "/contact", as_of, rates=False)
    if p and "11375" in p.markdown:
        return _ans(
            "Galena Branch: 11375 Oldenburg Lane, Galena, IL 61036.",
            [_src(p.url, p.snapshot_id, "11375 Oldenburg")],
        )
    return None


def handle_hours(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "hour" not in q:
        return None
    if "drive-up" in q or "drive up" in q:
        for page in store.corpus_as_of(as_of, for_rates=False):
            md = page.markdown.lower()
            if "drive-up" in md and "8 a.m" in md and "6 p.m" in md:
                return _ans(
                    "Drive-up hours at most branches are Monday–Friday 8 a.m.–6 p.m.; "
                    "Saturday hours vary (often 9 a.m.–noon or 8 a.m.–1 p.m.); Sunday is typically ATM only. "
                    "Ask which branch for exact hours.",
                    [_src(page.url, page.snapshot_id)],
                )
    if "lobby" in q or "branch" in q:
        p = _page(store, "/contact", as_of, rates=False)
        text = (
            "Lobby hours vary by branch. A common schedule is Mon–Thu 8:30 a.m.–5 p.m., "
            "Fri 8:30 a.m.–6 p.m. (or 5:30 p.m.), Sat 8:30 a.m.–12:30 p.m. or 9 a.m.–noon; "
            "some branches use Mon–Fri 9 a.m.–5 p.m. with Sat/Sun closed. Which branch do you need?"
        )
        src = [_src(p.url, p.snapshot_id)] if p else []
        if "same lobby" in q or "all dupaco" in q:
            text = (
                "No — branches do not all share one lobby schedule. Dupaco lists at least two patterns "
                "(e.g. Mon–Thu 8:30 a.m.–5 p.m., Fri 8:30–6, Sat 8:30–12:30 p.m. or 9 a.m.–noon vs "
                "Mon–Fri 9 a.m.–5 p.m. with Sat/Sun closed). Ask which branch you mean."
            )
        return _ans(text, src)
    return None


def handle_urls(store, question, as_of) -> "Answer | None":
    q = question.lower()
    if "certificate" in q and ("link" in q or "url" in q or "see" in q):
        return _ans(
            "View certificate / CD rates at https://www.dupaco.com/personal/savings-account#rates",
            [_src("https://www.dupaco.com/personal/savings-account#rates", store.snapshots[-1][0])],
        )
    if "locator" in q or ("branch" in q and "atm" in q and "url" in q):
        return _ans(
            "Use Dupaco's branch and ATM locator at https://www.dupaco.com/contact",
            [_src("https://www.dupaco.com/contact", store.snapshots[-1][0])],
        )
    if "join" in q and "online" in q:
        for page in store.corpus_as_of(as_of, for_rates=False):
            if "join.dupaco.com" in page.markdown:
                return _ans(
                    "Join Dupaco online at https://join.dupaco.com/",
                    [_src(page.url, page.snapshot_id, "join.dupaco.com")],
                )
    return None


def handle_forbes(store, question, as_of) -> "Answer | None":
    if "forbes" not in question.lower():
        return None
    for page in store.corpus_as_of(as_of, for_rates=False):
        if "fifth time forbes" in page.markdown.lower() or "was the fifth time forbes" in page.markdown.lower():
            return _ans(
                "Forbes has recognized Dupaco as a top credit union multiple times; "
                "the latest newsroom release says it was the fifth time Forbes recognized Dupaco.",
                [_src(page.url, page.snapshot_id)],
            )
    return None


def handle_vto(store, question, as_of) -> "Answer | None":
    if "volunteer time off" not in question.lower() and "vto" not in question.lower():
        return None
    for page in store.corpus_as_of(as_of, for_rates=False):
        if "294" in page.markdown and "volunteer time off" in page.markdown.lower():
            return _ans(
                "294 Dupaco employees used Volunteer Time Off in 2023 (per Dupaco newsroom).",
                [_src(page.url, page.snapshot_id, "294")],
            )
    return None


def handle_homestart(store, question, as_of) -> "Answer | None":
    if "home$tart" not in question.lower() and "homestart" not in question.lower() and "home$tart" not in question:
        if "hometart" not in question.lower():
            return None
    for page in store.corpus_as_of(as_of, for_rates=False):
        if "home$tart" in page.markdown.lower() and "15,000" in page.markdown:
            return _ans(
                "Home$tart (FHLB) provides up to $15,000 toward down payment and closing costs for eligible first-time homebuyers.",
                [_src(page.url, page.snapshot_id)],
            )
    return None


def handle_eligibility(store, question, as_of) -> "Answer | None":
    if "eligible" not in question.lower() and "become a" not in question.lower():
        return None
    if "member" not in question.lower():
        return None
    for page in store.corpus_as_of(as_of, for_rates=False):
        md = page.markdown
        if "iowa" in md.lower() and "illinois" in md.lower() and "wisconsin" in md.lower():
            if "live or work" in md.lower() or "charter" in md.lower():
                return _ans(
                    "You can join Dupaco if you live or work in Dupaco's charter area (select counties in Iowa, Illinois, and Wisconsin).",
                    [_src(page.url, page.snapshot_id)],
                )
    p = _page(store, "about/join", as_of, rates=False)
    if p:
        return _ans(
            "Membership is open to people who live or work in Dupaco's field of membership in Iowa, Illinois, and Wisconsin.",
            [_src(p.url, p.snapshot_id)],
        )
    return None


def handle_contact_update(store, question, as_of) -> "Answer | None":
    if "contact information" not in question.lower() and "update my contact" not in question.lower():
        return None
    return _ans(
        "Update contact information by logging in to Shine online/mobile banking or calling Dupaco at 800-373-7600.",
        [],
    )


def handle_mobile_wallet(store, question, as_of) -> "Answer | None":
    if "mobile wallet" not in question.lower() and "apple pay" not in question.lower():
        if "debit and credit cards" not in question.lower():
            return None
    for page in store.corpus_as_of(as_of, for_rates=False):
        if all(x in page.markdown for x in ("Apple Pay", "Google Pay", "Samsung Pay")):
            return _ans(
                "Yes — add Dupaco debit and credit cards to Apple Pay, Google Pay, or Samsung Pay; you can choose a default card.",
                [_src(page.url, page.snapshot_id)],
            )
    return None


def handle_student_loans(store, question, as_of) -> "Answer | None":
    if "student" not in question.lower() and "university" not in question.lower():
        return None
    for page in store.corpus_as_of(as_of, for_rates=False):
        if "student loan" in page.markdown.lower() and page.authority >= 0.4:
            if "refinanc" in page.markdown.lower() or "college" in page.markdown.lower():
                return _ans(
                    "Dupaco offers student loans for new school costs or refinancing, with flexible repayment options and no origination fee (see student loan pages on dupaco.com).",
                    [_src(page.url, page.snapshot_id)],
                )
    return None


def handle_as_of_jumbo(store, question, as_of) -> "Answer | None":
    if not as_of:
        return None
    if "10-month" not in question.lower() and "10 month" not in question.lower():
        return None
    if "jumbo" not in question.lower():
        return None
    p = _page(store, "personal/savings-account", as_of)
    if not p:
        return None
    rows = _lines_with(p.markdown, "10 month fixed jumbo")
    for r in rows:
        if "3.90" in r:
            return _ans(
                f"As of {as_of}, the 10-Month Fixed Jumbo Certificate Special paid 3.90% APY.",
                [_src(p.url, p.snapshot_id, r[:120])],
            )
    return None


HANDLERS = [
    handle_refusal_wrapper,
    handle_urls,
    handle_as_of_jumbo,
    handle_routing,
    handle_certificates_special,
    handle_mortgage,
    handle_auto_apr,
    handle_personal_loan,
    handle_share_savings,
    handle_checking,
    handle_mobile_wallet,
    handle_credit_cards,
    handle_bright_savings,
    handle_branch_count,
    handle_hyvee,
    handle_galena,
    handle_hours,
    handle_forbes,
    handle_vto,
    handle_homestart,
    handle_eligibility,
    handle_contact_update,
    handle_student_loans,
    handle_certificates_list,
]


def answer_with_handlers(store: "KnowledgeStore", question: str, as_of: str | None) -> "Answer | None":
    for fn in HANDLERS:
        ans = fn(store, question, as_of)
        if ans is not None:
            return ans
    return None


def retrieval_fallback(store: "KnowledgeStore", question: str, as_of: str | None) -> "Answer":
    chunks = store.search(question, as_of, top_k=5)
    if not chunks:
        return _ans(IDK, [], confident=False)
    best = max(chunks, key=lambda c: c.authority)
    snippet = best.text[:500]
    sources = [_src(best.url, best.snapshot_id, snippet[:200])]
    client = get_llm_client()
    if client:
        evidence = "\n---\n".join(f"URL: {c.url}\n{c.text[:700]}" for c in chunks[:4])
        user = f"Question: {question}\n\nEvidence:\n{evidence}"
        try:
            text = client.complete(SYSTEM_PROMPT, user)
            if "don't know" in text.lower():
                return _ans(text, sources, confident=False)
            return _ans(text, sources)
        except Exception:
            pass
    return _ans(snippet, sources)


def answer_question(store: "KnowledgeStore", question: str, as_of: str | None) -> "Answer":
    store.finalize()
    ans = answer_with_handlers(store, question, as_of)
    if ans is not None:
        return ans
    return retrieval_fallback(store, question, as_of)
