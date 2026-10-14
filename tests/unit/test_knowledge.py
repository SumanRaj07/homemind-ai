"""Unit tests: knowledge ingestion and retrieval."""

import fitz  # PyMuPDF
import pytest

from homemind.knowledge import ingestion, retrieval
from homemind.knowledge.ingestion import DocumentError


def _ingest_txt(dbsession, settings, text, name="notes.txt"):
    return ingestion.ingest_document(
        dbsession, settings.documents_dir, name, text.encode("utf-8"),
        max_mb=settings.max_upload_mb,
    )


def test_ingest_txt_and_search(dbsession, settings):
    doc = _ingest_txt(
        dbsession, settings,
        "The quick brown fox jumps over the lazy dog. " * 20,
        name="fox.txt",
    )
    assert doc.chunk_count >= 1
    assert doc.page_count == 1  # a txt file counts as a single page of text
    passages = retrieval.search(dbsession, "quick brown fox", limit=3)
    assert passages
    assert passages[0].filename == "fox.txt"
    assert passages[0].document_id == doc.id


def test_ingest_pdf_page_numbers(dbsession, settings, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf = fitz.open()
    for i in range(3):
        page = pdf.new_page()
        page.insert_text((72, 72), f"Unique marker page {i}: zebracake recipe notes.")
    pdf.save(pdf_path)
    pdf.close()

    doc = ingestion.ingest_document(
        dbsession, settings.documents_dir, "sample.pdf",
        pdf_path.read_bytes(), max_mb=settings.max_upload_mb,
    )
    assert doc.page_count == 3
    passages = retrieval.search(dbsession, "zebracake", limit=5)
    assert passages
    pages = {p.page_number for p in passages}
    assert pages <= {1, 2, 3}


def test_reject_bad_extension(dbsession, settings):
    with pytest.raises(DocumentError):
        ingestion.ingest_document(
            dbsession, settings.documents_dir, "evil.exe", b"data",
            max_mb=settings.max_upload_mb,
        )


def test_reject_empty_file(dbsession, settings):
    with pytest.raises(DocumentError):
        ingestion.ingest_document(
            dbsession, settings.documents_dir, "empty.txt", b"",
            max_mb=settings.max_upload_mb,
        )


def test_reject_oversized(dbsession, settings):
    with pytest.raises(DocumentError):
        ingestion.ingest_document(
            dbsession, settings.documents_dir, "big.txt", b"x" * 100,
            max_mb=0,  # anything over 0 bytes is too big
        )


def test_reject_malformed_pdf(dbsession, settings):
    with pytest.raises(DocumentError):
        ingestion.ingest_document(
            dbsession, settings.documents_dir, "broken.pdf",
            b"%PDF-1.4 not really a pdf {{{",
            max_mb=settings.max_upload_mb,
        )


def test_reject_blank_text_pdf(dbsession, settings, tmp_path):
    pdf_path = tmp_path / "blank.pdf"
    pdf = fitz.open()
    pdf.new_page()  # empty page, no text
    pdf.save(pdf_path)
    pdf.close()
    with pytest.raises(DocumentError):
        ingestion.ingest_document(
            dbsession, settings.documents_dir, "blank.pdf",
            pdf_path.read_bytes(), max_mb=settings.max_upload_mb,
        )


def test_remove_document_deindexes(dbsession, settings):
    doc = _ingest_txt(dbsession, settings, "wombat stew " * 50)
    assert retrieval.search(dbsession, "wombat", limit=3)
    ingestion.remove_document(dbsession, settings.documents_dir, doc.id)
    assert retrieval.search(dbsession, "wombat", limit=3) == []


def test_rebuild_index(dbsession, settings):
    _ingest_txt(dbsession, settings, "quokka facts " * 50)
    count = ingestion.rebuild_index(dbsession)
    assert count >= 1
    assert retrieval.search(dbsession, "quokka", limit=3)


def test_filename_sanitized(dbsession, settings):
    doc = _ingest_txt(dbsession, settings, "hello " * 50, name="../../etc/passwd.txt")
    assert ".." not in doc.filename
    assert "/" not in doc.filename
    stored = settings.documents_dir / f"{doc.id}_{doc.filename}"
    assert stored.exists()
    # And the stored path is inside the documents dir.
    assert stored.resolve().parent == settings.documents_dir.resolve()


def test_search_empty_query(dbsession):
    assert retrieval.search(dbsession, "   ", limit=5) == []


def test_search_with_quotes_does_not_crash(dbsession, settings):
    _ingest_txt(dbsession, settings, "plain content " * 30)
    # FTS special characters must not raise.
    assert isinstance(retrieval.search(dbsession, '"unbalanced', limit=5), list)


def test_remove_document_deletes_chunks_and_file(dbsession, settings):
    """Deletion must remove DB chunks, the stored file and the FTS entries."""
    from homemind.storage.models import Document, DocumentChunk

    doc = _ingest_txt(dbsession, settings, "wombat deletion check " * 50)
    doc_id = doc.id
    stored = settings.documents_dir / f"{doc_id}_{doc.filename}"
    assert stored.exists()
    assert dbsession.query(DocumentChunk).filter_by(document_id=doc_id).count() >= 1

    ingestion.remove_document(dbsession, settings.documents_dir, doc_id)

    assert dbsession.get(Document, doc_id) is None
    assert dbsession.query(DocumentChunk).filter_by(document_id=doc_id).count() == 0
    assert not stored.exists()
    assert retrieval.search(dbsession, "wombat", limit=3) == []
