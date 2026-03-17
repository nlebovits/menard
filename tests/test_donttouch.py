"""Tests for protected content guard."""

from pathlib import Path

from docsync.donttouch import load_donttouch


def test_load_donttouch_missing_file(tmp_path):
    """Should return None if .docsync/donttouch doesn't exist."""
    result = load_donttouch(tmp_path)
    assert result is None


def test_load_donttouch_file_patterns(tmp_path):
    """Should parse file patterns."""
    donttouch = tmp_path / ".docsync" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text("LICENSE\n*.lock\n")

    rules = load_donttouch(tmp_path)
    assert rules is not None
    assert rules.file_patterns.match_file("LICENSE")
    assert rules.file_patterns.match_file("package.lock")
