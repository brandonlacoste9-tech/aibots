"""Tests for aibots.journal: append/read round-trip, id/ts injection, limits."""

from __future__ import annotations

import json
from pathlib import Path

from aibots.journal import append_entry, read_entries


def test_read_missing_file_returns_empty_list(tmp_path: Path):
    assert read_entries(path=str(tmp_path / "nope.jsonl")) == []


def test_append_and_read_round_trip(tmp_path: Path):
    path = str(tmp_path / "journal.jsonl")
    entry = {"user_message": "research AAPL", "assistant_text": "looks bullish"}
    stored = append_entry(entry, path=path)

    entries = read_entries(path=path)
    assert len(entries) == 1
    assert entries[0]["user_message"] == "research AAPL"
    assert entries[0]["assistant_text"] == "looks bullish"


def test_id_and_ts_auto_added(tmp_path: Path):
    path = str(tmp_path / "journal.jsonl")
    stored = append_entry({"user_message": "hi"}, path=path)
    assert stored["id"]
    assert stored["ts"]
    assert stored["ts"].endswith("+00:00")

    on_disk = json.loads(Path(path).read_text(encoding="utf-8").strip())
    assert on_disk["id"] == stored["id"]
    assert on_disk["ts"] == stored["ts"]


def test_existing_id_and_ts_preserved(tmp_path: Path):
    path = str(tmp_path / "journal.jsonl")
    stored = append_entry({"id": "fixed-id", "ts": "2020-01-01T00:00:00+00:00"}, path=path)
    assert stored["id"] == "fixed-id"
    assert stored["ts"] == "2020-01-01T00:00:00+00:00"


def test_append_creates_parent_dirs(tmp_path: Path):
    path = str(tmp_path / "deep" / "nested" / "journal.jsonl")
    append_entry({"x": 1}, path=path)
    assert Path(path).exists()
    assert read_entries(path=path)[0]["x"] == 1


def test_limit_returns_last_n_oldest_first(tmp_path: Path):
    path = str(tmp_path / "journal.jsonl")
    for i in range(10):
        append_entry({"n": i}, path=path)

    entries = read_entries(path=path, limit=3)
    assert [e["n"] for e in entries] == [7, 8, 9]


def test_default_limit_is_50(tmp_path: Path):
    path = str(tmp_path / "journal.jsonl")
    for i in range(60):
        append_entry({"n": i}, path=path)
    entries = read_entries(path=path)
    assert len(entries) == 50
    assert entries[0]["n"] == 10
    assert entries[-1]["n"] == 59


def test_env_var_path_used_when_no_explicit_path(tmp_path: Path, monkeypatch):
    path = str(tmp_path / "env-journal.jsonl")
    monkeypatch.setenv("AIBOTS_JOURNAL_PATH", path)
    append_entry({"via": "env"})
    assert read_entries()[0]["via"] == "env"


def test_malformed_lines_skipped(tmp_path: Path):
    path = tmp_path / "journal.jsonl"
    path.write_text('{"ok": 1}\nnot-json\n\n{"ok": 2}\n', encoding="utf-8")
    entries = read_entries(path=str(path))
    assert [e["ok"] for e in entries] == [1, 2]
