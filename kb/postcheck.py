"""Post-check: grounding and authority (no eval-specific rules)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from kb.evidence import EvidencePack
from kb.grounding import apply_grounding

if TYPE_CHECKING:
    from contract import Answer


def postcheck_answer(answer: "Answer", pack: EvidencePack, question: str) -> "Answer":
    return apply_grounding(answer, pack, question)
