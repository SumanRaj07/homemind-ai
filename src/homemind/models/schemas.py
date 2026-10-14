"""Pydantic request/response schemas for the HomeMind AI API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# --------------------------------------------------------------------------- #
# Health / status
# --------------------------------------------------------------------------- #
class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class StatusResponse(BaseModel):
    provider: str
    model: str
    model_available: bool
    model_message: str
    offline_mode: bool
    db_path: str
    conversations: int
    memories: int
    documents: int


# --------------------------------------------------------------------------- #
# Conversations & messages
# --------------------------------------------------------------------------- #
class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", max_length=200)
    system_instructions: str = Field(default="", max_length=8000)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    system_instructions: str | None = Field(default=None, max_length=8000)


class ConversationOut(BaseModel):
    id: str
    title: str
    system_instructions: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    role: Literal["user"] = "user"

    @field_validator("content")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content must not be blank")
        return v


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    model: str
    created_at: datetime


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    use_knowledge: bool = False
    stream: bool = False

    @field_validator("content")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content must not be blank")
        return v


class CitationOut(BaseModel):
    document_id: str
    filename: str
    page_number: int | None
    excerpt: str


class ChatResponse(BaseModel):
    message: MessageOut
    citations: list[CitationOut] = Field(default_factory=list)
    model: str


# --------------------------------------------------------------------------- #
# Memories
# --------------------------------------------------------------------------- #
class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    category: str = Field(default="general", max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=20)
    source: str = Field(default="", max_length=200)


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    category: str | None = Field(default=None, max_length=80)
    tags: list[str] | None = Field(default=None, max_length=20)
    source: str | None = Field(default=None, max_length=200)


class MemoryOut(BaseModel):
    id: str
    content: str
    category: str
    tags: list[str]
    source: str
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Knowledge base
# --------------------------------------------------------------------------- #
class DocumentOut(BaseModel):
    id: str
    filename: str
    size_bytes: int
    mime: str
    page_count: int
    char_count: int
    chunk_count: int
    created_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class PassageOut(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: int | None
    text: str
    score: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    passages: list[PassageOut]


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
class ToolInfo(BaseModel):
    name: str
    description: str
    permission: Literal["read", "write"]
    input_schema: dict[str, Any]


class ToolExecuteRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    approval_id: str | None = None


class ToolExecuteResponse(BaseModel):
    status: Literal["executed", "approval_required", "denied"]
    approval_id: str | None = None
    result: dict[str, Any] | None = None
    message: str = ""


class ApprovalResolveRequest(BaseModel):
    approve: bool


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
class ExportResponse(BaseModel):
    exported_at: datetime
    conversations: list[dict[str, Any]]
    memories: list[dict[str, Any]]
    documents: list[dict[str, Any]]
