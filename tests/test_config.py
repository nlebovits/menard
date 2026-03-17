"""Tests for config.py."""

from pathlib import Path

from docsync.config import load_config


def test_load_config_missing_file(tmp_path: Path):
    """Test that missing pyproject.toml returns None."""
    config = load_config(tmp_path)
    assert config is None


def test_load_config_missing_section(tmp_path: Path):
    """Test that missing [tool.docsync] section returns None."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "test"
version = "0.1.0"
""")
    config = load_config(tmp_path)
    assert config is None


def test_load_config_partial_section(tmp_path: Path):
    """Test that partial config uses defaults for missing keys."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.docsync]
mode = "warn"
require_links = ["src/**/*.py"]
""")
    config = load_config(tmp_path)
    assert config.mode == "warn"
    assert config.transitive_depth == 1  # default
    assert config.require_links == ["src/**/*.py"]
    assert config.exempt == []  # default


def test_load_config_full_section(tmp_path: Path):
    """Test loading a complete config section."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.docsync]
mode = "warn"
transitive_depth = 2
enforce_symmetry = false
require_links = ["src/**/*.py", "lib/**/*.js"]
exempt = ["**/*_test.py", "**/test_*.py"]
doc_paths = ["docs/**/*.md", "README.md", "guides/**/*.txt"]
""")
    config = load_config(tmp_path)
    assert config.mode == "warn"
    assert config.transitive_depth == 2
    assert config.enforce_symmetry is False
    assert config.require_links == ["src/**/*.py", "lib/**/*.js"]
    assert config.exempt == ["**/*_test.py", "**/test_*.py"]
    assert config.doc_paths == ["docs/**/*.md", "README.md", "guides/**/*.txt"]


def test_load_config_ignores_unknown_keys(tmp_path: Path):
    """Test that unknown keys in config are ignored (forward compatibility)."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.docsync]
mode = "block"
unknown_future_key = "some value"
another_unknown = 123
""")
    # Should not raise an error
    config = load_config(tmp_path)
    assert config.mode == "block"


def test_load_config_invalid_toml(tmp_path: Path):
    """Test that invalid TOML returns None."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("this is not valid TOML [[[")
    config = load_config(tmp_path)
    # Should return None without crashing
    assert config is None
