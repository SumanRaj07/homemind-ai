"""Unit tests: tool registry — permissions, approvals, audit, safety."""

from homemind.tools.permissions import Permission
from homemind.tools.registry import Tool, build_default_registry


def _registry(settings):
    return build_default_registry(settings)


def test_builtin_tools_registered(settings):
    reg = _registry(settings)
    names = {t.name for t in reg.list_tools()}
    assert {"knowledge_search", "memory_get", "summarize_text",
            "workspace_list_files"} <= names


def test_read_tool_executes_immediately(dbsession, settings):
    reg = _registry(settings)
    out = reg.execute(dbsession, "summarize_text",
                      {"text": "First sentence. Second sentence. Third.", "max_sentences": 2})
    assert out["status"] == "executed"
    assert out["result"]["ok"] is True
    assert "First sentence." in out["result"]["summary"]


def test_unknown_tool_denied(dbsession, settings):
    reg = _registry(settings)
    out = reg.execute(dbsession, "no_such_tool", {})
    assert out["status"] == "denied"


def test_write_tool_requires_approval(dbsession, settings):
    reg = _registry(settings)
    calls = []

    def _handler(db, settings, inputs):
        calls.append(inputs)
        return {"ok": True}

    reg.register(Tool(name="demo_write", description="demo", permission=Permission.WRITE,
                      input_schema={}, handler=_handler))
    out = reg.execute(dbsession, "demo_write", {"x": 1})
    assert out["status"] == "approval_required"
    assert out["approval_id"]
    assert calls == []  # not executed yet

    resolved = reg.resolve_approval(dbsession, out["approval_id"], approve=True)
    assert resolved["status"] == "executed"
    assert calls == [{"x": 1}]


def test_write_tool_reject(dbsession, settings):
    reg = _registry(settings)
    calls = []

    def _handler(db, settings, inputs):
        calls.append(inputs)
        return {"ok": True}

    reg.register(Tool(name="demo_write2", description="demo", permission=Permission.WRITE,
                      input_schema={}, handler=_handler))
    out = reg.execute(dbsession, "demo_write2", {})
    resolved = reg.resolve_approval(dbsession, out["approval_id"], approve=False)
    assert resolved["status"] == "denied"
    assert calls == []


def test_approval_is_single_use(dbsession, settings):
    reg = _registry(settings)

    def _handler(db, settings, inputs):
        return {"ok": True}

    reg.register(Tool(name="demo_write3", description="demo", permission=Permission.WRITE,
                      input_schema={}, handler=_handler))
    out = reg.execute(dbsession, "demo_write3", {})
    reg.resolve_approval(dbsession, out["approval_id"], approve=True)
    # Reusing the same approval id must fail.
    again = reg.resolve_approval(dbsession, out["approval_id"], approve=True)
    assert again["status"] == "denied"


def test_audit_log_written(dbsession, settings):
    from sqlalchemy import func, select

    from homemind.storage.models import ToolAudit

    reg = _registry(settings)
    reg.execute(dbsession, "summarize_text", {"text": "Hello world."})
    count = dbsession.execute(select(func.count()).select_from(ToolAudit)).scalar()
    assert count and count >= 1


def test_workspace_list_blocks_traversal(dbsession, settings, tmp_path):
    reg = _registry(settings)
    out = reg.execute(dbsession, "workspace_list_files", {"subpath": "../.."})
    assert out["status"] == "executed"
    assert out["result"]["ok"] is False
    assert "outside" in out["result"]["error"]


def test_workspace_list_ok(dbsession, settings):
    reg = _registry(settings)
    (settings.workspace_dir / "demo.txt").write_text("hi")
    out = reg.execute(dbsession, "workspace_list_files", {"subpath": "."})
    assert out["result"]["ok"] is True
    assert any(e["name"] == "demo.txt" for e in out["result"]["entries"])
