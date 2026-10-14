# HomeMind AI

**HomeMind AI** is a local-first, private personal AI assistant you self-host on
your own computer. Chat with locally hosted models, keep persistent
conversations, manage your own memories, search your personal documents with
source citations, and use permission-gated tools — all without sending your
data to the cloud.

- 🖥️ **Local-first** — inference via [Ollama](https://ollama.com) on your machine. No cloud fallback.
- 💬 **Chat workspace** — conversations with history, rename, clear, delete, streaming replies.
- 🧠 **User-controlled memory** — explicit save/edit/delete/search/export. Nothing is memorized silently.
- 📚 **Personal knowledge base** — import PDF/TXT, full-text search (SQLite FTS5), cited answers.
- 🛠️ **Permissioned tools** — read-only tools run instantly; consequential ones need your approval.
- 🔒 **Privacy by default** — loopback networking, no prompt logging, one-click export & deletion.

## Quick start

```powershell
# 1. Create and activate a virtual environment (Windows PowerShell)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install
pip install -e ".[dev]"

# 3. Install Ollama (https://ollama.com), then pull a small model:
ollama pull llama3.2:3b

# 4. Start the backend (http://127.0.0.1:8000)
homemind-api

# 5. In another terminal, start the web UI (http://127.0.0.1:8501)
streamlit run frontend/app.py
```

No Ollama? The app still runs — set `HOMEMIND_PROVIDER=mock` to explore the UI
and API with deterministic test responses.

See **[INSTALL.md](INSTALL.md)** for the full setup guide (Windows 11),
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for design details,
**[docs/PRIVACY.md](docs/PRIVACY.md)** for the privacy model, and
**[SECURITY.md](SECURITY.md)** for the threat model.

## Hardware expectations

Developed for a typical laptop (Windows 11, Intel i5, 16 GB RAM, RTX 3050),
but the backend, database, search and UI work fine **without a GPU**.

| Model (Ollama) | VRAM needed | Notes |
|---|---|---|
| `llama3.2:3b` | ~2 GB | Default. Good balance for 16 GB RAM. |
| `qwen2.5:3b` | ~2 GB | Alternative small model. |
| `llama3.1:8b` | ~5 GB | Better quality if you have the VRAM. |

Set your model with `HOMEMIND_MODEL=qwen2.5:3b` (env var or Settings screen).

## Repository layout

```
homemind-ai/
├── src/homemind/        # Python package
│   ├── api/             # FastAPI app + routes
│   ├── core/            # Conversation service + chat orchestration
│   ├── models/          # Pydantic request/response schemas
│   ├── memory/          # User-controlled memory service
│   ├── knowledge/       # PDF/TXT ingestion + FTS5 retrieval
│   ├── providers/       # ModelProvider interface, Ollama + mock adapters
│   ├── tools/           # Tool registry, permissions, built-in tools
│   ├── storage/         # SQLAlchemy models, migrations, SQLite database
│   └── config/          # Settings (env-var based)
├── frontend/            # Streamlit web UI
├── desktop/             # Windows launcher + packaging notes
├── tests/               # unit / integration / privacy / security
├── docs/                # Architecture, privacy, examples
├── examples/            # Example API workflows
├── scripts/             # Run + backup helpers (sh and bat)
└── .github/workflows/   # CI
```

## API overview

| Method & path | Description |
|---|---|
| `GET /health`, `GET /status` | Health + model/runtime status |
| `POST /conversations` | New conversation |
| `GET/PATCH/DELETE /conversations/{id}` | Manage one conversation |
| `POST /conversations/{id}/chat` | Chat turn (`stream: true` → SSE) |
| `POST/GET/PATCH/DELETE /memories` | Memory CRUD + search |
| `POST /documents`, `GET /documents`, `DELETE /documents/{id}` | Knowledge base |
| `POST /knowledge/search` | Cited passage search |
| `GET /tools`, `POST /tools/{name}/execute` | Permissioned tools |
| `GET /export` | Full data export (JSON) |
| `DELETE /data/conversations`, `DELETE /data/memories` | Bulk deletion |

## Development

```bash
pytest            # 82 tests, mocked model — no Ollama needed
ruff check src tests frontend desktop
```

CI (`.github/workflows/ci.yml`) runs pytest + ruff on every push.

## License

MIT — see [LICENSE](LICENSE).
