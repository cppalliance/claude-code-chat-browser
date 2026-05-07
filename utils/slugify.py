"""Filesystem- and URL-safe slugs for export paths and download names.

Uses ASCII letters and digits only; other characters (including Unicode
letters and punctuation) become hyphen runs, then trimmed. Matches the
historical behavior of ``api/export_api.py`` and avoids platform-specific
issues with non-ASCII paths inside zip archives.
"""

from __future__ import annotations

import re


def slugify(text: str, *, default: str = "") -> str:
    """Lowercase *text* and replace each run of non-[a-z0-9] with one hyphen.

    After stripping leading/trailing hyphens, returns that string; if it is
    empty, returns *default*. Export code passes ``default="session"`` or
    ``default="project"``.
    Examples (handled by the ``[^a-z0-9]+`` substitution below):

    - ``AT&T`` → ``at-t``
    - ``issue#42`` → ``issue-42``
    """
    text = text.lower()
    # Non-ASCII-alphanumeric runs → '-'; e.g. AT&T → at-t, issue#42 → issue-42.
    text = re.sub(r"[^a-z0-9]+", "-", text)
    stripped = text.strip("-")
    return stripped if stripped else default
