"""
Graph nodes — the processing steps of the daily study pipeline.

Node 1  filter_by_memory       reads current position from Redis, fetches all
                                chunks for that module+chapter from Qdrant, and
                                computes the total character count from metadata.

Node 2  summarise_chunks       calls the configured LLM to produce a descriptive,
                                in-depth summary of the chapter content whose
                                length is between half and three-quarters of the
                                original chapter character count; prints the result.

Node 3  validate_summary_node  checks the summary for descriptiveness and length
                                constraints. On failure (and retries < 3) routes
                                back to summarise_chunks for a retry.

Node 4  update_progress        marks all retrieved chunks as seen in Qdrant,
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
    ensure_initialized,
    get_current_chapter,
    get_current_module,
    keys_exist,
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
    module_exists, chapter_exists = keys_exist()
    if not module_exists or not chapter_exists:
        print(
            f"[Node 1] Redis keys missing "
            f"(module_exists={module_exists}, chapter_exists={chapter_exists}). "
            "Initialising both to 1."
        )
        ensure_initialized()
    else:
        print("[Node 1] Redis keys found.")

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
        "summary_retry_count": 0,
        "summary_validation_passed": False,
    }


# ---------------------------------------------------------------------------
# Node 2 — Summarise chunks
# ---------------------------------------------------------------------------


def summarise_chunks(state: StudyState) -> StudyState:
    """
    Use the configured LLM to produce a descriptive, in-depth chapter summary.

    Target length: between ``total_chars // 2`` (minimum) and
    ``total_chars * 3 // 4`` (maximum) characters.
    The summary is printed to the terminal and stored in state["summary"].
    """
    chunks = state["chunks"]

    if not chunks:
        print(
            f"[Node 2] No chunks found for Module {state['current_module']}, "
            f"Chapter {state['current_chapter']} — skipping LLM call."
        )
        return {**state, "summary": ""}

    total_chars = state["total_chars"]
    min_chars = total_chars // 2
    max_chars = total_chars * 3 // 4

    combined_text = "\n\n".join(chunk.page_content for chunk in chunks)

    load_dotenv()
    llm = init_chat_model(
        settings.llm_model_name,
        temperature=settings.llm_temperature,
    )

    messages = [
        SystemMessage(
            content=(
                "You are a descriptive financial education assistant. "
                "Summarise the provided chapter content in a detailed, in-depth manner. "
                "Cover key concepts, explanations, and important details thoroughly. "
                f"Your summary must be between {min_chars} and {max_chars} characters long "
                "(not words — characters). Do not be concise at the expense of depth."
            )
        ),
        HumanMessage(content=combined_text),
    ]

    print(
        f"[Node 2] Generating detailed summary ({min_chars}–{max_chars} chars) "
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
# Node 3 — Validate summary
# ---------------------------------------------------------------------------


def validate_summary_node(state: StudyState) -> StudyState:
    """
    Check whether the generated summary is descriptive, in-depth, and
    satisfies the length constraint (between half and three-quarters of
    the original chapter).

    - If it passes         → set ``summary_validation_passed = True``.
    - If it fails and
      ``summary_retry_count < 3`` → increment retry count, set
      ``summary_validation_passed = False`` so the edge routes back to
      ``summarise_chunks``.
    - If it fails and
      ``summary_retry_count >= 3`` → accept what we have and let the
      edge route to ``update_progress``.
    """
    summary = state.get("summary", "")
    total_chars = state.get("total_chars", 0)
    retry_count = state.get("summary_retry_count", 0)

    if not summary:
        print("[Validate Summary] Empty summary — failing.")
        retry_count += 1
        return {
            **state,
            "summary_retry_count": retry_count,
            "summary_validation_passed": False,
        }

    min_chars = total_chars // 2
    max_chars = total_chars * 3 // 4
    actual_chars = len(summary)

    load_dotenv()
    llm = init_chat_model(settings.llm_model_name, temperature=0.0)

    check = llm.invoke([
        SystemMessage(
            content=(
                "You are a strict quality inspector for financial education content. "
                "Answer only with a single word: 'PASS' or 'FAIL'. "
                "Does the following summary meet ALL of these criteria?\n"
                "1. It is descriptive, in-depth, and covers key concepts thoroughly.\n"
                "2. It reads like educational material, not just bullet points.\n"
                "3. It demonstrates understanding of the topic, not just surface-level facts.\n"
                "Answer PASS only if ALL criteria are met."
            )
        ),
        HumanMessage(content=summary),
    ])

    quality_ok = "PASS" in check.content.strip().upper()

    if quality_ok and min_chars <= actual_chars <= max_chars:
        print(
            f"[Validate Summary] PASS — {actual_chars} chars "
            f"(range {min_chars}–{max_chars})."
        )
        return {
            **state,
            "summary_validation_passed": True,
        }

    # ── report what went wrong ──────────────────────────────────────────
    reasons = []
    if not quality_ok:
        reasons.append("not descriptive enough")
    if actual_chars < min_chars:
        reasons.append(f"too short ({actual_chars} < {min_chars} chars)")
    elif actual_chars > max_chars:
        reasons.append(f"too long ({actual_chars} > {max_chars} chars)")

    print(f"[Validate Summary] FAIL — {', '.join(reasons)}.")

    if retry_count >= 3:
        print(f"[Validate Summary] Max retries ({retry_count}) reached — accepting summary.")
        return {
            **state,
            "summary_validation_passed": False,
        }

    new_retry_count = retry_count + 1
    print(f"[Validate Summary] Retry {new_retry_count}/3 …")

    return {
        **state,
        "summary_retry_count": new_retry_count,
        "summary_validation_passed": False,
    }


# ---------------------------------------------------------------------------
# Node 4 — Update progress
# ---------------------------------------------------------------------------


def update_progress(state: StudyState) -> StudyState:
    """
    1. Mark all retrieved chunks as ``seen = True`` in Qdrant.
    2. Check whether the next chapter (current_chapter + 1) exists for the
       same module in the vector DB.
       - If yes  → advance to current_chapter + 1.
       - If no   → advance to current_module + 1, reset chapter to 1.
    3. Persist the new position to Redis.

    If no chunks were found (empty Qdrant), the position is left unchanged
    so the counter does not escalate across repeated runs.
    """
    current_module = state["current_module"]
    current_chapter = state["current_chapter"]

    if not state["chunks"]:
        print(
            f"[Node 3] No chunks were processed for Module {current_module}, "
            f"Chapter {current_chapter} — position unchanged."
        )
        return state

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
