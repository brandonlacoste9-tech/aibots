"""Command-line interface: ``python -m aibots <command>``.

Subcommands:
- ``research TICKER [--no-critic]`` — run a research turn and journal it.
- ``journal [--limit N]`` — print recent journal entries.
- ``indicators TICKER [--period P]`` — print an indicator table.

aibots researches and proposes; it never submits orders anywhere.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

from aibots.agent.loop import run_research_turn
from aibots.journal import append_entry, read_entries
from aibots.tools.indicators import compute_indicators
from aibots.tools.market_data import get_price_history

EXIT_USAGE = 2  # argparse convention for usage/config errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aibots",
        description=(
            "Research brain for a paper-trading desk. "
            "Researches tickers and proposes paper trades; never submits orders."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_research = sub.add_parser(
        "research", help="Run an agent research turn on a ticker and journal the result."
    )
    p_research.add_argument("ticker", help="Ticker symbol, e.g. AAPL.")
    p_research.add_argument(
        "--no-critic", action="store_true", help="Skip the bear-case critic pass."
    )
    p_research.set_defaults(func=_cmd_research)

    p_journal = sub.add_parser("journal", help="Print recent journal entries.")
    p_journal.add_argument(
        "--limit", type=int, default=10, help="Max entries to show (default: 10)."
    )
    p_journal.set_defaults(func=_cmd_journal)

    p_ind = sub.add_parser(
        "indicators", help="Fetch price history and print technical indicators."
    )
    p_ind.add_argument("ticker", help="Ticker symbol, e.g. AAPL.")
    p_ind.add_argument(
        "--period", default="6mo", help="History period passed to yfinance (default: 6mo)."
    )
    p_ind.set_defaults(func=_cmd_indicators)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


# --- research -----------------------------------------------------------------


def _cmd_research(args: argparse.Namespace) -> int:
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print(
            "Error: XAI_API_KEY is not set.\n"
            "Copy .env.example to .env, fill in your xAI API key, and load it\n"
            "into your environment before running `aibots research`.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    ticker = args.ticker.strip().upper()
    user_message = (
        f"Research {ticker}. Pull the recent price history, compute the "
        "technical indicators, and check the latest news. Then either propose "
        "one paper trade with propose_order or pass with decide_hold."
    )
    try:
        entry = asyncio.run(
            run_research_turn(
                user_message,
                api_key=api_key,
                model=os.environ.get("XAI_MODEL") or None,
                base_url=os.environ.get("XAI_BASE_URL") or None,
                with_critic=not args.no_critic,
            )
        )
    except Exception as exc:  # model/network failure: report, don't traceback
        print(f"Error: research turn failed: {exc}", file=sys.stderr)
        return 1

    stored = append_entry(entry)
    _print_research_result(stored)
    return 0


def _print_research_result(entry: dict[str, Any]) -> None:
    print("=== Research result ===")
    print(entry.get("assistant_text") or "(no assistant text)")

    proposal = entry.get("bull_proposal")
    if proposal:
        print("\n--- Bull proposal ---")
        order = proposal.get("order")
        if order:
            line = (
                f"{str(order.get('side', '?')).upper()} "
                f"{order.get('qty', '?')} {order.get('symbol', '?')}"
                f" ({order.get('order_type', 'limit')}"
            )
            if order.get("limit_price") is not None:
                line += f" @ {order['limit_price']}"
            line += ")"
            print(line)
        if proposal.get("text"):
            print(proposal["text"])

    critique = entry.get("bear_critique")
    if critique:
        print("\n--- Bear critique ---")
        print(critique)

    print(
        f"\nJournaled as entry {entry.get('id', '?')}. "
        "No order was placed — human confirmation happens downstream."
    )


# --- journal ------------------------------------------------------------------


def _cmd_journal(args: argparse.Namespace) -> int:
    entries = read_entries(limit=args.limit)
    if not entries:
        print("Journal is empty.")
        return 0
    for entry in entries:
        _print_journal_entry(entry)
    return 0


def _print_journal_entry(entry: dict[str, Any]) -> None:
    ts = entry.get("ts", "?")
    short_id = str(entry.get("id", ""))[:8]
    print(f"--- {ts}  id={short_id} ---")
    print(f"Q: {entry.get('user_message', '')}")

    tool_calls = entry.get("tool_calls") or []
    if tool_calls:
        names = ", ".join(
            f"{c.get('name', '?')}{'' if c.get('ok') else ' (failed)'}" for c in tool_calls
        )
        print(f"tools: {names}")

    print(f"A: {_truncate(entry.get('assistant_text') or '')}")

    proposal = entry.get("bull_proposal")
    if proposal and proposal.get("order"):
        o = proposal["order"]
        print(
            f"proposal: {o.get('side')} {o.get('qty')} {o.get('symbol')}"
            f" ({o.get('order_type')})"
        )
    elif proposal:
        print("proposal: (text only, no order)")

    if entry.get("bear_critique"):
        print(f"bear: {_truncate(entry['bear_critique'])}")

    print(f"human_decision: {entry.get('human_decision')}")
    print()


def _truncate(text: str, width: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + "…"


# --- indicators ---------------------------------------------------------------


def _cmd_indicators(args: argparse.Namespace) -> int:
    ticker = args.ticker.strip().upper()
    try:
        data = asyncio.run(get_price_history(ticker, period=args.period))
        result = compute_indicators(data["bars"])
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    _print_indicators(ticker, data, result)
    return 0


def _print_indicators(ticker: str, data: dict[str, Any], result: dict[str, Any]) -> None:
    latest = result["latest"]
    ctx = result["context"]
    macd = latest.get("macd") or {}
    bbands = latest.get("bbands") or {}

    print(
        f"{ticker} indicators — {ctx.get('bars_used', 0)} bars "
        f"(source: {data.get('source', '?')}, last close: {_fmt(ctx.get('last_close'))})"
    )
    rows = [
        ("sma_20", latest.get("sma_20")),
        ("sma_50", latest.get("sma_50")),
        ("rsi_14", latest.get("rsi_14")),
        ("macd", macd.get("macd")),
        ("macd_signal", macd.get("signal")),
        ("macd_histogram", macd.get("histogram")),
        ("bbands_upper", bbands.get("upper")),
        ("bbands_middle", bbands.get("middle")),
        ("bbands_lower", bbands.get("lower")),
    ]
    width = max(len(name) for name, _ in rows)
    print(f"{'indicator'.ljust(width)}  value")
    print(f"{'-' * width}  -----")
    for name, value in rows:
        print(f"{name.ljust(width)}  {_fmt(value)}")


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
