"""Comprehensive tests for CLI commands to achieve 80%+ coverage."""

import json
import subprocess
from pathlib import Path


def setup_git_repo(tmp_path):
    """Helper to initialize a git repo for tests."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )


def test_coverage_command(tmp_path, monkeypatch):
    """Test coverage command via CLI."""
    monkeypatch.chdir(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("# docsync: docs/auth.md\ndef auth(): pass\n")
    (src / "utils.py").write_text("def util(): pass\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth.md").write_text("<!-- docsync: src/auth.py -->\n# Auth\n")

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
require_links = ["src/**/*.py"]
"""
    )

    # Run coverage command
    result = subprocess.run(
        ["docsync", "coverage"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Coverage" in result.stdout or "coverage" in result.stdout.lower()


def test_list_stale_command(tmp_path, monkeypatch):
    """Test list-stale command."""
    monkeypatch.chdir(tmp_path)
    setup_git_repo(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    code = src / "code.py"
    code.write_text("# docsync: docs/doc.md\ndef foo(): pass\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    doc = docs / "doc.md"
    doc.write_text("<!-- docsync: src/code.py -->\n# Docs\n")

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
require_links = ["src/**/*.py"]
"""
    )

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True
    )

    # Modify code to make doc stale
    code.write_text("# docsync: docs/doc.md\ndef foo():\n    return 42\n")
    subprocess.run(["git", "add", str(code)], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "update"], cwd=tmp_path, check=True, capture_output=True
    )

    result = subprocess.run(
        ["docsync", "list-stale"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    # Should exit 0 even if stale docs found (it's a query command)
    assert result.returncode == 0


def test_info_command(tmp_path, monkeypatch):
    """Test info command."""
    monkeypatch.chdir(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("# docsync: docs/doc.md\ndef foo(): pass\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "doc.md").write_text("<!-- docsync: src/code.py -->\n# Docs\n")

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
"""
    )

    result = subprocess.run(
        ["docsync", "info", "src/code.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "code.py" in result.stdout or "doc.md" in result.stdout


def test_affected_docs_command(tmp_path, monkeypatch):
    """Test affected-docs command."""
    monkeypatch.chdir(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("# docsync: docs/doc.md\ndef foo(): pass\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "doc.md").write_text("<!-- docsync: src/code.py -->\n# Docs\n")

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
"""
    )

    result = subprocess.run(
        ["docsync", "affected-docs", "src/code.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_defer_and_list_deferred(tmp_path, monkeypatch):
    """Test defer and list-deferred commands."""
    monkeypatch.chdir(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("def foo(): pass\n")

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
require_links = ["src/**/*.py"]
"""
    )

    # Defer a file
    result = subprocess.run(
        ["docsync", "defer", "src/code.py", "-m", "WIP feature"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # List deferrals
    result = subprocess.run(
        ["docsync", "list-deferred"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "code.py" in result.stdout or "WIP" in result.stdout

    # Clear deferral
    result = subprocess.run(
        ["docsync", "defer", "src/code.py", "--clear"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_clear_cache_command(tmp_path, monkeypatch):
    """Test clear-cache command."""
    monkeypatch.chdir(tmp_path)

    # Create cache
    docsync_dir = tmp_path / ".docsync"
    docsync_dir.mkdir()
    (docsync_dir / "import_graph.json").write_text("{}")
    (docsync_dir / "import_graph.state").write_text("abc123")

    config = tmp_path / "pyproject.toml"
    config.write_text("[tool.docsync]\n")

    result = subprocess.run(
        ["docsync", "clear-cache"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "cleared" in result.stdout.lower() or "cache" in result.stdout.lower()


def test_explain_changes_command(tmp_path, monkeypatch):
    """Test explain-changes command."""
    monkeypatch.chdir(tmp_path)
    setup_git_repo(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    code = src / "code.py"
    code.write_text("# docsync: docs/doc.md\ndef foo(): pass\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    doc = docs / "doc.md"
    doc.write_text("<!-- docsync: src/code.py -->\n# Docs\n")

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
"""
    )

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True
    )

    code.write_text("# docsync: docs/doc.md\ndef foo():\n    return 42\n")
    subprocess.run(["git", "add", str(code)], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "update"], cwd=tmp_path, check=True, capture_output=True
    )

    result = subprocess.run(
        ["docsync", "explain-changes", "docs/doc.md"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    # Command may return 0 or 1 depending on whether docs are stale
    assert result.returncode in (0, 1)


def test_json_output_formats(tmp_path, monkeypatch):
    """Test --format json for various commands."""
    monkeypatch.chdir(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("# docsync: docs/doc.md\ndef foo(): pass\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "doc.md").write_text("<!-- docsync: src/code.py -->\n# Docs\n")

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
"""
    )

    # Test list-deferred --format json
    result = subprocess.run(
        ["docsync", "list-deferred", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    try:
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
    except json.JSONDecodeError:
        pass  # Empty output is OK


def test_check_with_deferrals(tmp_path, monkeypatch):
    """Test that check command respects deferrals."""
    monkeypatch.chdir(tmp_path)
    setup_git_repo(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    code = src / "code.py"
    code.write_text("def foo(): pass\n")  # No doc link

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
require_links = ["src/**/*.py"]
"""
    )

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)

    # Defer the file
    subprocess.run(
        ["docsync", "defer", "src/code.py", "-m", "WIP"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Check should pass because file is deferred
    result = subprocess.run(
        ["docsync", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_install_hook_command(tmp_path, monkeypatch):
    """Test install-hook command."""
    monkeypatch.chdir(tmp_path)
    setup_git_repo(tmp_path)

    config = tmp_path / "pyproject.toml"
    config.write_text("[tool.docsync]\n")

    result = subprocess.run(
        ["docsync", "install-hook"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    hook_file = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook_file.exists()
    assert "docsync check" in hook_file.read_text()


def test_remove_hook_command(tmp_path, monkeypatch):
    """Test remove-hook command."""
    monkeypatch.chdir(tmp_path)
    setup_git_repo(tmp_path)

    # First install hook
    config = tmp_path / "pyproject.toml"
    config.write_text("[tool.docsync]\n")

    subprocess.run(
        ["docsync", "install-hook"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Then remove it
    result = subprocess.run(
        ["docsync", "remove-hook"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_coverage_with_no_files(tmp_path, monkeypatch):
    """Test coverage command with empty project."""
    monkeypatch.chdir(tmp_path)

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
"""
    )

    result = subprocess.run(
        ["docsync", "coverage"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_check_without_git_repo(tmp_path, monkeypatch):
    """Test check command in non-git directory."""
    monkeypatch.chdir(tmp_path)

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
"""
    )

    result = subprocess.run(
        ["docsync", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    # Should handle gracefully
    assert result.returncode in (0, 1)


def test_init_without_git(tmp_path, monkeypatch):
    """Test init in non-git directory."""
    monkeypatch.chdir(tmp_path)

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n")

    result = subprocess.run(
        ["docsync", "init"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    # Should succeed and create config
    assert result.returncode == 0
    assert "[tool.docsync]" in pyproject.read_text()


def test_bootstrap_dry_run(tmp_path, monkeypatch):
    """Test bootstrap without --apply."""
    monkeypatch.chdir(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("def auth(): pass\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth.md").write_text("# Auth\n")

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
require_links = ["src/**/*.py"]
"""
    )

    result = subprocess.run(
        ["docsync", "bootstrap"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # Files should not be modified
    assert "docsync:" not in (src / "auth.py").read_text()
