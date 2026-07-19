"""Bigdata.com client tests (SDK mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from aibots.tools import bigdata as bd


def _company(**kwargs):
    base = dict(
        id="D8442A",
        name="Apple Inc.",
        ticker="AAPL",
        description="Makes phones",
        sector="Technology",
        industry="Computer Hardware",
        industry_group="Computer Hardware",
        country="United States",
        company_type="Public",
        webpage="http://www.apple.com",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_resolve_company_by_ticker(monkeypatch):
    monkeypatch.setenv("BIGDATA_API_KEY", "bd_v2_test")
    mock_bd = MagicMock()
    mock_bd.knowledge_graph.autosuggest.return_value = [
        _company(ticker="APLE", name="Other"),
        _company(ticker="AAPL"),
    ]
    with patch.object(bd, "_client", return_value=mock_bd):
        profile = await bd.get_company_profile("aapl")
    assert profile["ticker"] == "AAPL"
    assert profile["name"] == "Apple Inc."
    assert profile["sector"] == "Technology"
    assert profile["source"] == "bigdata"
    assert profile["entity_id"] == "D8442A"


@pytest.mark.asyncio
async def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("BIGDATA_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="BIGDATA_API_KEY"):
        await bd.get_company_profile("AAPL")


@pytest.mark.asyncio
async def test_get_news_degrades_on_search_error(monkeypatch):
    monkeypatch.setenv("BIGDATA_API_KEY", "bd_v2_test")
    mock_bd = MagicMock()
    mock_bd.knowledge_graph.autosuggest.return_value = [_company()]
    mock_bd.search.new.return_value.run.side_effect = RuntimeError("Access denied")
    with patch.object(bd, "_client", return_value=mock_bd):
        out = await bd.get_news("AAPL", limit=3)
    assert out["source"] == "bigdata"
    assert out["items"] == []
    assert "unavailable" in out["note"].lower() or "denied" in out["note"].lower()
