"""Integration tests for CLI commands."""

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


def test_init_command(tmp_path):
    """Test docsync init creates configuration."""
    # Create a pyproject.toml
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\n")

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Run init
    result = subprocess.run(
        ["docsync", "init"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[tool.docsync]" in pyproject.read_text()


def test_check_command_unconfigured(tmp_path):
    """Test check command on unconfigured repo."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    result = subprocess.run(
        ["docsync", "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    # Should pass (exit 0) with warning message
    assert result.returncode == 0
    assert "not configured" in result.stdout.lower()


def test_coverage_command_json(tmp_path):
    """Test coverage command with JSON output."""
    # Setup
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
mode = "block"
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
    )

    # Create src and docs
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    # Create code file with link
    code_file = src_dir / "module.py"
    code_file.write_text("# docsync: docs/module.md\n\ndef foo(): pass\n")

    # Create doc file with backlink
    doc_file = docs_dir / "module.md"
    doc_file.write_text("<!-- docsync: src/module.py -->\n\n# Module\n")

    # Initialize git
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    git_commit(tmp_path)

    # Run coverage with JSON output
    result = subprocess.run(
        ["docsync", "coverage", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    output = json.loads(result.stdout)
    assert "links" in output
    assert "stale_docs" in output
    assert "summary" in output


def test_list_stale_command(tmp_path):
    """Test list-stale command."""
    # Setup
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

    # Create linked files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    code_file = src_dir / "module.py"
    code_file.write_text("# docsync: docs/module.md\n\ndef foo(): pass\n")

    doc_file = docs_dir / "module.md"
    doc_file.write_text("<!-- docsync: src/module.py -->\n\n# Module\n")

    # Initialize git and commit
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    git_commit(tmp_path)

    # Run list-stale
    result = subprocess.run(
        ["docsync", "list-stale"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_info_command(tmp_path):
    """Test info command shows file information."""
    # Setup
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

    # Run info command
    result = subprocess.run(
        ["docsync", "info", "src/module.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "src/module.py" in result.stdout


def test_info_command_json(tmp_path):
    """Test info command with JSON output."""
    # Setup
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

    # Run info command with JSON format
    result = subprocess.run(
        ["docsync", "info", "src/module.py", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    output = json.loads(result.stdout)
    assert output["file"] == "src/module.py"
    assert "linked_docs" in output
    assert "docs/module.md" in output["linked_docs"]


def test_add_link_command(tmp_path):
    """Test add-link command."""
    # Setup
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
    code_file.write_text("def foo(): pass\n")

    doc_file = docs_dir / "module.md"
    doc_file.write_text("# Module\n")

    # Run add-link
    result = subprocess.run(
        ["docsync", "add-link", "src/module.py", "docs/module.md"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Verify links were added
    assert "docsync:" in code_file.read_text()
    assert "docsync:" in doc_file.read_text()


def test_defer_command(tmp_path):
    """Test defer command."""
    # Setup
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
    code_file.write_text("def foo(): pass\n")

    # Run defer
    result = subprocess.run(
        [
            "docsync",
            "defer",
            "src/module.py",
            "--message",
            "Will update in next commit",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Verify deferred file was created
    deferred_file = tmp_path / ".docsync-deferred.json"
    assert deferred_file.exists()

    # Verify content
    data = json.loads(deferred_file.read_text())
    assert "src/module.py" in data


def test_list_deferred_command(tmp_path):
    """Test list-deferred command."""
    # Setup
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
"""
    )

    # Create deferred file manually
    deferred_file = tmp_path / ".docsync-deferred.json"
    deferred_file.write_text(
        json.dumps(
            {
                "src/module.py": {
                    "message": "Will update later",
                    "deferred_at": "2026-03-12T10:00:00",
                }
            }
        )
    )

    # Run list-deferred
    result = subprocess.run(
        ["docsync", "list-deferred"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "src/module.py" in result.stdout


def test_clear_cache_command(tmp_path):
    """Test clear-cache command."""
    # Setup
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test"

[tool.docsync]
require_links = ["src/**/*.py"]
"""
    )

    # Create cache directory
    cache_dir = tmp_path / ".docsync"
    cache_dir.mkdir()
    cache_file = cache_dir / "import_graph.json"
    cache_file.write_text("{}")

    # Run clear-cache
    result = subprocess.run(
        ["docsync", "clear-cache"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "cleared" in result.stdout.lower()


def test_affected_docs_command(tmp_path):
    """Test affected-docs command."""
    # Setup
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

    # Run affected-docs
    result = subprocess.run(
        ["docsync", "affected-docs", "--files", "src/module.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
