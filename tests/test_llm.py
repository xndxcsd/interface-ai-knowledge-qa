import time

import pytest

from kb import llm as llm_mod
from kb.llm import llm_answer_from_evidence


class FakeCompletion:
    def __init__(self, content: str):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


class FakeCompletions:
    def __init__(self, delay: float = 0.0, content: str = '{"text":"ok","source_urls":[],"confident":true}'):
        self._delay = delay
        self._content = content

    def create(self, **kwargs):
        if self._delay:
            time.sleep(self._delay)
        return FakeCompletion(self._content)


class FakeOpenAI:
    def __init__(self, delay: float = 0.0, **kwargs):
        self.chat = type("Chat", (), {"completions": FakeCompletions(delay=delay)})()


def test_llm_json_roundtrip(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    llm_mod._openai_client = None
    monkeypatch.setattr(llm_mod, "_get_openai_client", lambda: FakeOpenAI())
    out = llm_answer_from_evidence("q", "evidence", None)
    assert out.get("confident") is True


def test_llm_wall_clock_times_out(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_WALL_S", "0.3")
    llm_mod._openai_client = None
    monkeypatch.setattr(llm_mod, "_get_openai_client", lambda: FakeOpenAI(delay=8.0))

    t0 = time.monotonic()
    with pytest.raises(TimeoutError):
        llm_answer_from_evidence("q", "evidence", None)
    assert time.monotonic() - t0 < 0.3 + 1.0
