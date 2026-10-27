"""Map question themes to canonical site paths (general site structure, not eval IDs)."""
from __future__ import annotations


def canonical_path_hints(question: str) -> list[str]:
    q = question.lower()
    hints: list[str] = []
    pairs = (
        (("certificate", " cd", "term share", "share certificate"), "personal/savings-account"),
        (("checking", "1st rate", "free checking"), "personal/checking-accounts"),
        (("mortgage", "home loan", "refinance", "30-year", "15-year"), "personal/loans/home-loans"),
        (("auto loan", "motorcycle", "vehicle loan"), "personal/loans/auto-motorcycle-loans"),
        (("personal loan", "signature loan"), "personal/loans/personal-loans"),
        (("credit card", "visa", "mastercard"), "personal/credit-cards"),
        (("business card", "business credit"), "business/credit-cards"),
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
    return hints
