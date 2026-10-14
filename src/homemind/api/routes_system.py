"""System endpoints: health, status, export, data deletion."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select

from homemind import __version__
from homemind.api.deps import DbDep, StateDep
from homemind.core import conversations as conv_service
from homemind.knowledge import ingestion as knowledge_ingestion
from homemind.memory import service as memory_service
from homemind.models.schemas import ExportResponse, HealthResponse, StatusResponse
from homemind.storage.models import Conversation, Document, Memory

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get("/status", response_model=StatusResponse)
def status(state: StateDep, db: DbDep) -> StatusResponse:
    available, message = state.provider.check_availability()
    conv_count = db.execute(select(func.count()).select_from(Conversation)).scalar() or 0
    mem_count = db.execute(select(func.count()).select_from(Memory)).scalar() or 0
    doc_count = db.execute(select(func.count()).select_from(Document)).scalar() or 0
    return StatusResponse(
        provider=state.provider.name,
        model=state.settings.model,
        model_available=available,
        model_message=message,
        offline_mode=state.settings.offline_mode,
        db_path=str(state.settings.db_path),
        conversations=int(conv_count),
        memories=int(mem_count),
        documents=int(doc_count),
    )


@router.get("/export", response_model=ExportResponse)
def export_data(state: StateDep, db: DbDep) -> ExportResponse:
    convs = []
    for conv in conv_service.list_conversations(db):
        msgs = conv_service.get_messages(db, conv.id, limit=100000)
        convs.append(
            {
                "id": conv.id,
                "title": conv.title,
                "system_instructions": conv.system_instructions,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "model": m.model,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in msgs
                ],
            }
        )
    mems = [
        {
            "id": m.id,
            "content": m.content,
            "category": m.category,
            "tags": m.tags,
            "source": m.source,
            "created_at": m.created_at.isoformat(),
            "updated_at": m.updated_at.isoformat(),
        }
        for m in memory_service.list_memories(db, limit=100000)
    ]
    docs = [
        {
            "id": d.id,
            "filename": d.filename,
            "size_bytes": d.size_bytes,
            "page_count": d.page_count,
            "created_at": d.created_at.isoformat(),
        }
        for d in db.execute(select(Document).order_by(Document.created_at)).scalars().all()
    ]
    return ExportResponse(
        exported_at=datetime.now(UTC),
        conversations=convs,
        memories=mems,
        documents=docs,
    )


@router.delete("/data/conversations")
def delete_all_conversations(state: StateDep, db: DbDep) -> dict:
    convs = conv_service.list_conversations(db)
    for conv in convs:
        conv_service.delete_conversation(db, conv.id)
    return {"deleted": len(convs)}


@router.delete("/data/memories")
def delete_all_memories(state: StateDep, db: DbDep) -> dict:
    count = memory_service.clear_memories(db)
    return {"deleted": count}


@router.post("/knowledge/rebuild")
def rebuild_index(state: StateDep, db: DbDep) -> dict:
    count = knowledge_ingestion.rebuild_index(db)
    return {"indexed_chunks": count}
