"""Local FTS5 search index over Claude Code JSONL session files.

Derived ``search_index.<uuid>.sqlite`` under ``~/.claude-code-chat-browser/``.
Session JSONL on disk remains source of truth; the index rebuilds when the
projects manifest or exclusion-rules fingerprint changes.

Bypass: ``CLAUDE_CODE_CHAT_BROWSER_NO_SEARCH_INDEX=1``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypedDict

from models.session import MessageDict, RoleLiteral
from utils.jsonl_helpers import entry_message, extract_text, first_title_line
from utils.session_path import list_projects, list_sessions
from utils.session_summary_cache import rules_fingerprint

__all__ = [
    "DEFAULT_SEARCH_WINDOW_DAYS",
    "IndexMessageHitDict",
    "IndexQueryResult",
    "build_search_index",
    "ensure_search_index",
    "index_is_usable",
    "index_search_enabled",
    "message_searchable_text",
    "query_index_hits",
    "resolve_search_since_ms",
    "search_snippet",
    "start_search_index_background",
    "timestamp_in_search_window_iso",
    "timestamp_in_search_window_ms",
    "tool_result_searchable_text",
]

_logger = logging.getLogger(__name__)

INDEX_VERSION = 1
DEFAULT_SEARCH_WINDOW_DAYS = 30
_INCLUDE_UNKNOWN_TIMESTAMPS_IN_WINDOW = True
_SKIP_ENTRY_TYPES = frozenset({"file-history-snapshot", "summary"})

_index_lock = threading.Lock()
_index_build_lock = threading.Lock()
_background_started = False
_background_lock_fd: int | None = None
_usability_cache: dict[tuple[str, str], tuple[bool, float]] = {}
_usability_cache_lock = threading.Lock()
_USABILITY_CACHE_TTL_SECONDS = 30.0
_FTS_BATCH_SIZE = 200


class IndexMessageHitDict(TypedDict):
    session_id: str
    project_name: str
    title: str
    role: RoleLiteral
    timestamp: str | None
    text: str
    file_path: str
    mtime: float


class IndexQueryResult(TypedDict):
    hits: list[IndexMessageHitDict]
    query_ok: bool
    sql_rows_fetched: int
    sql_exhausted: bool
    index_locked: bool


def cache_dir() -> Path:
    """Return directory for search index files (overridable in tests)."""
    override = os.environ.get("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".claude-code-chat-browser"


def index_search_enabled() -> bool:
    return os.environ.get("CLAUDE_CODE_CHAT_BROWSER_NO_SEARCH_INDEX", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    )


def resolve_search_since_ms(
    *,
    all_history: bool = False,
    since_days: int | None = None,
    now: datetime | None = None,
) -> int | None:
    """Return epoch-ms cutoff for search, or ``None`` to search all history."""
    if all_history:
        return None
    days = since_days if since_days is not None else DEFAULT_SEARCH_WINDOW_DAYS
    if days > 36_500:
        days = 36_500
    if days <= 0:
        return None
    ref = now or datetime.now(timezone.utc)
    cutoff = ref - timedelta(days=days)
    return int(cutoff.timestamp() * 1000)


def timestamp_to_ms(ts: str | None) -> int:
    if not ts:
        return 0
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except (ValueError, AttributeError, OverflowError, OSError):
        return 0


def ms_to_timestamp(ms: int) -> str | None:
    if ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clear_usability_cache() -> None:
    with _usability_cache_lock:
        _usability_cache.clear()


def _usability_cache_key(projects_dir: str, rules: list[Any]) -> tuple[str, str]:
    return (str(Path(projects_dir).resolve()), rules_fingerprint(rules))


def timestamp_in_search_window_ms(timestamp_ms: int, since_ms: int | None) -> bool:
    if since_ms is None:
        return True
    if timestamp_ms <= 0:
        return _INCLUDE_UNKNOWN_TIMESTAMPS_IN_WINDOW
    return timestamp_ms >= since_ms


def timestamp_in_search_window_iso(timestamp: str | None, since_ms: int | None) -> bool:
    return timestamp_in_search_window_ms(timestamp_to_ms(timestamp), since_ms)


def search_snippet(text: str, query: str, *, context: int = 80) -> str:
    """Return a ±*context* character snippet around the first case-insensitive match."""
    needle = query.lower()
    haystack = text.lower()
    idx = haystack.find(needle)
    if idx < 0:
        return text[: context * 2]
    start = max(0, idx - context)
    end = min(len(text), idx + len(query) + context)
    return text[start:end]


def _resolve_active_index_db_path() -> Path | None:
    pointer = cache_dir() / "search_index.active"
    legacy = cache_dir() / "search_index.sqlite"
    if pointer.is_file():
        try:
            name = pointer.read_text(encoding="utf-8").strip()
        except OSError:
            name = ""
        if name:
            candidate = cache_dir() / name
            if candidate.is_file():
                return candidate
    if legacy.is_file():
        return legacy
    return None


def _publish_active_index(new_db_path: Path) -> None:
    root = cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    pointer = root / "search_index.active"
    pointer_tmp = pointer.with_suffix(".active.tmp")
    pointer_tmp.write_text(new_db_path.name, encoding="utf-8")
    try:
        pointer_tmp.replace(pointer)
    except OSError:
        pointer.write_text(new_db_path.name, encoding="utf-8")
        try:
            pointer_tmp.unlink()
        except OSError:
            pass
    _prune_stale_index_files(keep=new_db_path)


def _prune_stale_index_files(*, keep: Path) -> None:
    root = cache_dir()
    for pattern in ("search_index.*.sqlite", "search_index.sqlite"):
        for path in root.glob(pattern):
            if path.resolve() == keep.resolve():
                continue
            try:
                path.unlink()
            except OSError:
                pass
    for suffix in (".sqlite.tmp", ".active.tmp"):
        for path in root.glob(f"search_index*{suffix}"):
            try:
                path.unlink()
            except OSError:
                pass


def _projects_fingerprint(projects_dir: str, rules: list[Any]) -> dict[str, Any]:
    base = Path(projects_dir).resolve()
    manifest: list[list[Any]] = []
    for project in list_projects(projects_dir):
        for sess in list_sessions(project["path"]):
            try:
                rel = os.path.relpath(sess["path"], projects_dir)
                stat = os.stat(sess["path"])
            except OSError:
                continue
            manifest.append([rel, stat.st_mtime_ns, stat.st_size])
    manifest.sort()
    return {
        "projects_dir": str(base),
        "manifest": manifest,
        "rules_fp": rules_fingerprint(rules),
    }


def _fingerprints_match(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        a.get("projects_dir") == b.get("projects_dir")
        and a.get("rules_fp") == b.get("rules_fp")
        and a.get("manifest") == b.get("manifest")
    )


def _open_index_db(*, readonly: bool = True) -> sqlite3.Connection | None:
    db_path = _resolve_active_index_db_path()
    if db_path is None:
        return None
    uri = db_path.resolve().as_uri()
    if readonly:
        uri += "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as exc:
        _logger.debug("Failed to open search index: %s", exc)
        return None


@contextmanager
def _index_db_conn(*, readonly: bool = True) -> Iterator[sqlite3.Connection | None]:
    conn = _open_index_db(readonly=readonly)
    try:
        yield conn
    finally:
        if conn is not None:
            conn.close()


def _read_stored_fingerprint(conn: sqlite3.Connection) -> dict[str, Any] | None:
    try:
        row = conn.execute("SELECT value FROM index_meta WHERE key = 'fingerprint'").fetchone()
        if not row or not row[0]:
            return None
        data = json.loads(row[0])
        return data if isinstance(data, dict) else None
    except (sqlite3.Error, json.JSONDecodeError):
        return None


def _fts_match_query(query_lower: str) -> str | None:
    tokens = [t for t in re.split(r"\W+", query_lower) if t]
    if not tokens:
        return None
    parts: list[str] = []
    for token in tokens:
        escaped = token.replace('"', '""')
        parts.append(f'"{escaped}"*')
    return " AND ".join(parts)


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT NOT NULL,
            project_name TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            first_ms INTEGER NOT NULL DEFAULT 0,
            last_ms INTEGER NOT NULL DEFAULT 0,
            file_path TEXT NOT NULL,
            mtime REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (session_id, project_name)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            session_id UNINDEXED,
            project_name UNINDEXED,
            role UNINDEXED,
            timestamp_ms UNINDEXED,
            text,
            tokenize='unicode61'
        );
        """
    )


