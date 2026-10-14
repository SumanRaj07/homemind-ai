"""Built-in safe tools.

All built-ins are read-only. Each handler receives the database session, the
app settings and a validated input dict, and returns a JSON-serializable dict.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from homemind.config.settings import Settings
from homemind.knowledge import retrieval
from homemind.memory import service as memory_service


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}


def tool_knowledge_search(
    db: Session, settings: Settings, inputs: dict[str, Any]
) -> dict[str, Any]:
    query = str(inputs.get("query", "")).strip()
    if not query:
        return _err("query is required")
    limit = inputs.get("limit", 5)
    try:
        limit = max(1, min(10, int(limit)))
    except (TypeError, ValueError):
        return _err("limit must be an integer")
    passages = retrieval.search(db, query, limit=limit)
    return {
        "ok": True,
        "query": query,
        "passages": [
            {
                "document_id": p.document_id,
                "filename": p.filename,
                "page_number": p.page_number,
                "excerpt": p.text[:400],
            }
            for p in passages
        ],
    }


def tool_memory_get(
    db: Session, settings: Settings, inputs: dict[str, Any]
) -> dict[str, Any]:
    memory_id = str(inputs.get("memory_id", "")).strip()
    if not memory_id:
        return _err("memory_id is required")
    try:
        mem = memory_service.get_memory(db, memory_id)
    except memory_service.MemoryNotFound:
        return _err("memory not found")
    return {
        "ok": True,
        "memory": {
            "id": mem.id,
            "content": mem.content,
            "category": mem.category,
            "tags": mem.tags.split(",") if mem.tags else [],
            "source": mem.source,
        },
    }


def tool_summarize_text(
    db: Session, settings: Settings, inputs: dict[str, Any]
) -> dict[str, Any]:
    """Extractive summary: returns the first N sentences (no model needed)."""
    text = str(inputs.get("text", "")).strip()
    if not text:
        return _err("text is required")
    if len(text) > 20000:
        return _err("text is too long (max 20000 characters)")
    max_sentences = inputs.get("max_sentences", 3)
    try:
        max_sentences = max(1, min(10, int(max_sentences)))
    except (TypeError, ValueError):
        return _err("max_sentences must be an integer")
    import re

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    summary = " ".join(sentences[:max_sentences])
    return {"ok": True, "summary": summary, "sentences_used": min(len(sentences), max_sentences)}


def tool_workspace_list_files(
    db: Session, settings: Settings, inputs: dict[str, Any]
) -> dict[str, Any]:
    """List files inside the user-approved workspace directory only.

    Path traversal (``..``) and absolute paths are rejected; symlinks are not
    followed outside the workspace.
    """
    subpath = str(inputs.get("subpath", "")).strip() or "."
    base = settings.workspace_dir.resolve()
    target = (base / subpath).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return _err("access denied: path is outside the approved workspace")
    if not target.exists():
        return _err("path does not exist")
    if not target.is_dir():
        return _err("path is not a directory")
    entries = []
    for child in sorted(target.iterdir()):
        try:
            is_dir = child.is_dir()
        except OSError:
            continue
        entries.append(
            {
                "name": child.name,
                "type": "directory" if is_dir else "file",
                "size_bytes": 0 if is_dir else child.stat().st_size,
            }
        )
        if len(entries) >= 200:
            break
    rel = str(target.relative_to(base)) if target != base else "."
    return {"ok": True, "path": rel, "entries": entries}


BUILTIN_TOOLS: list[dict[str, Any]] = [
    {
        "name": "knowledge_search",
        "description": "Search the user's indexed documents and return cited passages.",
        "permission": "read",
        "input_schema": {
            "query": "text to search for (required)",
            "limit": "max passages to return, 1-10 (default 5)",
        },
        "handler": tool_knowledge_search,
    },
    {
        "name": "memory_get",
        "description": "Retrieve one saved memory by its id.",
        "permission": "read",
        "input_schema": {"memory_id": "memory id (required)"},
        "handler": tool_memory_get,
    },
    {
        "name": "summarize_text",
        "description": "Produce a short extractive summary of the given text (no model used).",
        "permission": "read",
        "input_schema": {
            "text": "text to summarize, max 20000 chars (required)",
            "max_sentences": "sentences to keep, 1-10 (default 3)",
        },
        "handler": tool_summarize_text,
    },
    {
        "name": "workspace_list_files",
        "description": "List files inside the user-approved workspace directory.",
        "permission": "read",
        "input_schema": {"subpath": "relative directory inside workspace (default '.')"},
        "handler": tool_workspace_list_files,
    },
]
