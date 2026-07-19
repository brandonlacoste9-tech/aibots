"""API tests for market chat endpoint (agent mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from aibots.api import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["llm_configured"] is True


def test_chat_endpoint(client, tmp_path, monkeypatch):
    monkeypatch.setenv("AIBOTS_JOURNAL_PATH", str(tmp_path / "j.jsonl"))
    fake = {
        "assistant_text": "Markets clear trades via supply and demand.",
        "tool_calls": [],
        "model": "test-model",
        "history": [
            {"role": "user", "content": "How do stocks trade?"},
            {
                "role": "assistant",
                "content": "Markets clear trades via supply and demand.",
            },
        ],
        "mode": "market_chat",
    }
    with patch("aibots.api.run_market_chat", new=AsyncMock(return_value=fake)):
        r = client.post("/api/chat", json={"message": "How do stocks trade?"})
    assert r.status_code == 200
    body = r.json()
    assert "supply and demand" in body["assistant_text"]
    assert body["journal_id"]


def test_chat_requires_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    c = TestClient(app)
    r = c.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 503
