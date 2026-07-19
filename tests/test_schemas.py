"""Tests for aibots.schemas: tool set, JSON-schema tightness, both export formats."""

from __future__ import annotations

import json

from aibots.schemas import TOOL_NAMES, as_anthropic_tools, as_openai_tools

EXPECTED_NAMES = ["get_price_history", "compute_indicators", "get_news", "propose_order", "decide_hold"]


def test_tool_names_exact_set():
    assert TOOL_NAMES == EXPECTED_NAMES


def test_openai_format_contains_all_tools():
    tools = as_openai_tools()
    assert [t["function"]["name"] for t in tools] == EXPECTED_NAMES
    for tool in tools:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert set(fn) == {"name", "description", "parameters"}
        assert fn["description"]
        assert fn["parameters"]["type"] == "object"
        assert fn["parameters"]["additionalProperties"] is False


def test_anthropic_format_contains_all_tools():
    tools = as_anthropic_tools()
    assert [t["name"] for t in tools] == EXPECTED_NAMES
    for tool in tools:
        assert set(tool) == {"name", "description", "input_schema"}
        assert tool["description"]
        assert tool["input_schema"]["type"] == "object"
        assert tool["input_schema"]["additionalProperties"] is False


def test_same_parameters_in_both_formats():
    openai_params = {t["function"]["name"]: t["function"]["parameters"] for t in as_openai_tools()}
    anthropic_params = {t["name"]: t["input_schema"] for t in as_anthropic_tools()}
    assert openai_params == anthropic_params


def test_get_price_history_params():
    props = _props(as_openai_tools(), "get_price_history")
    assert set(props) == {"ticker", "period", "interval"}
    assert "6mo" in props["period"]["enum"]
    assert "1d" in props["interval"]["enum"]
    assert props["period"]["default"] == "6mo"
    assert props["interval"]["default"] == "1d"
    assert _required(as_openai_tools(), "get_price_history") == ["ticker"]


def test_compute_indicators_params():
    tools = as_openai_tools()
    props = _props(tools, "compute_indicators")
    assert props["bars"]["type"] == "array"
    bar = props["bars"]["items"]
    assert bar["required"] == ["date", "open", "high", "low", "close", "volume"]
    assert bar["additionalProperties"] is False
    assert props["indicators"]["items"]["enum"] == ["sma_20", "sma_50", "rsi_14", "macd", "bbands"]
    assert _required(tools, "compute_indicators") == ["bars"]


def test_get_news_params():
    props = _props(as_openai_tools(), "get_news")
    assert props["days"]["minimum"] == 1
    assert props["days"]["default"] == 7
    assert props["limit"]["default"] == 10
    assert _required(as_openai_tools(), "get_news") == ["ticker"]


def test_propose_order_params():
    tools = as_openai_tools()
    props = _props(tools, "propose_order")
    assert props["side"]["enum"] == ["buy", "sell"]
    assert props["qty"]["exclusiveMinimum"] == 0
    assert props["order_type"]["enum"] == ["limit", "market"]
    assert props["order_type"]["default"] == "limit"
    assert props["limit_price"]["exclusiveMinimum"] == 0
    assert props["reason"]["minLength"] == 8
    assert _required(tools, "propose_order") == ["symbol", "side", "qty", "reason"]


def test_decide_hold_params():
    tools = as_openai_tools()
    props = _props(tools, "decide_hold")
    assert set(props) == {"symbol", "reason"}
    assert props["reason"]["minLength"] == 8
    assert _required(tools, "decide_hold") == ["reason"]


def test_schemas_are_json_serializable():
    json.dumps(as_openai_tools())
    json.dumps(as_anthropic_tools())


def _props(tools: list[dict], name: str) -> dict:
    return next(t["function"]["parameters"]["properties"] for t in tools if t["function"]["name"] == name)


def _required(tools: list[dict], name: str) -> list[str]:
    return next(t["function"]["parameters"]["required"] for t in tools if t["function"]["name"] == name)
