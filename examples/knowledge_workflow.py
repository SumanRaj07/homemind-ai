"""Example: build a tiny knowledge base, search it, then clean up."""

import httpx

API = "http://127.0.0.1:8000"


def main() -> None:
    c = httpx.Client(base_url=API, timeout=60)

    text = (
        "HomeMind AI runs entirely on your own computer. Conversations are "
        "stored in a local SQLite database. Documents are indexed with "
        "SQLite FTS5 for full-text search. The default model backend is "
        "Ollama, which serves small quantized models on loopback."
    )
    doc = c.post("/documents",
                 files={"file": ("homemind-notes.txt", text.encode())}).json()
    print("uploaded:", doc["filename"])

    res = c.post("/knowledge/search",
                 json={"query": "where are conversations stored", "limit": 3}).json()
    for p in res["passages"]:
        page = f"p.{p['page_number']}" if p["page_number"] else "p.?"
        print(f"- [{p['filename']} {page}] {p['text'][:100]}...")

    c.post("/knowledge/rebuild")
    print("index rebuilt")

    c.delete(f"/documents/{doc['id']}")
    print("document removed; passages now:",
          len(c.post("/knowledge/search",
                     json={"query": "conversations stored"}).json()["passages"]))


if __name__ == "__main__":
    main()
