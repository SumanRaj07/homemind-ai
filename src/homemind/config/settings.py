"""Application configuration.

All settings are read from environment variables (prefix ``HOMEMIND_``) at
instantiation time, so tests can override them with ``monkeypatch``. A small
JSON file in the data dir can provide defaults; environment variables win.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    """Runtime configuration for HomeMind AI."""

    data_dir: Path = field(default_factory=lambda: Path.home() / ".homemind")
    model: str = "llama3.2:3b"
    provider: str = "ollama"  # "ollama" | "mock"
    ollama_url: str = "http://127.0.0.1:11434"
    host: str = "127.0.0.1"
    port: int = 8000
    max_context_messages: int = 20
    max_upload_mb: int = 25
    request_timeout_s: float = 120.0
    model_connect_timeout_s: float = 5.0
    max_message_chars: int = 20000
    offline_mode: bool = False
    workspace_dir: Path = field(
        default_factory=lambda: Path.home() / ".homemind" / "workspace"
    )
    system_instructions: str = (
        "You are HomeMind AI, a helpful local personal assistant. "
        "Be concise and accurate. If you do not know something, say so."
    )

    def __post_init__(self) -> None:
        env = os.environ

        def _get(name: str, default: str) -> str:
            return env.get(f"HOMEMIND_{name}", default)

        self.data_dir = Path(_get("DATA_DIR", str(self.data_dir)))
        self.model = _get("MODEL", self.model)
        self.provider = _get("PROVIDER", self.provider)
        self.ollama_url = _get("OLLAMA_URL", self.ollama_url)
        self.host = _get("HOST", self.host)
        self.port = int(_get("PORT", str(self.port)))
        self.max_context_messages = int(
            _get("MAX_CONTEXT_MESSAGES", str(self.max_context_messages))
        )
        self.max_upload_mb = int(_get("MAX_UPLOAD_MB", str(self.max_upload_mb)))
        self.request_timeout_s = float(
            _get("REQUEST_TIMEOUT", str(self.request_timeout_s))
        )
        self.model_connect_timeout_s = float(
            _get("CONNECT_TIMEOUT", str(self.model_connect_timeout_s))
        )
        self.max_message_chars = int(
            _get("MAX_MESSAGE_CHARS", str(self.max_message_chars))
        )
        self.offline_mode = _get("OFFLINE_MODE", "false").lower() == "true"
        self.workspace_dir = Path(
            _get("WORKSPACE_DIR", str(self.data_dir / "workspace"))
        )
        self.system_instructions = _get("SYSTEM_INSTRUCTIONS", self.system_instructions)

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Optional JSON overrides (env vars still take precedence).
        cfg_file = self.data_dir / "config.json"
        if cfg_file.exists():
            try:
                overrides = json.loads(cfg_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                overrides = {}
            for key, value in overrides.items():
                if f"HOMEMIND_{key.upper()}" not in env and hasattr(self, key):
                    setattr(self, key, value)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "homemind.db"

    @property
    def documents_dir(self) -> Path:
        d = self.data_dir / "documents"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self) -> None:
        """Persist non-secret settings to config.json (env vars still win)."""
        payload = {
            "model": self.model,
            "provider": self.provider,
            "ollama_url": self.ollama_url,
            "max_context_messages": self.max_context_messages,
            "system_instructions": self.system_instructions,
        }
        (self.data_dir / "config.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )


def get_settings() -> Settings:
    return Settings()
