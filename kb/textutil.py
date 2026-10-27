"""Markdown cleanup and tokenization."""
from __future__ import annotations

import re

WORD = re.compile(r"[a-z0-9$%.]+", re.I)

QUERY_STOPWORDS = frozenset(
    {
        "what", "the", "is", "are", "do", "does", "a", "an", "for", "on", "to",
        "you", "your", "me", "tell", "can", "how", "when", "where", "dupaco",
        "s", "i", "and", "or", "of", "in", "at", "be", "any", "our", "their",
        "give", "provide", "much", "many", "could", "branch", "street", "address",
        "hours", "lobby", "drive", "main", "named", "rate", "rates", "loan", "loans",
        "account", "current", "right", "now",
    }
)
IMG_LINK = re.compile(r"!\[[^\]]*\]\([^)]+\)")
LINK = re.compile(r"\[([^\]]*)\]\([^)]+\)")
HTML = re.compile(r"<[^>]+>")
MULTISPACE = re.compile(r"\s+")
DATA_URI = re.compile(r"data:[^)\s\"']+", re.I)
SCRIPT_BLOCK = re.compile(r"<script[^>]*>.*?</script>", re.I | re.S)
STYLE_BLOCK = re.compile(r"<style[^>]*>.*?</style>", re.I | re.S)
SVG_BLOCK = re.compile(r"<svg[^>]*>.*?</svg>", re.I | re.S)


def strip_non_content(md: str) -> str:
    """Remove embedded assets and markup that pollute fact extraction."""
    text = md or ""
    text = SCRIPT_BLOCK.sub(" ", text)
    text = STYLE_BLOCK.sub(" ", text)
    text = SVG_BLOCK.sub(" ", text)
    text = DATA_URI.sub(" ", text)
    return text


def clean_markdown(md: str) -> str:
    text = strip_non_content(md)
    text = IMG_LINK.sub(" ", text)
    text = LINK.sub(r"\1", text)
    text = HTML.sub(" ", text)
    text = text.replace("\\r\\n", "\n")
    text = MULTISPACE.sub(" ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    return WORD.findall(text.lower())


def question_tokens(question: str) -> set[str]:
    toks = set(tokenize(question))
    return {t for t in toks if t not in QUERY_STOPWORDS and len(t) > 1}


def has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text, re.I) is not None


def has_any_word(text: str, words: tuple[str, ...] | list[str]) -> bool:
    return any(has_word(text, w) for w in words)


def url_path_segments(url: str) -> set[str]:
    """Whole path segments from a URL (split on /, -, _)."""
    from urllib.parse import urlparse

    raw = url if "://" in url else f"https://{url}"
    path = urlparse(raw).path.lower()
    segs: set[str] = set()
    for part in re.split(r"[/\-_]", path):
        if len(part) > 1:
            segs.add(part)
    return segs


def hint_matches_url(path_hint: str, url: str) -> bool:
    """True when every hint segment appears as a whole segment in the URL path."""
    hint_parts = [p for p in re.split(r"[/\-_]", path_hint.lower()) if len(p) > 1]
    if not hint_parts:
        return path_hint.lower() in url.lower()
    url_segs = url_path_segments(url)
    return all(p in url_segs for p in hint_parts)


def split_paragraphs(md: str) -> list[str]:
    parts = re.split(r"\n\s*\n", md or "")
    return [p.strip() for p in parts if p.strip()]


def split_chunks(md: str, max_chars: int = 900) -> list[str]:
    paras = split_paragraphs(md)
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for p in paras:
        if size + len(p) > max_chars and buf:
            chunks.append("\n\n".join(buf))
            buf, size = [], 0
        buf.append(p)
        size += len(p)
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks
