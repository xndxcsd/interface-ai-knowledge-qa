"""Grounding: tokens in evidence; rates tied to page/row; unknown branch guard."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from contract import Answer

from kb.evidence import EvidencePack, FactEvidence
from kb.patterns import US_PHONE as PHONE
from kb.places import named_places, newsroom_place_match
from kb.retrieval_hints import is_hours_question, is_list_question, is_rate_question
from kb.textutil import has_any_word, has_word

NUM = re.compile(r"(\$)?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d+))?\s*(%|percent)?", re.I)
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
    if has_any_word(question, ("apy", "yield")):
        return "apy" in f or "yield" in f
    if has_word(question, "apr"):
        return "apr" in f or "annual percentage rate" in f or "apr range" in f
    if has_word(question, "dividend") and not has_any_word(question, ("apy", "yield")):
        return "dividend" in f
    if has_word(question, "rate") and has_any_word(question, ("interest",)):
        return any(x in f for x in ("rate", "apy", "apr", "dividend", "yield"))
    return True


def _page_product_ok(url: str, section: str, question: str, pack: EvidencePack) -> bool:
    if is_list_question(question):
        return True
    path = url.lower()
    asks_business = has_word(question, "business")
    asks_personal = has_word(question, "personal")
    if asks_business and asks_personal:
        return True
    if not asks_business and not asks_personal:
        return True
    on_business = "/business/" in path
    on_personal = "/personal/" in path
    if asks_business and not asks_personal and on_personal and not on_business:
        return False
    if asks_personal and not asks_business and on_business and not on_personal:
        return False
    return True


def _label_matches_question(label_blob: str, question: str) -> bool:
    if is_list_question(question):
        return True
    if not is_rate_question(question):
        return True
    q = question.lower()
    b = label_blob.lower()
    m = re.search(r"\b(\d+)\s*-?\s*month", q)
    if m and m.group(1) not in b and f"{m.group(1)} month" not in b:
        return False
    if has_word(question, "model"):
        ym = re.search(r"\b(20\d{2})\b", q)
        rng = re.search(r"(20\d{2})\s*[-–/]\s*(\d{2,4})", b)
        if ym and rng:
            y = int(ym.group(1))
            y1 = int(rng.group(1))
            tail = rng.group(2)
            y2 = int(tail) if len(tail) == 4 else y1 // 100 * 100 + int(tail)
            if not (y1 <= y <= y2):
                return False
    if has_word(question, "between"):
        lo = re.search(r"between\s+\$?\s*([\d,]+)", q)
        hi = re.search(r"and\s+\$?\s*([\d,]+)", q)
        digits = re.sub(r"[^\d]", "", b)
        if lo and lo.group(1).replace(",", "") not in digits:
            return False
        if hi and hi.group(1).replace(",", "") not in digits:
            return False
    return True


def _fact_grounds_rate(
    fe: FactEvidence, num: tuple[str, float], question: str, pack: EvidencePack
) -> bool:
    f = fe.fact
    if num not in _numbers(f.value):
        return False
    blob = f"{f.subject} {f.raw_row} {f.section}"
    return (
        _column_matches(f.field, question)
        and _page_product_ok(f.url, f.section, question, pack)
        and _label_matches_question(blob, question)
    )


def _window_around_number(text: str, num: tuple[str, float], radius: int = 120) -> str:
    target = str(num[1]).rstrip("0").rstrip(".")
    for m in NUM.finditer(text):
        unit = "%" if m.group(4) else ""
        val = float(m.group(2).replace(",", "") + ("." + m.group(3) if m.group(3) else ""))
        if (unit, round(val, 4)) == num or target in m.group(0):
            start = max(0, m.start() - radius)
            return text[start : m.end() + radius]
    return text[:220]


def _prose_column_ok(text: str, question: str, num: tuple[str, float]) -> bool:
    win = _window_around_number(text, num).lower()
    if has_any_word(question, ("apy", "yield")):
        return "apy" in win or "yield" in win
    if has_word(question, "apr"):
        return "apr" in win
    if has_word(question, "dividend") and not has_any_word(question, ("apy", "yield")):
        return "dividend" in win
    return True


def _rate_grounded(num: tuple[str, float], pack: EvidencePack, question: str) -> bool:
    list_q = is_list_question(question)
    for fe in pack.facts:
        if _fact_grounds_rate(fe, num, question, pack):
            return True

    table_urls_with_num = {
        fe.fact.url.rstrip("/")
        for fe in pack.facts
        if num in _numbers(fe.fact.value)
    }
    for ce in pack.chunks:
        if num not in _numbers(ce.chunk.text):
            continue
        url = ce.chunk.url.rstrip("/")
        if not _page_product_ok(ce.chunk.url, "", question, pack):
            continue
        win = _window_around_number(ce.chunk.text, num)
        if not list_q and not _label_matches_question(win, question) and not _label_matches_question(
            ce.chunk.text[:900], question
        ):
            continue
        if url in table_urls_with_num:
            if any(
                _fact_grounds_rate(fe, num, question, pack)
                for fe in pack.facts
                if fe.fact.url.rstrip("/") == url
            ):
                return True
            continue
        if _prose_column_ok(ce.chunk.text, question, num):
            return True
    return False


def _place_in_corpus(place: str, corpus: str) -> bool:
    return place in corpus or place.replace("-", " ") in corpus


def _location_corpus(pack: EvidencePack) -> str:
    parts: list[str] = []
    for fe in pack.facts:
        if fe.fact.field.lower() in ("address", "hours", "phone", "square feet"):
            parts.extend([fe.fact.subject, fe.fact.value, fe.fact.section])
    for ce in pack.chunks:
        if any(x in ce.chunk.url.lower() for x in ("/contact", "newsroom", "branch")):
            parts.append(ce.chunk.text)
    return " ".join(parts).lower()


def _branch_hours_for_place(place: str, pack: EvidencePack) -> bool:
    p = place.lower()
    for fe in pack.facts:
        if fe.fact.field.lower() != "hours":
            continue
        url = fe.fact.url.lower()
        if "/newsroom/" in url and not newsroom_place_match(fe.fact, p):
            continue
        blob = f"{fe.fact.subject} {fe.fact.value}".lower()
        if p in blob or has_word(blob, p):
            return True
    for ce in pack.chunks:
        low = ce.chunk.text.lower()
        if "/newsroom/" in ce.chunk.url.lower():
            title_line = low.split("\n", 1)[0]
            if p not in title_line and not has_word(low, p):
                continue
        if p in low or has_word(low, p):
            if TIME_TOKEN.search(ce.chunk.text) or has_any_word(
                low, ("hour", "hours", "open", "close", "lobby", "drive")
            ):
                return True
    return False


def _general_hours_snippet(pack: EvidencePack) -> str | None:
    for fe in pack.facts:
        if fe.fact.field.lower() == "hours" and fe.fact.value.strip():
            return fe.fact.value.strip()[:120]
    return None


def _adjust_branch_hours_answer(
    answer: Answer, question: str, pack: EvidencePack
) -> Answer:
    if not is_hours_question(question) or not answer.confident:
        return answer
    places = named_places(question)
    if len(places) != 1:
        return answer
    place = places[0]
    if not _place_in_corpus(place, _location_corpus(pack)):
        return answer
    if _branch_hours_for_place(place, pack):
        return answer
    if not TIME_TOKEN.search(answer.text):
        return answer
    msg = (
        f"The site does not list hours specifically for the {place.title()} branch."
    )
    gen = _general_hours_snippet(pack)
    if gen:
        msg += f" General hours on the site: {gen}"
    return Answer(text=msg, sources=answer.sources, confident=True)


def _unknown_place_in_question(question: str, pack: EvidencePack) -> bool:
    if not has_any_word(
        question,
        ("branch", "lobby", "hours", "address", "street", "avenue", "named"),
    ):
        return False
    places = named_places(question)
    if not places:
        return False
    corpus = _location_corpus(pack)
    return any(not _place_in_corpus(p, corpus) for p in places)


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
    """Refuse or rewrite answers whose numbers, times, or places are not in evidence."""
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

    answer = _adjust_branch_hours_answer(answer, question, pack)
    if answer.confident:
        return answer
    return sanitize_refusal(answer)


