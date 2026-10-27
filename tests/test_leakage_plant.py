"""Sanity-check that the leakage scanner catches planted eval strings."""
from __future__ import annotations

import tempfile
from pathlib import Path

from tests.test_no_eval_leakage import _banned_tokens, _literals, _split_groups


def test_planted_eval_token_detected():
    banned = _banned_tokens()
    split_groups = _split_groups(banned)
    assert split_groups or banned
    plant = next(iter(banned), "join.dupaco.com")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(f'X = "{plant}"\n')
        path = Path(f.name)
    assert plant.lower() in _literals(path)
