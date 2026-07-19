"""Tests for freeform market chat (LLM fully mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aibots.agent import market_chat


def _msg(content=None, tool_calls=None):
    m = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    m.model_dump = lambda exclude_none=True: {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in (tool_calls or [])
        ]
        if tool_calls
        else None,
    }
    return m


def _completion(message, finish_reason="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)]
    )


def _tc(name, arguments, call_id="c1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


@pytest.mark.asyncio
async def test_conceptual_answer_no_tools():
    mock_create = AsyncMock(
        return_value=_completion(
            _msg(content="A P/E ratio is price divided by earnings per share.")
        )
    )
    client = MagicMock()
    client.chat.completions.create = mock_create

    with patch("openai.AsyncOpenAI", return_value=client):
        out = await market_chat.run_market_chat(
            "What is a PE ratio?",
            api_key="k",
        )

    assert "P/E" in out["assistant_text"] or "price" in out["assistant_text"].lower()
    assert out["tool_calls"] == []
    assert out["history"][-1]["role"] == "assistant"
    assert out["mode"] == "market_chat"


@pytest.mark.asyncio
async def test_uses_price_tool_then_answers():
    tool_msg = _msg(
        content=None,
        tool_calls=[_tc("get_price_history", '{"ticker":"AAPL"}')],
    )
    final_msg = _msg(content="AAPL last close looks constructive on the tape.")
    mock_create = AsyncMock(
        side_effect=[
            _completion(tool_msg, finish_reason="tool_calls"),
            _completion(final_msg, finish_reason="stop"),
        ]
    )
    client = MagicMock()
    client.chat.completions.create = mock_create

    price = {
        "ticker": "AAPL",
        "bars": [
            {
                "date": "2024-01-02",
                "open": 1,
                "high": 2,
                "low": 0.5,
                "close": 190.0,
                "volume": 1,
            }
        ],
        "source": "yfinance",
        "cached": False,
    }

    with (
        patch("openai.AsyncOpenAI", return_value=client),
        patch.object(
            market_chat, "execute_tool", new=AsyncMock(return_value=price)
        ) as ex,
    ):
        out = await market_chat.run_market_chat(
            "How is AAPL trading?",
            api_key="k",
        )

    assert "AAPL" in out["assistant_text"]
    assert any(t["name"] == "get_price_history" and t["ok"] for t in out["tool_calls"])
    ex.assert_awaited()


@pytest.mark.asyncio
async def test_empty_message_raises():
    with pytest.raises(ValueError):
        await market_chat.run_market_chat("  ", api_key="k")


@pytest.mark.asyncio
async def test_history_is_passed_through():
    mock_create = AsyncMock(
        return_value=_completion(_msg(content="Yes — RSI is a momentum oscillator."))
    )
    client = MagicMock()
    client.chat.completions.create = mock_create

    with patch("openai.AsyncOpenAI", return_value=client):
        out = await market_chat.run_market_chat(
            "Is RSI a momentum tool?",
            api_key="k",
            history=[
                {"role": "user", "content": "Tell me about indicators"},
                {"role": "assistant", "content": "Sure — SMA, RSI, MACD…"},
            ],
        )

    # first user message to the model should include system + prior + new
    call_messages = mock_create.await_args.kwargs["messages"]
    roles = [m["role"] if isinstance(m, dict) else getattr(m, "role", None) for m in call_messages]
    assert roles[0] == "system"
    assert any(
        isinstance(m, dict) and m.get("content") == "Tell me about indicators"
        for m in call_messages
    )
    assert out["history"][0]["content"] == "Tell me about indicators"