def tool_result_searchable_text(raw: object) -> str:
    if not isinstance(raw, dict):
        return ""
    parts: list[str] = []
    for key in ("stdout", "stderr", "content", "filePath", "query", "url", "plan"):
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    parts.append(item)
                elif isinstance(item, dict):
                    nested = item.get("text") or item.get("content")
                    if isinstance(nested, str) and nested.strip():
                        parts.append(nested)
    return "\n".join(parts)


def progress_searchable_text(raw: object) -> str:
    if not isinstance(raw, dict):
        return ""
    output = raw.get("output")
    return output if isinstance(output, str) and output.strip() else ""


def combine_searchable_text(
    *,
    text: str = "",
    content: str = "",
    tool_result: object = None,
    progress_data: object = None,
) -> str:
    """Merge searchable fields the same way for index build and live scan."""
    merged = text if isinstance(text, str) else ""
    if not merged and isinstance(content, str):
        merged = content
    tool_text = tool_result_searchable_text(tool_result) if tool_result is not None else ""
    if tool_text:
        merged = f"{merged}\n{tool_text}" if merged else tool_text
    progress_text = progress_searchable_text(progress_data)
    if progress_text:
        merged = f"{merged}\n{progress_text}" if merged else progress_text
    return merged


def message_searchable_text(msg: MessageDict) -> str:
    """Searchable text for one parsed session message (live-scan path)."""
    role = msg["role"]
    text = ""
    content = ""
    tool_result: object = None
    progress_data: object = None

    if role == "user":
        raw_text = msg.get("text", "")
        text = raw_text if isinstance(raw_text, str) else ""
        tool_result = msg.get("tool_result")
    elif role == "assistant":
        raw_text = msg.get("text", "")
        text = raw_text if isinstance(raw_text, str) else ""
    elif role == "system":
        raw_text = msg.get("text", "") or msg.get("content", "") or ""
        text = raw_text if isinstance(raw_text, str) else ""
    elif role == "result":
        raw_text = msg.get("text", "") or msg.get("content", "") or ""
        text = raw_text if isinstance(raw_text, str) else ""
    elif role == "progress":
        progress_data = msg.get("data")

    return combine_searchable_text(
        text=text,
        content=content,
        tool_result=tool_result,
        progress_data=progress_data,
    )


