"""Shared content helpers for JSONL parsing and session peek."""

import re
from typing import Any

from models.session import MessageDict


def entry_message(entry: dict[str, Any]) -> dict[str, Any]:
    m = entry.get("message")
    return m if isinstance(m, dict) else {}


def normalize_content(content: Any) -> list[dict[str, Any]]:
    """Content can be a plain string, a list of strings, or a list of typed
    blocks. Normalize everything into [{type, text}, ...] form."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        result = []
        for part in content:
            if isinstance(part, str):
                result.append({"type": "text", "text": part})
            elif isinstance(part, dict):
                result.append(part)
        return result
    return []


def extract_text(content_parts: Any) -> str:
    """Grab just the text blocks out of a content array, ignore tool_use/thinking."""
    parts = normalize_content(content_parts)
    texts = []
    for part in parts:
        if part.get("type") == "text":
            texts.append(part.get("text", ""))
    return "\n".join(texts)


def extract_images(content_parts: Any) -> list[dict[str, Any]]:
    """Pull base64 image blocks out of a content array.
    Also looks inside nested tool_result content blocks."""
    parts = normalize_content(content_parts)
    images = []
    for part in parts:
        if part.get("type") == "image":
            source = part.get("source", {})
            if source.get("type") == "base64" and source.get("data"):
                images.append({
                    "media_type": source.get("media_type", "image/png"),
                    "data": source["data"],
                })
        elif part.get("type") == "tool_result":
            # Nested content is usually a block list; string content is not normalized here.
            nested = part.get("content", [])
            if isinstance(nested, list):
                for sub in nested:
                    if isinstance(sub, dict) and sub.get("type") == "image":
                        source = sub.get("source", {})
                        if source.get("type") == "base64" and source.get("data"):
                            images.append({
                                "media_type": source.get("media_type", "image/png"),
                                "data": source["data"],
                            })
    return images


def first_title_line(text: str, max_chars: int = 100) -> str:
    """First non-empty line after system-tag strip, truncated for session titles."""
    return strip_system_tags(text).strip().split("\n")[0][:max_chars]


def infer_title(messages: list[MessageDict]) -> str:
    """Use the first line of the first real user message as the session title."""
    for msg in messages:
        if msg["role"] == "user" and msg.get("text"):
            first_line = first_title_line(msg["text"])
            if first_line:
                return first_line
    return "Untitled Session"


def strip_system_tags(text: str) -> str:
    """Strip out the internal XML tags Claude Code injects (system-reminder,
    ide_opened_file, etc.) so exported text is clean."""
    # Remove block tags and their content
    for tag in (
        "system-reminder", "ide_opened_file", "user-prompt-submit-hook",
        "claude_background_info", "fast_mode_info", "env",
    ):
        text = re.sub(rf"<{tag}>[\s\S]*?</{tag}>", "", text)
    # Strip remaining known opening/closing tags
    text = re.sub(
        r"</?(?:ide_selection|local-command-stdout|local-command-stderr|"
        r"command-name|antml:\w+|function_calls|example\w*)>",
        "",
        text,
    )
    return text.strip()
