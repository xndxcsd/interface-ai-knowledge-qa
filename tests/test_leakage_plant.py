"""Planted eval strings must trip the real leakage scanner."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tests.test_no_eval_leakage import (
    _banned_tokens,
    _question_ngrams,
    _split_groups,
    scan_path_for_literals,
)

# Distinctive eval tokens the scanner must catch (subset verified at runtime).
_CANDIDATE_PLANTS = (
    "galena",
    "oldenburg",
    "hy-vee",
    "fifth",
    "mullan",
    "launchpad",
    "volunteer",
    "11375",
    "8:30",
    "join.dupaco.com",
)


def _resolve_plant(plant: str, banned: set[str]) -> str:
    assert plant in banned, f"{plant!r} not covered by eval banned set on this kit"
    return plant


@pytest.mark.parametrize("plant", _CANDIDATE_PLANTS)
def test_planted_token_fails_scanner(plant: str):
    banned = _banned_tokens()
    resolved = _resolve_plant(plant, banned)
    groups = _split_groups(banned)
    ngrams = _question_ngrams()
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(f'PLANT = "{resolved}"\n')
        path = Path(f.name)
    violations = scan_path_for_literals(path, banned, groups, ngrams)
    assert violations, f"scanner missed planted {resolved!r}"


def test_planted_split_oldenburg_fails_scanner():
    banned = _banned_tokens()
    groups = _split_groups(banned)
    ngrams = _question_ngrams()
    split = frozenset({"olden", "burg"})
    assert any(frozenset(g) == split for g in groups), "olden/burg split group not derived from eval"
    src = 'if "olden" in q and "burg" in q:\n    pass\n'
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src)
        path = Path(f.name)
    violations = scan_path_for_literals(path, banned, groups, ngrams)
    assert violations
