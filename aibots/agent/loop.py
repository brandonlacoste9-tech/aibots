"""Forced research agent loop (xAI / OpenAI-compatible tool calling).

Pipeline:
1. Deterministic research tools run first (price → indicators → news).
2. Grok may only propose_order or decide_hold, using those tool outputs.
3. Optional single bear-case critic pass over the same data.

This library RESEARCHES and PROPOSES. It never submits orders.
"""

from __future__ import annotations

import json
import re
from typing import Any

from aibots.agent.critic import run_bear_critique
from aibots.agent.executor import PROPOSAL_TOOLS, RESEARCH_TOOLS, execute_tool
from aibots.schemas import as_openai_tools

MAX_TOOL_ROUNDS = 4
DEFAULT_MODEL = "grok-4-1-fast-non-reasoning"
DEFAULT_BASE_URL = "https://api.x.ai/v1"

SYSTEM_PROMPT = """You are Grok — research analyst for a paper-trading desk.

Hard rules:
- Research tool outputs are ALREADY provided below (price history, indicators, news).
- You MUST base every number you cite on those tool outputs. Never invent prices, RSI, MACD, headlines, or dates.
- After reading the tool outputs, call exactly one of:
  · propose_order — when a paper trade is worth practicing
  · decide_hold — when no trade is warranted
- Prefer limit orders. Keep size modest. reason must be a concrete thesis citing tool numbers.
- Language: "looks constructive / I'd skip on paper" — never "guaranteed" or "you will make money".
- Paper trading only. You never submit orders; proposals are journaled for human review.
"""

_TICKER_RE = re.compile(r"\b([A-Z]{1,5}(?:\.[A-Z])?)\b")
# Common English words that look like tickers; filter when extracting.
_TICKER_STOP = frozenset(
    {
        "A",
        "I",
        "THE",
        "AND",
        "OR",
        "FOR",
        "WITH",
        "FROM",
        "THEN",
        "THAN",
        "THAT",
        "THIS",
        "PULL",
        "RECENT",
        "PRICE",
        "HISTORY",
        "COMPUTE",
        "TECHNICAL",
        "INDICATORS",
        "CHECK",
        "LATEST",
        "NEWS",
        "EITHER",
        "PROPOSE",
        "PAPER",
        "TRADE",
        "PASS",
        "HOLD",
        "RESEARCH",
        "MUST",
        "CALL",
        "TOOLS",
        "BUY",
        "SELL",
        "LIMIT",
        "MARKET",
    }
)


def extract_ticker(user_message: str) -> str | None:
    """Best-effort ticker extraction from a research prompt."""
    # Prefer explicit "Research TICKER" / "ticker TICKER"
    m = re.search(r"(?:research|ticker|symbol|analyze|look\s*up)\s+([A-Za-z]{1,5}(?:\.[A-Za-z])?)", user_message, re.I)
    if m:
        return m.group(1).upper()
    candidates = [c for c in _TICKER_RE.findall(user_message.upper()) if c not in _TICKER_STOP]
    return candidates[0] if candidates else None


