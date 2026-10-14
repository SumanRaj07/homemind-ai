"""Conversation and message endpoints, including chat (streaming + single-shot)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from homemind.api.deps import DbDep, StateDep
from homemind.core import assistant
from homemind.core import conversations as conv_service
from homemind.models.schemas import (
    ChatRequest,
    ChatResponse,
    CitationOut,
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    MessageCreate,
    MessageOut,
)

router = APIRouter(tags=["conversations"])


def _conv_out(db: Session, conv) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        system_instructions=conv.system_instructions,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=conv_service.message_count(db, conv.id),
    )


def _msg_out(msg) -> MessageOut:
    return MessageOut(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        model=msg.model,
        created_at=msg.created_at,
    )


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(payload: ConversationCreate, state: StateDep, db: DbDep):
    conv = conv_service.create_conversation(
        db, title=payload.title, system_instructions=payload.system_instructions
    )
    return _conv_out(db, conv)


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(state: StateDep, db: DbDep):
    return [_conv_out(db, c) for c in conv_service.list_conversations(db)]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: str, state: StateDep, db: DbDep):
    try:
        conv = conv_service.get_conversation(db, conversation_id)
    except conv_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="conversation not found") from None
    return _conv_out(db, conv)


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: str, payload: ConversationUpdate, state: StateDep, db: DbDep
):
    try:
        if payload.title is not None:
            conv = conv_service.rename_conversation(db, conversation_id, payload.title)
        else:
            conv = conv_service.get_conversation(db, conversation_id)
        if payload.system_instructions is not None:
            conv = conv_service.set_system_instructions(
                db, conversation_id, payload.system_instructions
            )
    except conv_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="conversation not found") from None
    return _conv_out(db, conv)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, state: StateDep, db: DbDep):
    try:
        conv_service.delete_conversation(db, conversation_id)
    except conv_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="conversation not found") from None
    return None


@router.post("/conversations/{conversation_id}/clear", response_model=ConversationOut)
def clear_conversation(conversation_id: str, state: StateDep, db: DbDep):
    try:
        conv = conv_service.clear_conversation(db, conversation_id)
    except conv_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="conversation not found") from None
    return _conv_out(db, conv)


@router.get(
    "/conversations/{conversation_id}/messages", response_model=list[MessageOut]
)
def list_messages(
    conversation_id: str,
    state: StateDep,
    db: DbDep,
    limit: int = Query(default=200, ge=1, le=1000),
):
    try:
        msgs = conv_service.get_messages(db, conversation_id, limit=limit)
    except conv_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="conversation not found") from None
    return [_msg_out(m) for m in msgs]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=201,
)
def add_user_message(
    conversation_id: str, payload: MessageCreate, state: StateDep, db: DbDep
):
    """Store a user message without generating a reply (rarely needed; /chat
    both stores and answers)."""
    try:
        msg = conv_service.add_message(db, conversation_id, "user", payload.content)
    except conv_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="conversation not found") from None
    return _msg_out(msg)


@router.post("/conversations/{conversation_id}/chat")
def chat(conversation_id: str, payload: ChatRequest, state: StateDep, db: DbDep):
    """Chat turn. Set ``stream: true`` for Server-Sent Events streaming."""
    try:
        conv_service.get_conversation(db, conversation_id)
    except conv_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="conversation not found") from None

    if payload.stream:
        chunks, outcome = assistant.chat_stream(
            db,
            state.provider,
            conversation_id,
            payload.content,
            max_messages=state.settings.max_context_messages,
            use_knowledge=payload.use_knowledge,
            timeout_s=state.settings.request_timeout_s,
        )

        def _event_stream():
            try:
                for chunk in chunks:
                    yield f"data: {chunk}\n\n"
            except Exception as exc:  # ProviderError -> error event, then end
                safe = str(exc).replace("\n", " ")
                yield f"event: error\ndata: {safe}\n\n"
            yield "event: done\ndata: [DONE]\n\n"

        return StreamingResponse(_event_stream(), media_type="text/event-stream")

    try:
        outcome = assistant.chat(
            db,
            state.provider,
            conversation_id,
            payload.content,
            max_messages=state.settings.max_context_messages,
            use_knowledge=payload.use_knowledge,
            timeout_s=state.settings.request_timeout_s,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ChatResponse(
        message=_msg_out(outcome.assistant_message),
        citations=[CitationOut(**c) for c in outcome.citations],
        model=outcome.assistant_message.model,
    )
