"""Shared export_state.json locking and atomic I/O for API and CLI."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

# Only when neither fcntl nor msvcrt exists (very rare): same-process only.
_fallback_locks: dict[str, threading.Lock] = {}
_fallback_locks_guard = threading.Lock()

EXPORT_STATE_FILE = os.path.join(
    os.path.expanduser("~"), ".claude-code-chat-browser", "export_state.json"
)


def _fallback_lock_for(path: str) -> threading.Lock:
    with _fallback_locks_guard:
        if path not in _fallback_locks:
            _fallback_locks[path] = threading.Lock()
        return _fallback_locks[path]


@contextmanager
def export_state_lock(state_path: str | None = None):
    """Serialize export_state.json reads/writes across processes.

    POSIX: ``flock`` on a sidecar ``*.lock`` file. Windows: ``msvcrt.locking`` on
    the same sidecar (byte-range lock). If neither is available, falls back to
    a per-path ``threading.Lock`` (same process only).
    """
    path = EXPORT_STATE_FILE if state_path is None else state_path
    if fcntl is not None:
        lock_path = path + ".lock"
        dir_name = os.path.dirname(lock_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        lock_fp = open(lock_path, "a+", encoding="utf-8")
        try:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
            lock_fp.close()
    elif msvcrt is not None:
        lock_path = path + ".lock"
        dir_name = os.path.dirname(lock_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        if not os.path.exists(lock_path):
            with open(lock_path, "wb") as f:
                f.write(b"\x00")
        lock_fp = open(lock_path, "r+b")
        try:
            if os.path.getsize(lock_path) == 0:
                lock_fp.write(b"\x00")
                lock_fp.flush()
            lock_fp.seek(0)
            msvcrt.locking(lock_fp.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_fp.seek(0)
                msvcrt.locking(lock_fp.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            lock_fp.close()
    else:
        with _fallback_lock_for(path):
            yield


def load_export_state_from_disk(state_path: str | None = None) -> dict:
    """Load state from disk (call under :func:`export_state_lock` for consistency).

    Migrates legacy flat ``{session_id: mtime, ...}`` to ``{"sessions": ...}``.
    Returns a dict with a mapping ``sessions``; malformed top-level values or
    a non-dict ``sessions`` entry are sanitized so callers always see a dict.
    """
    path = EXPORT_STATE_FILE if state_path is None else state_path
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    if "sessions" not in data and "lastExportTime" not in data:
        return {"sessions": data}
    if not isinstance(data.get("sessions"), dict):
        data = dict(data)
        data["sessions"] = {}
    return data


def atomic_write_export_state(state: dict, state_path: str | None = None) -> None:
    """Write *state* atomically (serialize, temp file + fsync + replace).

    Call under :func:`export_state_lock` matching *state_path*.
    """
    path = EXPORT_STATE_FILE if state_path is None else state_path
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    try:
        payload = json.dumps(state, indent=2)
    except (TypeError, ValueError) as e:
        raise ValueError(f"export state is not JSON-serializable: {e}") from e
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
        raise
