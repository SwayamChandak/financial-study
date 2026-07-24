"""
Graph nodes — chatbot pipeline.

Node 1  guardrail_node         checks user input for abusive/sexual language
                               and prompt injection attempts. If flagged, sets
                               a response and marks the guardrail flag.

Node 2  rag_lookup_node        verifies the query is about financial/stock
                               markets, searches seen-only Qdrant chunks,
                               and answers with an LLM.

Node 3  validate_response_node checks if the RAG answer is descriptive and
                               in-depth. If not (and retries remain), it
                               updates the search query for a better RAG
                               retrieval.
"""

from __future__ import annotations

import re

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config.settings import settings
from graph.state import StudyState
from ingestion.store import search_seen_chunks

_ABUSIVE_WORDS: set[str] = {
    "fuck", "shit", "ass", "bitch", "bastard", "damn", "crap",
    "dick", "cock", "piss", "slut", "whore", "douche", "moron",
    "idiot", "stupid", "retard", "nigger", "faggot", "cunt",
}

_SEXUAL_WORDS: set[str] = {
    "porn", "sex", "fuck", "cock", "dick", "pussy", "blowjob",
    "handjob", "masturbat", "orgasm", "cum", "semen", "penis",
    "vagina", "anal", "bdsm", "kink", "naked", "nude",
}

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts|directions)", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|your)\s+(instructions|training|prompts)", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|not\s+(required\s+to|supposed\s+to))", re.IGNORECASE),
    re.compile(r"system\s+(prompt|message|instruction)", re.IGNORECASE),
    re.compile(r"act\s+as\s+if", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow", re.IGNORECASE),
    re.compile(r"you\s+must\s+ignore", re.IGNORECASE),
    re.compile(r"override", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"dan\s*:", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)", re.IGNORECASE),
    re.compile(r"output\s+(the\s+)?(full\s+)?prompt", re.IGNORECASE),
    re.compile(r"reveal\s+(the\s+)?(system\s+)?prompt", re.IGNORECASE),
]


def _check_abusive(text: str) -> bool:
    words = set(text.lower().split())
    return bool(words & _ABUSIVE_WORDS)


def _check_sexual(text: str) -> bool:
    lower = text.lower()
    return any(word in lower for word in _SEXUAL_WORDS)


def _check_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION_PATTERNS)


def guardrail_node(state: StudyState) -> StudyState:
    """
    Check user input for abusive/sexual language and prompt injection.

    If any check fires, ``guardrail_flagged`` is set to ``True`` and
    ``chatbot_response`` is set to the warning message.  When this node
    returns with ``guardrail_flagged == True`` the conditional edge in
    the chat graph will route directly to END, skipping the RAG lookup.
    """
    user_input = state.get("user_input", "").strip()

    if not user_input:
        return {
            **state,
            "guardrail_flagged": False,
        }

    if _check_abusive(user_input) or _check_sexual(user_input) or _check_injection(user_input):
        print(f"[Guardrail] Flagged input: {user_input[:80]!r}…")
        return {
            **state,
            "guardrail_flagged": True,
            "chatbot_response": "this language will not be tolerated. you need to better yourself.",
        }

    return {
        **state,
        "guardrail_flagged": False,
    }


