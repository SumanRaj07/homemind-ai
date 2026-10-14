"""Unit tests: providers — mock behavior and Ollama failure handling."""

from homemind.providers.base import ChatMessage, ProviderError
from homemind.providers.mock import MockProvider, provider_for
from homemind.providers.ollama import OllamaProvider


def test_mock_generate():
    p = MockProvider()
    ok, msg = p.check_availability()
    assert ok
    res = p.generate([ChatMessage(role="user", content="hello there")])
    assert "hello there" in res.text


def test_mock_stream_chunks():
    p = MockProvider()
    chunks = list(p.generate_stream([ChatMessage(role="user", content="hi")]))
    assert len(chunks) > 1
    assert "".join(chunks) == p.generate(
        [ChatMessage(role="user", content="hi")]).text


def test_provider_factory():
    assert provider_for("m", "mock", "http://x").name == "mock"
    assert provider_for("m", "ollama", "http://127.0.0.1:9").name == "ollama"


def test_ollama_unavailable_gives_helpful_message():
    p = OllamaProvider(model="llama3.2:3b", base_url="http://127.0.0.1:9")
    ok, msg = p.check_availability()
    assert ok is False
    assert "ollama serve" in msg


def test_ollama_generate_raises_provider_error():
    p = OllamaProvider(model="llama3.2:3b", base_url="http://127.0.0.1:9")
    try:
        p.generate([ChatMessage(role="user", content="hi")], timeout_s=2)
    except ProviderError as exc:
        assert "Ollama" in str(exc)
    else:
        raise AssertionError("expected ProviderError")
