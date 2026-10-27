"""Markdown cleanup and tokenization."""
from __future__ import annotations

import re

WORD = re.compile(r"[a-z0-9$%.]+", re.I)
IMG_LINK = re.compile(r"!\[[^\]]*\]\([^)]+\)")
LINK = re.compile(r"\[([^\]]*)\]\([^)]+\)")
HTML = re.compile(r"<[^>]+>")
MULTISPACE = re.compile(r"\s+")


def clean_markdown(md: str) -> str:
    text = md or ""
    text = IMG_LINK.sub(" ", text)
    text = LINK.sub(r"\1", text)
    text = HTML.sub(" ", text)
    text = text.replace("\\r\\n", "\n")
    text = MULTISPACE.sub(" ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    return WORD.findall(text.lower())


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
