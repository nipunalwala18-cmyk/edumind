# EduMind — Institutional Knowledge Engine

EduMind is a RAG-based assistant that answers questions about a college's SOPs, policies, circulars, and other internal documentation. Instead of digging through shared drives and PDFs, staff and students can just ask — "what's the minimum attendance to sit for exams?", "who approves a purchase over ₹50,000?" — and get an answer with a citation pointing back to the exact document and section it came from.

It was built against Vidyalankar Institute of Technology's SOP corpus (20 documents across 20 departments — admissions, examinations, finance, placements, and so on), but the pipeline is generic enough to point at any set of institutional `.docx` files.

## Why this exists

Plain keyword search breaks down the moment someone phrases a question differently than the document does. Plugging a raw LLM in doesn't help either — it'll happily answer from its training data instead of your actual policy, which is exactly what you don't want in a compliance-sensitive setting. EduMind retrieves the relevant passages first and forces the model to answer only from those, with a citation attached to every claim.

## How it works

```
.docx documents
      │
      ▼
Ingestion & chunking (dedup via SHA-256, table-aware extraction)
      │
      ▼
Embeddings (BAAI/bge-base-en-v1.5)  ──►  ChromaDB
      │
      ▼
Query comes in ──► Dense search + BM25 ──► Reciprocal Rank Fusion
      │
      ▼
Cross-encoder reranking (bge-reranker-base)
      │
      ▼
LangGraph agents: analyze → plan → retrieve → validate → generate → cite → score confidence
   (low confidence triggers another retrieval pass instead of just guessing)
      │
      ▼
Qwen2.5:7B (Ollama, local) or HF Inference API ──► cited answer
```

Retrieval is hybrid on purpose: dense embeddings catch paraphrased questions, BM25 catches exact codes and identifiers (circular numbers, subject codes) that embeddings tend to blur. RRF merges the two ranked lists before reranking narrows things down to the chunks that actually matter.

## Stack

| Layer                   | Technology                                                                         |
| ----------------------- | ---------------------------------------------------------------------------------- |
| **Backend**             | FastAPI                                                                            |
| **Frontend**            | Vanilla HTML/CSS/JavaScript (single-page application served from `/frontend`)      |
| **Vector Store**        | ChromaDB                                                                           |
| **Embeddings**          | `BAAI/bge-base-en-v1.5`                                                            |
| **Reranker**            | `BAAI/bge-reranker-base`                                                           |
| **LLM**                 | `Qwen2.5:7B` via Ollama (default), with support for the Hugging Face Inference API |
| **Agent Orchestration** | LangGraph                                                                          |
| **Authentication**      | JWT + bcrypt                                                                       |
| **Database**            | SQLite (users, chat history, ingestion ledger)                                     |
| **Testing**             | pytest (500+ tests covering ingestion, retrieval, generation, and authentication)  |


## Getting started

### Option A — Docker (recommended)

```bash
cd docker
docker compose up --build
```

This spins up two containers: Ollama (pulls `qwen2.5:7b` on first run — takes a few minutes) and the FastAPI app on port 8000. Once both are healthy, open `http://localhost:8000`.

Default seeded accounts (change these before doing anything real with it):

| Role | Username | Password |
|---|---|---|
| Public | `public_user` | `Public@123` |
| Student | `student_test` | `Student@123` |
| Faculty | `faculty_test` | `Faculty@123` |
| Admin | `admin_test` | `Admin@123` |

### Option B — Run it locally

You'll need Python 3.11+, [Ollama](https://ollama.com) installed and running, and the `qwen2.5:7b` model pulled (`ollama pull qwen2.5:7b`).

```bash
python -m venv .venv
source .venv/bin/activate      # .venv\Scripts\activate on Windows
pip install -r requirements.txt

python seed_users.py           # creates institutional.db with the test accounts above
uvicorn backend.app:app --reload --port 8000
```

### Loading your own documents

Drop `.docx` files into `data/staging/`, then run:

```bash
python ingestion_pipeline.py   # extracts, cleans, chunks, dedups
```

This writes to `ingestion_ledger.db` for audit purposes and produces chunk records ready for embedding. `chunk_validation.py` will sanity-check the output afterwards (chunk sizes, missing metadata, id collisions) and drop a report at `chunk_validation_report.md`.

Admins can also upload documents through the UI directly, and Faculty who are marked as committee heads can submit documents for review — those sit in a pending queue until an admin approves them, at which point they go through the same ingestion pipeline. Nothing gets embedded without someone signing off on it first.

## Configuration

Everything is read from environment variables (put them in a `.env` file at the project root, or pass them via `docker-compose.yml`):

```bash
JWT_SECRET_KEY=some-long-random-string     # do NOT use the default in production
OLLAMA_BASE_URL=http://localhost:11434     # or http://ollama:11434 inside Docker

# Optional: switch the LLM backend to HuggingFace's hosted inference API
LLM_BACKEND=hf
HF_TOKEN=hf_xxxxxxxx
HF_MODEL=Qwen/Qwen2.5-7B-Instruct
```

## Running the tests

```bash
pytest                    # everything
pytest -m "not slow"      # skip the tests that need a live ChromaDB/BGE model
```

There's also `verify_rag.py`, which is a read-only script that pokes every stage of the pipeline (embedder, retriever, reranker, RAG engine) with real queries and prints what came back — useful for a quick gut-check after changing something, without waiting on the full test suite.

## Project layout

```
backend/          FastAPI app, auth, document management, committee approval workflow
agents/           LangGraph agent definitions and the multi-agent graph
rag/              Prompt building, citation engine, Ollama/HF clients, RAG engine
retrieval/        BM25, dense search, RRF fusion, reranking
frontend/         HTML/CSS/JS single-page app
tests/            pytest suite
scripts/          one-off utilities (retrieval evaluation, ledger restore, colab tunnel)
docker/           Dockerfile, docker-compose.yml, container startup script
ingestion_pipeline.py, chunker.py, chunk_validation.py   ingestion + QA scripts
seed_users.py     creates the four test accounts
demo.py           read-only CLI that prints current project status/stats
```

## Access control

Every chunk carries an access level (`Public` / `Student` / `Faculty` / `Admin`), checked against the requester's role before it's allowed into a retrieval result — so a student asking a question will never see a chunk tagged Faculty-only, regardless of how the query is phrased.

## Known limitations

- No live sync with an ERP; documents have to be ingested manually or through the upload/approval flow.
- The Ollama backend needs a reasonably capable machine (or GPU) to keep response times sane; the HF Inference API is there as a lighter-weight alternative if local compute is tight.
