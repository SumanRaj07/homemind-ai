"""Unit tests: memory service."""

import pytest

from homemind.memory import service as mem
from homemind.memory.service import MemoryNotFound


def test_crud(dbsession):
    m = mem.create_memory(
        dbsession, "User likes tea.", category="preferences", tags=["drinks"]
    )
    assert m.id
    got = mem.get_memory(dbsession, m.id)
    assert got.content == "User likes tea."
    assert got.tags == "drinks"

    mem.update_memory(dbsession, m.id, content="User likes coffee.")
    assert mem.get_memory(dbsession, m.id).content == "User likes coffee."

    mem.delete_memory(dbsession, m.id)
    with pytest.raises(MemoryNotFound):
        mem.get_memory(dbsession, m.id)


def test_list_and_category_filter(dbsession):
    mem.create_memory(dbsession, "a", category="work")
    mem.create_memory(dbsession, "b", category="personal")
    assert len(mem.list_memories(dbsession)) == 2
    assert len(mem.list_memories(dbsession, category="work")) == 1


def test_search(dbsession):
    mem.create_memory(dbsession, "The user's dog is named Biscuit.")
    mem.create_memory(dbsession, "Unrelated fact about cars.")
    results = mem.search_memories(dbsession, "biscuit")
    assert len(results) == 1
    assert "Biscuit" in results[0].content


def test_clear_memories(dbsession):
    mem.create_memory(dbsession, "one")
    mem.create_memory(dbsession, "two")
    removed = mem.clear_memories(dbsession)
    assert removed == 2
    assert mem.list_memories(dbsession) == []


def test_relevant_memories_matches_tokens(dbsession):
    mem.create_memory(dbsession, "User is vegetarian and loves hiking.")
    mem.create_memory(dbsession, "User's favourite colour is blue.")
    relevant = mem.relevant_memories(dbsession, "What vegetarian meals suit hiking?")
    assert len(relevant) == 1
    assert "vegetarian" in relevant[0].content


def test_relevant_memories_ignores_deleted(dbsession):
    m = mem.create_memory(dbsession, "User is vegetarian and loves hiking.")
    mem.delete_memory(dbsession, m.id)
    assert mem.relevant_memories(dbsession, "vegetarian hiking") == []
