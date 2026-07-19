"""Freeform stock-market Q&A agent.

Any market question: concepts, tickers, sectors, indicators, news context.
Uses research tools when numbers are needed; never submits orders.
"""

from __future__ import annotations

import json
from typing import Any

from aibots.agent.executor import RESEARCH_TOOLS, execute_tool
from aibots.schemas import as_openai_tools

MAX_TOOL_ROUNDS = 6
DEFAULT_MODEL = "grok-4-1-fast-non-reasoning"
DEFAULT_BASE_URL = "https://api.x.ai/v1"
MAX_HISTORY_MESSAGES = 24

CHAT_SYSTEM = """You are Indie Trader Desk — a sharp, practical stock-market assistant.

You answer ANY stock-market question: how markets work, tickers, sectors, earnings,
macro, technicals, risk, paper-trading strategy, jargon, comparisons, and news context.

Rules:
- Be clear and useful. Prefer plain language with precise terms when needed.
- When you cite specific prices, indicators (RSI/MACD/SMA), or recent headlines for a
  ticker, CALL the tools first. Never invent live numbers.
- Tools available: get_price_history, compute_indicators, get_news, get_company_profile.
  For compute_indicators, pass OHLCV bars from get_price_history.
  Use get_company_profile for sector/industry/company description (Bigdata KG).

- Educational / paper-trading context only. Never claim guaranteed profits.
  Never encourage reckless leverage. Say when something is uncertain or out of date.
- You never submit brokerage orders. If the user wants a trade idea, give a reasoned
  paper thesis (bull and risks) — do not claim an order was placed.
- If the question is conceptual (e.g. "what is a PE ratio?"), answer directly —
  tools are optional.
- Keep answers tight unless the user asks for depth.
"""


def _safe_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _research_tools_openai() -> list[dict]:
    allowed = RESEARCH_TOOLS
    return [t for t in as_openai_tools() if t["function"]["name"] in allowed]


def _normalize_history(history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Keep only user/assistant text turns for multi-message chat."""
    if not history:
        return []
    out: list[dict[str, str]] = []
    for msg in history:
        role = str(msg.get("role") or "").strip().lower()
        content = str(msg.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        out.append({"role": role, "content": content})
    return out[-MAX_HISTORY_MESSAGES:]


async def run_market_chat(
    user_message: str,
    *,
    api_key: str,
    history: list[dict[str, Any]] | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Answer a freeform market question with optional tool use.

    Returns::

        {
          "assistant_text": str,
          "tool_calls": [...],
          "model": str,
          "history": [ {role, content}, ... ]  # prior + this turn
        }
    """
    if not api_key:
        raise RuntimeError("api_key is required")
    text = (user_message or "").strip()
    if not text:
        raise ValueError("message must be non-empty")

    from openai import AsyncOpenAI

    resolved_model = model or DEFAULT_MODEL
    resolved_base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    client = AsyncOpenAI(api_key=api_key, base_url=resolved_base)
    tools = _research_tools_openai()

    prior = _normalize_history(history)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": CHAT_SYSTEM},
        *prior,
        {"role": "user", "content": text},
    ]

    tool_calls_log: list[dict[str, Any]] = []
    text_parts: list[str] = []

    for _ in range(MAX_TOOL_ROUNDS):
        resp = await client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.35,
        )
        choice = resp.choices[0]
        msg = choice.message
        messages.append(msg.model_dump(exclude_none=True))

        if msg.content:
            text_parts.append(msg.content)

        calls = msg.tool_calls or []
        if not calls:
            break

        for tc in calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}

            if name not in RESEARCH_TOOLS:
                err = f"tool {name!r} not available in market chat"
                tool_calls_log.append(
                    {"name": name, "args": args, "ok": False, "error": err}
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _safe_json({"error": err}),
                    }
                )
                continue

            try:
                # Auto-wire indicators: if bars missing but ticker present, fetch history first
                if name == "compute_indicators" and not args.get("bars"):
                    ticker = str(args.get("ticker") or "").strip().upper()
                    if ticker:
                        price = await execute_tool(
                            "get_price_history",
                            {"ticker": ticker, "period": "6mo", "interval": "1d"},
                        )
                        tool_calls_log.append(
                            {
                                "name": "get_price_history",
                                "args": {"ticker": ticker, "period": "6mo", "interval": "1d"},
                                "ok": True,
                                "result": price,
                            }
                        )
                        args = {**args, "bars": price.get("bars") or []}

                result = await execute_tool(name, args)
                # Don't dump full bar series into journal log for chat UI
                log_result = result
                if name == "get_price_history" and isinstance(result, dict):
                    bars = result.get("bars") or []
                    log_result = {
                        "ticker": result.get("ticker"),
                        "source": result.get("source"),
                        "bars_count": len(bars),
                        "last_close": bars[-1]["close"] if bars else None,
                        "bars_tail": bars[-5:] if bars else [],
                    }
                journal_args = dict(args)
                if name == "compute_indicators" and "bars" in journal_args:
                    journal_args = {
                        "bars_count": len(args.get("bars") or []),
                        "indicators": args.get("indicators"),
                    }
                tool_calls_log.append(
                    {
                        "name": name,
                        "args": journal_args,
                        "ok": True,
                        "result": log_result,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _safe_json(result),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                tool_calls_log.append(
                    {"name": name, "args": args, "ok": False, "error": str(exc)}
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _safe_json({"error": str(exc)}),
                    }
                )

    assistant_text = "\n".join(text_parts).strip() or (
        "I could not produce a reply. Try rephrasing your market question."
    )

    history_out = [
        *prior,
        {"role": "user", "content": text},
        {"role": "assistant", "content": assistant_text},
    ]

    return {
        "assistant_text": assistant_text,
        "tool_calls": tool_calls_log,
        "model": resolved_model,
        "history": history_out,
        "mode": "market_chat",
    }
