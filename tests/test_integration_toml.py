"""Integration test for TOML-based docsync workflow."""

import subprocess
import tempfile
from pathlib import Path


def _git_init(repo_root: Path):
    """Initialize git repo with config."""
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


def _git_commit(repo_root: Path, message: str):
    """Stage all files and commit."""
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True, capture_output=True)


def test_full_workflow_with_sections():
    """Test complete workflow: init, create links, detect staleness."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Initialize git
        _git_init(repo_root)

        # Create pyproject.toml
        (repo_root / "pyproject.toml").write_text(
            """
[tool.docsync]
mode = "block"
transitive_depth = 1
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
        )

        # Create .docsync/links.toml
        (repo_root / ".docsync").mkdir()
        (repo_root / ".docsync" / "links.toml").write_text(
            """
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]
"""
        )

        # Create code and docs
        (repo_root / "src").mkdir()
        (repo_root / "src" / "auth.py").write_text("def login(): pass")

        (repo_root / "docs").mkdir()
        (repo_root / "docs" / "api.md").write_text(
            """## Authentication

Login functionality.

## Other Section

Other docs.
"""
        )

        # Initial commit
        _git_commit(repo_root, "Initial commit")

        # Modify code
        (repo_root / "src" / "auth.py").write_text("def login():\n    return True")
        _git_commit(repo_root, "Update auth code")

        # Check staleness using CLI
        result = subprocess.run(
            ["docsync", "list-stale", "--format", "json"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        import json

        output = json.loads(result.stdout)

        # Should detect stale Authentication section
        assert len(output["stale"]) == 1
        assert output["stale"][0]["doc_target"] == "docs/api.md#Authentication"
        assert output["stale"][0]["section"] == "Authentication"

        # Update the Authentication section
        (repo_root / "docs" / "api.md").write_text(
            """## Authentication

Updated login functionality.

## Other Section

Other docs.
"""
        )
        _git_commit(repo_root, "Update auth docs")

        # Check staleness again - should be fresh now
        result = subprocess.run(
            ["docsync", "list-stale", "--format", "json"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert len(output["stale"]) == 0


def test_validate_links_command():
    """Test that validate-links detects missing sections."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create structure
        (repo_root / ".docsync").mkdir()
        (repo_root / ".docsync" / "links.toml").write_text(
            """
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#MissingSection"]
"""
        )

        (repo_root / "src").mkdir()
        (repo_root / "src" / "auth.py").write_text("# code")

        (repo_root / "docs").mkdir()
        (repo_root / "docs" / "api.md").write_text("## RealSection\n\nDocs")

        # Run validate-links
        result = subprocess.run(
            ["docsync", "validate-links"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1  # Should fail validation
        assert "MissingSection" in result.stdout
        assert "not found" in result.stdout