def _coerce_role(entry_type: str | None) -> RoleLiteral | None:
    if entry_type in ("user", "assistant", "system", "progress"):
        return entry_type  # type: ignore[return-value]
    if entry_type is None:
        return None
    return "system"


def _indexable_texts_from_entry(
    entry: dict[str, Any],
) -> list[tuple[str, str | None, RoleLiteral]]:
    """Extract searchable (text, timestamp, role) tuples from one JSONL entry."""
    entry_type = entry.get("type")
    if entry_type in _SKIP_ENTRY_TYPES:
        return []

    role = _coerce_role(entry_type if isinstance(entry_type, str) else None)
    timestamp = entry.get("timestamp")
    ts = timestamp if isinstance(timestamp, str) else None
    texts: list[tuple[str, str | None, RoleLiteral]] = []

    if entry_type == "user":
        msg = entry_message(entry)
        text = combine_searchable_text(
            text=extract_text(msg.get("content", [])),
            tool_result=entry.get("toolUseResult"),
        )
        if text:
            texts.append((text, ts, "user"))
        return texts

    if entry_type == "assistant":
        msg = entry_message(entry)
        text = combine_searchable_text(text=extract_text(msg.get("content", [])))
        if text:
            texts.append((text, ts, "assistant"))
        return texts

    if entry_type == "system":
        raw_content = entry.get("content", "")
        content = raw_content if isinstance(raw_content, str) else ""
        text = combine_searchable_text(content=content)
        if text:
            texts.append((text, ts, "system"))
        return texts

    if entry_type == "progress":
        text = combine_searchable_text(progress_data=entry.get("data"))
        if text:
            texts.append((text, ts, "progress"))
        return texts

    if role is not None:
        text = combine_searchable_text(content=entry.get("content", ""))
        if text:
            texts.append((text, ts, role))

    return texts


