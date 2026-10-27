from kb.llm import OpenAIChatClient


class FakeCompletion:
    def __init__(self, content: str):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


class FakeCompletions:
    def create(self, **kwargs):
        return FakeCompletion("I don't know.")


class FakeClient:
    def __init__(self, **kwargs):
        self.chat = type("Chat", (), {"completions": FakeCompletions()})()


def test_openai_client_complete(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    import kb.llm as llm_mod

    monkeypatch.setattr(
        llm_mod,
        "OpenAI",
        lambda **kw: FakeClient(),
        raising=False,
    )
    import openai

    monkeypatch.setattr(openai, "OpenAI", lambda **kw: FakeClient())
    client = OpenAIChatClient(model="gpt-4o-mini")
    out = client.complete("sys", "user")
    assert "don't know" in out.lower()
