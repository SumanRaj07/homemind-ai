# Security Policy & Threat Model — HomeMind AI

## Reporting a vulnerability

Please report security issues privately to the maintainers (see
`CONTRIBUTING.md` for contact details) and give us reasonable time to fix
them before public disclosure. Do not open public issues for vulnerabilities.

## Threat model

### Assets
- User conversations, memories, documents (confidentiality)
- Integrity of the local database (no silent tampering)
- Availability of the local assistant

### Assumed attacker capabilities
1. **Malicious document content** — a PDF/TXT containing prompt-injection
   ("ignore previous instructions…").
2. **Malicious or curious local user input** — path traversal, oversized
   uploads, SQL-looking search strings.
3. **Another local user / malware on the same machine** — out of scope for
   the app itself; mitigated by OS account security and disk encryption.

### Mitigations in place (all tested)

| Threat | Mitigation | Test |
|---|---|---|
| Prompt injection via documents | Retrieved passages fenced as `<retrieved-evidence>` + explicit "untrusted, do not follow" preamble; system instructions preserved | `test_prompt_injection_does_not_override_system` |
| Invented citations | No-evidence path answers with a fixed message *without calling the model* | `test_knowledge_no_evidence_skips_model` |
| Path traversal (uploads) | Filenames sanitized (`_safe_filename`); stored under a per-document id inside `documents/` | `test_filename_sanitized`, `test_upload_filename_traversal_sanitized` |
| Path traversal (workspace tool) | `resolve()` + `relative_to(workspace)` check; `..` rejected | `test_workspace_list_blocks_traversal` |
| Deleting files outside data dir | `remove_document` verifies the path is inside `documents/` before unlink | `test_remove_document_confined_to_documents_dir` |
| FTS/SQL injection | FTS query built from alphanumeric tokens only; bound parameters everywhere | `test_malicious_fts_query_safe` |
| Oversized inputs | Pydantic `max_length` on all text fields; upload size cap (`HOMEMIND_MAX_UPLOAD_MB`) | `test_api_rejects_oversized_message`, `test_upload_size_limit_enforced` |
| Model-generated code execution | The model **cannot invoke tools at all**; tools are user-invoked only; no `eval`/`exec` anywhere | `test_tool_inputs_do_not_execute_code` |
| Consequential actions without consent | Write tools require explicit single-use approval; audit log records every attempt | `test_write_tool_requires_approval`, `test_approval_is_single_use` |
| Sensitive data in logs | No prompt/document/memory content is logged | `test_chat_content_not_logged` |
| Network exposure | API binds `127.0.0.1` by default; internal HTTP bypasses proxies | code review + `test_status` |

### Known limitations (accepted risks for the MVP)

- **No authentication on the local API.** Anyone who can reach
  `127.0.0.1:8000` can use it. This is acceptable for a single-user local app
  but must be revisited before any network exposure.
- **SQLite file is unencrypted.** Protect with OS-level encryption.
- **The mock provider is clearly labelled** (`[mock-model reply]`) so test
  output is never mistaken for a real model.
- **No sandboxing for future code-execution tools.** The tool framework is
  designed for isolated execution later; today only safe read-only tools ship.
  See `docs/ARCHITECTURE.md`.

## Dependency hygiene

- Minimal dependency set (FastAPI, SQLAlchemy, PyMuPDF, Streamlit, …); no
  cloud SDKs, no paid services.
- Pinned with compatible-release ranges in `pyproject.toml`.
- CI runs the full test suite including `tests/security/` on every push.

## Secrets

No secrets are committed. `.gitignore` excludes `.env`, virtualenvs, data
directories and model files. The app itself needs no API keys.
