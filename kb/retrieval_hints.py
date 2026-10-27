"""Map question themes to canonical site paths (general site structure, not eval IDs)."""
from __future__ import annotations


def is_list_question(question: str) -> bool:
    q = question.lower()
    return any(
        w in q
        for w in (
            "all ",
            "each ",
            "list",
            "every",
            "what cards",
            "what are the",
            "summarize all",
            "name each",
            "rates for the",
            "give me all",
            "certificate",
            "credit card",
        )
    )


def canonical_path_hints(question: str) -> list[str]:
    q = question.lower()
    hints: list[str] = []
    if "credit card" in q or ("visa" in q and "apr" in q):
        hints.extend(["personal/credit-cards", "business/credit-cards"])
    pairs = (
        (("certificate", " cd", "term share", "share certificate"), "personal/savings-account"),
        (("checking", "1st rate", "free checking"), "personal/checking-accounts"),
        (("mortgage", "home loan", "refinance", "30-year", "15-year"), "personal/loans/home-loans"),
        (("auto loan", "motorcycle", "vehicle loan"), "personal/loans/auto-motorcycle-loans"),
        (("personal loan", "signature loan"), "personal/loans/personal-loans"),
        (("business card",), "business/credit-cards"),
        (("routing", "aba", "wire"), "business/cash-management"),
        (("branch", "lobby", "drive-up", "atm", "locator", "address"), "contact"),
        (("join", "membership", "eligible", "member"), "about/join"),
        (("mobile wallet", "apple pay", "google pay", "samsung pay"), "connect/online-and-mobile-banking"),
        (("student loan", "college"), "personal/loans"),
        (("money market", "investor"), "personal/savings-account"),
    )
    for keys, path in pairs:
        if any(k in q for k in keys):
            hints.append(path)
    seen: set[str] = set()
    out: list[str] = []
    for h in hints:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out
