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


# --- Regression / property baselines (fixed synthetic series) -----------------

# Oldest → newest. Mild uptrend used as a frozen fixture.
CLOSES_BASE = [
    100,
    102,
    101,
    103,
    105,
    104,
    106,
    108,
    107,
    109,
    111,
    110,
    112,
    114,
    113,
    115,
    117,
    116,
    118,
    120,
]

# Golden values from aibots pure-Python Wilder RSI / EMA MACD / population BB
# (freeze against accidental formula drift; re-compute only with intentional changes).
_GOLDEN_LONG = CLOSES_BASE * 3  # 60 bars — enough for MACD signal (needs ~34)


def test_rsi_14_range_and_golden_value():
    result = compute_indicators(_bars(CLOSES_BASE), indicators=["rsi_14"])
    rsi = result["latest"]["rsi_14"]
    assert rsi is not None
    assert 0.0 <= rsi <= 100.0
    # Uptrend series → RSI elevated
    assert rsi > 50.0
    # Golden: Wilder RSI-14 on CLOSES_BASE (frozen pure-Python baseline)
    assert abs(rsi - 81.7864) < 1e-4


def test_macd_signal_and_histogram_golden():
    result = compute_indicators(_bars(_GOLDEN_LONG), indicators=["macd"])
    macd = result["latest"]["macd"]
    assert macd["macd"] is not None
    assert macd["signal"] is not None
    assert macd["histogram"] is not None
    # histogram == macd - signal (within float packing)
    assert abs(macd["histogram"] - (macd["macd"] - macd["signal"])) < 1e-6
    # Golden on CLOSES_BASE * 3
    assert abs(macd["macd"] - 2.3627) < 1e-4
    assert abs(macd["signal"] - 1.2044) < 1e-4
    assert abs(macd["histogram"] - 1.1583) < 1e-4


def test_bbands_order_and_golden():
    result = compute_indicators(_bars(CLOSES_BASE), indicators=["bbands"])
    bb = result["latest"]["bbands"]
    assert bb["upper"] > bb["middle"] > bb["lower"]
    # middle is SMA20 of the 20 closes; bands use population stddev * 2
    assert abs(bb["middle"] - 109.55) < 1e-4
    assert abs(bb["upper"] - 121.2543) < 1e-4
    assert abs(bb["lower"] - 97.8457) < 1e-4


def test_rsi_all_equal_is_fifty():
    result = compute_indicators(_bars([50.0] * 30), indicators=["rsi_14"])
    assert result["latest"]["rsi_14"] == 50.0


def test_rsi_strict_uptrend_near_100():
    closes = [100.0 + i for i in range(40)]
    result = compute_indicators(_bars(closes), indicators=["rsi_14"])
    assert result["latest"]["rsi_14"] is not None
    assert result["latest"]["rsi_14"] > 90.0
