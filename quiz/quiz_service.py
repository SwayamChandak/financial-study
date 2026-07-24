"""
Quiz service — generates and grades MCQs from seen Qdrant content.

Flow:
  1. Identify completed chapters via ``seen=True`` in Qdrant metadata.
  2. Apply weighted chapter selection based on user chat history and recency.
  3. Generate MCQs per selected chapter via LLM (parallelised).
  4. Cache the full quiz (with answers) in Redis for 1 hour for grading.
  5. On submission, grade from the cached quiz — no Qdrant / LLM needed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import redis
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from config.settings import settings
from memory import memory_service

logger = logging.getLogger(__name__)

CACHE_TTL = 3600
_MAX_CHUNKS_PER_CHAPTER = 5
_CHAPTER_CONTENT_LIMIT = 3500


class QuizGenerationError(Exception):
    """Raised when quiz generation is not possible (e.g. no completed chapters)."""


class QuizNotFoundError(Exception):
    """Raised when the requested quiz_id does not exist or has expired."""


class QuizService:
    """Generate, cache, and grade MCQs based on seen Qdrant content."""

    def __init__(self) -> None:
        self._llm: BaseChatModel | None = None
        self._gen_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # LLM lazy init
    # ------------------------------------------------------------------

    def _get_llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = init_chat_model(
                settings.llm_chat_model_name,
                temperature=0.0,
                max_tokens=4096,
            )
        return self._llm

    # ------------------------------------------------------------------
    # Redis helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _redis() -> redis.Redis:
        return redis.from_url(settings.redis_url, decode_responses=True)

    @staticmethod
    def _cache_key(quiz_id: str) -> str:
        return f"quiz:{quiz_id}"

    # ------------------------------------------------------------------
    # Completed chapters — Qdrant scroll
    # ------------------------------------------------------------------

    def _get_completed_chapters(self) -> list[tuple[int, int]]:
        """Return sorted (module_no, chapter_no) pairs where chunks have ``seen=True``.

        Results are sorted by module then chapter (ascending) so later
        entries correspond to more advanced content.
        """
        client = QdrantClient(url=settings.qdrant_url)
        scroll_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.seen",
                    match=MatchValue(value=True),
                )
            ]
        )

        chapters: set[tuple[int, int]] = set()
        offset: Any = None

        while True:
            records, next_offset = client.scroll(
                collection_name=settings.qdrant_collection,
                scroll_filter=scroll_filter,
                with_payload=True,
                with_vectors=False,
                limit=100,
                offset=offset,
            )
            for record in records:
                meta = (record.payload or {}).get("metadata", {})
                mod = meta.get("module_no")
                ch = meta.get("chapter_no")
                if mod is not None and ch is not None:
                    chapters.add((int(mod), int(ch)))

            if next_offset is None:
                break
            offset = next_offset

        print(f"[Quiz] Extracted {len(chapters)} completed chapters from Qdrant: {chapters}")
        return sorted(chapters)

    # ------------------------------------------------------------------
    # User question topics — from Redis memory → Qdrant lookup
    # ------------------------------------------------------------------

    def _get_user_question_chapters(
        self,
        completed: list[tuple[int, int]],
    ) -> set[tuple[int, int]]:
        """Return the subset of *completed* chapters that match topics the
        user has asked questions about.

        Uses chat memory from Redis, filters out summary entries, and for
        each real user question performs a similarity search against seen
        Qdrant content.  Chapters that appear in the search results are
        considered "user-asked-about" chapters.
        """
        entries = memory_service.get_recent_memory(limit=100)
        questions = [
            e["question"]
            for e in entries
            if e.get("question")
            and e["question"] != "[SYSTEM SUMMARY]"
        ]

        if not questions:
            return set()

        client = QdrantClient(url=settings.qdrant_url)
        seen_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.seen",
                    match=MatchValue(value=True),
                )
            ]
        )

        matched: set[tuple[int, int]] = set()
        completed_set = set(completed)

        for q in questions[:10]:
            try:
                results = client.search(
                    collection_name=settings.qdrant_collection,
                    query_text=q,
                    query_filter=seen_filter,
                    limit=2,
                )
            except Exception:
                continue

            for scored_point in results:
                meta = (scored_point.payload or {}).get("metadata", {})
                mod = meta.get("module_no")
                ch = meta.get("chapter_no")
                if mod is not None and ch is not None:
                    pair = (int(mod), int(ch))
                    if pair in completed_set:
                        matched.add(pair)

        return matched

    # ------------------------------------------------------------------
    # Chapter selection — weighted algorithm
    # ------------------------------------------------------------------

    @staticmethod
    def _select_chapters(
        completed: list[tuple[int, int]],
        question_chapters: set[tuple[int, int]],
        count: int,
    ) -> list[tuple[int, int]]:
        """Distribute *count* chapter picks across three weighted buckets.

        When the user has asked questions:
          - 40 % topic-matched chapters  (from *question_chapters*)
          - 30 % most recent chapters     (last 2 in *completed*)
          - 30 % random from the rest

        When no user questions exist:
          - 50 % last 2 chapters
          - 50 % from chapters before those
        """
        if not completed:
            raise QuizGenerationError("No completed chapters found — study material first.")

        # ── recent = last 2 completed chapters ──────────────────────────
        recent = set(completed[-2:])

        if question_chapters:
            n = count
            topic_n = max(1, round(n * 0.4))
            recent_n = max(1, round(n * 0.3))
            random_n = n - topic_n - recent_n

            topic_pool = [c for c in completed if c in question_chapters]
            random_pool = [
                c for c in completed
                if c not in topic_pool and c not in recent
            ]

            picks: list[tuple[int, int]] = []
            picks.extend(_pick_n(topic_pool, topic_n))
            picks.extend(_pick_n(list(recent), recent_n))
            picks.extend(_pick_n(random_pool, random_n))

            return picks[:n]
        else:
            n = count
            before_pool = [c for c in completed if c not in recent]
            recent_n = max(1, round(n * 0.5))
            before_n = n - recent_n

            picks = []
            picks.extend(_pick_n(list(recent), recent_n))
            picks.extend(_pick_n(before_pool, before_n))

            return picks[:n]

    # ------------------------------------------------------------------
    # MCQ generation — one LLM call per unique chapter
    # ------------------------------------------------------------------

    def _generate_for_chapter(
        self,
        module_no: int,
        chapter_no: int,
        question_count: int,
    ) -> list[dict]:
        """Generate *question_count* MCQs from the chapter's Qdrant content.

        If the count exceeds 2, splits into multiple LLM calls of 2 each to
        avoid hitting output token limits.
        """
        if question_count < 1:
            return []

        content = self._fetch_chapter_content(module_no, chapter_no)
        if not content.strip():
            print(f"[Quiz] Empty content for Module {module_no}, Chapter {chapter_no} — skipping")
            return []

        all_questions: list[dict] = []
        remaining = question_count
        batch_size = 2

        while remaining > 0:
            batch = min(remaining, batch_size)
            batch_result = self._generate_batch(module_no, chapter_no, batch, content)
            if batch_result:
                all_questions.extend(batch_result)
                remaining -= batch
            else:
                # Batch failed — fall back to 1 question at a time
                if batch_size > 1:
                    print(f"[Quiz] Batch of {batch} failed for M{module_no} Ch{chapter_no}, falling back to 1x1")
                    batch_size = 1
                else:
                    # Even 1 question failed — give up on this chapter
                    print(f"[Quiz] Giving up on M{module_no} Ch{chapter_no}")
                    break

        return all_questions[:question_count]

    def _generate_batch(
        self,
        module_no: int,
        chapter_no: int,
        batch_size: int,
        content: str,
    ) -> list[dict]:
        """Generate *batch_size* questions in a single LLM call."""
        if batch_size < 1:
            return []

        print(f"[Quiz] Generating {batch_size} questions for Module {module_no}, Chapter {chapter_no} …")
        llm = self._get_llm()

        prompt = (
            f"You are a quiz generator for financial education. Based strictly on the "
            f"study material below (Module {module_no}, Chapter {chapter_no}), generate "
            f"exactly {batch_size} multiple-choice question(s). Keep your response concise "
            f"so the JSON stays complete.\n\n"
            f"Requirements:\n"
            f"1. Each question must be answerable from the provided material — do NOT use "
            f"external knowledge.\n"
            f"2. Each question has exactly 4 options labeled A, B, C, D.\n"
            f"3. One option is correct; the other three are plausible distractors.\n"
            f"4. Include a brief explanation of why the correct answer is right.\n"
            f"5. Include a \"source\" field with the value \"Module {module_no}, Chapter {chapter_no}\".\n\n"
            f"IMPORTANT — Output ONLY a valid JSON array. Each question must be an object "
            f"wrapped in {{curly braces}}, NOT in [square brackets].\n\n"
            f"Correct example:\n"
            f'[\n'
            f'  {{\n'
            f'    "question": "What is an IPO?",\n'
            f'    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},\n'
            f'    "correct_answer": "A",\n'
            f'    "explanation": "...",\n'
            f'    "source": "Module {module_no}, Chapter {chapter_no}"\n'
            f'  }}\n'
            f']\n\n'
            f"Wrong examples (do NOT do this):\n"
            f'1. ["question": "...", "options": {{...}}, "correct_answer": "..."] — using [ ] instead of {{ }}\n'
            f'2. {{"question": "..."}} {{"question": "..."}} — separate objects not inside an array\n\n'
            f"Study material:\n{content}"
        )

        try:
            response = llm.invoke([
                SystemMessage(content="You are a precise quiz generator that outputs only valid JSON."),
                HumanMessage(content=prompt),
            ])
            raw = response.content.strip()
            print(f"[Quiz] LLM raw response for M{module_no} Ch{chapter_no}:\n{raw[:500]}")
            questions = _extract_json_array(raw)
            if questions is None:
                print(f"[Quiz] Failed to parse JSON for M{module_no} Ch{chapter_no} — retrying with 1 question")
                return []
            if not isinstance(questions, list):
                print(f"[Quiz] LLM did not return a list — got {type(questions).__name__}")
                return []
            return questions[:batch_size]
        except Exception as exc:
            logger.error("LLM quiz generation failed for M%s Ch%s: %s", module_no, chapter_no, exc)
            return []

    @staticmethod
    def _fetch_chapter_content(module_no: int, chapter_no: int) -> str:
        """Concatenate and truncate chunks for the given chapter."""
        client = QdrantClient(url=settings.qdrant_url)
        scroll_filter = Filter(
            must=[
                FieldCondition(key="metadata.module_no", match=MatchValue(value=module_no)),
                FieldCondition(key="metadata.chapter_no", match=MatchValue(value=chapter_no)),
            ]
        )

        texts: list[str] = []
        offset: Any = None

        while len(texts) < _MAX_CHUNKS_PER_CHAPTER:
            records, next_offset = client.scroll(
                collection_name=settings.qdrant_collection,
                scroll_filter=scroll_filter,
                with_payload=True,
                with_vectors=False,
                limit=20,
                offset=offset,
            )
            for record in records:
                payload = record.payload or {}
                texts.append(payload.get("page_content", ""))
                if len(texts) >= _MAX_CHUNKS_PER_CHAPTER:
                    break
            if next_offset is None:
                break
            offset = next_offset

        combined = "\n\n".join(texts)
        return combined[:_CHAPTER_CONTENT_LIMIT]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_quiz(self, count: int = 10) -> dict:
        """Generate, cache, and return a quiz.

        Returns the quiz *without* correct answers for client display.
        The full quiz (with answers) is cached in Redis for grading.
        """
        async with self._gen_lock:
            return await asyncio.to_thread(self._generate_quiz_sync, count)

    def _generate_quiz_sync(self, count: int) -> dict:
        completed = self._get_completed_chapters()
        if not completed:
            raise QuizGenerationError("No completed chapters found — study some material first.")

        question_chapters = self._get_user_question_chapters(completed)
        selected = self._select_chapters(completed, question_chapters, count)

        # Count how many questions per chapter
        per_chapter: dict[tuple[int, int], int] = {}
        for ch in selected:
            per_chapter[ch] = per_chapter.get(ch, 0) + 1

        # Generate questions in parallel per chapter
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=min(5, len(per_chapter) or 1)) as pool:
            fut_map = {
                pool.submit(self._generate_for_chapter, m, c, n): (m, c)
                for (m, c), n in per_chapter.items()
            }
            all_questions: list[dict] = []
            for future in as_completed(fut_map):
                all_questions.extend(future.result())

        if not all_questions:
            raise QuizGenerationError("Failed to generate any questions — LLM error or empty content.")

        # Deduplicate by question text — same chapter picks or LLM repeats
        seen_questions: set[str] = set()
        unique_questions: list[dict] = []
        for q in all_questions:
            text = q.get("question", "")
            if text and text not in seen_questions:
                seen_questions.add(text)
                unique_questions.append(q)
        all_questions = unique_questions

        # Assign IDs and remove correct_answer from the public version
        public_questions: list[dict] = []
        for idx, q in enumerate(all_questions, start=1):
            q["id"] = idx
            public_q = {
                "id": idx,
                "question": q.get("question", ""),
                "options": q.get("options", {}),
            }
            public_questions.append(public_q)

        quiz_id = str(uuid.uuid4())
        created = datetime.now(UTC).isoformat()

        full_quiz = {
            "quiz_id": quiz_id,
            "created_at": created,
            "total_questions": len(all_questions),
            "questions": all_questions,
        }
        public_quiz = {
            "quiz_id": quiz_id,
            "created_at": created,
            "total_questions": len(public_questions),
            "questions": public_questions,
        }

        # Cache full quiz (with answers) for grading
        client = self._redis()
        client.setex(self._cache_key(quiz_id), CACHE_TTL, json.dumps(full_quiz))

        print(f"[Quiz] Quiz {quiz_id} ready — {len(all_questions)} questions")
        logger.info("Quiz %s generated — %d questions", quiz_id, len(all_questions))
        return public_quiz

    def get_quiz(self, quiz_id: str) -> dict:
        """Retrieve the cached full quiz (with answers, for grading)."""
        client = self._redis()
        raw = client.get(self._cache_key(quiz_id))
        if raw is None:
            raise QuizNotFoundError(f"Quiz {quiz_id} not found or has expired.")
        return json.loads(raw)

    async def submit_quiz(
        self,
        quiz_id: str,
        answers: dict[str, str],
    ) -> dict:
        """Grade a submitted quiz using the cached data.

        Returns score, per-question results with correct answers and
        explanations — no Qdrant or LLM calls are made.
        """
        full = await asyncio.to_thread(self.get_quiz, quiz_id)
        questions = full["questions"]

        results: list[dict] = []
        correct_count = 0

        for q in questions:
            qid = str(q["id"])
            user_answer = answers.get(qid, "")
            correct = q.get("correct_answer", "")
            is_correct = user_answer.strip().upper() == correct.strip().upper()

            if is_correct:
                correct_count += 1

            results.append({
                "question_id": qid,
                "question": q.get("question", ""),
                "options": q.get("options", {}),
                "user_answer": user_answer,
                "correct_answer": correct,
                "is_correct": is_correct,
                "explanation": q.get("explanation", ""),
                "source": q.get("source", ""),
            })

        total = len(questions)
        return {
            "quiz_id": quiz_id,
            "score": f"{correct_count}/{total}",
            "percentage": round((correct_count / total) * 100) if total else 0,
            "results": results,
        }


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _pick_n(pool: list[tuple[int, int]], n: int) -> list[tuple[int, int]]:
    """Pick *n* items from *pool*, repeating if the pool is smaller than *n*."""
    if not pool:
        return []
    import random

    random.shuffle(pool)
    return [pool[i % len(pool)] for i in range(n)]


def _extract_json_array(text: str) -> list | None:
    """Try multiple strategies to extract a JSON array from LLM output.

    1. Strip markdown code fences, then parse directly.
    2. Find the outermost ``[...]`` block and parse it.
    3. Find the first balanced ``[...]`` block.
    4. Collect all top-level ``{...}`` objects and wrap them in an array.
    Returns ``None`` when all strategies fail.
    """
    text = text.strip()

    # Strategy 1 — strip code fences and try direct parse
    cleaned = _strip_code_fences(text)
    result = _try_parse(cleaned)
    if result is not None:
        return result

    # Strategy 2 — find the outermost [...] block
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        result = _try_parse(candidate)
        if result is not None:
            return result

    # Strategy 3 — find first balanced [...] block
    brace_depth = 0
    for i, ch in enumerate(text):
        if ch == "[":
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif ch == "]":
            brace_depth -= 1
            if brace_depth == 0:
                candidate = text[start : i + 1]
                result = _try_parse(candidate)
                if result is not None:
                    return result

    # Strategy 4 — collect all top-level {...} objects and wrap in array
    # Handles case where LLM outputs separate objects without array wrapper.
    objects: list[str] = []
    depth = 0
    obj_start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and obj_start != -1:
                objects.append(text[obj_start : i + 1])
                obj_start = -1
    if len(objects) > 1:
        wrapped = "[" + ",".join(objects) + "]"
        result = _try_parse(wrapped)
        if result is not None:
            return result

    return None


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences and leading/trailing prose from LLM output."""
    text = text.strip()

    # Remove leading fenced code block marker (```json, ```, etc.)
    fence_start = text.find("```")
    if fence_start != -1:
        after_fence = text[fence_start + 3 :]
        first_nl = after_fence.find("\n")
        text = after_fence[first_nl + 1 :] if first_nl != -1 else after_fence

    # Remove trailing fence
    text = text.removesuffix("```")

    return text.strip()


