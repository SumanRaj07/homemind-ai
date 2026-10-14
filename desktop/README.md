# Desktop application — HomeMind AI

## Architecture decision

**Browser and desktop share everything.** There is exactly one backend
(FastAPI), one database (SQLite) and one frontend codebase (Streamlit):

```
┌────────────────┐      ┌────────────────┐
│ Browser tab    │      │ Desktop window │  <- same Streamlit app (frontend/app.py)
│ localhost:8501 │      │ (pywebview or  │
└───────┬────────┘      │  browser)      │
        │               └───────┬────────┘
        └───────────┬───────────┘
                    ▼
           FastAPI backend (127.0.0.1:8000, single instance)
                    ▼
           SQLite (~/.homemind/homemind.db) + Ollama (127.0.0.1:11434)
```

`desktop/launch.py` is the desktop app: it owns the backend lifecycle
(lock file → reuse-or-start → health check → model status → open UI →
graceful shutdown of only what it started).

### Trade-offs considered

| Option | Verdict | Reason |
|---|---|---|
| Rewrite UI in React+TS + Tauri 2 | Rejected for v1 | The Streamlit UI is implemented and verified; a rewrite would be a large untested change, and a Tauri/Windows installer cannot be built or tested on this Linux dev machine. The spec forbids claiming untested installers work. |
| Second UI codebase for desktop | Rejected | Would duplicate memory/document logic and risk divergence. The spec forbids separate implementations of storage. |
| **Launcher + shared Streamlit UI (chosen)** | **Implemented** | Zero duplication, fully testable lifecycle, one database, identical capabilities in both interfaces. `pywebview` gives a desktop window when installed; otherwise the system browser is used. |

Tauri remains a documented future option once a Windows build machine is
available — the backend API is UI-agnostic, so a native frontend can be
added later without touching it.

## Running the desktop app

```powershell
# Windows PowerShell, venv active, from the repo root:
python desktop/launch.py
```

What it does:
1. Takes `~/.homemind/backend.lock`. If a healthy backend already holds it,
   the launcher reuses it (no duplicate backend).
2. Starts the backend on `127.0.0.1:8000` (configurable via `HOMEMIND_PORT`)
   and waits up to 60s for `/health`.
3. Prints model status. If Ollama is down you get a clear warning with fix
   steps — chat will show the same error in the UI. No cloud fallback, ever.
4. Starts the Streamlit UI on `127.0.0.1:8501` (`HOMEMIND_UI_PORT`) and opens
   it in a desktop window (pywebview) or browser tab.
5. On window close / Ctrl+C it stops the UI and — only if it started it —
   the backend, then releases the lock. Processes it didn't start are never
   touched.

Environment overrides: `HOMEMIND_PORT`, `HOMEMIND_UI_PORT`,
`HOMEMIND_DATA_DIR`, `HOMEMIND_MODEL`, `HOMEMIND_PROVIDER`.

## Shared state & concurrency

- Single authoritative database: `~/.homemind/homemind.db`
  (override with `HOMEMIND_DATA_DIR`). Browser and desktop read/write the
  same conversations, memories, documents and FTS index.
- SQLite runs in **WAL mode** with a 30s busy timeout, so the two interfaces
  can be used at the same time without "database is locked" failures.
- Upgrades never overwrite user data: migrations are versioned
  (`schema_version` table); the installer must never bundle or delete the
  data directory.
- Export (`GET /export`) and deletion behave identically from either
  interface because both go through the same API.

## Building the Windows distribution

On **Windows 11** (PowerShell, repo root):

```powershell
.\scripts\build_desktop.ps1
```

This runs the test suite, then builds `dist\HomeMindAI.exe` with PyInstaller
(`desktop/homemind.spec`). Create a Start Menu shortcut pointing at the exe —
that is the "normal Windows application shortcut".

> **Honesty note:** the spec and this build script have not been executed on
> Windows in this Linux dev environment. Do not distribute the exe until the
> manual smoke test in `build_desktop.ps1` passes on a real Windows 11
> machine. Code-sign the exe before sharing it.

## Offline behavior

- Installation needs internet: `pip install`, Streamlit/Ollama downloads,
  `ollama pull <model>`.
- After setup, everything runs offline: backend, UI, database, search and
  inference are all loopback-local. The app never phones home.

## Acceptance-test mapping

| # | Requirement | Status |
|---|---|---|
| 1 | Browser chat with local Ollama | Code-complete; needs Ollama on a real machine (not installed on this VM) |
| 2 | Desktop chat with same model | Same as 1 (shared backend) |
| 3 | Conversation created in browser visible in desktop | ✅ Tested (`test_two_handles_share_conversations`) |
| 4 | Memory created in desktop visible in browser | ✅ Tested (`test_two_handles_share_memories`) |
| 5 | Both use the same database | ✅ Tested (same `db_path`, WAL mode) |
| 6 | Ollama stopped → clear error, no cloud fallback | ✅ Tested (provider failure paths; launcher prints guidance) |
| 7 | Closing desktop stops owned processes safely | ✅ Tested (`test_stop_process_*`; never kills unowned PIDs) |
| 8 | Export/delete from both interfaces | ✅ Tested (same API endpoints) |
| 9 | Backend tests pass in CI without a model | ✅ CI uses `HOMEMIND_PROVIDER=mock` |
| 10 | Core features work offline after setup | Code-verified (loopback only, `trust_env=False`); full airplane-mode test needs a real machine |
