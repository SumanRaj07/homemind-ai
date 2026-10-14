"""Shared-state tests: browser and desktop use ONE database.

Both interfaces talk to the same FastAPI backend / SQLite file, so a
conversation created in one must be visible in the other, and concurrent
handles must not corrupt data.
"""

from __future__ import annotations

from homemind.core import conversations as conv_service
from homemind.memory import service as mem_service
from homemind.storage.database import Database


def test_two_handles_share_conversations(settings):
    """Simulates browser + desktop: two Database handles, one file."""
    db_browser = Database(settings.db_path)
    db_desktop = Database(settings.db_path)

    with db_browser.session() as s:
        conv = conv_service.create_conversation(s, title="from browser")
        conv_id = conv.id
        conv_service.add_message(s, conv_id, "user", "hello from browser")

    with db_desktop.session() as s:
        seen = conv_service.get_conversation(s, conv_id)
        assert seen.title == "from browser"
        msgs = conv_service.get_messages(s, conv_id)
        assert [m.content for m in msgs] == ["hello from browser"]


def test_two_handles_share_memories(settings):
    db_a = Database(settings.db_path)
    db_b = Database(settings.db_path)

    with db_a.session() as s:
        mem = mem_service.create_memory(s, "desktop likes tea", category="pref")
        mem_id = mem.id

    with db_b.session() as s:
        found = mem_service.search_memories(s, "tea")
        assert [m.id for m in found] == [mem_id]
        # Edit from the other handle, delete from the first.
        mem_service.update_memory(s, mem_id, content="desktop likes coffee")

    with db_a.session() as s:
        assert mem_service.get_memory(s, mem_id).content == "desktop likes coffee"
        mem_service.delete_memory(s, mem_id)

    with db_b.session() as s:
        assert mem_service.search_memories(s, "coffee") == []


def test_interleaved_writes_do_not_corrupt(settings):
    db_a = Database(settings.db_path)
    db_b = Database(settings.db_path)
    with db_a.session() as s:
        c1 = conv_service.create_conversation(s, title="c1")
    with db_b.session() as s:
        c2 = conv_service.create_conversation(s, title="c2")
    with db_a.session() as s:
        conv_service.add_message(s, c1.id, "user", "m1")
    with db_b.session() as s:
        conv_service.add_message(s, c2.id, "user", "m2")
    with db_a.session() as s:
        assert conv_service.message_count(s, c1.id) == 1
        assert conv_service.message_count(s, c2.id) == 1
        assert len(conv_service.list_conversations(s)) == 2
