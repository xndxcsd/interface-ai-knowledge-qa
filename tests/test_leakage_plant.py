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
    "lobby opens 8:30",
)


def _resolve_plant(plant: str, banned: set[str]) -> str | None:
    if plant in banned:
        return plant
    for tok in banned:
        if plant in tok or tok in plant:
            return plant if plant in tok else tok
    return None


@pytest.mark.parametrize("plant", _CANDIDATE_PLANTS)
def test_planted_token_fails_scanner(plant: str):
    banned = _banned_tokens()
    resolved = _resolve_plant(plant, banned)
    if resolved is None:
        pytest.skip(f"{plant!r} not covered by eval banned set on this kit")
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
    split = ("olden", "burg")
    if not any(tuple(sorted(g)) == split for g in groups):
        pytest.skip("olden/burg split group not derived from eval")
    src = 'if "olden" in q and "burg" in q:\n    pass\n'
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src)
        path = Path(f.name)
    violations = scan_path_for_literals(path, banned, groups, ngrams)
    assert violations
