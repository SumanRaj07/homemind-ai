"""Integration tests: full API surface with the mock model provider."""

import io


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_status(client):
    r = client.get("/status")
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "mock"
    assert body["model_available"] is True


def test_conversation_crud(client):
    c = client.post("/conversations", json={"title": "My chat"}).json()
    assert c["title"] == "My chat"

    listed = client.get("/conversations").json()
    assert any(x["id"] == c["id"] for x in listed)

    got = client.get(f"/conversations/{c['id']}").json()
    assert got["id"] == c["id"]

    upd = client.patch(f"/conversations/{c['id']}",
                       json={"title": "Renamed"}).json()
    assert upd["title"] == "Renamed"

    assert client.get("/conversations/missing").status_code == 404


def test_conversation_delete_and_clear(client):
    c = client.post("/conversations", json={}).json()
    client.post(f"/conversations/{c['id']}/messages", json={"content": "hi"})
    client.post(f"/conversations/{c['id']}/clear")
    assert client.get(f"/conversations/{c['id']}").json()["message_count"] == 0
    assert client.delete(f"/conversations/{c['id']}").status_code == 204
    assert client.get(f"/conversations/{c['id']}").status_code == 404


def test_messages_validation(client):
    c = client.post("/conversations", json={}).json()
    assert client.post(f"/conversations/{c['id']}/messages",
                       json={"content": "   "}).status_code == 422
    assert client.post("/conversations/missing/messages",
                       json={"content": "hi"}).status_code == 404


def test_chat_roundtrip(client):
    c = client.post("/conversations", json={}).json()
    r = client.post(f"/conversations/{c['id']}/chat",
                    json={"content": "Hello assistant"})
    assert r.status_code == 200
    body = r.json()
    assert "mock-model reply" in body["message"]["content"]
    msgs = client.get(f"/conversations/{c['id']}/messages").json()
    assert len(msgs) == 2


def test_chat_missing_conversation(client):
    r = client.post("/conversations/missing/chat", json={"content": "hi"})
    assert r.status_code == 404


def test_chat_stream(client):
    c = client.post("/conversations", json={}).json()
    r = client.post(f"/conversations/{c['id']}/chat",
                    json={"content": "stream please", "stream": True})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "[DONE]" in r.text
    msgs = client.get(f"/conversations/{c['id']}/messages").json()
    assert len(msgs) == 2
    assert len(msgs[1]["content"]) > 0


def test_memory_crud_and_search(client):
    m = client.post("/memories", json={
        "content": "User likes green tea.", "category": "preferences",
        "tags": ["drinks"], "source": "chat"}).json()
    assert m["category"] == "preferences"

    got = client.get(f"/memories/{m['id']}").json()
    assert got["content"] == "User likes green tea."

    found = client.get("/memories", params={"q": "green tea"}).json()
    assert len(found) == 1

    upd = client.patch(f"/memories/{m['id']}",
                       json={"content": "User likes black tea."}).json()
    assert upd["content"] == "User likes black tea."

    assert client.delete(f"/memories/{m['id']}").status_code == 204
    assert client.get(f"/memories/{m['id']}").status_code == 404


def test_memory_clear_requires_confirm(client):
    client.post("/memories", json={"content": "x"})
    assert client.delete("/memories").status_code == 400
    r = client.delete("/memories", params={"confirm": "true"})
    assert r.json()["deleted"] == 1


def test_document_upload_search_delete(client):
    files = {"file": ("notes.txt", io.BytesIO(b"HomeMind uses local models. " * 40))}
    up = client.post("/documents", files=files)
    assert up.status_code == 201
    doc = up.json()
    assert doc["filename"] == "notes.txt"

    docs = client.get("/documents").json()
    assert any(d["id"] == doc["id"] for d in docs)

    res = client.post("/knowledge/search",
                      json={"query": "local models", "limit": 3}).json()
    assert res["passages"]
    assert res["passages"][0]["filename"] == "notes.txt"

    assert client.delete(f"/documents/{doc['id']}").status_code == 204
    res2 = client.post("/knowledge/search",
                       json={"query": "local models", "limit": 3}).json()
    assert res2["passages"] == []


def test_document_upload_rejects_exe(client):
    files = {"file": ("bad.exe", io.BytesIO(b"nope"))}
    r = client.post("/documents", files=files)
    assert r.status_code == 400


def test_tools_list_and_execute(client):
    tools = client.get("/tools").json()
    names = {t["name"] for t in tools}
    assert "knowledge_search" in names

    r = client.post("/tools/summarize_text/execute",
                    json={"inputs": {"text": "Alpha. Beta. Gamma.", "max_sentences": 1}})
    assert r.json()["status"] == "executed"
    assert r.json()["result"]["ok"] is True

    r2 = client.post("/tools/unknown/execute", json={"inputs": {}})
    assert r2.json()["status"] == "denied"


def test_export_and_data_deletion(client):
    c = client.post("/conversations", json={"title": "t"}).json()
    client.post(f"/conversations/{c['id']}/messages", json={"content": "hi"})
    client.post("/memories", json={"content": "remember this"})

    exp = client.get("/export").json()
    assert len(exp["conversations"]) == 1
    assert exp["conversations"][0]["messages"]
    assert len(exp["memories"]) == 1

    assert client.delete("/data/conversations").json()["deleted"] == 1
    assert client.delete("/data/memories").json()["deleted"] == 1
    assert client.get("/conversations").json() == []
    assert client.get("/memories").json() == []


def test_error_schema_is_consistent(client):
    r = client.post("/conversations", json={"title": "x" * 500})
    assert r.status_code == 422
    assert "error" in r.json()
    assert "code" in r.json()["error"]
