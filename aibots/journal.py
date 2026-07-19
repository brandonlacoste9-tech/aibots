"""Append-only JSONL journal for research turns and trade proposals.

Human decisions are a controlled rewrite of a single line (full-file rewrite),
safe for small desk journals — not a multi-writer database.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_PATH = "journal.jsonl"

# Allowed human_decision values for desk close-loop.
HUMAN_DECISIONS = frozenset({"confirm", "reject", "edit", "expired"})


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
    stored.setdefault("human_decision", None)
    stored.setdefault("decided_at", None)

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


def set_human_decision(
    entry_id: str,
    decision: str,
    *,
    notes: str | None = None,
    path: str | None = None,
) -> dict | None:
    """Update an existing journal entry with the human decision.

    Rewrites the entire JSONL file (safe for small journals).
    Returns the updated entry or None if not found.

    decision: confirm | reject | edit | expired
    """
    decision = (decision or "").strip().lower()
    if decision not in HUMAN_DECISIONS:
        raise ValueError(
            f"decision must be one of {sorted(HUMAN_DECISIONS)}, got {decision!r}"
        )
    if not entry_id:
        raise ValueError("entry_id is required")

    target = _resolve_path(path)
    if not target.exists():
        return None

    entries: list[dict] = []
    updated: dict | None = None
    with target.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("id") == entry_id:
                entry["human_decision"] = decision
                entry["decided_at"] = datetime.now(timezone.utc).isoformat()
                if notes is not None:
                    entry["human_notes"] = notes
                updated = entry
            entries.append(entry)

    if updated is None:
        return None

    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    tmp.replace(target)
    return updated
