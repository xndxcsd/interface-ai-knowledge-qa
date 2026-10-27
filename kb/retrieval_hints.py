"""Map question themes to canonical site paths (structure only, not eval wording)."""
from __future__ import annotations


def is_list_question(question: str) -> bool:
    q = question.lower()
    if " and " in q and any(w in q for w in ("card", "certificate", "account", "loan")):
        return True
    return any(
        w in q
        for w in (
            " list",
            " each ",
            " every ",
            " all ",
            " both ",
            "types of",
        )
    )


def canonical_path_hints(question: str) -> list[str]:
    q = question.lower()
    hints: list[str] = []
    if "card" in q and ("credit" in q or "visa" in q or "apr" in q):
        hints.extend(["personal/credit-cards", "business/credit-cards"])
    pairs = (
        (("certificate", " cd", "share certificate"), "personal/savings-account"),
        (("checking",), "personal/checking-accounts"),
        (("mortgage", "home loan", "refinance"), "personal/loans/home-loans"),
        (("auto", "motorcycle", "vehicle"), "personal/loans/auto-motorcycle-loans"),
        (("personal loan",), "personal/loans/personal-loans"),
        (("routing", "aba"), "business/cash-management"),
        (("branch", "lobby", "drive", "atm", "locator", "address"), "contact"),
        (("join", "membership", "eligible"), "about/join"),
        (("mobile wallet", "mobile payment"), "connect/online-and-mobile-banking"),
        (("student", "college"), "personal/loans"),
        (("money market",), "personal/savings-account"),
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
