import time

import pytest

from kb.llm import OpenAIChatClient, llm_answer_from_evidence


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


class FakeClient:
    def __init__(self, delay: float = 0.0, **kwargs):
        self.chat = type("Chat", (), {"completions": FakeCompletions(delay=delay)})()


def test_openai_client_complete(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    import kb.llm as llm_mod
    import openai

    monkeypatch.setattr(openai, "OpenAI", lambda **kw: FakeClient())
    monkeypatch.setattr(llm_mod, "OpenAI", lambda **kw: FakeClient(), raising=False)
    client = OpenAIChatClient(model="gpt-4o-mini")
    out = client.complete("sys", "user")
    assert "ok" in out.lower() or "don't" in out.lower()


def test_llm_wall_clock_times_out(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_WALL_S", "0.3")

    import kb.llm as llm_mod
    import openai

    monkeypatch.setattr(openai, "OpenAI", lambda **kw: FakeClient(delay=2.0))
    monkeypatch.setattr(llm_mod, "OpenAI", lambda **kw: FakeClient(delay=2.0), raising=False)

    with pytest.raises(TimeoutError):
        llm_answer_from_evidence("q", "evidence", None)