def _safe_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _record(
    name: str,
    args: dict[str, Any],
    *,
    ok: bool,
    result: Any = None,
    error: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": name, "args": args, "ok": ok}
    if ok:
        entry["result"] = result
    else:
        entry["error"] = error or "unknown error"
    return entry


async def _run_forced_research(ticker: str) -> list[dict[str, Any]]:
    """Always execute the three research tools before the model proposes."""
    tool_calls: list[dict[str, Any]] = []

    price_args = {"ticker": ticker, "period": "6mo", "interval": "1d"}
    try:
        price = await execute_tool("get_price_history", price_args)
        tool_calls.append(_record("get_price_history", price_args, ok=True, result=price))
        bars = price.get("bars") or []
    except Exception as exc:  # noqa: BLE001
        tool_calls.append(_record("get_price_history", price_args, ok=False, error=str(exc)))
        bars = []

    ind_args: dict[str, Any] = {"bars": bars} if bars else {"bars": []}
    try:
        if not bars:
            raise ValueError("no bars available for indicator computation")
        indicators = await execute_tool("compute_indicators", ind_args)
        # Journal a compact args form (full bars already live under get_price_history).
        journal_args = {"ticker": ticker, "bars_count": len(bars), "indicators": None}
        tool_calls.append(
            _record(
                "compute_indicators",
                journal_args,
                ok=True,
                result=indicators,
            )
        )
    except Exception as exc:  # noqa: BLE001
        tool_calls.append(
            _record(
                "compute_indicators",
                {"ticker": ticker, "bars_count": len(bars)},
                ok=False,
                error=str(exc),
            )
        )

    news_args = {"ticker": ticker, "days": 7, "limit": 10}
    try:
        news = await execute_tool("get_news", news_args)
        tool_calls.append(_record("get_news", news_args, ok=True, result=news))
    except Exception as exc:  # noqa: BLE001
        tool_calls.append(_record("get_news", news_args, ok=False, error=str(exc)))

    return tool_calls


def _research_context_message(tool_calls: list[dict[str, Any]]) -> str:
    """Compact tool dump for the model (truncate long bar series)."""
    blocks: list[dict[str, Any]] = []
    for call in tool_calls:
        block: dict[str, Any] = {
            "tool": call["name"],
            "ok": call["ok"],
            "args": call.get("args"),
        }
        if call["ok"]:
            result = call.get("result")
            if call["name"] == "get_price_history" and isinstance(result, dict):
                bars = result.get("bars") or []
                block["result"] = {
                    "ticker": result.get("ticker"),
                    "source": result.get("source"),
                    "bars_count": len(bars),
                    "bars_tail": bars[-10:] if isinstance(bars, list) else [],
                }
            else:
                block["result"] = result
        else:
            block["error"] = call.get("error")
        blocks.append(block)
    return (
        "Forced research tool outputs (already executed; do not re-fetch):\n"
        f"```json\n{_safe_json(blocks)}\n```\n"
        "Now call propose_order or decide_hold once."
    )


def _proposal_tools_openai() -> list[dict]:
    """Only proposal tools are exposed after forced research."""
    allowed = PROPOSAL_TOOLS
    return [t for t in as_openai_tools() if t["function"]["name"] in allowed]


def _extract_bull_proposal(
    tool_calls: list[dict[str, Any]],
    assistant_text: str,
) -> dict[str, Any] | None:
    """Pull the last successful propose_order / decide_hold into bull_proposal."""
    for call in reversed(tool_calls):
        if not call.get("ok"):
            continue
        name = call.get("name")
        result = call.get("result")
        if name == "propose_order" and isinstance(result, dict):
            order = {k: v for k, v in result.items() if k not in {"recorded", "submitted"}}
            return {"text": assistant_text, "order": order}
        if name == "decide_hold" and isinstance(result, dict):
            return {
                "text": assistant_text,
                "order": None,
                "hold": {
                    "symbol": result.get("symbol"),
                    "reason": result.get("reason"),
                },
            }
    return None


async def _llm_propose(
    *,
    user_message: str,
    research_calls: list[dict[str, Any]],
    api_key: str,
    model: str,
    base_url: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Run the model with only proposal tools; returns (assistant_text, new tool_calls)."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    tools = _proposal_tools_openai()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
        {"role": "user", "content": _research_context_message(research_calls)},
    ]

    proposal_calls: list[dict[str, Any]] = []
    text_parts: list[str] = []

    for _ in range(MAX_TOOL_ROUNDS):
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="required",
            temperature=0.2,
        )
        choice = resp.choices[0]
        msg = choice.message
        messages.append(msg.model_dump(exclude_none=True))

        if msg.content:
            text_parts.append(msg.content)

        tool_calls = msg.tool_calls or []
        if not tool_calls:
            # Model produced text only; nudge once via next loop if rounds remain
            if choice.finish_reason == "stop":
                break
            continue

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}

            if name not in PROPOSAL_TOOLS:
                err = f"tool {name!r} not allowed after research; use propose_order or decide_hold"
                proposal_calls.append(_record(name, args, ok=False, error=err))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _safe_json({"error": err}),
                    }
                )
                continue

            try:
                result = await execute_tool(name, args)
                proposal_calls.append(_record(name, args, ok=True, result=result))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _safe_json(result),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                proposal_calls.append(_record(name, args, ok=False, error=str(exc)))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _safe_json({"error": str(exc)}),
                    }
                )

        # Done once we have a successful proposal/hold
        if any(c.get("ok") and c.get("name") in PROPOSAL_TOOLS for c in proposal_calls):
            # Optional short closing text without more tools
            follow = await client.chat.completions.create(
                model=model,
                messages=messages
                + [
                    {
                        "role": "user",
                        "content": (
                            "In 2–4 sentences, summarize the proposal (or hold) for the human. "
                            "Cite only numbers already present in the tool outputs. No new tools."
                        ),
                    }
                ],
                temperature=0.2,
            )
            closing = (follow.choices[0].message.content or "").strip()
            if closing:
                text_parts.append(closing)
            break

    assistant_text = "\n".join(text_parts).strip() or "Research complete. See proposal tools."
    return assistant_text, proposal_calls


async def run_research_turn(
    user_message: str,
    *,
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
    with_critic: bool = True,
    ticker: str | None = None,
) -> dict[str, Any]:
    """Run one forced-research turn and return a journal-entry-shaped dict.

    Fields:
      - user_message, assistant_text
      - tool_calls (research + proposal)
      - bull_proposal, bear_critique
      - human_decision, decided_at (always None here — human confirms downstream)
      - model, ticker
    """
    if not api_key:
        raise RuntimeError("api_key is required")

    resolved_model = model or DEFAULT_MODEL
    resolved_base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    symbol = (ticker or extract_ticker(user_message) or "").strip().upper()
    if not symbol:
        raise ValueError(
            "could not extract a ticker from the message; pass ticker= explicitly"
        )

    research_calls = await _run_forced_research(symbol)
    assistant_text, proposal_calls = await _llm_propose(
        user_message=user_message,
        research_calls=research_calls,
        api_key=api_key,
        model=resolved_model,
        base_url=resolved_base,
    )

    tool_calls = research_calls + proposal_calls
    bull_proposal = _extract_bull_proposal(proposal_calls, assistant_text)

    bear_critique: str | None = None
    if with_critic:
        bear_critique = await run_bear_critique(
            tool_calls=tool_calls,
            bull_proposal=bull_proposal,
            assistant_text=assistant_text,
            api_key=api_key,
            model=resolved_model,
            base_url=resolved_base,
        )

    return {
        "user_message": user_message,
        "assistant_text": assistant_text,
        "tool_calls": tool_calls,
        "bull_proposal": bull_proposal,
        "bear_critique": bear_critique,
        "human_decision": None,
        "decided_at": None,
        "model": resolved_model,
        "ticker": symbol,
        "research_tools_used": sorted(
            {c["name"] for c in research_calls if c["name"] in RESEARCH_TOOLS}
        ),
    }
