"""Integration test for TOML-based menard workflow."""

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
[tool.menard]
mode = "block"
transitive_depth = 1
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
"""
        )

        # Create .menard/links.toml
        (repo_root / ".menard").mkdir()
        (repo_root / ".menard" / "links.toml").write_text(
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
            ["menard", "list-stale", "--format", "json"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        import json

        output = json.loads(result.stdout)

        # Should detect stale Authentication section
        assert len(output["stale"]) == 1
        # Issue #34: doc_target is now a structured object
        assert output["stale"][0]["doc_target"]["file"] == "docs/api.md"
        assert output["stale"][0]["doc_target"]["section"] == "Authentication"
        assert output["stale"][0]["doc_target"]["line_range"] is not None

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
            ["menard", "list-stale", "--format", "json"],
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
        (repo_root / ".menard").mkdir()
        (repo_root / ".menard" / "links.toml").write_text(
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
            ["menard", "validate-links"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1  # Should fail validation
        assert "MissingSection" in result.stdout
        assert "not found" in result.stdout


def test_list_stale_paths_format():
    """Test that --format paths outputs unique doc file paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Initialize git
        subprocess.run(["git", "init"], cwd=repo_root, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_root,
            capture_output=True,
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, capture_output=True)

        # Create structure with multiple links to same doc file
        (repo_root / ".menard").mkdir()
        (repo_root / ".menard" / "links.toml").write_text(
            """
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]

[[link]]
code = "src/models.py"
docs = ["docs/api.md#Models", "docs/other.md"]
"""
        )

        (repo_root / "pyproject.toml").write_text('[tool.menard]\nmode = "warn"')

        (repo_root / "src").mkdir()
        (repo_root / "src" / "auth.py").write_text("def login(): pass")
        (repo_root / "src" / "models.py").write_text("class User: pass")

        (repo_root / "docs").mkdir()
        (repo_root / "docs" / "api.md").write_text(
            """## Authentication

Login functionality.

## Models

Model docs.
"""
        )
        (repo_root / "docs" / "other.md").write_text("## Other\n\nDocs.\n")

        _git_commit(repo_root, "Initial commit")

        # Modify code to make docs stale
        (repo_root / "src" / "auth.py").write_text("def login():\n    return True")
        (repo_root / "src" / "models.py").write_text("class User:\n    name: str")
        _git_commit(repo_root, "Update code")

        # Test --format paths
        result = subprocess.run(
            ["menard", "list-stale", "--format", "paths"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        paths = result.stdout.strip().split("\n")

        # Should output unique doc paths (no duplicates, no section anchors)
        assert "docs/api.md" in paths
        assert "docs/other.md" in paths
        # Should NOT include section anchors
        assert "docs/api.md#Authentication" not in paths
        assert "docs/api.md#Models" not in paths
        # Should be deduplicated (api.md appears once even though two sections are stale)
        assert paths.count("docs/api.md") == 1
