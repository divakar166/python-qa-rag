---
marp: true
theme: uncover
class:
  - lead
  - invert
paginate: true
backgroundColor: #1a1a2e
color: #eaeaea
style: |
  section {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
  }
  h1 {
    color: #00d4ff;
    font-size: 2.2em;
    margin-bottom: 0.3em;
  }
  h2 {
    color: #00d4ff;
    font-size: 1.6em;
    margin-bottom: 0.4em;
  }
  ul {
    list-style: none;
    padding-left: 0;
  }
  li {
    margin: 0.4em 0;
    font-size: 0.95em;
    line-height: 1.5;
    padding-left: 1.5em;
    position: relative;
  }
  li::before {
    content: "▸";
    color: #00d4ff;
    position: absolute;
    left: 0;
  }
  code {
    background: #16213e;
    color: #00d4ff;
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-size: 0.85em;
  }
  strong {
    color: #ffffff;
  }
  .small {
    font-size: 0.75em;
    color: #8899aa;
  }
  .mermaid {
    background: #16213e;
    padding: 1em;
    border-radius: 8px;
    margin: 1em 0;
  }
  section.lead p {
    color: #8899aa;
  }
  footer {
    font-size: 0.6em;
    color: #556677;
  }
  table {
    margin: 0.5em auto;
    font-size: 0.75em;
    border-collapse: collapse;
  }
  th, td {
    border: 1px solid #334;
    padding: 0.3em 0.6em;
    text-align: left;
  }
  th {
    background: #16213e;
    color: #00d4ff;
  }
  td {
    background: #1a1a2e;
  }
---

<!-- _class: lead invert -->
<!-- _paginate: false -->

# **Python QA RAG Assistant**

**Retrieval-Augmented Generation for Python Q&A**

<br>

<div class="small">
  AI Engineer Assessment<br>
  Candidate Name<br>
  June 2026
</div>

---

## **Problem Statement**

Build a Q&A assistant that answers Python programming questions using grounded Stack Overflow knowledge.

- Users ask natural-language Python questions
- System retrieves relevant Q&A from a curated corpus
- LLM generates answers **strictly from retrieved context**
- Every answer includes **source attribution** (scores, titles, tags)
- Expose via a clean REST API + web chat UI

<!-- _footer: "Requirement: grounded, traceable, deployable" -->

---

## **Dataset & Data Processing**

**Source:** Kaggle Stack Overflow Python Questions Dataset

- Raw dataset: ~380K Stack Overflow Python questions
- Cleaning pipeline (BeautifulSoup HTML stripping):
  - Filtered questions with `score ≥ 2`
  - Selected top-3 answers per question by vote
  - Stripped HTML tags from body and answers
- Constructed `document` field: `Title + Tags + Question + Top Answers`
- **Final corpus: ~175K high-quality documents**

<!-- _footer: "Data Cleaning.ipynb → stack_overflow_rag.parquet (240 MB)" -->

---

## **System Architecture**

```
┌────────┐   ┌─────────┐   ┌──────────┐   ┌─────────┐
│  User  │──▶│ FastAPI  │──▶│  Qdrant  │──▶│   LLM   │
│(Browser)│  │  Server  │   │  Cloud   │   │ (NVIDIA)│
└────────┘   └─────────┘   └──────────┘   └─────────┘
                  │               │              │
                  ▼               ▼              ▼
            Chat UI (HTML)   Vectors (384d)   Meta-Llama
                             all-MiniLM-L6-v2  3.3-70B
```

- **FastAPI** — async Python web server with 3 endpoints
- **Qdrant Cloud** — vector database with server-side embedding inference
- **LLM API** — OpenAI-compatible (NVIDIA), temperature=0 for determinism

<!-- _footer: "Stack: FastAPI + Qdrant Cloud + OpenAI SDK + Docker" -->

---

## **RAG Pipeline**

| Stage | Component | Detail |
|-------|-----------|--------|
| **I**ngestion | `ingestion.py` | Batch-upserts ~175K docs to Qdrant (100/batch) |
| **E**mbedding | Qdrant Cloud Inference | `all-MiniLM-L6-v2` → 384-dim vectors |
| **R**etrieval | `qdrant_client.query_points()` | Cosine similarity, top-5 |
| **G**eneration | OpenAI Chat Completions | Context-grounded system prompt → answer |

