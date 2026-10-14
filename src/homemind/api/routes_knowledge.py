"""Knowledge-base endpoints: document upload/list/delete and passage search."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select

from homemind.api.deps import DbDep, StateDep
from homemind.knowledge import ingestion, retrieval
from homemind.models.schemas import (
    DocumentOut,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    PassageOut,
)
from homemind.storage.models import Document

router = APIRouter(tags=["knowledge"])


def _doc_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        size_bytes=doc.size_bytes,
        mime=doc.mime,
        page_count=doc.page_count,
        char_count=doc.char_count,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
    )


@router.post("/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    state: StateDep, db: DbDep, file: Annotated[UploadFile, File(...)]
):
    data = await file.read()
    try:
        doc = ingestion.ingest_document(
            db,
            state.settings.documents_dir,
            filename=file.filename or "document",
            data=data,
            max_mb=state.settings.max_upload_mb,
        )
    except ingestion.DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _doc_out(doc)


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(state: StateDep, db: DbDep):
    docs = db.execute(select(Document).order_by(Document.created_at.desc()))
    return [_doc_out(d) for d in docs.scalars().all()]


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, state: StateDep, db: DbDep):
    try:
        ingestion.remove_document(db, state.settings.documents_dir, document_id)
    except ingestion.DocumentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return None


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
def knowledge_search(
    payload: KnowledgeSearchRequest, state: StateDep, db: DbDep
):
    passages = retrieval.search(db, payload.query, limit=payload.limit)
    return KnowledgeSearchResponse(
        query=payload.query,
        passages=[
            PassageOut(
                chunk_id=p.chunk_id,
                document_id=p.document_id,
                filename=p.filename,
                page_number=p.page_number,
                text=p.text,
                score=p.score,
            )
            for p in passages
        ],
    )
