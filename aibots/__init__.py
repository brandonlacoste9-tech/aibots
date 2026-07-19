"""aibots: research brain for a paper-trading desk.

This library RESEARCHES and PROPOSES — it never submits orders to any broker.
"""

from __future__ import annotations

from importlib import import_module

from .journal import append_entry, read_entries
from .schemas import TOOL_NAMES, as_anthropic_tools, as_openai_tools

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "TOOL_NAMES",
    "as_openai_tools",
    "as_anthropic_tools",
    "append_entry",
    "read_entries",
    "run_research_turn",
    "tools",
    "agent",
]


def __getattr__(name: str):
    """Lazy submodule access so `aibots` imports even if optional deps are absent."""
    if name in {"tools", "agent"}:
        return import_module(f"aibots.{name}")
    if name == "run_research_turn":
        return import_module("aibots.agent.loop").run_research_turn
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
