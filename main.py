"""
Entry point — run either the ingestion pipeline or the study workflow.

Usage:
    python main.py ingest   --source-dir data
    python main.py run
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv


def run_ingestion(args: argparse.Namespace) -> None:
    from ingestion.pipeline import run_pipeline

    run_pipeline(args.source_dir)


def run_study(args: argparse.Namespace) -> None:  # noqa: ARG001
    from graph.builder import build_study_graph

    graph = build_study_graph()
    graph.invoke({})


def run_chat(args: argparse.Namespace) -> None:
    from graph.builder import build_chat_graph

    graph = build_chat_graph()
    result = graph.invoke({"user_input": args.query})
    print(result.get("chatbot_response", ""))


def main() -> None:
    load_dotenv()

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
