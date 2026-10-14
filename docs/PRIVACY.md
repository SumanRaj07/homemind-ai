# Privacy Model — HomeMind AI

## Principle

Your data stays on your computer. HomeMind AI is designed so that **no
personal content ever needs to leave the machine it runs on**.

## What is stored, and where

Everything lives under `%USERPROFILE%\.homemind\` (overridable with
`HOMEMIND_DATA_DIR`):

| Data | File | Contains |
|---|---|---|
| Conversations & messages | `homemind.db` (SQLite) | Your chats, per-conversation system instructions |
| Memories | `homemind.db` | Facts you explicitly saved (+ category/tags/source) |
| Documents & search index | `homemind.db` + `documents/` | Your uploaded PDFs/TXTs and their text chunks |
| Tool audit log | `homemind.db` | Tool name, permission, outcome, input summary |
| Settings | `config.json` | Model name, provider, UI preferences |

There is no account, no telemetry, no analytics, no crash reporting.

## What is NOT stored or sent anywhere

- **No cloud fallback.** If Ollama is unreachable, the app tells you how to
  fix it — it never reroutes your prompt to an external API.
- **No prompt logging.** Message content, document text and memory content are
  never written to log files (enforced by `tests/privacy/test_privacy.py`).
- **No silent memorization.** Conversations are never automatically converted
  into permanent memories. A memory exists only if you created it.

## Network behavior (verified)

| Situation | Network use |
|---|---|
| Normal chat, memory, search | None — loopback HTTP to Ollama (`127.0.0.1:11434`) and to the API (`127.0.0.1:8000`) only. Internal clients bypass proxy env vars (`trust_env=False`). |
| Installation | Internet needed: `pip install`, Ollama download, `ollama pull <model>`. |
| After setup | Fully offline-capable. Set `HOMEMIND_OFFLINE_MODE=true` to surface this in the UI. |

> We do **not** claim the product is "completely offline" merely because
> inference is local: installation and model downloads require internet, and
> the user may optionally change the Ollama URL. The table above is the
> honest accounting.

## Your controls

- **Inspect** everything: Chat, Memory, Knowledge and Tools screens show the
  raw stored data.
- **Export** everything: Settings → *Export all data (JSON)*, or `GET /export`.
- **Delete** everything: per-item delete buttons, plus bulk
  `DELETE /data/conversations` and `DELETE /data/memories`
  (the UI's "clear all memories" requires an explicit confirmation checkbox).
- **Back up**: `python scripts/backup_db.py` copies the SQLite file.

Deleting a memory removes it from the database immediately, and because chat
context is assembled from a live query, the deleted memory can never appear
in a later prompt (tested).

## Limits of the privacy promise

- Anyone with access to your Windows user account can read
  `%USERPROFILE%\.homemind`. Use OS-level disk encryption / account passwords
  for protection against other local users.
- The tool **audit log** stores a short *input summary* (first 500 chars of
  the JSON inputs) so you can review what tools did. Treat it as sensitive
  too — it is included in export/deletion.
- Documents you import are *yours*, but treat their *contents* as untrusted:
  the app fences retrieved passages as non-instructional evidence.
