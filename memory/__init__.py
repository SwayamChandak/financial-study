"""
Memory package — Redis-backed persistent state for the studying agent.
"""

from memory.chat_memory import MemoryService
from memory.progress import (
    ensure_initialized,
    get_current_chapter,
    get_current_module,
    keys_exist,
    set_current_chapter,
    set_current_module,
)

memory_service = MemoryService()

__all__ = [
    "MemoryService",
    "ensure_initialized",
    "get_current_chapter",
    "get_current_module",
    "keys_exist",
    "memory_service",
    "set_current_chapter",
    "set_current_module",
]