def rag_lookup_node(state: StudyState) -> StudyState:
    """
    Answer the user's question using seen-only Qdrant content.

    Pipeline inside this node:
      1. If the query is *not* about financial/stock markets → return
         "not applicable, i wasn't made for that".
      2. Search Qdrant for chunks with ``seen == True``.
      3. If nothing is found → return "can't find answer, sorry bro".
      4. **Hard evidence gate** — LLM checks whether the retrieved
         context contains direct evidence for the question.  If not,
         return the fallback immediately without generating an answer.
      5. Otherwise, feed the retrieved context to the LLM and return
         the answer.

    The user message and the AI response are both appended to
    ``state["messages"]`` so the conversation history stays intact.
    """
    user_input = state.get("user_input", "").strip()

    if not user_input:
        return {**state, "chatbot_response": "Please provide a question.", "evidence_found": False}

    llm = init_chat_model(settings.llm_chat_model_name, temperature=0.0)

    # ── Step 1: classify topic ──────────────────────────────────────────
    classification = llm.invoke([
        SystemMessage(
            content=(
                "You are a strict classifier. Answer only with a single word: "
                "'YES' or 'NO'. Is the following query related to financial "
                "stock markets, investing, trading, or any topic that could "
                "be found in educational financial content?"
            )
        ),
        HumanMessage(content=user_input),
    ])

    if "NO" in classification.content.strip().upper():
        print("[RAG] Query rejected — not a financial topic.")
        return {
            **state,
            "chatbot_response": "not applicable, i wasn't made for that",
            "evidence_found": False,
        }

    # ── Step 2: search seen-only chunks ─────────────────────────────────
    search_query = state.get("rag_search_query") or user_input
    results = search_seen_chunks(search_query, top_k=settings.rag_top_k)

    if not results:
        print("[RAG] No seen chunks found for the query.")
        return {
            **state,
            "chatbot_response": "can't find answer, sorry bro",
            "evidence_found": False,
        }

    # ── Step 3: hard evidence gate ──────────────────────────────────────
    context = "\n\n".join(
        doc.page_content for doc in results
    )

    evidence_check = llm.invoke([
        SystemMessage(
            content=(
                "You are a strict evidence detector. Answer only with a single word: "
                "'YES' or 'NO'. Does the provided context contain specific facts, data, "
                "or information that directly answers the user's question? Answer NO if "
                "the context only tangentially relates or contains no direct evidence."
            )
        ),
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {user_input}"),
    ])

    if "NO" in evidence_check.content.strip().upper():
        print("[RAG] Evidence gate — no direct evidence in retrieved chunks.")
        return {
            **state,
            "chatbot_response": "can't find answer, sorry bro",
            "evidence_found": False,
        }

    # ── Step 4: extract source info from retrieved chunks ──────────────
    sources: set[tuple[int, int]] = set()
    for doc in results:
        mod = doc.metadata.get("module_no")
        ch = doc.metadata.get("chapter_no")
        if mod is not None and ch is not None:
            sources.add((int(mod), int(ch)))

    # ── Step 5: build system prompt with optional memory context ──────
    memory_context = state.get("memory_context", "")
    system_parts = [
        ("You are a helpful financial assistant. Answer the user's "
        "question based on the provided context. If the context "
        "does not contain enough information to answer, say "
        "'can't find answer, sorry bro'. Be descriptive and in-depth.")
    ]
    if memory_context:
        system_parts.append(f"\n\nConversation history:\n{memory_context}")

    response = llm.invoke([
        SystemMessage(content="\n".join(system_parts)),
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {user_input}"),
    ])

    answer = response.content.strip()

    # ── Step 6: append source citation ──────────────────────────────────
    if sources:
        source_text = ", ".join(
            sorted(f"Module {m}, Chapter {c}" for m, c in sources)
        )
        answer += f"\n\n— *Source: {source_text}*"

    # ── Step 6: persist conversation history ────────────────────────────
    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=user_input))
    messages.append(AIMessage(content=answer))

    print(f"[RAG] Answered: {answer[:120]}…")

    return {
        **state,
        "messages": messages,
        "chatbot_response": answer,
        "rag_search_query": "",
        "evidence_found": True,
    }


def validate_response_node(state: StudyState) -> StudyState:
    """
    Check whether the RAG answer is descriptive and in-depth.

    If it passes → do nothing (set ``validation_passed = True``).
    If it fails and ``rag_retry_count < 3`` → increment the counter,
    generate an improved search query, and let the conditional edge
    route back to ``rag_lookup_node`` for a retry.
    If it fails and ``rag_retry_count >= 3`` → pass through (edge
    will route to END with whatever we have).
    """
    answer = state.get("chatbot_response", "")
    user_input = state.get("user_input", "")
    retry_count = state.get("rag_retry_count", 0)

    llm = init_chat_model(settings.llm_chat_model_name, temperature=0.0)

    # ── check if answer is descriptive enough ──────────────────────────
    check = llm.invoke([
        SystemMessage(
            content=(
                "You are a strict quality inspector. Answer only with a single word: "
                "'PASS' or 'FAIL'. Does the following answer provide a descriptive, "
                "in-depth response to the user's question? A FAIL answer is one that "
                "is vague, too short, lacks detail, or says it can't find the answer. "
                "A PASS answer is substantive, well-explained, and demonstrates "
                "understanding of the topic."
            )
        ),
        HumanMessage(content=f"Question: {user_input}\n\nAnswer: {answer}"),
    ])

    passed = "PASS" in check.content.strip().upper()

    if passed:
        return {
            **state,
            "validation_passed": True,
        }

    # ── not descriptive enough ─────────────────────────────────────────
    if retry_count >= 3:
        print(f"[Validate] Answer failed validation, max retries ({retry_count}) reached.")
        note = (
            "\n\n— *Note: I've tried my best with the available study material "
            "but couldn't find a fully detailed explanation. Consider studying "
            "more chapters to get broader context.*"
        )
        return {
            **state,
            "chatbot_response": answer + note,
            "validation_passed": False,
        }

    # ── generate a better search query ─────────────────────────────────
    new_retry_count = retry_count + 1
    print(f"[Validate] Answer not descriptive enough — retry {new_retry_count}/3 …")

    improved_query = llm.invoke([
        SystemMessage(
            content=(
                "You are a search query rewriter. The user asked a question but the "
                "retrieved content did not produce a sufficiently detailed answer. "
                "Rewrite the user's question into a more specific, detailed search "
                "query that will retrieve deeper, more comprehensive information "
                "from a financial knowledge base. Output ONLY the rewritten query, "
                "no explanation."
            )
        ),
        HumanMessage(content=user_input),
    ])

    new_query = improved_query.content.strip()

    return {
        **state,
        "rag_retry_count": new_retry_count,
        "rag_search_query": new_query,
        "validation_passed": False,
    }
