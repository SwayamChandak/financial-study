from __future__ import annotations

import sys
from pathlib import Path

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"


def _enable_ansi_on_windows() -> None:
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


def print_bot(text: str) -> None:
    print(f"{CYAN}{text}{RESET}")


def print_error(text: str) -> None:
    print(f"{RED}{text}{RESET}")


def print_system(text: str) -> None:
    print(f"{GREEN}{text}{RESET}")


def read_query() -> str | None:
    try:
        return input(f"\n{YELLOW}{BOLD}You: {RESET}")
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def main() -> None:
    _enable_ansi_on_windows()

    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    from dotenv import load_dotenv

    load_dotenv()

    from config.settings import setup_langsmith
    from graph.graph_builder import build_chat_graph
    from memory import memory_service

    setup_langsmith()
    graph = build_chat_graph()

    print(f"{CLEAR}{GREEN}{BOLD}Financial Study — Chatbot{RESET}")
    print_system("Ask any question about the financial markets.")
    print_system("Type  exit  /  quit  /  q  to quit.\n")

    while True:
        query = read_query()
        if query is None:
            break
        stripped = query.strip()
        if stripped.lower() in ("exit", "quit", "q"):
            print_system("Goodbye!")
            break
        if not stripped:
            continue

        try:
            memory_context = memory_service.format_memory_for_prompt(limit=10)
            result = graph.invoke({
                "user_input": stripped,
                "memory_context": memory_context,
            })
            response = result.get("chatbot_response", "")
            memory_service.add_to_memory(stripped, response)
            print_bot(response)
        except Exception as exc:
            print_error(f"Error: {exc}")


if __name__ == "__main__":
    main()
