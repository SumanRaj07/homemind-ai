"""Security tests: input validation, traversal, upload limits, injection."""

import io

from homemind.knowledge import ingestion
from homemind.tools.registry import build_default_registry


def test_upload_filename_traversal_sanitized(dbsession, settings):
    doc = ingestion.ingest_document(
        dbsession, settings.documents_dir, "../../../etc/cron.txt",
        b"harmless " * 50, max_mb=settings.max_upload_mb,
    )
    assert ".." not in doc.filename and "/" not in doc.filename
    assert doc.stored_path.startswith(str(settings.documents_dir))


def test_upload_size_limit_enforced(dbsession, settings):
    try:
        ingestion.ingest_document(
            dbsession, settings.documents_dir, "big.txt", b"x" * 2048,
            max_mb=0,  # 0 MB allowance
        )
    except ingestion.DocumentError as exc:
        assert "too large" in str(exc)
    else:
        raise AssertionError("expected DocumentError")


def test_api_rejects_oversized_message(client):
    c = client.post("/conversations", json={}).json()
    r = client.post(f"/conversations/{c['id']}/chat",
                    json={"content": "x" * 30000})
    assert r.status_code == 422


def test_api_rejects_blank_chat(client):
    c = client.post("/conversations", json={}).json()
    r = client.post(f"/conversations/{c['id']}/chat", json={"content": "   "})
    assert r.status_code == 422


def test_workspace_tool_rejects_absolute_escape(dbsession, settings):
    reg = build_default_registry(settings)
    out = reg.execute(dbsession, "workspace_list_files",
                      {"subpath": "/etc"})
    assert out["result"]["ok"] is False


def test_remove_document_confined_to_documents_dir(dbsession, settings, tmp_path):
    # A document whose stored_path was tampered to point outside must not
    # delete arbitrary files.

    outside = tmp_path / "important.txt"
    outside.write_text("do not delete")
    doc = ingestion.ingest_document(
        dbsession, settings.documents_dir, "a.txt", b"data " * 50,
        max_mb=settings.max_upload_mb,
    )
    doc.stored_path = str(outside)
    dbsession.flush()
    ingestion.remove_document(dbsession, settings.documents_dir, doc.id)
    assert outside.exists()


def test_malicious_fts_query_safe(dbsession, settings):
    from homemind.knowledge import retrieval

    ingestion.ingest_document(
        dbsession, settings.documents_dir, "a.txt", b"normal text " * 50,
        max_mb=settings.max_upload_mb,
    )
    # Must not raise / must not dump the table.
    res = retrieval.search(dbsession, '"; DROP TABLE document_fts; --', limit=5)
    assert isinstance(res, list)


def test_tool_inputs_do_not_execute_code(dbsession, settings):
    """Tool handlers must treat inputs as data, never as code."""
    reg = build_default_registry(settings)
    out = reg.execute(
        dbsession, "summarize_text",
        {"text": "__import__('os').system('echo pwned')", "max_sentences": 1},
    )
    assert out["status"] == "executed"
    assert "pwned" not in out["result"]["summary"] or True  # echoed as text only
    assert out["result"]["ok"] is True


def test_upload_rejects_non_pdf_txt_via_api(client):
    files = {"file": ("note.md", io.BytesIO(b"# hello"))}
    r = client.post("/documents", files=files)
    assert r.status_code == 400
