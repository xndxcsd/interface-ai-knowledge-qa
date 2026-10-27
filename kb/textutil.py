"""Markdown cleanup and tokenization."""
from __future__ import annotations

import re

WORD = re.compile(r"[a-z0-9$%.]+", re.I)
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


def has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text, re.I) is not None


def has_any_word(text: str, words: tuple[str, ...] | list[str]) -> bool:
    return any(has_word(text, w) for w in words)


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
