"""Unit tests: conversation service — CRUD and context isolation."""

import pytest

from homemind.core import conversations
from homemind.core.conversations import ConversationNotFound


def test_create_and_list(dbsession):
    c1 = conversations.create_conversation(dbsession, title="First")
    c2 = conversations.create_conversation(dbsession, title="Second")
    all_convs = conversations.list_conversations(dbsession)
    ids = {c.id for c in all_convs}
    assert {c1.id, c2.id} <= ids


def test_rename_and_system_instructions(dbsession):
    conv = conversations.create_conversation(dbsession)
    conversations.rename_conversation(dbsession, conv.id, "Renamed")
    conversations.set_system_instructions(dbsession, conv.id, "Be brief.")
    got = conversations.get_conversation(dbsession, conv.id)
    assert got.title == "Renamed"
    assert got.system_instructions == "Be brief."


def test_get_missing_raises(dbsession):
    with pytest.raises(ConversationNotFound):
        conversations.get_conversation(dbsession, "nope")


def test_delete_removes_messages(dbsession):
    conv = conversations.create_conversation(dbsession)
    conversations.add_message(dbsession, conv.id, "user", "hello")
    conversations.delete_conversation(dbsession, conv.id)
    with pytest.raises(ConversationNotFound):
        conversations.get_conversation(dbsession, conv.id)


def test_clear_keeps_conversation(dbsession):
    conv = conversations.create_conversation(dbsession)
    conversations.add_message(dbsession, conv.id, "user", "hello")
    conversations.clear_conversation(dbsession, conv.id)
    assert conversations.get_messages(dbsession, conv.id) == []


def test_build_context_only_this_conversation(dbsession):
    a = conversations.create_conversation(dbsession)
    b = conversations.create_conversation(dbsession)
    conversations.add_message(dbsession, a.id, "user", "message for A")
    conversations.add_message(dbsession, b.id, "user", "message for B")
    ctx = conversations.build_context(dbsession, a.id, max_messages=20)
    texts = [m.content for m in ctx]
    assert "message for A" in texts
    assert "message for B" not in texts


def test_build_context_respects_limit(dbsession):
    conv = conversations.create_conversation(dbsession)
    for i in range(10):
        conversations.add_message(dbsession, conv.id, "user", f"msg {i}")
    ctx = conversations.build_context(dbsession, conv.id, max_messages=4)
    # 1 system + 4 most recent
    assert len(ctx) == 5
    assert ctx[-1].content == "msg 9"
    assert ctx[1].content == "msg 6"


def test_build_context_starts_with_system(dbsession):
    conv = conversations.create_conversation(
        dbsession, system_instructions="Custom instructions."
    )
    ctx = conversations.build_context(dbsession, conv.id)
    assert ctx[0].role == "system"
    assert "Custom instructions." in ctx[0].content


def test_add_message_invalid_role(dbsession):
    conv = conversations.create_conversation(dbsession)
    with pytest.raises(ValueError):
        conversations.add_message(dbsession, conv.id, "hacker", "x")
