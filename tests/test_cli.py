"""Tests for the aibots CLI. All network/model calls are mocked at the
``aibots.cli`` boundary; nothing here touches the network or an LLM."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aibots import cli


def _sample_entry() -> dict:
    """A journal-entry-shaped dict as produced by run_research_turn."""
    return {
        "user_message": "Research AAPL. ...",
        "assistant_text": "AAPL looks constructive; proposing a small buy.",
        "tool_calls": [
            {
                "name": "get_price_history",
                "args": {"ticker": "AAPL"},
                "ok": True,
                "result": {"ticker": "AAPL", "bars": []},
            },
            {
                "name": "propose_order",
                "args": {"symbol": "AAPL", "side": "buy", "qty": 5},
                "ok": True,
                "result": {"recorded": True},
            },
        ],
        "bull_proposal": {
            "text": "Momentum is up and RSI is not overbought.",
            "order": {
                "symbol": "AAPL",
                "side": "buy",
                "qty": 5,
                "order_type": "limit",
                "limit_price": 190.0,
                "reason": "uptrend with room to run",
            },
        },
        "bear_critique": "Price is rising into resistance near 195 on thin news flow.",
        "human_decision": None,
        "decided_at": None,
    }


def _sample_bars() -> list[dict]:
    return [
        {
            "date": f"2026-01-{day:02d}",
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 100,
        }
        for day in range(1, 6)
    ]


def _sample_indicator_result() -> dict:
    return {
        "latest": {
            "sma_20": 185.12,
            "sma_50": 178.9,
            "rsi_14": 61.23,
            "macd": {"macd": 1.23, "signal": 1.11, "histogram": 0.12},
            "bbands": {"upper": 195.0, "middle": 185.12, "lower": 175.2},
        },
        "context": {
            "last_close": 189.43,
            "bars_used": 120,
            "sma_20_series_tail": [184.0, 184.5, 185.0, 185.1, 185.12],
            "close_series_tail": [186.0, 187.0, 188.0, 189.0, 189.43],
        },
    }


# --- research -----------------------------------------------------------------


def test_research_routes_and_journals(monkeypatch, capsys):
    entry = _sample_entry()
    stored = {**entry, "id": "abc123def456", "ts": "2026-01-05T00:00:00+00:00"}
    monkeypatch.setenv("XAI_API_KEY", "test-key")

    with patch.object(cli, "run_research_turn", new=AsyncMock(return_value=entry)) as mock_run, \
         patch.object(cli, "append_entry", return_value=stored) as mock_append:
        code = cli.main(["research", "aapl"])

    assert code == 0
    mock_run.assert_awaited_once()
    call = mock_run.await_args
    assert "AAPL" in call.args[0]  # ticker normalized into the user message
    assert call.kwargs["api_key"] == "test-key"
    assert call.kwargs["with_critic"] is True
    mock_append.assert_called_once_with(entry)

    out = capsys.readouterr().out
    assert "AAPL looks constructive" in out
    assert "BUY 5 AAPL" in out
    assert "resistance near 195" in out
    assert "abc123de" in out


def test_research_no_critic_flag(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    entry = {**_sample_entry(), "bear_critique": None}

    with patch.object(cli, "run_research_turn", new=AsyncMock(return_value=entry)) as mock_run, \
         patch.object(cli, "append_entry", side_effect=lambda e: e):
        code = cli.main(["research", "AAPL", "--no-critic"])

    assert code == 0
    assert mock_run.await_args.kwargs["with_critic"] is False


def test_research_missing_api_key_exits_2(monkeypatch, capsys):
    monkeypatch.delenv("XAI_API_KEY", raising=False)

    with patch.object(cli, "run_research_turn", new=AsyncMock()) as mock_run, \
         patch.object(cli, "append_entry") as mock_append:
        code = cli.main(["research", "AAPL"])

    assert code == 2
    mock_run.assert_not_called()
    mock_append.assert_not_called()
    err = capsys.readouterr().err
    assert "XAI_API_KEY" in err


def test_research_turn_failure_exits_1(monkeypatch, capsys):
    monkeypatch.setenv("XAI_API_KEY", "test-key")

    with patch.object(
        cli, "run_research_turn", new=AsyncMock(side_effect=RuntimeError("boom"))
    ), patch.object(cli, "append_entry") as mock_append:
        code = cli.main(["research", "AAPL"])

    assert code == 1
    mock_append.assert_not_called()
    assert "boom" in capsys.readouterr().err


# --- journal ------------------------------------------------------------------


def test_journal_prints_entries(capsys):
    entries = [{**_sample_entry(), "id": "abc123def456", "ts": "2026-01-05T00:00:00+00:00"}]

    with patch.object(cli, "read_entries", return_value=entries) as mock_read:
        code = cli.main(["journal", "--limit", "3"])

    assert code == 0
    mock_read.assert_called_once_with(limit=3)
    out = capsys.readouterr().out
    assert "2026-01-05" in out
    assert "abc123de" in out
    assert "Research AAPL" in out
    assert "get_price_history" in out
    assert "buy 5 AAPL" in out
    assert "human_decision: None" in out


def test_journal_empty(capsys):
    with patch.object(cli, "read_entries", return_value=[]):
        code = cli.main(["journal"])

    assert code == 0
    assert "empty" in capsys.readouterr().out.lower()


# --- indicators ---------------------------------------------------------------


def test_indicators_prints_table(capsys):
    bars = _sample_bars()
    price_payload = {"ticker": "AAPL", "bars": bars, "source": "yfinance", "cached": False}

    with patch.object(cli, "get_price_history", new=AsyncMock(return_value=price_payload)) as mock_px, \
         patch.object(cli, "compute_indicators", return_value=_sample_indicator_result()) as mock_ci:
        code = cli.main(["indicators", "aapl", "--period", "1y"])

    assert code == 0
    mock_px.assert_awaited_once()
    assert mock_px.await_args.args[0] == "AAPL"
    assert mock_px.await_args.kwargs["period"] == "1y"
    mock_ci.assert_called_once_with(bars)

    out = capsys.readouterr().out
    assert "sma_20" in out
    assert "185.12" in out
    assert "macd_histogram" in out
    assert "bbands_lower" in out
    assert "last close: 189.43" in out


def test_indicators_insufficient_data_shows_na(capsys):
    bars = _sample_bars()
    result = _sample_indicator_result()
    result["latest"] = {
        "sma_20": None,
        "sma_50": None,
        "rsi_14": None,
        "macd": {"macd": None, "signal": None, "histogram": None},
        "bbands": {"upper": None, "middle": None, "lower": None},
    }
    price_payload = {"ticker": "AAPL", "bars": bars, "source": "yfinance", "cached": False}

    with patch.object(cli, "get_price_history", new=AsyncMock(return_value=price_payload)), \
         patch.object(cli, "compute_indicators", return_value=result):
        code = cli.main(["indicators", "AAPL"])

    assert code == 0
    assert "n/a" in capsys.readouterr().out


def test_indicators_unknown_ticker_exits_2(capsys):
    with patch.object(
        cli, "get_price_history", new=AsyncMock(side_effect=ValueError("unknown ticker: XX"))
    ):
        code = cli.main(["indicators", "XX"])

    assert code == 2
    assert "unknown ticker" in capsys.readouterr().err


# --- parser -------------------------------------------------------------------


def test_no_subcommand_exits_with_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2
