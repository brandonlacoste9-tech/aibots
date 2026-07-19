"""Desk / preflight payload shaping for the control plane.

Maps a journaled research entry into the modal contract:
bull + bear side-by-side, optional tool snapshots, TTL for human confirm.
Never submits orders.
"""

from __future__ import annotations

from typing import Any

from aibots.journal import append_entry


def _tool_result(tool_calls: list[dict[str, Any]], name: str) -> Any | None:
    for call in tool_calls or []:
        if call.get("name") == name and call.get("ok"):
            return call.get("result")
    return None


def _compact_price(result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    bars = result.get("bars") or []
    return {
        "ticker": result.get("ticker"),
        "source": result.get("source"),
        "cached": result.get("cached"),
        "bars_count": len(bars) if isinstance(bars, list) else 0,
        "bars_tail": bars[-5:] if isinstance(bars, list) else [],
        "last_close": bars[-1].get("close") if isinstance(bars, list) and bars else None,
    }


def to_preflight_payload(entry: dict[str, Any], *, ttl_seconds: int = 180) -> dict[str, Any]:
    """Shape a journal entry (or run_research_turn dict) for the preflight modal.

    Recommended TypeScript-facing contract — see docs/DESK_INTEGRATION.md.
    """
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    bull = entry.get("bull_proposal") or {}
    order = bull.get("order") if isinstance(bull, dict) else None
    hold = bull.get("hold") if isinstance(bull, dict) else None
    tool_calls = entry.get("tool_calls") or []

    symbol = (
        (order or {}).get("symbol")
        or (hold or {}).get("symbol")
        or entry.get("ticker")
        or ""
    )
    symbol = str(symbol).upper() if symbol else ""

    if order and order.get("side") in {"buy", "sell"}:
        side: str = str(order["side"])
    else:
        side = "hold"

    bull_text = ""
    if isinstance(bull, dict):
        bull_text = str(bull.get("text") or "")
    if not bull_text:
        bull_text = str(entry.get("assistant_text") or "")

    bear_text = entry.get("bear_critique")
    if bear_text is None:
        bear_text = ""
    else:
        bear_text = str(bear_text)

    payload: dict[str, Any] = {
        "journal_id": entry.get("id"),
        "symbol": symbol,
        "side": side,
        "ttl_seconds": int(ttl_seconds),
        "bull": {
            "text": bull_text,
            "order": order,
        },
        "bear": {
            "text": bear_text,
        },
        "tools": {
            "price": _compact_price(_tool_result(tool_calls, "get_price_history")),
            "indicators": _tool_result(tool_calls, "compute_indicators"),
            "news": _tool_result(tool_calls, "get_news"),
        },
        "assistant_text": entry.get("assistant_text"),
        "human_decision": entry.get("human_decision"),
        "decided_at": entry.get("decided_at"),
    }

    if order:
        if order.get("qty") is not None:
            payload["qty"] = order["qty"]
        if order.get("order_type") is not None:
            payload["order_type"] = order["order_type"]
        if order.get("limit_price") is not None:
            payload["limit_price"] = order["limit_price"]

    return payload


async def research_for_desk(
    user_message: str,
    *,
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
    with_critic: bool = True,
    ticker: str | None = None,
    ttl_seconds: int = 180,
    journal_path: str | None = None,
) -> dict[str, Any]:
    """Run research, append to journal, return preflight modal payload.

    One-shot helper for the control plane. Does not submit orders.
    """
    from aibots.agent.loop import run_research_turn

    entry = await run_research_turn(
        user_message,
        api_key=api_key,
        model=model,
        base_url=base_url,
        with_critic=with_critic,
        ticker=ticker,
    )
    stored = append_entry(entry, path=journal_path)
    return to_preflight_payload(stored, ttl_seconds=ttl_seconds)
