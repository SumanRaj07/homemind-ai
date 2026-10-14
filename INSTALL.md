# Installation Guide — HomeMind AI (Windows 11)

## 1. Prerequisites

- **Windows 11**, 64-bit
- **Python 3.12** — download from https://www.python.org/downloads/
  (tick *"Add python.exe to PATH"* during setup)
- **Git** — https://git-scm.com/download/win
- **Ollama** — https://ollama.com/download (for real local AI chat)
- ~4 GB free disk space (dependencies + one small model)

Verify in PowerShell:

```powershell
py --version        # Python 3.12.x
git --version
ollama --version
```

## 2. Get the code

```powershell
git clone <your-repo-url> homemind-ai
cd homemind-ai
```

(Or unzip `homemind-ai.zip` and `cd` into it.)

## 3. Create a virtual environment and install

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dev]"
```

> If PowerShell blocks the activation script, run once as Administrator:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

## 4. Install a local model

```powershell
ollama pull llama3.2:3b
```

Other good small options: `qwen2.5:3b`, `phi3:mini`. Larger models
(`llama3.1:8b`) need ~5 GB VRAM. Point HomeMind AI at your model:

```powershell
$env:HOMEMIND_MODEL = "qwen2.5:3b"
```

## 5. Start the backend

```powershell
homemind-api
```

You should see `Uvicorn running on http://127.0.0.1:8000`. The API binds to
**loopback only** — it is not reachable from your network.

## 6. Start the web UI

In a second terminal (venv activated):

```powershell
streamlit run frontend/app.py
```

Open http://127.0.0.1:8501 in your browser.

Alternatively, `python desktop/launch.py` starts both and opens the browser.

## 7. Verify it works

1. Open the UI → **Chat** → create a conversation → send a message.
2. **Settings** should show 🟢 next to your model.
3. **Knowledge Base** → import a PDF → **Search** should return cited passages.
4. **Memory** → add a memory → it appears in the list.

## 8. Running without Ollama (demo / test mode)

```powershell
$env:HOMEMIND_PROVIDER = "mock"
homemind-api
```

The UI and API work end-to-end with deterministic mock replies — useful for
trying the interface before downloading a model.

## 9. Data location & backup

All data lives in `%USERPROFILE%\.homemind\`:

- `homemind.db` — conversations, messages, memories, documents index
- `documents\` — your uploaded files
- `config.json` — saved settings

Back up with:

```powershell
python scripts\backup_db.py --dest D:\backups
```

## 10. Updating

```powershell
git pull
pip install -e ".[dev]"
```

Database migrations run automatically on startup; your data is preserved.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ollama: command not found` | Reopen PowerShell after installing Ollama |
| UI says "Backend is not running" | Start `homemind-api` first |
| 🔴 Model unavailable | Run `ollama serve`, then `ollama pull llama3.2:3b` |
| Model too slow | Use a smaller model (`qwen2.5:1.5b`) or close GPU-heavy apps |
| Port 8000 in use | Set `$env:HOMEMIND_PORT = "8001"` |
| Slow first answer | Ollama loads the model into memory on first use — one-time cost |
