"""Ollama chat provider (default local inference backend)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

from homemind.providers.base import ChatMessage, ModelProvider, ProviderError, ProviderResult


class OllamaProvider(ModelProvider):
    """Talks to a local Ollama server over HTTP (loopback only by default)."""

    name = "ollama"

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        connect_timeout_s: float = 5.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.connect_timeout_s = connect_timeout_s

    # -- availability ----------------------------------------------------- #
    def check_availability(self) -> tuple[bool, str]:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=self.connect_timeout_s,
                trust_env=False)
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            return False, (
                f"Cannot reach Ollama at {self.base_url}. "
                "Make sure Ollama is installed and running (`ollama serve`), "
                "then pull a model, e.g. `ollama pull llama3.2:3b`."
            )
        if resp.status_code != 200:
            return False, f"Ollama returned HTTP {resp.status_code}."
        try:
            models = [m.get("name", "") for m in resp.json().get("models", [])]
        except (ValueError, AttributeError):
            return True, "Ollama is reachable but the model list could not be parsed."
        if self.model not in models:
            return False, (
                f"Model '{self.model}' is not installed in Ollama. "
                f"Install it with: ollama pull {self.model}"
            )
        return True, f"Ollama is running and model '{self.model}' is available."

    # -- generation -------------------------------------------------------- #
    def _payload(self, messages: list[ChatMessage], stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
        }

    def _wrap_error(self, exc: Exception) -> ProviderError:
        if isinstance(exc, httpx.TimeoutException):
            return ProviderError(
                "The model took too long to respond (timeout). Try a smaller model "
                "or a shorter prompt, then try again."
            )
        if isinstance(exc, httpx.ConnectError | httpx.NetworkError | OSError):
            return ProviderError(
                f"Lost connection to Ollama at {self.base_url}. "
                "Restart it with `ollama serve` and try again."
            )
        return ProviderError(f"Ollama model request failed: {exc}")

    def generate(
        self, messages: list[ChatMessage], *, timeout_s: float = 120.0
    ) -> ProviderResult:
        try:
            resp = httpx.post(
                f"{self.base_url}/api/chat",
                json=self._payload(messages, stream=False),
                timeout=timeout_s,
                trust_env=False,
            )
            resp.raise_for_status()
            data = resp.json()
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - wrapped into ProviderError
            raise self._wrap_error(exc) from exc
        text = (data.get("message") or {}).get("content", "")
        return ProviderResult(text=text, model=self.model, metadata={"raw": data})

    def generate_stream(
        self, messages: list[ChatMessage], *, timeout_s: float = 120.0
    ) -> Iterator[str]:
        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=self._payload(messages, stream=True),
                timeout=timeout_s,
                trust_env=False,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except ValueError:
                        continue
                    delta = (chunk.get("message") or {}).get("content", "")
                    if delta:
                        yield delta
                    if chunk.get("done"):
                        break
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - wrapped into ProviderError
            raise self._wrap_error(exc) from exc
