"""JSON export format. Dumps everything -- no data loss compared to the raw
JSONL, but in a sane structure with computed stats included."""

import json
from datetime import datetime, timezone
from typing import Any

from models.session import MessageDict, SessionDict, SessionMetadataDict
from models.stats import SessionStatsDict


def session_to_json(
    session: SessionDict,
    stats: SessionStatsDict | None = None,
    indent: int = 2,
) -> str:
    """Serialize a parsed session to a JSON string with schema versioning.
    Pass indent=None if you want compact output for piping."""
    output = {
        "schema_version": "2.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session["session_id"],
        "title": session["title"],
        "metadata": _serialize_metadata(session["metadata"]),
        "stats": stats,
        "messages": _serialize_messages(session["messages"]),
    }
    return json.dumps(output, indent=indent, default=str, ensure_ascii=False)


def _serialize_metadata(meta: SessionMetadataDict) -> dict[str, Any]:
    """json.dumps chokes on sets, so convert them to sorted lists."""
    result: dict[str, Any] = {}
    for key, val in meta.items():
        if isinstance(val, set):
            result[key] = sorted(val)
        else:
            result[key] = val
    return result


def _serialize_messages(messages: list[MessageDict]) -> list[dict[str, Any]]:
    """Same set-to-list cleanup, but for each message dict."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        clean: dict[str, Any] = {}
        for key, val in msg.items():
            if isinstance(val, set):
                clean[key] = sorted(val)
            else:
                clean[key] = val
        out.append(clean)
    return out
