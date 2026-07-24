"""
Entry point — run either the ingestion pipeline or the study workflow.

Usage:
    python main.py ingest   --source-dir data
    python main.py run
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from config.settings import setup_langsmith


def run_ingestion(args: argparse.Namespace) -> None:
    from ingestion.pipeline import run_pipeline

    run_pipeline(args.source_dir)


def run_study(args: argparse.Namespace) -> None:
    from graph.graph_builder import build_study_graph

    graph = build_study_graph()
    graph.invoke({})


def run_chat(args: argparse.Namespace) -> None:
    from graph.graph_builder import build_chat_graph
    from memory import memory_service

    memory_context = memory_service.format_memory_for_prompt(limit=10)

    graph = build_chat_graph()
    result = graph.invoke({
        "user_input": args.query,
        "memory_context": memory_context,
    })

    response = result.get("chatbot_response", "")
    memory_service.add_to_memory(args.query, response)
    print(response)


def main() -> None:
    load_dotenv()
    setup_langsmith()

    parser = argparse.ArgumentParser(
        description="Financial studying agent — ingestion & AI workflow"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_parser = sub.add_parser("ingest", help="Run the PDF ingestion pipeline")
    ingest_parser.add_argument(
        "--source-dir",
        required=True,
        help="Path to the directory containing PDF files",
    )
    ingest_parser.set_defaults(func=run_ingestion)

    run_parser = sub.add_parser("run", help="Run the AI study workflow")
    run_parser.set_defaults(func=run_study)

    chat_parser = sub.add_parser("chat", help="Ask a question to the chatbot")
    chat_parser.add_argument("query", help="Your question about financial markets")
    chat_parser.set_defaults(func=run_chat)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
