"""Tests for pure-Python technical indicators."""

from __future__ import annotations

import pytest

from aibots.tools.indicators import compute_indicators


def _bars(closes: list[float]) -> list[dict]:
    out = []
    for i, c in enumerate(closes):
        out.append(
            {
                "date": f"2024-01-{(i % 28) + 1:02d}",
                "open": c - 0.5,
                "high": c + 1.0,
                "low": c - 1.0,
                "close": c,
                "volume": 1000 + i,
            }
        )
    return out


def test_empty_bars_raises():
    with pytest.raises(ValueError, match="non-empty"):
        compute_indicators([])


def test_short_series_yields_none_latest():
    result = compute_indicators(_bars([10.0, 11.0, 12.0]))
    latest = result["latest"]
    assert latest["sma_20"] is None
    assert latest["sma_50"] is None
    assert latest["rsi_14"] is None
    assert latest["macd"]["macd"] is None
    assert latest["bbands"]["middle"] is None
    assert result["context"]["bars_used"] == 3
    assert result["context"]["last_close"] == 12.0


def test_sma_on_flat_series():
    closes = [100.0] * 60
    result = compute_indicators(_bars(closes))
    assert result["latest"]["sma_20"] == 100.0
    assert result["latest"]["sma_50"] == 100.0
    assert result["latest"]["rsi_14"] == 50.0  # no gains/losses
    assert result["context"]["bars_used"] == 60


def test_rsi_all_up_moves_toward_100():
    closes = [float(i) for i in range(1, 40)]
    result = compute_indicators(_bars(closes), indicators=["rsi_14"])
    assert result["latest"]["rsi_14"] is not None
    assert result["latest"]["rsi_14"] > 70.0
    # Unrequested stay present as None
    assert result["latest"]["sma_20"] is None


def test_macd_and_bbands_populated():
    # Gentle uptrend — enough length for MACD signal (34+) and bbands (20+)
    closes = [100.0 + i * 0.3 for i in range(80)]
    result = compute_indicators(_bars(closes))
    macd = result["latest"]["macd"]
    assert macd["macd"] is not None
    assert macd["signal"] is not None
    assert macd["histogram"] is not None
    bb = result["latest"]["bbands"]
    assert bb["upper"] > bb["middle"] > bb["lower"]


def test_context_tails_length_5():
    closes = [float(i) for i in range(1, 30)]
    result = compute_indicators(_bars(closes))
    assert len(result["context"]["close_series_tail"]) == 5
    assert len(result["context"]["sma_20_series_tail"]) == 5
    assert result["context"]["close_series_tail"][-1] == 29.0
