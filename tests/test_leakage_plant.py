"""Distinctive eval gold tokens must be in the leakage banned set."""
from __future__ import annotations

from tests.test_no_eval_leakage import _banned_from_eval


def test_distinctive_gold_tokens_are_banned():
    banned = _banned_from_eval()
    for tok in (
        "273974581",
        "800-373-7600",
        "11375 oldenburg",
        "8:30",
        "fifth",
        "join.dupaco.com",
        "11375",
    ):
        assert any(
            tok in b or b in tok for b in banned
        ), f"expected eval gold token {tok!r} in banned set"
