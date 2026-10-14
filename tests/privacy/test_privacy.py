"""Privacy tests: no sensitive logging, deletion effectiveness, data locality."""

import logging

from homemind.core import assistant, conversations
from homemind.memory import service as mem_service


def test_chat_content_not_logged(client, caplog):
    """Prompts must never be written to log files by default."""
    c = client.post("/conversations", json={}).json()
    secret = "my private phrase PINEAPPLE42"  # noqa: S105 - test data, not a credential
    with caplog.at_level(logging.INFO, logger="homemind"):
        r = client.post(f"/conversations/{c['id']}/chat",
                        json={"content": secret})
    assert r.status_code == 200
    for record in caplog.records:
        assert secret not in record.getMessage()


def test_deleted_memory_never_in_prompt(dbsession):
    conv = conversations.create_conversation(dbsession)
    m = mem_service.create_memory(dbsession, "SECRET_TOKEN_XYZ user birthday")
    mem_service.delete_memory(dbsession, m.id)

    from homemind.providers.base import ModelProvider, ProviderResult

    class Spy(ModelProvider):
        name = "spy"

        def check_availability(self):
            return True, "ok"

        def generate(self, messages, *, timeout_s=120.0):
            self.sent = [m.content for m in messages]
            return ProviderResult(text="ok", model=self.name)

    spy = Spy()
    assistant.chat(dbsession, spy, conv.id, "birthday SECRET_TOKEN_XYZ")
    # The user's own message legitimately contains the token; what matters is
    # that the *system* prompt carries no trace of the deleted memory.
    system_text = spy.sent[0]  # first message is the system prompt
    assert "SECRET_TOKEN_XYZ" not in system_text
    assert "User-approved stored facts" not in system_text


def test_export_reflects_deletions(client):
    c = client.post("/conversations", json={}).json()
    client.post(f"/conversations/{c['id']}/chat", json={"content": "hello"})
    client.delete(f"/conversations/{c['id']}")
    exp = client.get("/export").json()
    assert exp["conversations"] == []


def test_db_lives_under_data_dir(settings, db):
    assert str(db.db_path).startswith(str(settings.data_dir))
    assert db.db_path.exists()


def test_memory_export_excludes_deleted(client):
    m = client.post("/memories", json={"content": "temporary note"}).json()
    client.delete(f"/memories/{m['id']}")
    exp = client.get("/export").json()
    assert all(x["id"] != m["id"] for x in exp["memories"])


def test_mock_provider_is_default_in_tests(client):
    body = client.get("/status").json()
    assert body["provider"] == "mock"
