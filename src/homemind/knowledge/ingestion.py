"""Document ingestion: validation, text extraction, chunking and FTS indexing.

Supported formats: PDF (via PyMuPDF) and plain text. Every chunk keeps its
source document id, filename and page number so answers can cite them.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import fitz  # PyMuPDF
from sqlalchemy import text
from sqlalchemy.orm import Session

from homemind.storage import database as db_module
from homemind.storage.models import Document, DocumentChunk

ALLOWED_SUFFIXES = {".pdf", ".txt"}
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120


class DocumentError(Exception):
    """User-facing error for invalid or unreadable documents."""


def _safe_filename(name: str) -> str:
    """Strip path components and unsafe characters from an upload filename."""
    base = Path(name).name.strip()
    safe = "".join(c for c in base if c.isalnum() or c in ("-", "_", ".", " "))
    safe = safe.strip(" .")
    return safe[:200] or "document"


def validate_upload(filename: str, size_bytes: int, max_mb: int) -> str:
    """Validate an upload; returns the sanitized filename."""
    safe = _safe_filename(filename)
    suffix = Path(safe).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise DocumentError(
            f"Unsupported file type {suffix or '(none)'!r}. "
            f"Only {sorted(ALLOWED_SUFFIXES)} are accepted."
        )
    if size_bytes <= 0:
        raise DocumentError("The file is empty.")
    if size_bytes > max_mb * 1024 * 1024:
        raise DocumentError(
            f"File is too large ({size_bytes / 1024 / 1024:.1f} MB). "
            f"Maximum allowed is {max_mb} MB."
        )
    return safe


def extract_text(path: Path) -> list[tuple[int | None, str]]:
    """Return a list of (page_number, text) tuples. page_number is None for txt."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            doc = fitz.open(path)
        except Exception as exc:
            raise DocumentError(f"Could not read PDF: {exc}") from exc
        pages: list[tuple[int | None, str]] = []
        try:
            for i, page in enumerate(doc, start=1):
                pages.append((i, page.get_text("text") or ""))
        finally:
            doc.close()
        return pages
    if suffix == ".txt":
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise DocumentError(f"Could not read file: {exc}") from exc
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                return [(None, raw.decode(encoding))]
            except (UnicodeDecodeError, ValueError):
                continue
        raise DocumentError("Could not decode text file.")
    raise DocumentError(f"Unsupported file type: {suffix}")


def chunk_pages(
    pages: list[tuple[int | None, str]],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[tuple[int | None, str]]:
    """Split page texts into overlapping chunks, preserving page numbers."""
    chunks: list[tuple[int | None, str]] = []
    for page_number, page_text in pages:
        cleaned = " ".join(page_text.split())
        if not cleaned:
            continue
        start = 0
        while start < len(cleaned):
            end = start + chunk_size
            chunks.append((page_number, cleaned[start:end]))
            if end >= len(cleaned):
                break
            start = end - overlap
    return chunks


def _index_chunk(db: Session, chunk: DocumentChunk, document_id: str) -> None:
    if not db_module.FTS5_AVAILABLE:
        return
    db.execute(
        text(
            "INSERT INTO document_fts (chunk_id, document_id, page_number, text) "
            "VALUES (:cid, :did, :page, :text)"
        ),
        {
            "cid": chunk.id,
            "did": document_id,
            "page": chunk.page_number,
            "text": chunk.text,
        },
    )


def ingest_document(
    db: Session,
    documents_dir: Path,
    filename: str,
    data: bytes,
    max_mb: int,
) -> Document:
    """Validate, store, extract, chunk and index one uploaded document."""
    safe_name = validate_upload(filename, len(data), max_mb)
    documents_dir.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4().hex
    stored = documents_dir / f"{doc_id}_{safe_name}"
    stored.write_bytes(data)
    doc = Document(
        id=doc_id,
        filename=safe_name,
        stored_path=str(stored),
        size_bytes=len(data),
        mime="application/pdf" if stored.suffix == ".pdf" else "text/plain",
    )
    db.add(doc)
    db.flush()

    pages = extract_text(stored)
    doc.page_count = sum(1 for _, t in pages if t.strip())
    chunks = chunk_pages(pages)
    if not chunks:
        db.delete(doc)
        stored.unlink(missing_ok=True)
        db.flush()
        raise DocumentError("No readable text found in the document.")

    doc.char_count = sum(len(t) for _, t in chunks)
    for i, (page_number, ctext) in enumerate(chunks):
        chunk = DocumentChunk(
            document_id=doc.id, chunk_index=i, page_number=page_number, text=ctext
        )
        db.add(chunk)
        db.flush()
        _index_chunk(db, chunk, doc.id)
    doc.chunk_count = len(chunks)
    db.flush()
    return doc


def remove_document(db: Session, documents_dir: Path, document_id: str) -> None:
    """Delete a document, its chunks, its file and its index entries."""
    doc: Document | None = db.get(Document, document_id)
    if doc is None:
        raise DocumentError(f"Document not found: {document_id}")
    chunk_ids = [c.id for c in doc.chunks]
    if db_module.FTS5_AVAILABLE and chunk_ids:
        placeholders = ",".join(f":c{i}" for i in range(len(chunk_ids)))
        db.execute(
            text(f"DELETE FROM document_fts WHERE chunk_id IN ({placeholders})"),  # noqa: S608 - placeholders are bound-parameter names, not user input
            {f"c{i}": cid for i, cid in enumerate(chunk_ids)},
        )
    stored = Path(doc.stored_path)
    if stored.exists():
        # Only delete files inside our own documents directory.
        try:
            stored.resolve().relative_to(documents_dir.resolve())
        except ValueError:
            pass
        else:
            stored.unlink(missing_ok=True)
    db.delete(doc)
    db.flush()


def rebuild_index(db: Session) -> int:
    """Drop and rebuild the entire FTS index from stored chunks. Returns count."""
    if not db_module.FTS5_AVAILABLE:
        return 0
    db.execute(text("DELETE FROM document_fts"))
    count = 0
    for chunk in db.query(DocumentChunk).all():
        _index_chunk(db, chunk, chunk.document_id)
        count += 1
    db.flush()
    return count
