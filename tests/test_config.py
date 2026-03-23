"""Tests for config.py."""

from pathlib import Path

from menard.config import load_config


def test_load_config_missing_file(tmp_path: Path):
    """Test that missing pyproject.toml returns None."""
    config = load_config(tmp_path)
    assert config is None


def test_load_config_missing_section(tmp_path: Path):
    """Test that missing [tool.menard] section returns None."""
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
[tool.menard]
mode = "warn"
require_links = ["src/**/*.py"]
""")
    config = load_config(tmp_path)
    assert config is not None
    assert config.mode == "warn"
    assert config.transitive_depth == 1  # default
    assert config.require_links == ["src/**/*.py"]
    assert config.exempt == []  # default


def test_load_config_full_section(tmp_path: Path):
    """Test loading a complete config section."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.menard]
mode = "warn"
transitive_depth = 2
enforce_symmetry = false
require_links = ["src/**/*.py", "lib/**/*.js"]
exempt = ["**/*_test.py", "**/test_*.py"]
doc_paths = ["docs/**/*.md", "README.md", "guides/**/*.txt"]
""")
    config = load_config(tmp_path)
    assert config is not None
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
[tool.menard]
mode = "block"
unknown_future_key = "some value"
another_unknown = 123
""")
    # Should not raise an error
    config = load_config(tmp_path)
    assert config is not None
    assert config.mode == "block"


def test_load_config_invalid_toml(tmp_path: Path):
    """Test that invalid TOML returns None."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("this is not valid TOML [[[")
    config = load_config(tmp_path)
    # Should return None without crashing
    assert config is None


def test_load_config_exclude_docs(tmp_path: Path):
    """Test loading exclude_docs config option."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.menard]
mode = "block"
exclude_docs = ["**/adr/**", "**/plans/**"]
""")
    config = load_config(tmp_path)
    assert config is not None
    assert config.exclude_docs == ["**/adr/**", "**/plans/**"]


def test_load_config_exclude_docs_default(tmp_path: Path):
    """Test that exclude_docs defaults to empty list."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.menard]
mode = "block"
""")
    config = load_config(tmp_path)
    assert config is not None
    assert config.exclude_docs == []


def test_load_config_brevity_exclude(tmp_path: Path):
    """Test loading brevity_exclude config option."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.menard]
mode = "block"
brevity_exclude = ["CLAUDE.md", "*#License"]
""")
    config = load_config(tmp_path)
    assert config is not None
    assert config.brevity_exclude == ["CLAUDE.md", "*#License"]


def test_load_config_brevity_exclude_default(tmp_path: Path):
    """Test that brevity_exclude defaults to empty list."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.menard]
mode = "block"
""")
    config = load_config(tmp_path)
    assert config is not None
    assert config.brevity_exclude == []
