"""
Graph nodes — chatbot pipeline.

Node 1  guardrail_node     checks user input for abusive/sexual language
                           and prompt injection attempts. If flagged, sets
                           a response and marks the guardrail flag.

Node 2  rag_lookup_node    verifies the query is about financial/stock
                           markets, searches seen-only Qdrant chunks,
                           and answers with an LLM.
"""

from __future__ import annotations

import re

from dotenv import load_dotenv
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
      4. Otherwise, feed the retrieved context to the LLM and return
         the answer.

    The user message and the AI response are both appended to
    ``state["messages"]`` so the conversation history stays intact.
    """
    user_input = state.get("user_input", "").strip()

    if not user_input:
        return {**state, "chatbot_response": "Please provide a question."}

    load_dotenv()
    llm = init_chat_model(settings.llm_model_name, temperature=0.0)

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
        }

    # ── Step 2: search seen-only chunks ─────────────────────────────────
    results = search_seen_chunks(user_input, top_k=settings.rag_top_k)

    if not results:
        print("[RAG] No seen chunks found for the query.")
        return {
            **state,
            "chatbot_response": "can't find answer, sorry bro",
        }

    # ── Step 3: answer with context ─────────────────────────────────────
    context = "\n\n".join(
        doc.page_content for doc in results
    )

    response = llm.invoke([
        SystemMessage(
            content=(
                "You are a helpful financial assistant. Answer the user's "
                "question based on the provided context. If the context "
                "does not contain enough information to answer, say "
                "'can't find answer, sorry bro'. Be concise."
            )
        ),
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {user_input}"),
    ])

    answer = response.content.strip()

    # ── Step 4: persist conversation history ────────────────────────────
    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=user_input))
    messages.append(AIMessage(content=answer))

    print(f"[RAG] Answered: {answer[:120]}…")

    return {
        **state,
        "messages": messages,
        "chatbot_response": answer,
    }
