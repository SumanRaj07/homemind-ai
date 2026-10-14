# HomeMind AI — Release Notes

## v0.1.0 (2026-10-14) — Initial MVP release

The first public release of HomeMind AI: a local-first, private personal AI
assistant you self-host on your own computer. No cloud, no accounts, no
tracking — your conversations, memories and documents never leave your machine.

### What's included

**Chat workspace**
- Multiple conversations with unique IDs, history, rename, clear and delete
- Streaming (SSE) and single-shot replies from your local model
- Per-conversation system instructions and configurable context limits
- Strict conversation isolation — one conversation's messages never leak
  into another's prompt

**User-controlled memory**
- Explicit create / list / search / edit / delete; category + tags + source
- Clear-all requires explicit `?confirm=true`
- Nothing is memorized silently; deleted memories never appear in prompts again
- Full JSON export

**Personal knowledge base**
- Import PDF (PyMuPDF) and TXT with validation, size limits and filename
  sanitization
- SQLite FTS5 full-text search with BM25 ranking
- Answers cite `[filename p.N]`; a fixed no-evidence reply when nothing is
  found (the model is not even called)
- Document contents are treated as untrusted data — prompt-injection fenced

**Local models**
- Ollama adapter behind a swappable `ModelProvider` interface
- Configurable model name, connect + response timeouts
- Clear, actionable errors when Ollama is down or the model isn't installed
- Mock provider for tests and UI exploration (`HOMEMIND_PROVIDER=mock`)

**Permissioned tools**
- Registry with typed schemas, permission levels, timeouts and audit logging
- Read-only tools run instantly; consequential tools need explicit,
  single-use approval
- The model cannot invoke tools at all — tools are user-invoked only

**Privacy & safety**
- Binds `127.0.0.1` by default; internal HTTP bypasses proxy env vars
- No prompt, document or memory contents in logs
- One-click export and bulk deletion; documented privacy + threat models

**Interfaces**
- Streamlit web UI: Chat, Conversations, Memory, Knowledge Base, Tools,
  Settings — all wired to the real backend, no demo data
- Windows launcher script + packaging notes (`desktop/`)

### Quality gates (all verified for this release)

- `pytest`: **82 passed, 0 failed** (unit / integration / privacy / security;
  mocked model — no Ollama required)
- `ruff check`: clean · `mypy`: clean
- GitHub Actions CI runs lint + tests on every push
- Live smoke test: real server, SSE streaming, PDF ingest → cited answers,
  restart persistence, Streamlit boot (HTTP 200)

### Known limitations

- No authentication on the local API (acceptable for single-user loopback use;
  do not expose to a network)
- SQLite database file is unencrypted — rely on OS-level disk encryption
- Desktop packaging is launcher + docs; no installer yet
- Code-execution tools are not shipped (framework is ready for future
  isolated execution)

### Upgrading

This is the first release — no migration needed. Your data lives in
`~/.homemind/` (or `HOMEMIND_DATA_DIR`); back it up with
`scripts/backup_db.py` before upgrading in future releases.

MIT licensed. See `README.md`, `INSTALL.md`, `SECURITY.md`,
`docs/PRIVACY.md` and `docs/ARCHITECTURE.md`.
