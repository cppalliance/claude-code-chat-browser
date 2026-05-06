"""Filesystem- and URL-safe slugs for export paths and download names.

Uses ASCII letters and digits only; other characters (including Unicode
letters and punctuation) become hyphen runs, then trimmed. Matches the
historical behavior of ``api/export_api.py`` and avoids platform-specific
issues with non-ASCII paths inside zip archives.
"""

from __future__ import annotations

import re


def slugify(text: str) -> str:
    """Lowercase *text* and replace each run of non-[a-z0-9] with a single hyphen."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")
