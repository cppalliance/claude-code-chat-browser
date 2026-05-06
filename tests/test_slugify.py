"""Regression tests for utils.slugify (Issue #30 / CCC8).

Historically ``scripts/export.py`` used ``isalnum()`` (Unicode letters preserved)
while ``api/export_api.py`` used ASCII-only ``[^a-z0-9]+``. The canonical
implementation matches the API for portable zip / download filenames.
"""

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
