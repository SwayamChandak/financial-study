# Financial Study — LangGraph Agent System

A multi-agent LangGraph project for financial research, analysis, and reporting.

## Project Structure

```
financial-study/
├── agents/                     # Agent definitions
│   ├── research_agent/         # Fetches and gathers financial data
│   ├── analysis_agent/         # Analyses market data and financials
│   ├── portfolio_agent/        # Portfolio management decisions
│   └── report_agent/           # Generates structured reports
│
├── graph/                      # LangGraph graph construction
│   ├── builder.py              # StateGraph assembly
│   ├── nodes.py                # Node functions
│   └── edges.py                # Edge / routing logic
│
├── state/
│   └── schema.py               # Shared graph state schema (TypedDict / Pydantic)
│
├── tools/                      # LangChain tools used by agents
│   ├── market_data.py          # Market price / OHLCV tools
│   ├── financial_statements.py # Balance sheet, income, cash-flow tools
│   └── news_search.py          # Financial news search tools
│
├── mcp/                        # Model Context Protocol servers
│   ├── servers/
│   │   ├── market_data_server/ # MCP server — live market data
│   │   ├── news_server/        # MCP server — financial news
│   │   └── document_server/    # MCP server — SEC filings / PDF analysis
│   └── client.py               # Shared MCP client helpers
│
├── config/
│   └── settings.py             # App settings, API keys, model config
│
├── main.py                     # Entry point
└── pyproject.toml
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
```

## Running

### Ingestion pipeline

```bash
python main.py ingest --source-dir data
```

This loads PDF files from the given directory, chunks them, generates embeddings, and stores them in Qdrant.

### CLI chatbot

```bash
python -m frontend.cli
```

### Web server + UI

Build the UI (first time or after changes):

```bash
cd frontend/ui
npm run build
cd ../..
```

Start the server:

```bash
uv run python -m frontend.server
```

Then open http://127.0.0.1:8000 in your browser.

### One-off query

```bash
python main.py chat "your question"
```
