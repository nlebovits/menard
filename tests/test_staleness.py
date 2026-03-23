"""Tests for git diff-based staleness detection."""

import subprocess
import tempfile
from pathlib import Path

from menard.staleness import is_doc_stale
from menard.toml_links import LinkTarget


def _git_init_and_commit(repo_root: Path, files: dict[str, str], message: str):
    """Helper to initialize git repo and commit files."""
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )

    for file_path, content in files.items():
        full_path = repo_root / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True, capture_output=True)


def test_is_doc_stale_whole_file_fresh():
    """Test that a doc updated after code is not stale."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Initial commit with code
        _git_init_and_commit(
            repo_root, {"src/auth.py": "def login(): pass", "docs/api.md": "# API"}, "Initial"
        )

        # Change code
        (repo_root / "src" / "auth.py").write_text("def login():\n    return True")
        _git_init_and_commit(repo_root, {}, "Update code")

        # Update doc
        (repo_root / "docs" / "api.md").write_text("# API\n\nUpdated docs")
        _git_init_and_commit(repo_root, {}, "Update docs")

        # Check staleness
        target = LinkTarget(file="docs/api.md")
        is_stale, reason = is_doc_stale(repo_root, "src/auth.py", target)

        assert not is_stale
        assert "updated after" in reason.lower()


def test_is_doc_stale_whole_file_stale():
    """Test that a doc not updated after code change is stale."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Initial commit
        _git_init_and_commit(
            repo_root, {"src/auth.py": "def login(): pass", "docs/api.md": "# API"}, "Initial"
        )

        # Change code without updating doc
        (repo_root / "src" / "auth.py").write_text("def login():\n    return True")
        _git_init_and_commit(repo_root, {}, "Update code")

        # Check staleness
        target = LinkTarget(file="docs/api.md")
        is_stale, reason = is_doc_stale(repo_root, "src/auth.py", target)

        assert is_stale
        assert "unchanged" in reason.lower()


def test_is_doc_stale_section_updated():
    """Test that updating a specific section marks it as not stale."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Initial commit
        _git_init_and_commit(
            repo_root,
            {
                "src/auth.py": "def login(): pass",
                "docs/api.md": "## Authentication\n\nOld docs\n\n## Other\n\nOther",
            },
            "Initial",
        )

        # Change code
        (repo_root / "src" / "auth.py").write_text("def login():\n    return True")
        _git_init_and_commit(repo_root, {}, "Update code")

        # Update the Authentication section
        (repo_root / "docs" / "api.md").write_text(
            "## Authentication\n\nUpdated auth docs\n\n## Other\n\nOther"
        )
        _git_init_and_commit(repo_root, {}, "Update auth docs")

        # Check staleness for the Authentication section
        target = LinkTarget(file="docs/api.md", section="Authentication")
        is_stale, reason = is_doc_stale(repo_root, "src/auth.py", target)

        assert not is_stale


def test_is_doc_stale_section_not_updated():
    """Test that not updating a section marks it as stale."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Initial commit
        _git_init_and_commit(
            repo_root,
            {
                "src/auth.py": "def login(): pass",
                "docs/api.md": "## Authentication\n\nOld docs\n\n## Other\n\nOther",
            },
            "Initial",
        )

        # Change code
        (repo_root / "src" / "auth.py").write_text("def login():\n    return True")
        _git_init_and_commit(repo_root, {}, "Update code")

        # Update a DIFFERENT section
        (repo_root / "docs" / "api.md").write_text(
            "## Authentication\n\nOld docs\n\n## Other\n\nUpdated other section"
        )
        _git_init_and_commit(repo_root, {}, "Update other section")

        # Authentication section should still be stale
        target = LinkTarget(file="docs/api.md", section="Authentication")
        is_stale, reason = is_doc_stale(repo_root, "src/auth.py", target)

        assert is_stale


def test_is_doc_stale_new_file():
    """Test that new code files with no git history are considered stale."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Initialize git but don't commit the code file
        _git_init_and_commit(repo_root, {"docs/api.md": "# API"}, "Initial")

        # Create code file (not committed)
        (repo_root / "src").mkdir()
        (repo_root / "src" / "auth.py").write_text("def login(): pass")

        # Check staleness
        target = LinkTarget(file="docs/api.md")
        is_stale, reason = is_doc_stale(repo_root, "src/auth.py", target)

        assert is_stale
        assert "new" in reason.lower() or "untracked" in reason.lower()
