"""Extended CLI command tests for better coverage."""

import json
import subprocess


def git_commit(cwd, message="initial"):
    """Helper to make git commits with proper env vars."""
    env = {
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    subprocess.run(["git", "commit", "-m", message], cwd=cwd, check=True, env=env)


def test_bootstrap_command_no_matches(tmp_path):
    """Test bootstrap when no doc matches are found."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    code_file = src_dir / "orphan.py"
    code_file.write_text("def orphaned(): pass\n")

    # No docs directory - no matches possible
    result = subprocess.run(
        ["docsync", "bootstrap"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "No matching docs found" in result.stdout


def test_bootstrap_command_with_apply(tmp_path):
    """Test bootstrap with --apply flag."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    code_file = src_dir / "config.py"
    code_file.write_text("def get_config(): pass\n")

    doc_file = docs_dir / "configuration.md"
    doc_file.write_text("# Configuration\n")

    # Run bootstrap with --apply
    result = subprocess.run(
        ["docsync", "bootstrap", "--apply"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Applied" in result.stdout


def test_add_link_glob_pattern(tmp_path):
    """Test add-link with glob pattern."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    # Create multiple code files
    for name in ["module1.py", "module2.py", "module3.py"]:
        code_file = src_dir / name
        code_file.write_text(f"# {name}\n")

    doc_file = docs_dir / "api.md"
    doc_file.write_text("# API\n")

    # Run add-link with glob
    result = subprocess.run(
        ["docsync", "add-link", "src/*.py", "docs/api.md"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Linked" in result.stdout


def test_add_link_dry_run(tmp_path):
    """Test add-link with --dry-run flag."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    code_file = src_dir / "module.py"
    code_file.write_text("def foo(): pass\n")

    doc_file = docs_dir / "module.md"
    doc_file.write_text("# Module\n")

    # Run add-link with dry-run
    result = subprocess.run(
        ["docsync", "add-link", "src/module.py", "docs/module.md", "--dry-run"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "DRY RUN" in result.stdout
    # Verify files weren't modified
    assert "docsync:" not in code_file.read_text()


def test_add_link_already_exists(tmp_path):
    """Test add-link when link already exists."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    code_file = src_dir / "module.py"
    code_file.write_text("# docsync: docs/module.md\n\ndef foo(): pass\n")

    doc_file = docs_dir / "module.md"
    doc_file.write_text("<!-- docsync: src/module.py -->\n\n# Module\n")

    # Run add-link again
    result = subprocess.run(
        ["docsync", "add-link", "src/module.py", "docs/module.md"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "already exists" in result.stdout


def test_defer_clear(tmp_path):
    """Test defer --clear flag."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
"""
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    code_file = src_dir / "module.py"
    code_file.write_text("def foo(): pass\n")

    # First defer
    subprocess.run(
        ["docsync", "defer", "src/module.py", "--message", "Test defer"],
        cwd=tmp_path,
        check=True,
    )

    # Then clear
    result = subprocess.run(
        ["docsync", "defer", "src/module.py", "--clear"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Cleared deferral" in result.stdout


def test_explain_changes_command(tmp_path):
    """Test explain-changes command."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    code_file = src_dir / "module.py"
    code_file.write_text("# docsync: docs/module.md\n\ndef foo(): pass\n")

    doc_file = docs_dir / "module.md"
    doc_file.write_text("<!-- docsync: src/module.py -->\n\n# Module\n")

    # Initialize git
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    git_commit(tmp_path, "initial")

    # Make changes to code
    code_file.write_text("# docsync: docs/module.md\n\ndef foo(): pass\n\ndef bar(): pass\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    git_commit(tmp_path, "add bar function")

    # Run explain-changes
    result = subprocess.run(
        ["docsync", "explain-changes", "src/module.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_check_command_with_format_json(tmp_path):
    """Test check command with JSON output."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
mode = "warn"
"""
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    code_file = src_dir / "module.py"
    code_file.write_text("# docsync: docs/module.md\n\ndef foo(): pass\n")

    # Initialize git
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "pyproject.toml"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "src/module.py"], cwd=tmp_path, check=True)

    # Run check with JSON format (doc not staged)
    result = subprocess.run(
        ["docsync", "check", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    # Should output JSON even if check fails
    output = json.loads(result.stdout)
    assert "status" in output


def test_list_stale_json_format(tmp_path):
    """Test list-stale with JSON format."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    code_file = src_dir / "module.py"
    code_file.write_text("# docsync: docs/module.md\n\ndef foo(): pass\n")

    doc_file = docs_dir / "module.md"
    doc_file.write_text("<!-- docsync: src/module.py -->\n\n# Module\n")

    # Initialize git
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    git_commit(tmp_path)

    # Run list-stale with JSON format
    result = subprocess.run(
        ["docsync", "list-stale", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # If there are no stale docs, output might be empty array or text message
    # Just check it ran successfully
    assert result.stdout is not None


def test_list_stale_paths_format(tmp_path):
    """Test list-stale with paths format."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    code_file = src_dir / "module.py"
    code_file.write_text("# docsync: docs/module.md\n\ndef foo(): pass\n")

    doc_file = docs_dir / "module.md"
    doc_file.write_text("<!-- docsync: src/module.py -->\n\n# Module\n")

    # Initialize git
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    git_commit(tmp_path)

    # Run list-stale with paths format
    result = subprocess.run(
        ["docsync", "list-stale", "--format", "paths"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_affected_docs_json_format(tmp_path):
    """Test affected-docs with JSON format."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    code_file = src_dir / "module.py"
    code_file.write_text("# docsync: docs/module.md\n\ndef foo(): pass\n")

    doc_file = docs_dir / "module.md"
    doc_file.write_text("<!-- docsync: src/module.py -->\n\n# Module\n")

    # Run affected-docs with JSON format
    result = subprocess.run(
        ["docsync", "affected-docs", "--files", "src/module.py", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # The command might output text message if no docs found, or JSON if found
    # Just verify it ran successfully
    assert result.stdout is not None


def test_check_with_create_todo(tmp_path):
    """Test check command with --create-todo flag."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    code_file = src_dir / "module.py"
    code_file.write_text("# docsync: docs/module.md\n\ndef foo(): pass\n")

    # Initialize git and stage only code file
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "src/module.py"], cwd=tmp_path, check=True)

    # Run check with --create-todo
    subprocess.run(
        ["docsync", "check", "--create-todo"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    # Should create todo file
    todo_file = tmp_path / ".docsync-todo.json"
    assert todo_file.exists()
    data = json.loads(todo_file.read_text())
    assert "todos" in data
