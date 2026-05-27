"""
Memory package — Redis-backed persistent state for the studying agent.
"""

from memory.progress import (
    advance_chapter,
    advance_module,
    get_current_chapter,
    get_current_module,
    set_current_chapter,
    set_current_module,
)

__all__ = [
    "get_current_module",
    "set_current_module",
    "advance_module",
    "get_current_chapter",
    "set_current_chapter",
    "advance_chapter",
]
