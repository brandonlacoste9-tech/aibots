"""Append-only JSONL journal for research turns and trade proposals."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_PATH = "journal.jsonl"


def _resolve_path(path: str | None) -> Path:
    return Path(path or os.environ.get("AIBOTS_JOURNAL_PATH") or _DEFAULT_PATH)


def append_entry(entry: dict, path: str | None = None) -> dict:
    """Append one entry as a JSON line; add `id` and `ts` if absent.

    Path resolution: explicit `path` > AIBOTS_JOURNAL_PATH env > ./journal.jsonl.
    Creates parent directories as needed. Returns the stored entry.
    """
    stored = dict(entry)
    stored.setdefault("id", uuid.uuid4().hex)
    stored.setdefault("ts", datetime.now(timezone.utc).isoformat())

    target = _resolve_path(path)
    if target.parent != Path(""):
        target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
    return stored


def read_entries(path: str | None = None, limit: int = 50) -> list[dict]:
    """Read up to the last `limit` entries, oldest to newest.

    Returns [] when the journal file does not exist. Blank or malformed
    lines are skipped rather than raising.
    """
    target = _resolve_path(path)
    if not target.exists():
        return []

    entries: list[dict] = []
    with target.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-limit:]
