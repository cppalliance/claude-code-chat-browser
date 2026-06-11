"""Reads Claude Code .jsonl session files and turns them into dicts we can
actually work with -- messages, tool calls, token counts, file activity, etc."""

import json
import os
from datetime import datetime
from typing import Any

from models.record_data import RecordDataUnion
from models.session import MessageDict, SessionDict, ToolUseDict
from models.tool_results import ToolResultUnion, is_tool_result_dict
from utils.jsonl_helpers import (
    entry_message as _entry_message,
    extract_images as _extract_images,
    extract_text as _extract_text,
    infer_title as _infer_title,
    normalize_content as _normalize_content,
    strip_system_tags as _strip_system_tags,
)
from utils.session_peek import quick_session_info
from utils.tool_dispatch import _TOOL_RESULT_DISPATCH, _parse_tool_result
from utils.validation import validate_session_dict

__all__ = [
    "parse_session",
    "quick_session_info",
    "_parse_tool_result",
    "_TOOL_RESULT_DISPATCH",
    "_entry_message",
    "_process_user",
    "_process_assistant",
    "_process_system",
    "_process_progress",
    "_normalize_content",
    "_extract_text",
    "_extract_images",
    "_infer_title",
    "_strip_system_tags",
    "_track_file_activity",
]


def _safe_int(val: Any) -> int:
    """Coerce a value to int for token accounting; non-numeric input becomes 0
    so fuzzed/malformed usage fields never raise during arithmetic."""
    if isinstance(val, bool):
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    return 0


def parse_session(filepath: str) -> SessionDict:
    """Main entry point. Reads every line from a .jsonl file and builds up
    a session dict with messages, metadata (tokens, models, tool counts),
    and file/command activity."""
    session_id = os.path.basename(filepath).replace(".jsonl", "")
    messages: list[MessageDict] = []
    metadata: dict[str, Any] = {
        "session_id": session_id,
        "models_used": set(),
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cache_read_tokens": 0,
        "total_cache_creation_tokens": 0,
        "total_tool_calls": 0,
        "tool_call_counts": {},
        "first_timestamp": None,
        "last_timestamp": None,
        "version": None,
        "cwd": None,
        "git_branch": None,
        "permission_mode": None,
        "compactions": 0,
        # Extended token accounting
        "total_ephemeral_5m_tokens": 0,
        "total_ephemeral_1h_tokens": 0,
        "service_tiers": set(),
        # Timing
        "session_wall_time_seconds": None,
        # Compaction details
        "compact_boundaries": [],
        # Error tracking
        "api_errors": 0,
        # File activity (from tool_use inputs)
        "files_read": set(),
        "files_written": set(),
        "files_created": set(),
        "bash_commands": [],
        "web_fetches": [],
        # Sidechain tracking
        "sidechain_messages": 0,
        # Stop reasons
        "stop_reasons": {},
        # Entry type counts
        "entry_counts": {},
    }

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(entry, dict):
                continue

            entry_type = entry.get("type")
            ts = entry.get("timestamp")
            # file-history-snapshot stores timestamp inside snapshot
            if not ts and entry_type == "file-history-snapshot":
                snap = entry.get("snapshot")
                if isinstance(snap, dict):
                    ts = snap.get("timestamp")

            if ts:
                if metadata["first_timestamp"] is None:
                    metadata["first_timestamp"] = ts
                metadata["last_timestamp"] = ts

            # Count entry types (upstream may send non-str discriminants)
            if entry_type is not None:
                type_key = entry_type if isinstance(entry_type, str) else str(entry_type)
                metadata["entry_counts"][type_key] = metadata["entry_counts"].get(type_key, 0) + 1

            # Track sidechain
            if entry.get("isSidechain"):
                metadata["sidechain_messages"] += 1

            if entry_type == "user":
                _process_user(entry, messages, metadata)
            elif entry_type == "assistant":
                _process_assistant(entry, messages, metadata)
            elif entry_type == "system":
                _process_system(entry, messages, metadata)
            elif entry_type == "progress":
                _process_progress(entry, messages)

    metadata["models_used"] = sorted(metadata["models_used"])
    metadata["service_tiers"] = sorted(metadata["service_tiers"])
    metadata["files_read"] = sorted(metadata["files_read"])
    metadata["files_written"] = sorted(metadata["files_written"])
    metadata["files_created"] = sorted(metadata["files_created"])

    # Compute wall clock time
    first_ts = metadata["first_timestamp"]
    last_ts = metadata["last_timestamp"]
    if isinstance(first_ts, str) and isinstance(last_ts, str):
        try:
            t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            metadata["session_wall_time_seconds"] = max(0, (t1 - t0).total_seconds())
        except (ValueError, AttributeError):
            pass

    title = _infer_title(messages)

    return validate_session_dict(
        {
            "session_id": session_id,
            "title": title,
            "messages": messages,
            "metadata": metadata,
        }
    )


