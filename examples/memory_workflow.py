"""Example: memory lifecycle — create, search, update, export, delete."""

import json

import httpx

API = "http://127.0.0.1:8000"


def main() -> None:
    c = httpx.Client(base_url=API, timeout=30)

    m = c.post("/memories", json={
        "content": "User's anniversary is June 14.",
        "category": "personal",
        "tags": ["family"],
        "source": "example script",
    }).json()
    print("created:", m["id"])

    found = c.get("/memories", params={"q": "anniversary"}).json()
    print("search hits:", len(found))

    updated = c.patch(f"/memories/{m['id']}",
                      json={"tags": ["family", "reminder"]}).json()
    print("updated tags:", updated["tags"])

    export = c.get("/export").json()
    with open("memory-export-example.json", "w", encoding="utf-8") as f:
        json.dump(export["memories"], f, indent=2)
    print("exported memories to memory-export-example.json")

    c.delete(f"/memories/{m['id']}")
    print("deleted again; remaining:", len(c.get("/memories").json()))


if __name__ == "__main__":
    main()
