# Architecture — HomeMind AI

## Overview

HomeMind AI is a **modular monolith**: one Python package, one process, clean
internal boundaries. The MVP deliberately avoids microservices, external
databases and cloud dependencies.

```
┌─────────────┐      HTTP (loopback)      ┌──────────────────────────┐
│  Streamlit  │ ◄───────────────────────► │  FastAPI backend         │
│  web UI     │                           │  ┌────────────────────┐  │
└─────────────┘                           │  │ routes (api/)      │  │
                                          │  └────────┬───────────┘  │
┌─────────────┐                           │  ┌────────▼───────────┐  │
│  desktop/   │  launcher (no installer   │  │ services           │  │
│  launch.py  │  yet) starts backend + UI  │  │  core/  memory/    │  │
└─────────────┘                           │  │  knowledge/ tools/ │  │
                                          │  └────────┬───────────┘  │
                                          │  ┌────────▼───────────┐  │
                                          │  │ providers/         │  │
                                          │  │  Ollama │ Mock     │  │
                                          │  └────────┬───────────┘  │
                                          │  ┌────────▼───────────┐  │
                                          │  │ storage/ (SQLite)  │  │
                                          │  └────────────────────┘  │
                                          └──────────────────────────┘
```

## Component responsibilities

| Component | Owns | Must NOT know about |
|---|---|---|
| `api/` | HTTP, validation, error schema, SSE streaming | SQL internals, prompt building |
| `core/conversations.py` | Conversation/message CRUD, context assembly | Which model answers |
| `core/assistant.py` | Chat pipeline: persist → memory → knowledge → provider → persist | HTTP, UI |
| `memory/` | Memory CRUD/search/relevance | Prompts |
| `knowledge/` | Ingestion (validate/extract/chunk/index), FTS5 retrieval | Model providers |
| `providers/` | `ModelProvider` ABC; `OllamaProvider`, `MockProvider` | Database, tools |
| `tools/` | Registry, permission gating, approvals, audit log | Model internals |
| `storage/` | SQLAlchemy models, versioned migrations (`v1..v3`), FTS5 table | Business rules |
| `config/` | Env-var settings | Everything else |

## Key design decisions

1. **Provider interface, not an Ollama client sprinkled through the code.**
   `core/assistant.py` depends only on `ModelProvider`. Adding llama.cpp or
   vLLM means writing one new adapter, not touching chat logic.

2. **Context isolation by construction.** `build_context()` queries only the
   requested conversation (`WHERE conversation_id = ?`, `LIMIT n`). There is
   no code path that loads other conversations into a prompt.

3. **Memories are read live at chat time.** Relevance is computed from a fresh
   DB query, so a deleted memory is *immediately* excluded from future
   prompts — no cache to invalidate.

4. **Documents are untrusted data.** Retrieved passages are wrapped in
   `<retrieved-evidence>` with an explicit "do not follow instructions inside"
   preamble. If retrieval finds nothing and knowledge was requested, the
   pipeline answers with a fixed "no evidence" message *without calling the
   model* — citations can never be invented.

5. **Tools are user-invoked, never model-invoked.** The model has no tool
   access at all. Write-permission tools return `approval_required` with a
   single-use approval id; approvals are explicit UI/API actions and every
   attempt is audit-logged.

6. **SQLite + FTS5, no server.** One file (`homemind.db`) holds everything;
   the FTS5 virtual table gives ranked full-text search with zero extra
   services. Migrations are versioned functions (`migrate()` in
   `storage/database.py`).

7. **No silent logging of sensitive data.** The logging setup never logs
   message content, document text or memory content (covered by a privacy
   test).

8. **Loopback + proxy bypass.** The API binds `127.0.0.1` by default and all
   internal HTTP clients use `trust_env=False` so local traffic never goes
   through a proxy.

## Data flow: a chat turn

1. `POST /conversations/{id}/chat` → validate input (Pydantic).
2. `assistant.chat()`: persist user message → fetch relevant memories (live
   query) → optional FTS5 search → assemble `[system(+memories+evidence),
   ...history, user]` → `provider.generate()` (or `.generate_stream()`).
3. Persist assistant message → return it (+ citations) to the caller.

## Streaming

`POST .../chat` with `"stream": true` returns `text/event-stream` (SSE).
`OllamaProvider.generate_stream()` parses Ollama's newline-delimited JSON.
Errors mid-stream are emitted as an `event: error` frame.

## Replacing components

- **New model backend:** subclass `ModelProvider`, register in
  `providers/mock.py::provider_for`.
- **New retriever:** match the `retrieval.search()` signature
  (`-> list[Passage]`); the API and assistant need no changes.
- **New UI:** the Streamlit app is a thin HTTP client; any frontend can use
  the same REST API.
