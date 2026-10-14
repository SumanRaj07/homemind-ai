"""Assistant orchestration: turns a user message into a model reply.

Pipeline:
  1. Persist the user message.
  2. Optionally retrieve knowledge-base evidence (with citations).
  3. Collect relevant user-approved memories.
  4. Assemble context (system instructions + memories + evidence + history).
  5. Call the model provider (streaming or single-shot).
  6. Persist the assistant message.

Deleted memories are never injected: relevance is computed from a live database
query at chat time. Document passages are wrapped as explicitly untrusted data.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from homemind.core import conversations
from homemind.knowledge import retrieval
from homemind.memory import service as memory_service
from homemind.providers.base import ChatMessage, ModelProvider, ProviderResult
from homemind.storage.models import Message

NO_EVIDENCE_REPLY = (
    "I searched your knowledge base but couldn't find any relevant information "
    "to answer that. Try importing a document that covers this topic, or ask "
    "me something else."
)


@dataclass
class ChatOutcome:
    user_message: Message
    assistant_message: Message
    citations: list[dict] = field(default_factory=list)
    memories_used: list[str] = field(default_factory=list)


def _memory_block(db: Session, query: str) -> tuple[str, list[str]]:
    relevant = memory_service.relevant_memories(db, query, limit=5)
    if not relevant:
        return "", []
    lines = ["User-approved stored facts (use when relevant):"]
    for mem in relevant:
        lines.append(f"- [{mem.category}] {mem.content}")
    return "\n".join(lines), [m.id for m in relevant]


def _knowledge_block(
    db: Session, query: str, use_knowledge: bool
) -> tuple[str, list[dict], bool]:
    """Returns (evidence_text, citations, found_anything)."""
    if not use_knowledge:
        return "", [], True
    passages = retrieval.search(db, query, limit=5)
    if not passages:
        return "", [], False
    citations = [
        {
            "document_id": p.document_id,
            "filename": p.filename,
            "page_number": p.page_number,
            "excerpt": p.text[:300],
        }
        for p in passages
    ]
    return retrieval.format_evidence(passages), citations, True


def _build_prompt_messages(
    db: Session,
    conversation_id: str,
    user_text: str,
    *,
    max_messages: int,
    use_knowledge: bool,
) -> tuple[list[ChatMessage], list[str], list[dict], bool]:
    memory_text, memory_ids = _memory_block(db, user_text)
    evidence_text, citations, found = _knowledge_block(db, user_text, use_knowledge)

    extra_parts = []
    if memory_text:
        extra_parts.append(memory_text)
    if evidence_text:
        extra_parts.append(evidence_text)
    extra_system = "\n\n".join(extra_parts)

    messages = conversations.build_context(
        db, conversation_id, max_messages=max_messages, extra_system=extra_system
    )
    messages.append(ChatMessage(role="user", content=user_text))
    return messages, memory_ids, citations, found


def chat(
    db: Session,
    provider: ModelProvider,
    conversation_id: str,
    user_text: str,
    *,
    max_messages: int = 20,
    use_knowledge: bool = False,
    timeout_s: float = 120.0,
) -> ChatOutcome:
    """Single-shot chat turn. Raises ProviderError / ConversationNotFound."""
    user_msg = conversations.add_message(
        db, conversation_id, "user", user_text, model=provider.name
    )

    messages, memory_ids, citations, found = _build_prompt_messages(
        db, conversation_id, user_text,
        max_messages=max_messages, use_knowledge=use_knowledge,
    )
    if not found:
        assistant_msg = conversations.add_message(
            db, conversation_id, "assistant", NO_EVIDENCE_REPLY, model=provider.name
        )
        return ChatOutcome(user_msg, assistant_msg, [], memory_ids)

    result: ProviderResult = provider.generate(messages, timeout_s=timeout_s)
    assistant_msg = conversations.add_message(
        db, conversation_id, "assistant", result.text, model=result.model
    )
    return ChatOutcome(user_msg, assistant_msg, citations, memory_ids)


def chat_stream(
    db: Session,
    provider: ModelProvider,
    conversation_id: str,
    user_text: str,
    *,
    max_messages: int = 20,
    use_knowledge: bool = False,
    timeout_s: float = 120.0,
) -> tuple[Iterator[str], ChatOutcome]:
    """Streaming chat turn.

    Returns (chunk_iterator, outcome). The outcome's assistant message is
    created up-front and updated as chunks arrive; iterate the chunks to drive
    generation, then read ``outcome`` for the persisted result.
    """
    user_msg = conversations.add_message(
        db, conversation_id, "user", user_text, model=provider.name
    )
    messages, memory_ids, citations, found = _build_prompt_messages(
        db, conversation_id, user_text,
        max_messages=max_messages, use_knowledge=use_knowledge,
    )
    assistant_msg = conversations.add_message(
        db, conversation_id, "assistant", "", model=provider.name
    )
    outcome = ChatOutcome(user_msg, assistant_msg, citations, memory_ids)

    if not found:
        assistant_msg.content = NO_EVIDENCE_REPLY

        def _no_evidence() -> Iterator[str]:
            yield NO_EVIDENCE_REPLY

        return _no_evidence(), outcome

    def _generate() -> Iterator[str]:
        parts: list[str] = []
        for chunk in provider.generate_stream(messages, timeout_s=timeout_s):
            parts.append(chunk)
            yield chunk
        assistant_msg.content = "".join(parts)
        db.flush()

    return _generate(), outcome
