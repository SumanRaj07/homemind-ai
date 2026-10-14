"""Database engine, session handling and versioned schema migrations.

Migration history:
  v1 — core tables: schema_version, conversations, messages, memories,
       documents, document_chunks, settings.
  v2 — full-text search: ``document_fts`` virtual table (FTS5).
  v3 — tool audit log: ``tool_audit`` table.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from homemind.storage.models import Base

SCHEMA_VERSION = 3

#: Set to False when the SQLite build has no FTS5; retrieval falls back to LIKE.
FTS5_AVAILABLE = True


def _is_fts5_available(engine: Engine) -> bool:
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)"))
            conn.execute(text("DROP TABLE _fts5_probe"))
            return True
        except Exception:  # pragma: no cover - depends on sqlite build
            return False


def _migration_v1(engine: Engine) -> None:
    """Create the core tables."""
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables["schema_version"],
        Base.metadata.tables["conversations"],
        Base.metadata.tables["messages"],
        Base.metadata.tables["memories"],
        Base.metadata.tables["documents"],
        Base.metadata.tables["document_chunks"],
        Base.metadata.tables["settings"],
    ])


def _migration_v2(engine: Engine) -> None:
    """Create the FTS5 full-text index for document chunks."""
    global FTS5_AVAILABLE
    if not _is_fts5_available(engine):
        FTS5_AVAILABLE = False
        return
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5("
            "chunk_id UNINDEXED, document_id UNINDEXED, page_number UNINDEXED, text, "
            "tokenize='porter')"
        ))


def _migration_v3(engine: Engine) -> None:
    """Create the tool audit log table."""
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["tool_audit"]])


_MIGRATIONS = {
    1: _migration_v1,
    2: _migration_v2,
    3: _migration_v3,
}


def _current_version(engine: Engine) -> int:
    with engine.connect() as conn:
        exists = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )).first()
        if not exists:
            return 0
        row = conn.execute(text("SELECT MAX(version) FROM schema_version")).first()
        return int(row[0]) if row and row[0] is not None else 0


def migrate(engine: Engine) -> int:
    """Apply all pending migrations. Returns the resulting schema version."""
    current = _current_version(engine)
    for version in range(current + 1, SCHEMA_VERSION + 1):
        _MIGRATIONS[version](engine)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO schema_version (version, applied_at) VALUES (:v, :t)"),
                {"v": version, "t": datetime.now(UTC).isoformat()},
            )
    return SCHEMA_VERSION


class Database:
    """Thin wrapper around the SQLAlchemy engine for the app."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.engine: Engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 30.0},
        )
        # Browser and desktop may use the database from two processes at the
        # same time: WAL allows readers during writes, and the busy timeout
        # makes writers wait instead of failing immediately.
        with self.engine.begin() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=30000"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
        migrate(self.engine)
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def backup_to(self, dest: Path) -> Path:
        """Create a file-level backup of the SQLite database."""
        import shutil

        dest.parent.mkdir(parents=True, exist_ok=True)
        # Checkpoint first so the backup is consistent.
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        shutil.copy2(self.db_path, dest)
        return dest
