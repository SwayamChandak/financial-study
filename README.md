# Financial Study — LangGraph Agent System

A LangGraph-based system for studying financial education material (Zerodha Varsity PDFs). Features PDF ingestion into a Qdrant vector store, an AI-powered study pipeline that generates chapter summaries while tracking progress, a chatbot with RAG over studied content, and quiz generation.

## Project Structure

```
financial-study/
├── config/
│   └── settings.py              # Application settings (Pydantic), LangSmith wiring
├── data/                        # Source PDFs and generated markdown output
├── frontend/
│   ├── cli.py                   # Interactive CLI chatbot
│   ├── server.py                # FastAPI server (chat + quiz + teach endpoints)
│   ├── static/                  # Built frontend assets
│   └── ui/                      # Vite-based frontend source
├── graph/
│   ├── graph_builder.py         # StateGraph assembly (study + chat)
│   ├── state.py                 # StudyState TypedDict
│   ├── chat_nodes.py            # Chatbot nodes (guardrail, RAG, validation)
│   └── study_nodes.py           # Study pipeline nodes (filter, summarise, validate, update)
├── ingestion/
│   ├── chunker.py               # PDF chunking with preamble/comments stripping
│   ├── embedder.py              # HuggingFace embeddings
│   ├── loader.py                # PDF loading with metadata extraction
│   ├── pipeline.py              # Pipeline orchestrator
│   └── store.py                 # Qdrant vector store operations
├── memory/
│   ├── chat_memory.py           # Redis-backed conversation memory
│   └── progress.py              # Redis-backed reading progress tracking
├── quiz/
│   └── quiz_service.py          # MCQ generation and grading from seen content
├── main.py                      # Entry point (ingest / run / chat)
├── .env.example
├── pyproject.toml
├── requirements.txt
└── hld.md                       # High-level design document
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
cp .env.example .env
```

## Running

### Ingestion pipeline

```bash
python main.py ingest --source-dir data
```

Loads PDFs, chunks them, generates embeddings, and stores them in Qdrant.

### Study workflow

```bash
python main.py run
```

Runs the daily study graph: reads current position from Redis, fetches chunks from Qdrant, generates an LLM summary, validates it (with retries), and advances progress.

### CLI chatbot

```bash
python -m frontend.cli
```

Interactive chatbot with guardrails and RAG over studied (seen) Qdrant content.

### Web server + UI

```bash
cd frontend/ui
npm run build
cd ../..
uv run python -m frontend.server
```

Opens a FastAPI server at http://127.0.0.1:8000 with chat, quiz generation/submission, and teach endpoints.

### One-off query

```bash
python main.py chat "your question"
```

## Graphs

### Study graph
`START → filter_by_memory → summarise_chunks → validate_summary → (valid → update_progress → END | retry → summarise_chunks | max_retries → update_progress → END)`

### Chat graph
`START → guardrail_node → (flagged → END | clean → rag_lookup_node) → (evidence_missing → END | has_evidence → validate_response_node) → (valid → END | retry → rag_lookup_node | max_retries → END)`

## Configuration

Settings are loaded from `.env` via Pydantic `BaseSettings`. Key variables:

| Variable | Default | Description |
|---|---|---|
| `LLM_CHAT_MODEL_NAME` | `ollama:llama3.2` | Chat model provider string |
| `LLM_STUDY_MODEL_NAME` | `ollama:llama3.2` | Study summary model provider string |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector store URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis progress & memory URL |
| `LANGSMITH_PROJECT` | `financial-study` | LangSmith tracing project name |
