"""Grounding: tokens in evidence; rates tied to page/row; unknown branch guard."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from contract import Answer

from kb.evidence import EvidencePack, is_rate_question
from kb.textutil import tokenize

NUM = re.compile(r"(\$)?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d+))?\s*(%|percent)?", re.I)
PHONE = re.compile(
    r"\b(?:\+1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
URL_RE = re.compile(
    r"(?:https?://[^\s\])\"']+|(?:[a-z0-9-]+\.)+dupaco\.com[^\s\])\"']*)",
    re.I,
)
TIME_TOKEN = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)\b", re.I
)
STREET = re.compile(
    r"\b\d+\s+[A-Za-z0-9.\'\-]+(?:\s+(?:St|Street|Ln|Lane|Ave|Avenue|Rd|Road|Dr|Drive|Blvd|Hwy))\.?\b",
    re.I,
)
ZIP = re.compile(r"\b\d{5}\b")
REFUSAL = "I don't know."

GENERIC = frozenset(
    {
        "what", "the", "is", "are", "do", "does", "for", "on", "to", "you", "your",
        "dupaco", "rate", "rates", "loan", "loans", "account", "current", "right",
        "now", "tell", "give", "provide", "much", "many", "any", "can", "could",
        "branch", "street", "address", "hours", "lobby", "drive", "main", "named",
    }
)
def _numbers(text: str) -> set[tuple[str, float]]:
    out: set[tuple[str, float]] = set()
    for m in NUM.finditer(text or ""):
        unit = "$" if m.group(1) else ("%" if m.group(4) else "")
        val = float(m.group(2).replace(",", "") + ("." + m.group(3) if m.group(3) else ""))
        out.add((unit, round(val, 4)))
    return out


def evidence_corpus(pack: EvidencePack) -> str:
    parts: list[str] = []
    for fe in pack.facts:
        f = fe.fact
        parts.extend([f.url, f.section, f.subject, f.field, f.value, f.raw_row])
    for ce in pack.chunks:
        parts.extend([ce.chunk.url, ce.chunk.text])
    return "\n".join(parts)


def _norm_time(s: str) -> str:
    t = re.sub(r"\b([ap])\.\s?m\.?", r"\1m", s.lower())
    return re.sub(r"\s+", " ", t).strip()


def _substr_in_corpus(needle: str, corpus: str) -> bool:
    n = re.sub(r"\s+", " ", needle.lower().strip())
    c = corpus.lower()
    if n in c:
        return True
    if _norm_time(needle) in _norm_time(corpus):
        return True
    digits = re.sub(r"\D", "", needle)
    if len(digits) >= 5 and digits in re.sub(r"\D", "", c):
        return True
    return False


def _url_in_corpus(url: str, corpus: str) -> bool:
    u = url.rstrip(".,)")
    if u in corpus:
        return True
    for alt in (u.replace("https://www.", "https://"), u.replace("https://", "https://www.")):
        if alt in corpus:
            return True
    try:
        p = urlparse(u if "://" in u else f"https://{u}")
        host_path = p.netloc.removeprefix("www.") + p.path.rstrip("/")
        if host_path.lower() in corpus.lower():
            return True
        bare = f"dupaco.com{p.path.rstrip('/')}"
        if bare.lower() in corpus.lower():
            return True
    except Exception:
        pass
    return False


def _column_matches(field: str, question: str) -> bool:
    f = field.lower()
    q = question.lower()
    if re.search(r"\bapy\b|\byield\b", q):
        return "apy" in f or "yield" in f
    if re.search(r"\bapr\b", q):
        return "apr" in f or "annual percentage rate" in f
    if "dividend" in q and "apy" not in q:
        return "dividend" in f
    if re.search(r"\brate\b", q) and "interest rate" in q:
        return any(x in f for x in ("rate", "apy", "apr", "dividend", "yield"))
    return True


def _row_matches(subject: str, section: str, url: str, question: str) -> bool:
    q = question.lower()
    blob = f"{subject} {section} {url}".lower()
    qtoks = {t for t in tokenize(question) if len(t) > 2 and t not in GENERIC}
    if not qtoks:
        return True
    if "mortgage" in qtoks or "mortgage" in q:
        return "home-loan" in url.lower()
    if "certificate" in q or "jumbo" in q:
        return any(x in blob for x in ("month", "jumbo", "certificate", "special"))
    if "share" in q and "savings" in q:
        return "share" in blob and "savings" in blob
    if "money market" in q:
        return "money" in blob and "market" in blob
    if "hsa" in q:
        return "hsa" in blob
    if "card" in q or "visa" in q:
        if "business" in q:
            return "business" in url.lower()
        if "business" in url.lower():
            return False
        return "personal" in url.lower() or "credit-card" in url.lower()
    if any(x in q for x in ("boat", "recreational")):
        return "recreational" in url.lower()
    if any(x in q for x in ("auto", "vehicle", "motorcycle")):
        return "auto" in url.lower() or "motorcycle" in url.lower()
    overlap = qtoks & set(tokenize(blob))
    return len(overlap) >= 1


def _window_around_number(text: str, num: tuple[str, float], radius: int = 90) -> str:
    target = str(num[1]).rstrip("0").rstrip(".")
    for m in NUM.finditer(text):
        unit = "%" if m.group(4) else ""
        val = float(m.group(2).replace(",", "") + ("." + m.group(3) if m.group(3) else ""))
        if (unit, round(val, 4)) == num or target in m.group(0):
            start = max(0, m.start() - radius)
            return text[start : m.end() + radius]
    return text[:180]


def _prose_column_ok(text: str, question: str, num: tuple[str, float]) -> bool:
    q = question.lower()
    win = _window_around_number(text, num).lower()
    if re.search(r"\bapy\b|\byield\b", q):
        return "apy" in win or "yield" in win
    if re.search(r"\bapr\b", q):
        return "apr" in win
    if "dividend" in q and "apy" not in q:
        return "dividend" in win
    return True


def _rate_grounded(num: tuple[str, float], pack: EvidencePack, question: str) -> bool:
    for fe in pack.facts:
        if num not in _numbers(fe.fact.value):
            continue
        f = fe.fact
        if _column_matches(f.field, question) and _row_matches(
            f.subject, f.section, f.url, question
        ):
            return True
    urls_with_table = {
        fe.fact.url.rstrip("/")
        for fe in pack.facts
        if num in _numbers(fe.fact.value)
    }
    for ce in pack.chunks:
        if num not in _numbers(ce.chunk.text):
            continue
        url = ce.chunk.url.rstrip("/")
        if not _row_matches("", ce.chunk.text[:400], ce.chunk.url, question):
            continue
        if url in urls_with_table:
            continue
        if _prose_column_ok(ce.chunk.text, question, num):
            return True
    return False


def _named_places(question: str) -> list[str]:
    q = re.sub(r"\bDupaco(?:'s|s)\b", "", question, flags=re.I)
    places: list[str] = []
    for m in re.finditer(
        r"\b([A-Z][A-Za-z'\-]+)\s+(?:Branch|branch|Avenue|Street|St\.|Blvd\.|Road|Rd\.)\b",
        q,
    ):
        places.append(m.group(1).lower().rstrip("'s"))
    for m in re.finditer(
        r"(?:branch|lobby|hours)\s+(?:for|at|on)\s+(?:the\s+)?([A-Z][A-Za-z'\-]{4,})\b",
        q,
        re.I,
    ):
        places.append(m.group(1).lower().rstrip("'s"))
    for m in re.finditer(r"\b([A-Z][A-Za-z'\-]+),\s*([A-Z]{2})\b", q):
        places.append(m.group(1).lower().rstrip("'s"))
    for m in re.finditer(r"\b([A-Z][A-Za-z'\-]+)\s+branch\b", q, re.I):
        places.append(m.group(1).lower().rstrip("'s"))
    out: list[str] = []
    for p in places:
        if p == "dupaco" or len(p) < 5:
            continue
        if p not in out:
            out.append(p)
    return out


def _location_corpus(pack: EvidencePack) -> str:
    parts: list[str] = []
    for fe in pack.facts:
        if fe.fact.field.lower() in ("address", "hours", "phone"):
            parts.extend([fe.fact.subject, fe.fact.value, fe.fact.section])
    for ce in pack.chunks:
        if any(x in ce.chunk.url.lower() for x in ("/contact", "newsroom", "branch")):
            parts.append(ce.chunk.text)
    return " ".join(parts).lower()


def _unknown_place_in_question(question: str, pack: EvidencePack) -> bool:
    if not any(
        k in question.lower()
        for k in ("branch", "lobby", "hours", "address", "street", "avenue", "named")
    ):
        return False
    places = _named_places(question)
    if not places:
        return False
    corpus = _location_corpus(pack)
    for p in places:
        if p not in corpus and p.replace("-", " ") not in corpus:
            return True
    return False


def _refuse(answer: Answer) -> Answer:
    return Answer(text=REFUSAL, sources=answer.sources, confident=False)


def sanitize_refusal(answer: Answer) -> Answer:
    if answer.confident:
        return answer
    if _numbers(answer.text) or re.search(r"\b\d+\s*months?\b", answer.text, re.I):
        return Answer(text=REFUSAL, sources=answer.sources, confident=False)
    if answer.text and answer.text.strip().lower() != REFUSAL.lower():
        low = answer.text.lower()
        if any(x in low for x in ("don't know", "do not know", "not sure", "couldn't find")):
            return Answer(text=REFUSAL, sources=answer.sources, confident=False)
    return answer


def apply_grounding(answer: Answer, pack: EvidencePack, question: str) -> Answer:
    answer = sanitize_refusal(answer)
    if not answer.text:
        return Answer(text=REFUSAL, sources=[], confident=False)

    if _unknown_place_in_question(question, pack):
        return _refuse(answer)

    corpus = evidence_corpus(pack)
    text = answer.text

    if is_rate_question(question):
        for n in _numbers(text):
            if n[0] == "%" and not _rate_grounded(n, pack, question):
                return _refuse(answer)

    for m in PHONE.finditer(text):
        if not _substr_in_corpus(m.group(0), corpus):
            return _refuse(answer)

    for m in URL_RE.finditer(text):
        if not _url_in_corpus(m.group(0), corpus):
            return _refuse(answer)

    for m in TIME_TOKEN.finditer(text):
        if not _substr_in_corpus(m.group(0), corpus):
            return _refuse(answer)

    if STREET.search(text) or ZIP.search(text):
        for zm in ZIP.finditer(text):
            if not _substr_in_corpus(zm.group(0), corpus):
                return _refuse(answer)

    return answer


def postcheck_answer(answer: Answer, pack: EvidencePack, question: str) -> Answer:
    return apply_grounding(answer, pack, question)
