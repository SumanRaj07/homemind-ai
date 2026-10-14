"""Shared pytest fixtures: isolated temp data dir, mock provider, test client."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def settings(tmp_path, monkeypatch):
    data_dir = tmp_path / "homemind-data"
    monkeypatch.setenv("HOMEMIND_DATA_DIR", str(data_dir))
    monkeypatch.setenv("HOMEMIND_PROVIDER", "mock")
    monkeypatch.setenv("HOMEMIND_MODEL", "mock-model")
    monkeypatch.setenv("HOMEMIND_OLLAMA_URL", "http://127.0.0.1:9")  # unused port

    from homemind.config.settings import Settings

    return Settings()


@pytest.fixture
def db(settings):
    from homemind.storage.database import Database

    return Database(settings.db_path)


@pytest.fixture
def dbsession(db):
    with db.session() as session:
        yield session


@pytest.fixture
def client(settings):
    from homemind.api.app import create_app

    app = create_app(settings)
    with TestClient(app) as c:
        yield c
