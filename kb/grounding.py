"""Ensure answer tokens appear in retrieved evidence."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from contract import Answer

from kb.evidence import EvidencePack, is_rate_question
from kb.product_match import product_aligns
from kb.textutil import tokenize

NUM = re.compile(r"(\$)?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d+))?\s*(%|percent)?", re.I)
PHONE = re.compile(
    r"\b(?:\+1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
URL_RE = re.compile(r"https?://[^\s\])\"']+", re.I)
TIME_TOKEN = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)\b", re.I
)
STREET = re.compile(
    r"\b\d+\s+[A-Za-z0-9.\'\-]+(?:\s+(?:St|Street|Ln|Lane|Ave|Avenue|Rd|Road|Dr|Drive|Blvd|Hwy))\.?\b",
    re.I,
)
ZIP = re.compile(r"\b\d{5}\b")
NAMED_BRANCH = re.compile(
    r"(?<!\w)([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)?)\s+"
    r"(?:Branch|branch|Avenue|Street|St\.|Blvd\.|Road|Rd\.)\b"
    r"|(?:branch|lobby)\s+(?:for|at|on)\s+(?:the\s+)?([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)?)",
)
REFUSAL = "I don't know."


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
        parts.extend([f.url, f.subject, f.field, f.value, f.raw_row])
    for ce in pack.chunks:
        parts.extend([ce.chunk.url, ce.chunk.text])
    return "\n".join(parts)


def _question_product_overlap(question: str, fact_blob: str) -> float:
    q = {t for t in tokenize(question) if len(t) > 2}
    if not q:
        return 1.0
    f = set(tokenize(fact_blob))
    return len(q & f) / len(q)


def rate_supported(num: tuple[str, float], pack: EvidencePack, question: str) -> bool:
    for fe in pack.facts:
        if num not in _numbers(fe.fact.value):
            continue
        if not product_aligns(question, fe.fact):
            continue
        blob = f"{fe.fact.subject} {fe.fact.field} {fe.fact.value}"
        if _question_product_overlap(question, blob) >= 0.12:
            return True
        if _question_product_overlap(question, fe.fact.url) >= 0.08:
            return True
    for ce in pack.chunks:
        if num not in _numbers(ce.chunk.text):
            continue
        if not product_aligns(question, _FactLike(ce.chunk.url, ce.chunk.text)):
            continue
        if _question_product_overlap(question, ce.chunk.text) >= 0.1:
            return True
    return False


class _FactLike:
    __slots__ = ("url", "subject", "section", "field")

    def __init__(self, url: str, text: str) -> None:
        self.url = url
        self.subject = text[:80]
        self.section = ""
        self.field = ""


def _substr_in_corpus(needle: str, corpus: str) -> bool:
    n = re.sub(r"\s+", " ", needle.lower().strip())
    c = corpus.lower()
    if n in c:
        return True
    digits = re.sub(r"\D", "", needle)
    if len(digits) >= 5 and digits in re.sub(r"\D", "", c):
        return True
    return False


def _url_in_corpus(url: str, corpus: str) -> bool:
    u = url.rstrip(".,)")
    if u in corpus:
        return True
    alt = u.replace("https://www.", "https://")
    if alt in corpus:
        return True
    try:
        p = urlparse(u)
        host_path = p.netloc.removeprefix("www.") + p.path.rstrip("/")
        if host_path.lower() in corpus.lower():
            return True
        if p.path.rstrip("/") and p.path.rstrip("/").lower() in corpus.lower():
            return True
    except Exception:
        pass
    return False


def _explicit_location_names(question: str) -> list[str]:
    names: list[str] = []
    for m in NAMED_BRANCH.finditer(question):
        g = m.group(1) or m.group(2)
        if g:
            names.append(g.lower())
    return names


def _refuse(answer: Answer) -> Answer:
    return Answer(text=REFUSAL, sources=answer.sources, confident=False)


def apply_grounding(answer: Answer, pack: EvidencePack, question: str) -> Answer:
    if not answer.text:
        return Answer(text=REFUSAL, sources=[], confident=False)

    corpus = evidence_corpus(pack)
    text = answer.text

    for name in _explicit_location_names(question):
        if name not in corpus.lower() and name.replace("-", " ") not in corpus.lower():
            if any(k in question.lower() for k in ("branch", "lobby", "hours", "address", "street")):
                return _refuse(answer)

    if is_rate_question(question):
        for n in _numbers(text):
            if n[0] == "%" and not rate_supported(n, pack, question):
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