def _scan_session_file(
    filepath: str,
) -> tuple[str, str, int, int, float, list[tuple[str, str | None, RoleLiteral]]]:
    session_id = os.path.basename(filepath).replace(".jsonl", "")
    title = "Untitled Session"
    first_ms = 0
    last_ms = 0
    messages: list[tuple[str, str | None, RoleLiteral]] = []
    mtime = os.path.getmtime(filepath)

    with open(filepath, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue

            ts = entry.get("timestamp")
            if isinstance(ts, str):
                ms = timestamp_to_ms(ts)
                if ms > 0:
                    if first_ms == 0:
                        first_ms = ms
                    last_ms = ms

            if title == "Untitled Session" and entry.get("type") == "user":
                msg = entry_message(entry)
                text = extract_text(msg.get("content", []))
                if text:
                    candidate = first_title_line(text)
                    if candidate:
                        title = candidate

            messages.extend(_indexable_texts_from_entry(entry))

    return session_id, title, first_ms, last_ms, mtime, messages


def build_search_index(
    projects_dir: str,
    rules: list[Any],
    *,
    force: bool = False,
) -> bool:
    """Rebuild search index when fingerprint differs. Returns True if rebuilt."""
    if not index_search_enabled():
        return False
    if not os.path.isdir(projects_dir):
        return False

    fingerprint = _projects_fingerprint(projects_dir, rules)

    with _index_build_lock:
        active_path = _resolve_active_index_db_path()
        if not force and active_path is not None:
            with _index_db_conn(readonly=True) as existing:
                if existing is not None:
                    stored = _read_stored_fingerprint(existing)
                    if stored is not None and _fingerprints_match(stored, fingerprint):
                        return False

        root = cache_dir()
        root.mkdir(parents=True, exist_ok=True)
        new_path = root / f"search_index.{uuid.uuid4().hex[:12]}.sqlite"
        session_count = 0
        message_count = 0

        try:
            with closing(sqlite3.connect(new_path)) as conn:
                _create_schema(conn)
                for project in list_projects(projects_dir):
                    for sess in list_sessions(project["path"]):
                        try:
                            session_id, title, first_ms, last_ms, mtime, texts = _scan_session_file(
                                sess["path"]
                            )
                        except OSError as exc:
                            _logger.warning(
                                "Skipping session during index build: %s (%s)",
                                sess["path"],
                                exc,
                            )
                            continue
                        if not texts:
                            continue
                        conn.execute(
                            "INSERT OR REPLACE INTO sessions"
                            " (session_id, project_name, title, first_ms, last_ms,"
                            " file_path, mtime)"
                            " VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                session_id,
                                project["name"],
                                title,
                                first_ms,
                                last_ms,
                                sess["path"],
                                mtime,
                            ),
                        )
                        session_count += 1
                        for text, ts, role in texts:
                            conn.execute(
                                "INSERT INTO messages_fts"
                                " (session_id, project_name, role, timestamp_ms, text)"
                                " VALUES (?, ?, ?, ?, ?)",
                                (
                                    session_id,
                                    project["name"],
                                    role,
                                    timestamp_to_ms(ts),
                                    text,
                                ),
                            )
                            message_count += 1

                conn.execute(
                    "INSERT OR REPLACE INTO index_meta(key, value) VALUES (?, ?)",
                    ("fingerprint", json.dumps(fingerprint, ensure_ascii=False)),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO index_meta(key, value) VALUES (?, ?)",
                    ("version", str(INDEX_VERSION)),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO index_meta(key, value) VALUES (?, ?)",
                    (
                        "stats",
                        json.dumps(
                            {"sessions": session_count, "messages": message_count},
                            ensure_ascii=False,
                        ),
                    ),
                )
                conn.commit()

            _publish_active_index(new_path)
            _clear_usability_cache()
            _logger.info(
                "Search index rebuilt: %d sessions, %d messages -> %s",
                session_count,
                message_count,
                new_path.name,
            )
            return True
        except Exception:
            _logger.exception("Search index rebuild failed")
            if new_path.is_file():
                try:
                    new_path.unlink()
                except OSError:
                    pass
            return False


def ensure_search_index(projects_dir: str, rules: list[Any]) -> None:
    """Build index synchronously if missing or stale."""
    if not index_search_enabled():
        return
    if _resolve_active_index_db_path() is None:
        build_search_index(projects_dir, rules)
        return
    fingerprint = _projects_fingerprint(projects_dir, rules)
    with _index_db_conn(readonly=True) as conn:
        if conn is None:
            build_search_index(projects_dir, rules)
            return
        stored = _read_stored_fingerprint(conn)
        if stored is None or not _fingerprints_match(stored, fingerprint):
            build_search_index(projects_dir, rules)


def _try_acquire_cross_process_background_lock() -> bool:
    """Return True when this process should own the background index worker."""
    global _background_lock_fd
    if _background_lock_fd is not None:
        return True
    root = cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / "search_index.background.lock"
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        os.close(fd)
        return False
    _background_lock_fd = fd
    return True


def start_search_index_background(
    projects_dir: str,
    rules: list[Any],
    *,
    poll_seconds: int = 60,
) -> None:
    """Kick off initial + periodic index refresh in a daemon thread."""
    global _background_started
    if not index_search_enabled():
        return
    with _index_lock:
        if _background_started:
            return
        if not _try_acquire_cross_process_background_lock():
            return
        _background_started = True

    def _worker() -> None:
        while True:
            try:
                ensure_search_index(projects_dir, rules)
            except Exception:
                _logger.exception("Background search index refresh failed")
            time.sleep(poll_seconds)

    thread = threading.Thread(target=_worker, name="search-index-refresh", daemon=True)
    thread.start()


