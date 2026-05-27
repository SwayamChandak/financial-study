"""
Graph nodes — the three processing steps of the daily study pipeline.

Node 1  filter_by_memory    reads current position from Redis, fetches all
                             chunks for that module+chapter from Qdrant, and
                             computes the total character count from metadata.

Node 2  summarise_chunks     calls the configured LLM to produce a summary of
                             the chapter content whose length is ~half the
                             total character count; prints the result.

Node 3  update_progress      marks all retrieved chunks as seen in Qdrant,
                             then advances the Redis pointers to the next
                             chapter (or next module if no next chapter exists).
"""

from __future__ import annotations

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import settings
from graph.state import StudyState
from ingestion.store import fetch_all_chunks, mark_chunks_seen
from memory.progress import (
    get_current_chapter,
    get_current_module,
    set_current_chapter,
    set_current_module,
)


# ---------------------------------------------------------------------------
# Node 1 — Filter by memory
# ---------------------------------------------------------------------------


def filter_by_memory(state: StudyState) -> StudyState:
    """
    Read current module and chapter from Redis, pull every matching chunk
    from Qdrant, and sum their character counts using the ``text_length``
    metadata field set by chunker.py.

    Returns updated state with:
      current_module, current_chapter, chunks, point_ids, total_chars
    """
    module_no = get_current_module()
    chapter_no = get_current_chapter()

    print(f"[Node 1] Fetching chunks for Module {module_no}, Chapter {chapter_no} …")

    chunks, point_ids = fetch_all_chunks(module_no, chapter_no)

    total_chars = sum(
        chunk.metadata.get("text_length", len(chunk.page_content))
        for chunk in chunks
    )

    print(f"[Node 1] Retrieved {len(chunks)} chunks — {total_chars} total characters.")

    return {
        **state,
        "current_module": module_no,
        "current_chapter": chapter_no,
        "chunks": chunks,
        "point_ids": point_ids,
        "total_chars": total_chars,
    }


# ---------------------------------------------------------------------------
# Node 2 — Summarise chunks
# ---------------------------------------------------------------------------


def summarise_chunks(state: StudyState) -> StudyState:
    """
    Use the configured LLM to produce a chapter summary.

    Target length: state["total_chars"] // 2 characters.
    The summary is printed to the terminal and stored in state["summary"].
    """
    chunks = state["chunks"]
    total_chars = state["total_chars"]
    target_chars = total_chars // 2

    combined_text = "\n\n".join(chunk.page_content for chunk in chunks)

    load_dotenv()
    llm = init_chat_model(
        settings.llm_model_name,
        temperature=settings.llm_temperature,
    )

    messages = [
        SystemMessage(
            content=(
                "You are a concise financial education assistant. "
                "Summarise the provided chapter content clearly and accurately. "
                f"Your summary must be approximately {target_chars} characters long "
                "(not words — characters). Do not exceed twice that length."
            )
        ),
        HumanMessage(content=combined_text),
    ]

    print(
        f"[Node 2] Generating summary (target {target_chars} chars) "
        f"for Module {state['current_module']}, Chapter {state['current_chapter']} …"
    )

    response = llm.invoke(messages)
    summary: str = response.content  # type: ignore[assignment]

    print("\n" + "=" * 60)
    print(f"SUMMARY — Module {state['current_module']}, Chapter {state['current_chapter']}")
    print("=" * 60)
    print(summary)
    print("=" * 60 + "\n")

    return {**state, "summary": summary}


# ---------------------------------------------------------------------------
# Node 3 — Update progress
# ---------------------------------------------------------------------------


def update_progress(state: StudyState) -> StudyState:
    """
    1. Mark all retrieved chunks as ``seen = True`` in Qdrant.
    2. Check whether the next chapter (current_chapter + 1) exists for the
       same module in the vector DB.
       - If yes  → advance to current_chapter + 1.
       - If no   → advance to current_module + 1, reset chapter to 1.
    3. Persist the new position to Redis.
    """
    current_module = state["current_module"]
    current_chapter = state["current_chapter"]

    # Step 1 — mark chunks seen in Qdrant
    print(
        f"[Node 3] Marking {len(state['point_ids'])} chunks as seen "
        f"for Module {current_module}, Chapter {current_chapter} …"
    )
    mark_chunks_seen(state["point_ids"], state["chunks"])

    # Step 2 — check if next chapter exists
    next_chapter_docs, _ = fetch_all_chunks(current_module, current_chapter + 1)

    if next_chapter_docs:
        new_module = current_module
        new_chapter = current_chapter + 1
        print(
            f"[Node 3] Next chapter found — advancing to "
            f"Module {new_module}, Chapter {new_chapter}."
        )
    else:
        new_module = current_module + 1
        new_chapter = 1
        print(
            f"[Node 3] No Chapter {current_chapter + 1} in Module {current_module}. "
            f"Advancing to Module {new_module}, Chapter {new_chapter}."
        )

    # Step 3 — persist to Redis
    set_current_module(new_module)
    set_current_chapter(new_chapter)

    return {**state, "current_module": new_module, "current_chapter": new_chapter}
