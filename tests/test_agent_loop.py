"""Tests for forced research loop + critic. Network/LLM fully mocked."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aibots.agent import critic, loop
from aibots.agent.executor import execute_tool


def _bars(n: int = 60) -> list[dict]:
    return [
        {
            "date": f"2024-03-{(i % 28) + 1:02d}",
            "open": 100.0 + i * 0.1,
            "high": 101.0 + i * 0.1,
            "low": 99.0 + i * 0.1,
            "close": 100.5 + i * 0.1,
            "volume": 1_000_000,
        }
        for i in range(n)
    ]


def _price_payload(ticker: str = "AAPL") -> dict:
    return {
        "ticker": ticker,
        "bars": _bars(),
        "source": "yfinance",
        "cached": False,
    }


def _news_payload(ticker: str = "AAPL") -> dict:
    return {
        "ticker": ticker,
        "items": [
            {
                "headline": "Apple news",
                "datetime": "2024-03-01T00:00:00+00:00",
                "source": "Reuters",
                "url": "https://example.com",
            }
        ],
        "source": "finnhub",
    }


def _tool_call(name: str, arguments: str, call_id: str = "call_1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _completion(message, finish_reason: str = "tool_calls"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)]
    )


def _msg(content=None, tool_calls=None):
    m = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    m.model_dump = lambda exclude_none=True: {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in (tool_calls or [])
        ]
        if tool_calls
        else None,
    }
    return m


# --- extract_ticker -----------------------------------------------------------


def test_extract_ticker_from_research_phrase():
    assert loop.extract_ticker("Research AAPL. Pull the recent price history.") == "AAPL"


def test_extract_ticker_case_insensitive():
    assert loop.extract_ticker("please research msft today") == "MSFT"


# --- executor -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_propose_order_never_submits():
    result = await execute_tool(
        "propose_order",
        {
            "symbol": "aapl",
            "side": "buy",
            "qty": 5,
            "order_type": "limit",
            "limit_price": 190.0,
            "reason": "uptrend with room to run",
        },
    )
    assert result["submitted"] is False
    assert result["recorded"] is True
    assert result["symbol"] == "AAPL"
    assert result["side"] == "buy"


@pytest.mark.asyncio
async def test_executor_decide_hold():
    result = await execute_tool(
        "decide_hold",
        {"symbol": "AAPL", "reason": "no clear edge today after weak RSI"},
    )
    assert result["decision"] == "hold"
    assert result["submitted"] is False


@pytest.mark.asyncio
async def test_executor_unknown_tool():
    with pytest.raises(ValueError, match="unknown tool"):
        await execute_tool("submit_order", {"symbol": "AAPL"})


# --- forced research + propose ------------------------------------------------


@pytest.mark.asyncio
async def test_run_research_turn_forces_tools_then_proposes():
    propose_args = (
        '{"symbol":"AAPL","side":"buy","qty":5,"order_type":"limit",'
        '"limit_price":190,"reason":"sma20 above sma50 with rsi under 70"}'
    )
    propose_msg = _msg(
        content=None,
        tool_calls=[_tool_call("propose_order", propose_args)],
    )
    summary_msg = _msg(content="I'd paper-buy a small lot of AAPL here.", tool_calls=[])

    mock_create = AsyncMock(
        side_effect=[
            _completion(propose_msg),
            _completion(summary_msg, finish_reason="stop"),
        ]
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    with (
        patch.object(loop, "execute_tool", new=AsyncMock(side_effect=_fake_execute)) as mock_ex,
        patch("openai.AsyncOpenAI", return_value=mock_client),
        patch.object(
            loop,
            "run_bear_critique",
            new=AsyncMock(return_value="Price is extended into resistance."),
        ) as mock_crit,
    ):
        entry = await loop.run_research_turn(
            "Research AAPL and propose a paper trade if warranted.",
            api_key="test-key",
            with_critic=True,
        )

    names = [c["name"] for c in entry["tool_calls"]]
    # Forced research tools always run first
    assert names[:3] == ["get_price_history", "compute_indicators", "get_news"]
    assert "propose_order" in names
    assert entry["bull_proposal"]["order"]["symbol"] == "AAPL"
    assert entry["bull_proposal"]["order"]["side"] == "buy"
    assert entry["bear_critique"] == "Price is extended into resistance."
    assert entry["human_decision"] is None
    assert entry["ticker"] == "AAPL"
    mock_crit.assert_awaited_once()
    # Research tools + propose_order
    called_names = [c.args[0] for c in mock_ex.await_args_list]
    assert called_names.count("get_price_history") == 1
    assert called_names.count("compute_indicators") == 1
    assert called_names.count("get_news") == 1
    assert "propose_order" in called_names


@pytest.mark.asyncio
async def test_run_research_turn_no_critic_skips_pass():
    hold_args = '{"symbol":"AAPL","reason":"choppy tape, wait for clearer setup"}'
    hold_msg = _msg(tool_calls=[_tool_call("decide_hold", hold_args)])
    summary_msg = _msg(content="Holding for now.", tool_calls=[])

    mock_create = AsyncMock(
        side_effect=[
            _completion(hold_msg),
            _completion(summary_msg, finish_reason="stop"),
        ]
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    with (
        patch.object(loop, "execute_tool", new=AsyncMock(side_effect=_fake_execute)),
        patch("openai.AsyncOpenAI", return_value=mock_client),
        patch.object(loop, "run_bear_critique", new=AsyncMock()) as mock_crit,
    ):
        entry = await loop.run_research_turn(
            "Research AAPL.",
            api_key="k",
            with_critic=False,
        )

    assert entry["bear_critique"] is None
    assert entry["bull_proposal"]["order"] is None
    assert entry["bull_proposal"]["hold"]["reason"]
    mock_crit.assert_not_called()


async def _fake_execute(name: str, args: dict):
    if name == "get_price_history":
        return _price_payload(str(args.get("ticker", "AAPL")).upper())
    if name == "compute_indicators":
        from aibots.tools.indicators import compute_indicators

        return compute_indicators(args["bars"])
    if name == "get_news":
        return _news_payload(str(args.get("ticker", "AAPL")).upper())
    if name == "propose_order":
        from aibots.agent.executor import execute_tool as real

        return await real(name, args)
    if name == "decide_hold":
        from aibots.agent.executor import execute_tool as real

        return await real(name, args)
    raise ValueError(name)


# --- critic -------------------------------------------------------------------


def test_critic_message_compacts_bars():
    tool_calls = [
        {
            "name": "get_price_history",
            "ok": True,
            "args": {"ticker": "AAPL"},
            "result": {"ticker": "AAPL", "bars": _bars(30), "source": "yfinance"},
        },
        {
            "name": "propose_order",
            "ok": True,
            "args": {"symbol": "AAPL", "side": "buy", "qty": 1, "reason": "x" * 10},
            "result": {"symbol": "AAPL", "side": "buy", "qty": 1},
        },
    ]
    msg = critic.build_critic_user_message(
        tool_calls,
        bull_proposal={"text": "buy", "order": {"symbol": "AAPL", "side": "buy"}},
    )
    assert "bear case" in msg.lower()
    assert "bars_tail" in msg
    # Full 30-bar dump should not explode the prompt
    assert msg.count('"open"') <= 10


@pytest.mark.asyncio
async def test_run_bear_critique_returns_text():
    mock_create = AsyncMock(
        return_value=_completion(
            _msg(content="RSI is elevated and news is thin."),
            finish_reason="stop",
        )
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        text = await critic.run_bear_critique(
            tool_calls=[],
            bull_proposal={"text": "buy", "order": None},
            api_key="k",
        )
    assert "RSI" in text