def index_is_usable(projects_dir: str, rules: list[Any]) -> bool:
    """True when the on-disk index matches the current projects fingerprint."""
    if not index_search_enabled() or _resolve_active_index_db_path() is None:
        return False

    key = _usability_cache_key(projects_dir, rules)
    now = time.monotonic()
    with _usability_cache_lock:
        cached = _usability_cache.get(key)
        if cached is not None and now - cached[1] < _USABILITY_CACHE_TTL_SECONDS:
            return cached[0]

    fingerprint = _projects_fingerprint(projects_dir, rules)
    with _index_db_conn(readonly=True) as conn:
        if conn is None:
            result = False
        else:
            stored = _read_stored_fingerprint(conn)
            result = stored is not None and _fingerprints_match(stored, fingerprint)

    with _usability_cache_lock:
        _usability_cache[key] = (result, now)
    return result


def query_index_hits(
    query_lower: str,
    *,
    since_ms: int | None,
    max_results: int,
    sql_offset: int = 0,
) -> IndexQueryResult:
    """Return message hits from the FTS index (pre-exclusion, pre-snippet)."""
    if not query_lower or not index_search_enabled():
        return {
            "hits": [],
            "query_ok": False,
            "sql_rows_fetched": 0,
            "sql_exhausted": True,
            "index_locked": False,
        }

    fts_q = _fts_match_query(query_lower)
    if not fts_q:
        return {
            "hits": [],
            "query_ok": False,
            "sql_rows_fetched": 0,
            "sql_exhausted": True,
            "index_locked": False,
        }

    sql_limit = max(max_results, _FTS_BATCH_SIZE)
    with _index_db_conn(readonly=True) as conn:
        if conn is None:
            return {
                "hits": [],
                "query_ok": False,
                "sql_rows_fetched": 0,
                "sql_exhausted": True,
                "index_locked": False,
            }
        try:
            rows = conn.execute(
                "SELECT m.session_id, m.project_name, m.role, m.timestamp_ms, m.text,"
                " s.title, s.file_path, s.mtime"
                " FROM messages_fts m"
                " JOIN sessions s"
                " ON s.session_id = m.session_id AND s.project_name = m.project_name"
                " WHERE messages_fts MATCH ?"
                " ORDER BY m.timestamp_ms DESC"
                " LIMIT ? OFFSET ?",
                (fts_q, sql_limit, sql_offset),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            _logger.debug("FTS query locked (%s); index may be rebuilding", exc)
            return {
                "hits": [],
                "query_ok": False,
                "sql_rows_fetched": 0,
                "sql_exhausted": True,
                "index_locked": True,
            }
        except sqlite3.Error as exc:
            _logger.debug("FTS query failed (%s); index may be rebuilding", exc)
            return {
                "hits": [],
                "query_ok": False,
                "sql_rows_fetched": 0,
                "sql_exhausted": True,
                "index_locked": False,
            }

    hits: list[IndexMessageHitDict] = []
    rows_scanned = 0
    for row in rows:
        rows_scanned += 1
        text = row["text"] or ""
        if query_lower not in text.lower():
            continue
        ts_ms = int(row["timestamp_ms"] or 0)
        if not timestamp_in_search_window_ms(ts_ms, since_ms):
            continue
        hits.append(
            IndexMessageHitDict(
                session_id=row["session_id"],
                project_name=row["project_name"],
                title=row["title"] or "Untitled Session",
                role=row["role"],
                timestamp=ms_to_timestamp(ts_ms),
                text=text,
                file_path=row["file_path"],
                mtime=float(row["mtime"] or 0),
            )
        )
        if len(hits) >= max_results:
            break
    batch_fully_scanned = rows_scanned == len(rows)
    return {
        "hits": hits,
        "query_ok": True,
        "sql_rows_fetched": rows_scanned,
        "sql_exhausted": batch_fully_scanned and len(rows) < sql_limit,
        "index_locked": False,
    }


def reset_background_for_tests() -> None:
    """Allow tests to restart the background worker."""
    global _background_started, _background_lock_fd
    with _index_lock:
        _background_started = False
        if _background_lock_fd is not None:
            try:
                os.close(_background_lock_fd)
            except OSError:
                pass
            _background_lock_fd = None
    _clear_usability_cache()
