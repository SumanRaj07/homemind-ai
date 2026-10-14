"""Mock provider for tests, CI and offline UI demos.

Never contacts the network. Produces deterministic, clearly-labelled answers so
tests stay hermetic and the UI can be exercised without a model download.
"""

from __future__ import annotations

from collections.abc import Iterator

from homemind.providers.base import ChatMessage, ModelProvider, ProviderResult


class MockProvider(ModelProvider):
    name = "mock"

    def __init__(self, model: str = "mock-model") -> None:
        self.model = model

    def check_availability(self) -> tuple[bool, str]:
        return True, "Mock provider is always available (test mode)."

    def _answer(self, messages: list[ChatMessage]) -> str:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "(no user message)",
        )
        return (
            f"[mock-model reply] I received your message: {last_user!r}. "
            "This is a deterministic test response."
        )

    def generate(
        self, messages: list[ChatMessage], *, timeout_s: float = 120.0
    ) -> ProviderResult:
        return ProviderResult(text=self._answer(messages), model=self.model)

    def generate_stream(
        self, messages: list[ChatMessage], *, timeout_s: float = 120.0
    ) -> Iterator[str]:
        text = self._answer(messages)
        # Yield in a few chunks to exercise streaming code paths.
        chunk_size = max(1, len(text) // 4)
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]


def provider_for(settings_model: str, provider_name: str, ollama_url: str) -> ModelProvider:
    """Factory used by the API layer."""
    from homemind.providers.ollama import OllamaProvider  # local import: no cycle

    if provider_name == "mock":
        return MockProvider(model=settings_model)
    return OllamaProvider(model=settings_model, base_url=ollama_url)
