"""Disk-backed session list summary cache with mtime and rules fingerprint keys."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, TypedDict

from models.project import ProjectSessionRowDict, SessionListItemDict
from models.session import QuickSessionInfoDict, SessionDict

DEFAULT_MAX_ROWS = 2000


def max_cache_rows() -> int:
    """Return LRU capacity (override via CLAUDE_CODE_CHAT_BROWSER_SUMMARY_CACHE_MAX_ROWS)."""
    raw = os.environ.get("CLAUDE_CODE_CHAT_BROWSER_SUMMARY_CACHE_MAX_ROWS", "").strip()
    if not raw:
        return DEFAULT_MAX_ROWS
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_MAX_ROWS


_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


class SummaryCacheRowDict(TypedDict):
    title: str
    models: list[str]
    tokens: int
    tool_calls: int
    first_timestamp: str | None
    last_timestamp: str | None
    is_excluded: bool
    is_untitled: bool
    is_complete: bool


def cache_db_path() -> Path:
    """Return SQLite path for the summary cache (overridable in tests)."""
    override = os.environ.get("CLAUDE_CODE_CHAT_BROWSER_SUMMARY_CACHE", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".claude-code-chat-browser" / "session_summary_cache.sqlite"


def rules_fingerprint(rules: list[Any]) -> str:
    """Stable short hash for exclusion rules loaded at process start."""
    if not rules:
        return "none"
    payload = json.dumps(rules, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _ensure_connection() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    path = cache_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS summary_cache (
            path TEXT NOT NULL,
            mtime REAL NOT NULL,
            rules_fp TEXT NOT NULL,
            payload TEXT NOT NULL,
            accessed_at REAL NOT NULL,
            PRIMARY KEY (path, mtime, rules_fp)
        )
        """
    )
    conn.commit()
    _conn = conn
    return conn


def _row_to_payload(row: SummaryCacheRowDict) -> str:
    return json.dumps(row, ensure_ascii=False)


def _payload_to_row(raw: str) -> SummaryCacheRowDict:
    data = json.loads(raw)
    return SummaryCacheRowDict(
        title=str(data["title"]),
        models=list(data.get("models") or []),
        tokens=int(data.get("tokens") or 0),
        tool_calls=int(data.get("tool_calls") or 0),
        first_timestamp=data.get("first_timestamp"),
        last_timestamp=data.get("last_timestamp"),
        is_excluded=bool(data.get("is_excluded")),
        is_untitled=bool(data.get("is_untitled")),
        is_complete=bool(data.get("is_complete", True)),
    )


def get_summary(path: str, mtime: float, rules_fingerprint: str) -> SummaryCacheRowDict | None:
    """Return a cached summary row when path, mtime, and rules_fp match."""
    abspath = os.path.abspath(path)
    with _lock:
        conn = _ensure_connection()
        row = conn.execute(
            "SELECT payload FROM summary_cache WHERE path = ? AND mtime = ? AND rules_fp = ?",
            (abspath, mtime, rules_fingerprint),
        ).fetchone()
        if row is None:
            return None
        return _payload_to_row(str(row[0]))


def put_summary(
    path: str,
    mtime: float,
    rules_fingerprint: str,
    row: SummaryCacheRowDict,
) -> None:
    """Store or replace a summary row and evict LRU entries when over capacity."""
    abspath = os.path.abspath(path)
    now = time.time()
    payload = _row_to_payload(row)
    with _lock:
        conn = _ensure_connection()
        conn.execute(
            "DELETE FROM summary_cache WHERE path = ? AND rules_fp = ? AND mtime != ?",
            (abspath, rules_fingerprint, mtime),
        )
        conn.execute(
            """
            INSERT INTO summary_cache (path, mtime, rules_fp, payload, accessed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path, mtime, rules_fp) DO UPDATE SET
                payload = excluded.payload,
                accessed_at = excluded.accessed_at
            """,
            (abspath, mtime, rules_fingerprint, payload, now),
        )
        count = conn.execute("SELECT COUNT(*) FROM summary_cache").fetchone()
        limit = max_cache_rows()
        if count is not None and int(count[0]) > limit:
            conn.execute(
                """
                DELETE FROM summary_cache
                WHERE rowid IN (
                    SELECT rowid FROM summary_cache
                    ORDER BY accessed_at ASC
                    LIMIT ?
                )
                """,
                (int(count[0]) - limit,),
            )
        conn.commit()


def clear_cache() -> None:
    """Clear all cached summaries and close the connection (for tests)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.execute("DELETE FROM summary_cache")
            _conn.commit()
            _conn.close()
            _conn = None


def summary_from_peek(info: QuickSessionInfoDict) -> SummaryCacheRowDict:
    """Build a partial summary row from a lightweight JSONL peek."""
    title = info["title"]
    return SummaryCacheRowDict(
        title=title,
        models=[],
        tokens=0,
        tool_calls=0,
        first_timestamp=info.get("first_timestamp"),
        last_timestamp=info.get("last_timestamp"),
        is_excluded=False,
        is_untitled=title == "Untitled Session",
        is_complete=False,
    )


def summary_from_session(
    parsed: SessionDict,
    *,
    is_excluded: bool,
) -> SummaryCacheRowDict:
    """Build a complete summary row from a parsed session."""
    meta = parsed["metadata"]
    models = meta.get("models_used", [])
    title = parsed["title"]
    return SummaryCacheRowDict(
        title=title,
        models=sorted(models) if isinstance(models, set) else list(models),
        tokens=meta["total_input_tokens"] + meta["total_output_tokens"],
        tool_calls=meta["total_tool_calls"],
        first_timestamp=meta["first_timestamp"],
        last_timestamp=meta["last_timestamp"],
        is_excluded=is_excluded,
        is_untitled=title == "Untitled Session",
        is_complete=True,
    )


def session_row_from_summary(
    s: SessionListItemDict,
    row: SummaryCacheRowDict,
) -> ProjectSessionRowDict:
    """Map a cached summary onto the API session list row shape."""
    return ProjectSessionRowDict(
        id=s["id"],
        path=s["path"],
        size_bytes=s["size_bytes"],
        modified=s["modified"],
        title=row["title"],
        models=row["models"],
        tokens=row["tokens"],
        tool_calls=row["tool_calls"],
        first_timestamp=row["first_timestamp"],
        last_timestamp=row["last_timestamp"],
    )


def reset_connection_for_tests(db_path: Path) -> None:
    """Point the cache at *db_path* and open a fresh connection."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        os.environ["CLAUDE_CODE_CHAT_BROWSER_SUMMARY_CACHE"] = str(db_path)
        _ensure_connection()
