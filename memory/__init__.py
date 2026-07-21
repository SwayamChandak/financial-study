"""
Memory package — Redis-backed persistent state for the studying agent.
"""

from memory.chat_memory import MemoryService
from memory.progress import (
    advance_chapter,
    advance_module,
    ensure_initialized,
    get_current_chapter,
    get_current_module,
    keys_exist,
    set_current_chapter,
    set_current_module,
)

memory_service = MemoryService()

__all__ = [
    "get_current_module",
    "set_current_module",
    "advance_module",
    "get_current_chapter",
    "set_current_chapter",
    "advance_chapter",
    "keys_exist",
    "ensure_initialized",
    "MemoryService",
    "memory_service",
]
