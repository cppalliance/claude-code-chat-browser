"""Fast metadata peek for Claude Code JSONL session files."""

import json
import os

from models.session import QuickSessionInfoDict
from utils.jsonl_helpers import entry_message, extract_text, first_title_line

_TAIL_READ_MIN_BYTES = 10 * 1024
_MAX_HEAD_LINES = 80


def quick_session_info(filepath: str) -> QuickSessionInfoDict:
    """Lightweight peek at a session file -- returns title and last_timestamp
    without fully parsing all messages.  Much faster than parse_session() for
    large files.

    Strategy: files over 10 KiB cap the head scan at 80 lines for title, then
    tail-read for last_timestamp; smaller files are scanned fully in pass 1."""
    title = None
    first_ts = None
    last_ts = None
    file_size = os.path.getsize(filepath)

    # --- Pass 1: read first lines to find the title and first_timestamp ---
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines_read = 0
        for line in f:
            lines_read += 1
            # Large files use pass-2 tail read for last_timestamp; cap head scan only then.
            if file_size > _TAIL_READ_MIN_BYTES and lines_read > _MAX_HEAD_LINES:
                break
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = entry.get("timestamp")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts  # keep updating in case file is small

            if title is None and entry.get("type") == "user":
                msg = entry_message(entry)
                text = extract_text(msg.get("content", []))
                if text:
                    first_line = first_title_line(text)
                    if first_line:
                        title = first_line

    # --- Pass 2: read last chunk for the last timestamp ---
    if file_size > _TAIL_READ_MIN_BYTES:
        # Only bother with tail-read for non-tiny files
        chunk_size = min(file_size, 32768)
        with open(filepath, "rb") as f:
            f.seek(file_size - chunk_size)
            tail = f.read().decode("utf-8", errors="replace")
        # First line in tail is often a partial record after seek; json.loads skips it.
        # Parse lines in reverse to find latest timestamp
        for line in reversed(tail.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = entry.get("timestamp")
            if ts:
                last_ts = ts
                break

    return {
        "title": title or "Untitled Session",
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
    }
