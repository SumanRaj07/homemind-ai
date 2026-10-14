"""Example: chat with memory injection and knowledge-base citations.

Requires a running backend:  homemind-api   (http://127.0.0.1:8000)
"""

import httpx

API = "http://127.0.0.1:8000"


def main() -> None:
    c = httpx.Client(base_url=API, timeout=60)

    # 1. Conversation + memory
    conv = c.post("/conversations", json={"title": "Example chat"}).json()
    cid = conv["id"]
    c.post("/memories", json={
        "content": "The user is training for a 10k run.",
        "category": "fitness",
    })
    print("saved a memory about 10k training")

    # 2. Upload a document
    doc_text = (
        "A 10k training plan: run 3 times per week, one long slow run, "
        "one interval session, one easy recovery run. Rest at least one "
        "day between hard sessions. Increase weekly distance by at most 10%."
    )
    files = {"file": ("training.txt", doc_text.encode())}
    doc = c.post("/documents", files=files).json()
    print("uploaded:", doc["filename"], f"({doc['chunk_count']} chunks)")

    # 3. Plain chat (memory may be injected if relevant)
    r = c.post(f"/conversations/{cid}/chat",
               json={"content": "Any tips for my running this week?"}).json()
    print("\n--- plain chat ---")
    print(r["message"]["content"][:300])

    # 4. Knowledge-grounded chat (cited)
    r = c.post(f"/conversations/{cid}/chat", json={
        "content": "How often should I run each week?",
        "use_knowledge": True,
    }).json()
    print("\n--- knowledge chat ---")
    print(r["message"]["content"][:300])
    for cit in r["citations"]:
        print(f"  cited: [{cit['filename']}] {cit['excerpt'][:80]}...")

    # 5. Cleanup
    c.delete(f"/documents/{doc['id']}")
    print("\ndocument removed again")


if __name__ == "__main__":
    main()
