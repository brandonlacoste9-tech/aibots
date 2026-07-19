"""Tests for desk preflight payload shaping."""

from __future__ import annotations

from pathlib import Path

from aibots.journal import append_entry, set_human_decision
from aibots.preflight import to_preflight_payload


def _sample_entry(**overrides) -> dict:
    base = {
        "user_message": "Research AAPL.",
        "assistant_text": "AAPL looks constructive on paper.",
        "ticker": "AAPL",
        "tool_calls": [
            {
                "name": "get_price_history",
                "ok": True,
                "args": {"ticker": "AAPL"},
                "result": {
                    "ticker": "AAPL",
                    "source": "yfinance",
                    "bars": [
                        {
                            "date": "2024-01-01",
                            "open": 1,
                            "high": 2,
                            "low": 0.5,
                            "close": 180.0,
                            "volume": 1,
                        },
                        {
                            "date": "2024-01-02",
                            "open": 1,
                            "high": 2,
                            "low": 0.5,
                            "close": 189.4,
                            "volume": 1,
                        },
                    ],
                },
            },
            {
                "name": "compute_indicators",
                "ok": True,
                "args": {},
                "result": {"latest": {"rsi_14": 61.2}, "context": {"last_close": 189.4}},
            },
            {
                "name": "get_news",
                "ok": True,
                "args": {},
                "result": {"items": [{"headline": "News"}], "source": "finnhub"},
            },
            {
                "name": "propose_order",
                "ok": True,
                "args": {},
                "result": {
                    "symbol": "AAPL",
                    "side": "buy",
                    "qty": 5,
                    "order_type": "limit",
                    "limit_price": 189.4,
                    "reason": "uptrend with room",
                    "submitted": False,
                },
            },
        ],
        "bull_proposal": {
            "text": "Momentum constructive; RSI not extreme.",
            "order": {
                "symbol": "AAPL",
                "side": "buy",
                "qty": 5,
                "order_type": "limit",
                "limit_price": 189.4,
                "reason": "uptrend with room",
            },
        },
        "bear_critique": "Extended into resistance; thin news.",
        "human_decision": None,
        "decided_at": None,
    }
    base.update(overrides)
    return base


def test_to_preflight_buy_order_shape(tmp_path: Path):
    stored = append_entry(_sample_entry(), path=str(tmp_path / "j.jsonl"))
    payload = to_preflight_payload(stored, ttl_seconds=180)

    assert payload["journal_id"] == stored["id"]
    assert payload["symbol"] == "AAPL"
    assert payload["side"] == "buy"
    assert payload["qty"] == 5
    assert payload["order_type"] == "limit"
    assert payload["limit_price"] == 189.4
    assert payload["ttl_seconds"] == 180
    assert "Momentum" in payload["bull"]["text"]
    assert payload["bull"]["order"]["side"] == "buy"
    assert "resistance" in payload["bear"]["text"]
    assert payload["tools"]["price"]["last_close"] == 189.4
    assert payload["tools"]["price"]["bars_count"] == 2
    assert payload["tools"]["indicators"]["latest"]["rsi_14"] == 61.2
    assert payload["tools"]["news"]["source"] == "finnhub"
    assert payload["human_decision"] is None


def test_to_preflight_hold():
    entry = _sample_entry(
        bull_proposal={
            "text": "No edge today.",
            "order": None,
            "hold": {"symbol": "AAPL", "reason": "choppy tape wait"},
        },
        bear_critique="Complacent hold also risks missing breakdown.",
        id="abc",
    )
    payload = to_preflight_payload(entry)
    assert payload["side"] == "hold"
    assert payload["symbol"] == "AAPL"
    assert "qty" not in payload
    assert payload["bull"]["order"] is None


def test_preflight_then_human_decision_round_trip(tmp_path: Path):
    path = str(tmp_path / "j.jsonl")
    stored = append_entry(_sample_entry(), path=path)
    payload = to_preflight_payload(stored, ttl_seconds=120)
    updated = set_human_decision(payload["journal_id"], "confirm", path=path)
    assert updated["human_decision"] == "confirm"
    assert updated["decided_at"]
