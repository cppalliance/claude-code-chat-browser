"""Finds where Claude Code stores its .jsonl session files on disk and
lists projects/sessions from that directory."""

import json
import logging
import os
import platform
import threading

from models.project import ProjectDict, SessionListItemDict

_logger = logging.getLogger(__name__)

_display_name_cache: dict[str, tuple[float, str]] = {}
_display_name_lock = threading.Lock()


def safe_join(base: str, *parts: str) -> str:
    """Join path components and verify the result stays under base.
    Raises ValueError if the resolved path escapes the base directory."""
    joined = os.path.realpath(os.path.join(base, *parts))
    base_resolved = os.path.realpath(base)
    if not joined.startswith(base_resolved + os.sep) and joined != base_resolved:
        raise ValueError(f"Path escapes base directory: {joined}")
    return joined


def get_claude_projects_dir() -> str:
    """~/.claude/projects/ -- handles Windows USERPROFILE vs Unix HOME."""
    system = platform.system()
    if system == "Windows":
        home = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    else:
        home = os.path.expanduser("~")
    return os.path.join(home, ".claude", "projects")


def clear_display_name_cache() -> None:
    """Clear the in-memory display-name cache (for tests)."""
    with _display_name_lock:
        _display_name_cache.clear()


def _project_jsonl_max_mtime(project_dir: str, jsonl_files: list[str]) -> float:
    return max(os.path.getmtime(os.path.join(project_dir, jf)) for jf in jsonl_files)


def _resolve_display_name(project_dir: str, jsonl_files: list[str], fallback: str) -> str:
    max_mtime = _project_jsonl_max_mtime(project_dir, jsonl_files)
    with _display_name_lock:
        hit = _display_name_cache.get(project_dir)
        if hit is not None and hit[0] == max_mtime:
            return hit[1]
    display_name = fallback
    for jf in jsonl_files:
        candidate = _get_display_name(os.path.join(project_dir, jf), None)
        if candidate is not None:
            display_name = candidate
            break
    with _display_name_lock:
        _display_name_cache[project_dir] = (max_mtime, display_name)
    return display_name


def list_projects(base_dir: str | None = None) -> list[ProjectDict]:
    """Scan the projects dir and return info for each one that has .jsonl files."""
    base = base_dir or get_claude_projects_dir()
    if not os.path.isdir(base):
        return []

    projects: list[ProjectDict] = []
    for name in sorted(os.listdir(base)):
        project_dir = os.path.join(base, name)
        if not os.path.isdir(project_dir):
            continue
        jsonl_files = [
            f for f in os.listdir(project_dir) if f.endswith(".jsonl") and not f.startswith(".")
        ]
        if jsonl_files:
            latest_mtime = max(
                os.path.getmtime(os.path.join(project_dir, jf)) for jf in jsonl_files
            )
            from datetime import datetime, timezone

            last_modified = datetime.fromtimestamp(latest_mtime, tz=timezone.utc).isoformat()
            display_name = _resolve_display_name(project_dir, jsonl_files, name)
            projects.append(
                {
                    "name": name,
                    "path": project_dir,
                    "display_name": display_name,
                    "session_count": len(jsonl_files),
                    "last_modified": last_modified,
                }
            )
    return projects


def _get_display_name(jsonl_path: str, fallback: str | None) -> str | None:
    """Peek at the first entry's cwd field to get a human-readable project path
    instead of the hashed directory name."""
    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                cwd = entry.get("cwd")
                if cwd:
                    # Normalize: replace backslashes, strip trailing slash
                    cwd = cwd.replace("\\", "/").rstrip("/")
                    # Extract last folder name and capitalize first letter
                    folder = cwd.rsplit("/", 1)[-1]
                    out = folder[:1].upper() + folder[1:] if folder else cwd
                    return str(out)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        _logger.warning("Failed to extract display name from %s: %s", jsonl_path, exc)
    return fallback


def list_sessions(project_dir: str) -> list[SessionListItemDict]:
    """Return id, path, size, mtime for each .jsonl file in a project dir."""
    sessions: list[SessionListItemDict] = []
    if not os.path.isdir(project_dir):
        return sessions

    for fname in sorted(os.listdir(project_dir)):
        if not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(project_dir, fname)
        session_id = fname.replace(".jsonl", "")
        stat = os.stat(fpath)
        sessions.append(
            {
                "id": session_id,
                "path": fpath,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
            }
        )
    return sessions
