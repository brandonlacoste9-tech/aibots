"""aibots: research brain for a paper-trading desk.

This library RESEARCHES and PROPOSES — it never submits orders to any broker.
"""

from __future__ import annotations

from importlib import import_module

from .journal import append_entry, read_entries, set_human_decision
from .preflight import research_for_desk, to_preflight_payload
from .schemas import TOOL_NAMES, as_anthropic_tools, as_openai_tools

__version__ = "0.1.1"

__all__ = [
    "__version__",
    "TOOL_NAMES",
    "as_openai_tools",
    "as_anthropic_tools",
    "append_entry",
    "read_entries",
    "set_human_decision",
    "to_preflight_payload",
    "research_for_desk",
    "run_research_turn",
    "tools",
    "agent",
]


def __getattr__(name: str):
    """Lazy submodule access so `aibots` imports even if optional deps are absent."""
    if name in {"tools", "agent", "preflight"}:
        return import_module(f"aibots.{name}")
    if name == "run_research_turn":
        return import_module("aibots.agent.loop").run_research_turn
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
