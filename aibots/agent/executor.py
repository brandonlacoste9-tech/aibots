"""Dispatch research tools. Proposals are recorded only — never submitted."""

from __future__ import annotations

from typing import Any

from aibots.tools.indicators import compute_indicators
from aibots.tools.market_data import get_price_history
from aibots.tools.news import get_news

RESEARCH_TOOLS = frozenset({"get_price_history", "compute_indicators", "get_news"})
PROPOSAL_TOOLS = frozenset({"propose_order", "decide_hold"})


async def execute_tool(name: str, args: dict[str, Any]) -> Any:
    """Run one tool by name. Raises ValueError for unknown tools / bad args."""
    args = args or {}
    if name == "get_price_history":
        return await get_price_history(
            ticker=str(args["ticker"]),
            period=str(args.get("period") or "6mo"),
            interval=str(args.get("interval") or "1d"),
        )
    if name == "compute_indicators":
        bars = args.get("bars")
        if not isinstance(bars, list) or not bars:
            raise ValueError("compute_indicators requires a non-empty bars list")
        indicators = args.get("indicators")
        return compute_indicators(bars, indicators=indicators if isinstance(indicators, list) else None)
    if name == "get_news":
        return await get_news(
            ticker=str(args["ticker"]),
            days=int(args.get("days") or 7),
            limit=int(args.get("limit") or 10),
        )
    if name == "propose_order":
        return _record_propose_order(args)
    if name == "decide_hold":
        return _record_decide_hold(args)
    raise ValueError(f"unknown tool: {name}")


def _record_propose_order(args: dict[str, Any]) -> dict[str, Any]:
    symbol = str(args.get("symbol") or "").strip().upper()
    side = str(args.get("side") or "").strip().lower()
    qty = float(args["qty"])
    order_type = str(args.get("order_type") or "limit").strip().lower()
    reason = str(args.get("reason") or "").strip()
    if not symbol:
        raise ValueError("propose_order requires symbol")
    if side not in {"buy", "sell"}:
        raise ValueError("propose_order side must be buy or sell")
    if qty <= 0:
        raise ValueError("propose_order qty must be > 0")
    if len(reason) < 8:
        raise ValueError("propose_order reason must be at least 8 characters")
    if order_type not in {"limit", "market"}:
        raise ValueError("propose_order order_type must be limit or market")

    order: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "order_type": order_type,
        "reason": reason,
        "recorded": True,
        "submitted": False,
    }
    if args.get("limit_price") is not None:
        lp = float(args["limit_price"])
        if lp <= 0:
            raise ValueError("limit_price must be > 0")
        order["limit_price"] = lp
    return order


def _record_decide_hold(args: dict[str, Any]) -> dict[str, Any]:
    reason = str(args.get("reason") or "").strip()
    if len(reason) < 8:
        raise ValueError("decide_hold reason must be at least 8 characters")
    out: dict[str, Any] = {
        "decision": "hold",
        "reason": reason,
        "recorded": True,
        "submitted": False,
    }
    symbol = str(args.get("symbol") or "").strip().upper()
    if symbol:
        out["symbol"] = symbol
    return out
