# Example workflows — HomeMind AI

These scripts talk to a running backend (`homemind-api` on
`http://127.0.0.1:8000`). They use only the standard library plus `httpx`
(`pip install httpx` if needed).

## 1. Chat with memory and knowledge (`examples/chat_with_memory.py`)

- Creates a conversation, saves a memory, uploads a document.
- Chats twice: once normally, once with `use_knowledge=True` (cited answer).

## 2. Manage memories (`examples/memory_workflow.py`)

- Create → search → update → export → delete a memory.

## 3. Build a knowledge base (`examples/knowledge_workflow.py`)

- Upload a TXT, search it, show citations, then remove the document.

Run any of them with:

```bash
python examples/chat_with_memory.py
```
