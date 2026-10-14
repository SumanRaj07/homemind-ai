"""Memory endpoints: CRUD, search, export, clear-all (with confirmation)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from homemind.api.deps import DbDep, StateDep
from homemind.memory import service as memory_service
from homemind.models.schemas import MemoryCreate, MemoryOut, MemoryUpdate

router = APIRouter(tags=["memories"])


def _mem_out(mem) -> MemoryOut:
    return MemoryOut(
        id=mem.id,
        content=mem.content,
        category=mem.category,
        tags=mem.tags.split(",") if mem.tags else [],
        source=mem.source,
        created_at=mem.created_at,
        updated_at=mem.updated_at,
    )


@router.post("/memories", response_model=MemoryOut, status_code=201)
def create_memory(payload: MemoryCreate, state: StateDep, db: DbDep):
    mem = memory_service.create_memory(
        db,
        content=payload.content,
        category=payload.category,
        tags=payload.tags,
        source=payload.source,
    )
    return _mem_out(mem)


@router.get("/memories", response_model=list[MemoryOut])
def list_memories(
    state: StateDep,
    db: DbDep,
    category: str | None = Query(default=None),
    q: str | None = Query(default=None, description="search text"),
    limit: int = Query(default=200, ge=1, le=1000),
):
    if q:
        mems = memory_service.search_memories(db, q, limit=limit)
    else:
        mems = memory_service.list_memories(db, category=category, limit=limit)
    return [_mem_out(m) for m in mems]


@router.get("/memories/{memory_id}", response_model=MemoryOut)
def get_memory(memory_id: str, state: StateDep, db: DbDep):
    try:
        mem = memory_service.get_memory(db, memory_id)
    except memory_service.MemoryNotFound:
        raise HTTPException(status_code=404, detail="memory not found") from None
    return _mem_out(mem)


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
def update_memory(
    memory_id: str, payload: MemoryUpdate, state: StateDep, db: DbDep
):
    try:
        mem = memory_service.update_memory(
            db,
            memory_id,
            content=payload.content,
            category=payload.category,
            tags=payload.tags,
            source=payload.source,
        )
    except memory_service.MemoryNotFound:
        raise HTTPException(status_code=404, detail="memory not found") from None
    return _mem_out(mem)


@router.delete("/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: str, state: StateDep, db: DbDep):
    try:
        memory_service.delete_memory(db, memory_id)
    except memory_service.MemoryNotFound:
        raise HTTPException(status_code=404, detail="memory not found") from None
    return None


@router.delete("/memories", status_code=200)
def clear_memories(
    state: StateDep, db: DbDep, confirm: bool = Query(default=False)
):
    """Delete ALL memories. Requires ``?confirm=true`` as an explicit safeguard."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="refusing to clear memories without ?confirm=true",
        )
    count = memory_service.clear_memories(db)
    return {"deleted": count}
