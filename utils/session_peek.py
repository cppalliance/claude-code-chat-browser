"""Fast metadata peek for Claude Code JSONL session files."""

import json
import os

from models.session import QuickSessionInfoDict
from utils.jsonl_helpers import entry_message, extract_text, strip_system_tags


def quick_session_info(filepath: str) -> QuickSessionInfoDict:
    """Lightweight peek at a session file -- returns title and last_timestamp
    without fully parsing all messages.  Much faster than parse_session() for
    large files.

    Strategy: read the first ~50 lines for the title, then seek to the end of
    the file and read the last chunk to find the last timestamp."""
    title = None
    first_ts = None
    last_ts = None

    # --- Pass 1: read first lines to find the title and first_timestamp ---
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines_read = 0
        for line in f:
            lines_read += 1
            if lines_read > 80:
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
                    clean = strip_system_tags(text).strip()
                    first_line = clean.split("\n")[0][:100]
                    if first_line:
                        title = first_line

    # --- Pass 2: read last chunk for the last timestamp ---
    file_size = os.path.getsize(filepath)
    if file_size > 10000:
        # Only bother with tail-read for non-tiny files
        chunk_size = min(file_size, 32768)
        with open(filepath, "rb") as f:
            f.seek(file_size - chunk_size)
            tail = f.read().decode("utf-8", errors="replace")
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
