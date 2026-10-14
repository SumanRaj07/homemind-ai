"""HomeMind AI — local web interface (Streamlit).

Talks to the FastAPI backend over loopback HTTP. No demo data: every screen
reads from and writes to the real backend.
"""

from __future__ import annotations

import json
import os

import httpx
import streamlit as st

API_URL = os.environ.get("HOMEMIND_API_URL", "http://127.0.0.1:8000")


def api(method: str, path: str, **kwargs):
    try:
        resp = httpx.request(method, f"{API_URL}{path}", timeout=60,
                        trust_env=False, **kwargs)
    except (httpx.ConnectError, httpx.TimeoutException):
        st.error(
            "Cannot reach the HomeMind AI backend. Start it first:\n\n"
            "`homemind-api`  or  `python -m homemind.api.app`"
        )
        st.stop()
    if resp.status_code >= 400:
        try:
            detail = resp.json()["error"]["message"]
        except Exception:
            detail = resp.text[:300]
        st.error(f"Request failed ({resp.status_code}): {detail}")
        st.stop()
    if resp.status_code == 204:
        return None
    return resp.json()


def api_stream_post(path: str, payload: dict):
    """Yield SSE text chunks; surfaces error events as exceptions."""
    with httpx.stream(
        "POST", f"{API_URL}{path}", json=payload, timeout=300,
        trust_env=False
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line.startswith("event: error"):
                # next data line carries the message
                continue
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                yield data


st.set_page_config(page_title="HomeMind AI", page_icon="🧠", layout="wide")
st.title("🧠 HomeMind AI")

# ---- backend status banner ------------------------------------------------- #
try:
    health = httpx.get(f"{API_URL}/health", timeout=5, trust_env=False).json()
    status = httpx.get(f"{API_URL}/status", timeout=10, trust_env=False).json()
    backend_ok = True
except Exception:
    backend_ok = False
    status = {}

if not backend_ok:
    st.error(
        "Backend is not running. Start it with `homemind-api`, then reload this page."
    )
    st.stop()

model_dot = "🟢" if status.get("model_available") else "🔴"
offline = " (offline mode)" if status.get("offline_mode") else ""
st.caption(
    f"{model_dot} Model: `{status.get('model')}` via {status.get('provider')}{offline}  ·  "
    f"{status.get('conversations', 0)} conversations · "
    f"{status.get('memories', 0)} memories · {status.get('documents', 0)} documents"
)
if not status.get("model_available"):
    st.warning(status.get("model_message", "Model unavailable."))

# ---- navigation ------------------------------------------------------------ #
section = st.sidebar.radio(
    "Navigate",
    ["Chat", "Conversations", "Memory", "Knowledge Base", "Tools", "Settings"],
)

# =============================================================================
# CHAT
# =============================================================================
if section == "Chat":
    convs = api("GET", "/conversations") or []
    if not convs:
        if st.button("➕ Start your first conversation"):
            conv = api("POST", "/conversations", json={"title": "First chat"})
            st.session_state["conv_id"] = conv["id"]
            st.rerun()
        st.info("No conversations yet. Create one to start chatting.")
    else:
        options = {c["id"]: f"{c['title']} ({c['message_count']})" for c in convs}
        default_id = st.session_state.get("conv_id") or convs[0]["id"]
        idx = list(options).index(default_id) if default_id in options else 0
        conv_id = st.selectbox(
            "Conversation",
            list(options),
            index=idx,
            format_func=lambda i: options[i],
            key="conv_id",
        )

        use_knowledge = st.toggle(
            "Use knowledge base",
            help="Retrieve passages from your documents and cite them.",
        )

        messages = api("GET", f"/conversations/{conv_id}/messages") or []
        for m in messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        if prompt := st.chat_input("Ask HomeMind AI..."):
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                placeholder = st.empty()
                full = ""
                try:
                    for chunk in api_stream_post(
                        f"/conversations/{conv_id}/chat",
                        {"content": prompt, "use_knowledge": use_knowledge,
                         "stream": True},
                    ):
                        full += chunk
                        placeholder.markdown(full + "▌")
                    placeholder.markdown(full)
                except Exception as exc:
                    st.error(f"Generation failed: {exc}")
            st.rerun()

# =============================================================================
# CONVERSATIONS
# =============================================================================
elif section == "Conversations":
    st.header("Conversations")
    with st.expander("➕ New conversation"):
        title = st.text_input("Title", value="New conversation")
        sys_inst = st.text_area("System instructions (optional)", height=80)
        if st.button("Create"):
            api("POST", "/conversations",
                json={"title": title, "system_instructions": sys_inst})
            st.success("Created.")
            st.rerun()

    convs = api("GET", "/conversations") or []
    for c in convs:
        with st.expander(f"💬 {c['title']}  — {c['message_count']} messages"):
            new_title = st.text_input("Rename", value=c["title"], key=f"t_{c['id']}")
            new_sys = st.text_area(
                "System instructions", value=c["system_instructions"],
                key=f"s_{c['id']}", height=80,
            )
            col1, col2, col3 = st.columns(3)
            if col1.button("💾 Save", key=f"sv_{c['id']}"):
                api("PATCH", f"/conversations/{c['id']}",
                    json={"title": new_title, "system_instructions": new_sys})
                st.rerun()
            if col2.button("🧹 Clear messages", key=f"cl_{c['id']}"):
                api("POST", f"/conversations/{c['id']}/clear")
                st.rerun()
            if col3.button("🗑️ Delete", key=f"dl_{c['id']}"):
                api("DELETE", f"/conversations/{c['id']}")
                st.rerun()

# =============================================================================
# MEMORY
# =============================================================================
elif section == "Memory":
    st.header("Memory")
    st.caption("Memories are only created when you explicitly add them — "
               "conversations are never silently saved as memories.")

    q = st.text_input("🔍 Search memories")
    cat = st.text_input("Filter by category (optional)")
    mems = api("GET", "/memories", params={"q": q or None, "category": cat or None}) or []
    st.write(f"{len(mems)} memories")

    with st.expander("➕ Add a memory"):
        content = st.text_area("Content")
        category = st.text_input("Category", value="general")
        tags = st.text_input("Tags (comma-separated)")
        source = st.text_input("Source (optional)")
        if st.button("Save memory"):
            if not content.strip():
                st.warning("Content is required.")
            else:
                api("POST", "/memories", json={
                    "content": content,
                    "category": category,
                    "tags": [t.strip() for t in tags.split(",") if t.strip()],
                    "source": source,
                })
                st.success("Memory saved.")
                st.rerun()

    for m in mems:
        with st.expander(f"[{m['category']}] {m['content'][:80]}"):
            st.write(m["content"])
            st.caption(f"tags: {', '.join(m['tags']) or '—'} · source: {m['source'] or '—'}")
            new_content = st.text_area("Edit content", value=m["content"],
                                       key=f"mc_{m['id']}", height=100)
            if st.button("💾 Save changes", key=f"ms_{m['id']}"):
                api("PATCH", f"/memories/{m['id']}", json={"content": new_content})
                st.rerun()
            if st.button("🗑️ Delete", key=f"md_{m['id']}"):
                api("DELETE", f"/memories/{m['id']}")
                st.rerun()

    st.divider()
    data = api("GET", "/export")
    st.download_button("⬇️ Export all data (JSON)",
                       data=json.dumps(data, indent=2),
                       file_name="homemind-export.json",
                       mime="application/json")
    st.warning("Danger zone")
    confirm = st.checkbox("I understand this deletes ALL memories permanently")
    if st.button("Clear all memories", disabled=not confirm):
        api("DELETE", "/memories", params={"confirm": "true"})
        st.rerun()

# =============================================================================
# KNOWLEDGE BASE
# =============================================================================
elif section == "Knowledge Base":
    st.header("Knowledge Base")

    uploaded = st.file_uploader("Import a document", type=["pdf", "txt"])
    if uploaded and st.button("📥 Import"):
        files = {"file": (uploaded.name, uploaded.getvalue())}
        try:
            resp = httpx.post(f"{API_URL}/documents", files=files, timeout=120,
                    trust_env=False)
            if resp.status_code == 201:
                st.success(f"Imported: {resp.json()['filename']}")
                st.rerun()
            else:
                st.error(resp.json()["error"]["message"])
        except Exception as exc:
            st.error(f"Upload failed: {exc}")

    st.subheader("Search documents")
    query = st.text_input("Query")
    if query and st.button("🔍 Search"):
        res = api("POST", "/knowledge/search", json={"query": query, "limit": 5})
        if not res["passages"]:
            st.info("No relevant passages found.")
        for p in res["passages"]:
            page = f"p.{p['page_number']}" if p["page_number"] else "p.?"
            st.markdown(f"**[{p['filename']} {page}]**")
            st.write(p["text"][:600])

    st.subheader("Indexed documents")
    docs = api("GET", "/documents") or []
    for d in docs:
        col1, col2 = st.columns([4, 1])
        col1.write(f"📄 **{d['filename']}** — {d['page_count']} pages, "
                   f"{d['chunk_count']} chunks")
        if col2.button("🗑️", key=f"dd_{d['id']}"):
            api("DELETE", f"/documents/{d['id']}")
            st.rerun()
    if st.button("🔄 Rebuild search index"):
        res = api("POST", "/knowledge/rebuild")
        st.success(f"Rebuilt: {res['indexed_chunks']} chunks indexed.")

# =============================================================================
# TOOLS
# =============================================================================
elif section == "Tools":
    st.header("Tools")
    st.caption("Read-only tools run immediately. Anything consequential "
               "requires your explicit approval.")

    tools = api("GET", "/tools") or []
    tool_names = [t["name"] for t in tools]
    chosen = st.selectbox("Tool", tool_names)
    info = next(t for t in tools if t["name"] == chosen)
    st.write(f"**{info['name']}** ({info['permission']}) — {info['description']}")
    st.json(info["input_schema"])
    raw_inputs = st.text_area("Inputs (JSON)", value="{}")
    if st.button("▶ Run tool"):
        try:
            inputs = json.loads(raw_inputs or "{}")
        except json.JSONDecodeError:
            st.error("Inputs must be valid JSON.")
            st.stop()
        res = api("POST", f"/tools/{chosen}/execute", json={"inputs": inputs})
        if res["status"] == "approval_required":
            st.warning("This tool needs your approval to run.")
            st.session_state["approval_id"] = res["approval_id"]
            st.session_state["approval_tool"] = chosen
        elif res["status"] == "executed":
            st.json(res["result"])
        else:
            st.error(res["message"])

    if "approval_id" in st.session_state:
        st.divider()
        st.write(f"Pending approval for **{st.session_state['approval_tool']}**")
        c1, c2 = st.columns(2)
        if c1.button("✅ Approve and run"):
            res = api("POST",
                      f"/tools/approvals/{st.session_state['approval_id']}/resolve",
                      json={"approve": True})
            del st.session_state["approval_id"]
            if res["status"] == "executed":
                st.json(res["result"])
            else:
                st.error(res["message"])
        if c2.button("❌ Reject"):
            api("POST", f"/tools/approvals/{st.session_state['approval_id']}/resolve",
                json={"approve": False})
            del st.session_state["approval_id"]
            st.info("Rejected.")

# =============================================================================
# SETTINGS
# =============================================================================
elif section == "Settings":
    st.header("Settings")

    st.subheader("Model")
    st.write(f"Provider: `{status.get('provider')}`")
    st.write(f"Model: `{status.get('model')}`")
    st.write("Availability:", status.get("model_message", ""))
    if status.get("provider") == "ollama" and not status.get("model_available"):
        st.info("Install Ollama from https://ollama.com, run `ollama serve`, "
                "then `ollama pull <model>` (e.g. `llama3.2:3b`).")

    st.subheader("Storage")
    st.code(status.get("db_path", ""))
    st.write(f"Offline mode: **{status.get('offline_mode')}**")

    st.subheader("Privacy")
    st.write(
        "HomeMind AI stores conversations, memories, documents and settings in a "
        "local SQLite database on this computer. Nothing is sent to the cloud: "
        "inference runs against your local Ollama server (or the mock provider "
        "in test mode). Prompts, document contents and memory contents are not "
        "written to log files. See `docs/PRIVACY.md` for the full privacy model."
    )

    st.subheader("Diagnostics (no sensitive data)")
    st.json({
        "backend": "ok",
        "provider": status.get("provider"),
        "model_available": status.get("model_available"),
        "offline_mode": status.get("offline_mode"),
        "counts": {
            "conversations": status.get("conversations"),
            "memories": status.get("memories"),
            "documents": status.get("documents"),
        },
    })

    st.subheader("Data management")
    data = api("GET", "/export")
    st.download_button("⬇️ Export all data (JSON)",
                       data=json.dumps(data, indent=2),
                       file_name="homemind-export.json",
                       mime="application/json")
    st.warning("Danger zone")
    if st.button("Delete ALL conversations"):
        api("DELETE", "/data/conversations")
        st.rerun()
    confirm = st.checkbox("I understand this deletes ALL memories permanently",
                          key="mem_confirm")
    if st.button("Delete ALL memories", disabled=not confirm):
        api("DELETE", "/data/memories")
        st.rerun()
