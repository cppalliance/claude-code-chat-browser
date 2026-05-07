"""Regression tests for utils.slugify (Issue #30 / CCC8).

Historically ``scripts/export.py`` used ``isalnum()`` (Unicode letters preserved)
while ``api/export_api.py`` used ASCII-only ``[^a-z0-9]+``. The canonical
implementation matches the API for portable zip / download filenames.
"""

import os

from utils.slugify import slugify


def test_ascii_words_hyphenated():
    assert slugify("Hello World") == "hello-world"


def test_punctuation_collapses_to_single_hyphen():
    assert slugify("foo__bar") == "foo-bar"
    assert slugify("a.b.c") == "a-b-c"


def test_unicode_letters_become_ascii_safe():
    """Old CLI kept Latin-1 letters (e.g. é); canonical slug strips to ASCII."""
    assert slugify("Café noir") == "caf-noir"


def test_empty_after_strip():
    assert slugify("!!!") == ""


def test_digits_preserved():
    assert slugify("Issue 42 Fix") == "issue-42-fix"


def test_punctuation_examples_match_regex_behavior():
    assert slugify("AT&T") == "at-t"
    assert slugify("issue#42") == "issue-42"


def test_default_used_when_slug_empty():
    assert slugify("!!!", default="session") == "session"
    assert slugify("!!!") == ""


def test_export_leaf_path_parity_api_zip_vs_cli():
    """Same session inputs → same ``proj_slug``, ``title_slug``, and file leaf as API vs CLI."""
    title = "Issue #42: AT&T"
    project = "Foo/Bar!"
    sid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    ts_file = "2026-05-07T12-00-00"
    short_id = sid[:8]
    title_slug = slugify(title, default="session")
    proj_slug = slugify(project, default="project")
    leaf_md = f"{ts_file}__{title_slug}__{short_id}.md"
    api_zip_inner = f"{proj_slug}/{leaf_md}"
    date_str = ts_file[:10]
    cli_rel = os.path.join(date_str, proj_slug, leaf_md)
    assert api_zip_inner.endswith(leaf_md)
    assert os.path.basename(cli_rel) == leaf_md
    assert cli_rel.replace("\\", "/").endswith(f"{proj_slug}/{leaf_md}")