def _process_user(
    entry: dict[str, Any], messages: list[MessageDict], metadata: dict[str, Any]
) -> None:
    """Pull out text, tool results, and session-level metadata (cwd, version, etc.)
    from a user entry."""
    if metadata["version"] is None:
        metadata["version"] = entry.get("version")
    if metadata["cwd"] is None:
        metadata["cwd"] = entry.get("cwd")
    if metadata["git_branch"] is None:
        metadata["git_branch"] = entry.get("gitBranch")
    if metadata["permission_mode"] is None:
        metadata["permission_mode"] = entry.get("permissionMode")

    msg = _entry_message(entry)
    content = msg.get("content", [])
    text = _extract_text(content)
    images = _extract_images(content)

    raw_tool_result = entry.get("toolUseResult")
    tool_result: ToolResultUnion | None = raw_tool_result if raw_tool_result is not None else None
    tool_result_parsed = _parse_tool_result(tool_result, entry.get("slug"))

    # Also extract images from toolUseResult content (e.g., Read tool on image files)
    if is_tool_result_dict(tool_result) and "content" in tool_result:
        tr_content = tool_result["content"]
        if isinstance(tr_content, list):
            tr_images = _extract_images(tr_content)
            if tr_images:
                images = (images or []) + tr_images

    messages.append(
        {
            "role": "user",
            "uuid": entry.get("uuid"),
            "parent_uuid": entry.get("parentUuid"),
            "timestamp": entry.get("timestamp"),
            "text": text,
            "images": images if images else None,
            "is_sidechain": entry.get("isSidechain", False),
            "tool_result": tool_result,
            "tool_result_parsed": tool_result_parsed,
            "slug": entry.get("slug"),
        }
    )


def _process_assistant(
    entry: dict[str, Any], messages: list[MessageDict], metadata: dict[str, Any]
) -> None:
    """Handle assistant responses -- splits content into text, thinking blocks,
    and tool_use calls, and accumulates token/model/tool stats."""
    msg = _entry_message(entry)
    model = msg.get("model", "")
    if isinstance(model, str) and model and model != "<synthetic>":
        metadata["models_used"].add(model)

    # API error tracking
    if entry.get("isApiErrorMessage"):
        metadata["api_errors"] += 1

    usage = msg.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    metadata["total_input_tokens"] += _safe_int(usage.get("input_tokens"))
    metadata["total_output_tokens"] += _safe_int(usage.get("output_tokens"))
    metadata["total_cache_read_tokens"] += _safe_int(usage.get("cache_read_input_tokens"))
    metadata["total_cache_creation_tokens"] += _safe_int(usage.get("cache_creation_input_tokens"))

    # Extended cache metrics
    cache_creation = usage.get("cache_creation", {})
    if isinstance(cache_creation, dict):
        metadata["total_ephemeral_5m_tokens"] += _safe_int(
            cache_creation.get("ephemeral_5m_input_tokens")
        )
        metadata["total_ephemeral_1h_tokens"] += _safe_int(
            cache_creation.get("ephemeral_1h_input_tokens")
        )

    # Service tier
    tier = usage.get("service_tier")
    if isinstance(tier, str) and tier:
        metadata["service_tiers"].add(tier)

    # Stop reason tracking
    stop_reason = msg.get("stop_reason", "")
    if isinstance(stop_reason, str) and stop_reason:
        metadata["stop_reasons"][stop_reason] = metadata["stop_reasons"].get(stop_reason, 0) + 1

    content_parts = _normalize_content(msg.get("content", []))
    text_parts = []
    thinking_parts = []
    tool_uses: list[ToolUseDict] = []

    for part in content_parts:
        ptype = part.get("type")
        if ptype == "text":
            text_parts.append(part.get("text", ""))
        elif ptype == "thinking":
            thinking_parts.append(part.get("thinking", ""))
        elif ptype == "tool_use":
            raw_name = part.get("name", "unknown")
            tool_name = raw_name if isinstance(raw_name, str) else "unknown"
            raw_input = part.get("input", {})
            safe_input = raw_input if isinstance(raw_input, dict) else {}
            metadata["total_tool_calls"] += 1
            metadata["tool_call_counts"][tool_name] = (
                metadata["tool_call_counts"].get(tool_name, 0) + 1
            )
            tool_use: ToolUseDict = {
                "name": tool_name,
                "input": safe_input,
            }
            tool_id = part.get("id")
            if isinstance(tool_id, str):
                tool_use["id"] = tool_id
            tool_uses.append(tool_use)
            _track_file_activity(tool_name, safe_input, metadata)

    messages.append(
        {
            "role": "assistant",
            "uuid": entry.get("uuid"),
            "parent_uuid": entry.get("parentUuid"),
            "timestamp": entry.get("timestamp"),
            "model": model,
            "stop_reason": stop_reason,
            "text": "\n".join(text_parts),
            "thinking": "\n\n".join(thinking_parts) if thinking_parts else None,
            "tool_uses": tool_uses if tool_uses else None,
            "is_sidechain": entry.get("isSidechain", False),
            "is_api_error": entry.get("isApiErrorMessage", False),
            "usage": {
                "input_tokens": _safe_int(usage.get("input_tokens")),
                "output_tokens": _safe_int(usage.get("output_tokens")),
                "cache_read": _safe_int(usage.get("cache_read_input_tokens")),
                "cache_creation": _safe_int(usage.get("cache_creation_input_tokens")),
                "service_tier": usage.get("service_tier"),
            },
        }
    )


