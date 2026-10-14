"""User-controlled persistent memory.

Memories are explicit: the application never silently stores conversation
content as a permanent memory. Only memories present in the database at query
time can be injected into a prompt, so deleting a memory immediately removes it
from future context.
"""

from __future__ import annotations

import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from homemind.storage.models import Memory

_WS = re.compile(r"\s+")


class MemoryNotFound(Exception):
    pass


def _norm_tags(tags: list[str]) -> str:
    cleaned = []
    for t in tags:
        t = _WS.sub(" ", t.strip().lower())[:40]
        if t and t not in cleaned:
            cleaned.append(t)
    return ",".join(cleaned[:20])


def create_memory(
    db: Session,
    content: str,
    category: str = "general",
    tags: list[str] | None = None,
    source: str = "",
) -> Memory:
    mem = Memory(
        content=content.strip(),
        category=(category.strip() or "general")[:80].lower(),
        tags=_norm_tags(tags or []),
        source=source.strip()[:200],
    )
    db.add(mem)
    db.flush()
    return mem


def list_memories(
    db: Session, category: str | None = None, limit: int = 200
) -> list[Memory]:
    stmt = select(Memory).order_by(Memory.updated_at.desc()).limit(limit)
    if category:
        stmt = stmt.where(Memory.category == category.strip().lower())
    return list(db.execute(stmt).scalars().all())


def get_memory(db: Session, memory_id: str) -> Memory:
    mem = db.get(Memory, memory_id)
    if mem is None:
        raise MemoryNotFound(memory_id)
    return mem


def search_memories(db: Session, query: str, limit: int = 20) -> list[Memory]:
    """Case-insensitive substring search over content, category and tags."""
    q = f"%{query.strip().lower()}%"
    stmt = (
        select(Memory)
        .where(
            or_(
                Memory.content.ilike(q),
                Memory.category.ilike(q),
                Memory.tags.ilike(q),
            )
        )
        .order_by(Memory.updated_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def update_memory(
    db: Session,
    memory_id: str,
    *,
    content: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    source: str | None = None,
) -> Memory:
    mem = get_memory(db, memory_id)
    if content is not None:
        mem.content = content.strip()
    if category is not None:
        mem.category = (category.strip() or "general")[:80].lower()
    if tags is not None:
        mem.tags = _norm_tags(tags)
    if source is not None:
        mem.source = source.strip()[:200]
    db.flush()
    return mem


def delete_memory(db: Session, memory_id: str) -> None:
    mem = get_memory(db, memory_id)
    db.delete(mem)
    db.flush()


def clear_memories(db: Session) -> int:
    """Delete every memory. Returns the number removed."""
    stmt = select(Memory)
    memories = list(db.execute(stmt).scalars().all())
    for mem in memories:
        db.delete(mem)
    db.flush()
    return len(memories)


def relevant_memories(db: Session, query: str, limit: int = 5) -> list[Memory]:
    """Heuristic relevance: memories sharing content tokens with the query.

    Only used to *suggest* context; the user can always inspect what was
    injected because the API returns which memories were used.
    """
    tokens = set(re.findall(r"[a-z0-9]{3,}", query.lower()))
    if not tokens:
        return []
    scored: list[tuple[int, Memory]] = []
    for mem in list_memories(db, limit=500):
        mem_tokens = set(re.findall(r"[a-z0-9]{3,}", mem.content.lower()))
        overlap = len(tokens & mem_tokens)
        if overlap:
            scored.append((overlap, mem))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [mem for _, mem in scored[:limit]]
