"""Model provider interface.

A provider turns a list of chat messages into a model response. Providers are
swappable: the conversation service only depends on this interface, so a new
local backend (llama.cpp, vLLM, ...) can be added without touching chat logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ProviderResult:
    text: str
    model: str
    metadata: dict = field(default_factory=dict)


class ProviderError(Exception):
    """Raised when the model backend cannot fulfil a request.

    The message is user-facing: it must explain what went wrong and how to
    fix it, without leaking internals.
    """


class ModelProvider(ABC):
    name: str = "base"

    @abstractmethod
    def check_availability(self) -> tuple[bool, str]:
        """Return (available, human-readable message). Never raises."""

    @abstractmethod
    def generate(
        self,
        messages: list[ChatMessage],
        *,
        timeout_s: float = 120.0,
    ) -> ProviderResult:
        """Generate a completion for the message list. May raise ProviderError."""

    def generate_stream(
        self,
        messages: list[ChatMessage],
        *,
        timeout_s: float = 120.0,
    ) -> Iterator[str]:
        """Yield response text chunks. Default impl: single chunk from generate()."""
        yield self.generate(messages, timeout_s=timeout_s).text