def _try_parse(text: str) -> list | None:
    """Attempt to ``json.loads`` *text*, with trailing-comma workaround and
    bracket-correction fallback for LLMs that confuse ``[...]`` with ``{...}``."""

    def _attempt(t: str) -> list | None:
        try:
            parsed = json.loads(t)
            return parsed if isinstance(parsed, list) else None
        except json.JSONDecodeError:
            return None

    # Direct parse
    result = _attempt(text)
    if result is not None:
        return result

    # Trailing-comma fix
    import re as _re

    fixed = _re.sub(r",\s*([}\]])", r"\1", text)
    result = _attempt(fixed)
    if result is not None:
        return result

    # Bracket correction: some LLMs use [ "key": "value" ] instead of { "key": "value" }.
    # Detect objects wrapped in [...] (without inner {}) and swap the brackets.
    # Pattern: "key": value or "key": { ... } inside [...] — swap [→{ and ]→}.
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        # Heuristic: if the top-level content starts with a double-quote (a JSON key)
        # instead of a {, the wrong brackets were used.
        if inner and not inner.startswith("{"):
            swapped = "{" + inner + "}"
            result = _attempt(swapped)
            if result is not None:
                return result

    # Last resort: wrap each [...] object with {...}
    # Detect pattern: ["key": val] ["key": val] (multiple objects, each in [])
    # Strategy: find all [...] blocks, convert each to {...}, then wrap in outer [...]
    blocks: list[str] = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and start != -1:
                block = text[start + 1 : i]
                if block.strip() and not block.strip().startswith("{"):
                    blocks.append("{" + block + "}")
                start = -1
    if blocks:
        attempt = "[" + ",".join(blocks) + "]"
        result = _attempt(attempt)
        if result is not None:
            return result

    return None


quiz_service = QuizService()