- Embedding computed server-side by Qdrant (no local model)
- Context block: 5 documents joined with `\n\n---\n\n`
- System prompt enforces: *"Answer based only on context"*

<!-- _footer: "Single dense embedding model — no hybrid search yet" -->

---

## **API & Deployment**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serves chat UI (vanilla HTML/JS) |
| `/health` | GET | Returns Qdrant connection status |
| `/ask` | POST | Accepts `{"question": "..."}` → answer + sources |

- **Validation:** question 10–1000 chars, Pydantic models
- **Error handling:** 404 (no docs), 422 (validation), 502 (upstream failure)
- **Deployment:** Docker → Hugging Face Spaces 🌊
  - Environment variables as Space Secrets
  - `uvicorn app.api:app --host 0.0.0.0 --port 8000`

<!-- _footer: "Live: huggingface.co/spaces/divakarsingh166/python-qa-rag-assistant" -->

---

## **Testing & Evaluation**

**Unit Tests** (13 tests, pytest-asyncio + httpx)
- All endpoints: success, failure, validation, edge cases
- Mocked Qdrant + LLM clients for deterministic runs

**Evaluation** (12 queries against live API)
```
╔════════════════════════╤══════════╤═══════════╗
║ Query                  │ Relevant │ Correct   ║
╠════════════════════════╪══════════╪═══════════╣
║ Virtual environment    │ ✓        │ ✓         ║
║ Decorators             │ ✓        │ ✓         ║
║ Exception handling     │ ✓        │ ✓         ║
║ Async/await            │ ✓        │ ✓         ║
║ GIL                    │ ~ partial│ ✓         ║
║ Empty question (edge)  │ N/A      │ 422 error ║
╚════════════════════════╧══════════╧═══════════╝
```

<!-- _footer: "All 9 valid queries returned relevant + correct answers" -->

---

## **Observations & Limitations**

**What works well:**
- High relevance for common Python topics (decorators, async, OOP)
- Source attribution provides user trust and verifiability
- Deterministic LLM (temp=0) gives consistent answers

**Known limitations:**
- ⏱ **Timeout risk** — external LLM calls can hang; no client-side timeout
- 📡 **Retrieval gaps** — single dense embedding misses keyword-critical matches
- 📚 **Dataset coverage** — dated Stack Overflow data; niche libraries sparse
- 🔄 **No caching** — identical questions re-query Qdrant + LLM each time

<!-- _footer: "Documented in evaluation/evaluation_results.md" -->

---

## **Scaling to 100+ Concurrent Users**

| Strategy | Implementation |
|----------|---------------|
| **Async I/O** | FastAPI async handlers + `httpx.AsyncClient` |
| **Redis caching** | Cache (question → answer) for frequent queries, TTL-based invalidation |
| **Horizontal scaling** | Stateless app → multiple Docker replicas behind load balancer |
| **Load balancing** | nginx / Traefik — round-robin across replicas |
| **Qdrant clustering** | Qdrant Cloud auto-scales; shard + replicate collection |

- Estimated throughput: **~200 req/s** with 3–5 app replicas + Redis cache hit ratio > 40%
- LLM calls are the bottleneck — caching and async are critical

<!-- _footer: "Key: stateless app + cache external calls + scale horizontally" -->

---

## **Future Improvements & Conclusion**

**Planned enhancements:**
- 🔍 **Hybrid search** — dense + sparse (BM25) retrieval for better recall
- 📊 **Reranking** — cross-encoder to re-rank top-20 before LLM
- ⚡ **Streaming responses** — token-by-token via SSE for better UX
- ✅ **Confidence scoring** — low-confidence fallback responses
- 🛡️ **Rate limiting + auth** — API key validation, tenant isolation

**Conclusion:**
The Python QA RAG Assistant delivers a **production-ready, grounded Q&A system** with clear architecture, comprehensive testing, and a path to scale. Designed for maintainability and extension.

<!-- _footer: "github.com/divakarsingh166/python-qa-rag-assistant" -->
