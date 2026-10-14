"""Shared FastAPI dependencies and application state."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from sqlalchemy.orm import Session

from homemind.config.settings import Settings, get_settings
from homemind.providers.base import ModelProvider
from homemind.providers.mock import provider_for
from homemind.storage.database import Database
from homemind.tools.registry import ToolRegistry, build_default_registry


@dataclass
class AppState:
    settings: Settings
    db: Database
    provider: ModelProvider
    registry: ToolRegistry


def build_state(settings: Settings | None = None) -> AppState:
    settings = settings or get_settings()
    db = Database(settings.db_path)
    provider = provider_for(settings.model, settings.provider, settings.ollama_url)
    registry = build_default_registry(settings)
    return AppState(settings=settings, db=db, provider=provider, registry=registry)


def get_state(request: Request) -> AppState:
    return request.app.state.homemind  # type: ignore[no-any-return]


StateDep = Annotated[AppState, Depends(get_state)]


def get_db_session(state: StateDep) -> Iterator[Session]:
    with state.db.session() as session:
        yield session


DbDep = Annotated[Session, Depends(get_db_session)]


def attach_state(app: FastAPI, state: AppState) -> None:
    app.state.homemind = state
