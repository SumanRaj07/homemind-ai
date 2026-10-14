"""Conversation service: CRUD, messages and context assembly.

Context rule: only messages from the requested conversation are ever loaded,
capped at ``max_messages`` most-recent messages. Conversations are strictly
isolated from each other.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homemind.providers.base import ChatMessage
from homemind.storage.models import Conversation, Message


class ConversationNotFound(Exception):
    pass


def create_conversation(
    db: Session, title: str = "New conversation", system_instructions: str = ""
) -> Conversation:
    conv = Conversation(title=title[:200], system_instructions=system_instructions)
    db.add(conv)
    db.flush()
    return conv


def list_conversations(db: Session) -> list[Conversation]:
    stmt = select(Conversation).order_by(Conversation.updated_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_conversation(db: Session, conversation_id: str) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise ConversationNotFound(conversation_id)
    return conv


def rename_conversation(db: Session, conversation_id: str, title: str) -> Conversation:
    conv = get_conversation(db, conversation_id)
    conv.title = title[:200]
    db.flush()
    return conv


def set_system_instructions(
    db: Session, conversation_id: str, instructions: str
) -> Conversation:
    conv = get_conversation(db, conversation_id)
    conv.system_instructions = instructions[:8000]
    db.flush()
    return conv


def delete_conversation(db: Session, conversation_id: str) -> None:
    conv = get_conversation(db, conversation_id)
    db.delete(conv)
    db.flush()


def clear_conversation(db: Session, conversation_id: str) -> Conversation:
    conv = get_conversation(db, conversation_id)
    for msg in list(conv.messages):
        db.delete(msg)
    db.flush()
    return conv


def message_count(db: Session, conversation_id: str) -> int:
    stmt = select(func.count()).select_from(Message).where(
        Message.conversation_id == conversation_id
    )
    return int(db.execute(stmt).scalar() or 0)


def add_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    model: str = "",
) -> Message:
    get_conversation(db, conversation_id)  # validates existence
    if role not in ("user", "assistant", "system"):
        raise ValueError(f"invalid role: {role}")
    msg = Message(
        conversation_id=conversation_id, role=role, content=content, model=model
    )
    db.add(msg)
    db.flush()  # lets updated_at triggers/orderings settle
    return msg


def get_messages(
    db: Session, conversation_id: str, limit: int = 200
) -> list[Message]:
    get_conversation(db, conversation_id)
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def build_context(
    db: Session,
    conversation_id: str,
    *,
    max_messages: int = 20,
    extra_system: str = "",
) -> list[ChatMessage]:
    """Assemble the prompt context for one conversation.

    Order: system instructions (+ optional extra system text), then the most
    recent ``max_messages`` messages of *this* conversation only.
    """
    conv = get_conversation(db, conversation_id)
    system_text = conv.system_instructions.strip() or "You are a helpful assistant."
    if extra_system.strip():
        system_text = f"{system_text}\n\n{extra_system.strip()}"
    messages = [ChatMessage(role="system", content=system_text)]

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(max_messages)
    )
    recent = list(db.execute(stmt).scalars().all())
    for msg in reversed(recent):
        messages.append(ChatMessage(role=msg.role, content=msg.content))
    return messages