def _process_system(
    entry: dict[str, Any], messages: list[MessageDict], metadata: dict[str, Any]
) -> None:
    """Handle system entries (mostly compact_boundary markers from context
    compaction)."""
    subtype = entry.get("subtype", "")
    if subtype == "compact_boundary":
        metadata["compactions"] += 1
        compact_meta = entry.get("compactMetadata")
        if isinstance(compact_meta, dict):
            metadata["compact_boundaries"].append(
                {
                    "timestamp": entry.get("timestamp"),
                    "trigger": compact_meta.get("trigger"),
                    "pre_tokens": compact_meta.get("preTokens"),
                }
            )

    messages.append(
        {
            "role": "system",
            "uuid": entry.get("uuid"),
            "parent_uuid": entry.get("parentUuid"),
            "timestamp": entry.get("timestamp"),
            "subtype": subtype,
            "content": entry.get("content", ""),
            "is_sidechain": entry.get("isSidechain", False),
        }
    )


def _process_progress(entry: dict[str, Any], messages: list[MessageDict]) -> None:
    """Capture progress entries -- streaming bash output, hook results, etc.
    These are noisy so we mostly just store them for the JSON export."""
    raw_data = entry.get("data", {})
    data: RecordDataUnion = raw_data if isinstance(raw_data, dict) else {}
    progress_type = str(data.get("type", ""))

    messages.append(
        {
            "role": "progress",
            "uuid": entry.get("uuid"),
            "parent_uuid": entry.get("parentUuid"),
            "timestamp": entry.get("timestamp"),
            "progress_type": progress_type,
            "data": data,
            "tool_use_id": entry.get("toolUseID"),
            "parent_tool_use_id": entry.get("parentToolUseID"),
            "is_sidechain": entry.get("isSidechain", False),
        }
    )


def _track_file_activity(
    tool_name: str, tool_input: dict[str, Any], metadata: dict[str, Any]
) -> None:
    """Look at what each tool call did and record which files got touched,
    what commands got run, what URLs got fetched."""
    raw_fp = tool_input.get("file_path", "")
    fp = raw_fp if isinstance(raw_fp, str) else ""
    if tool_name == "Read" and fp:
        metadata["files_read"].add(fp)
    elif tool_name == "Write" and fp:
        metadata["files_created"].add(fp)
    elif tool_name == "Edit" and fp:
        metadata["files_written"].add(fp)
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if isinstance(cmd, str) and cmd:
            metadata["bash_commands"].append(cmd)
    elif tool_name in ("WebFetch", "WebSearch"):
        url_or_query = tool_input.get("url") or tool_input.get("query", "")
        if isinstance(url_or_query, str) and url_or_query:
            metadata["web_fetches"].append(url_or_query)
