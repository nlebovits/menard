"""Tests for enriched staleness detection (issues #28, #31, #33)."""

import subprocess
import tempfile
from pathlib import Path

from docsync.staleness import (
    CommitInfo,
    StalenessResult,
    check_staleness_enriched,
    get_code_diff,
    get_commit_date,
    get_commits_since,
)
from docsync.toml_links import LinkTarget


def _git_init_and_commit(repo_root: Path, files: dict[str, str], message: str) -> str:
    """Helper to initialize git repo and commit files. Returns commit SHA."""
    # Check if already initialized
    if not (repo_root / ".git").exists():
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

    # Return the commit SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_commit_info_to_dict():
    """Test CommitInfo serialization."""
    info = CommitInfo(sha="abc1234", date="2026-03-17", message="feat: add feature")
    data = info.to_dict()

    assert data["sha"] == "abc1234"
    assert data["date"] == "2026-03-17"
    assert data["message"] == "feat: add feature"


def test_staleness_result_to_dict_basic():
    """Test StalenessResult basic serialization."""
    result = StalenessResult(
        is_stale=True,
        reason="Doc unchanged since code changed",
        code_file="src/auth.py",
        doc_target="docs/api.md#Authentication",
        section="Authentication",
    )
    data = result.to_dict()

    assert data["code_file"] == "src/auth.py"
    assert data["doc_target"] == "docs/api.md#Authentication"
    assert data["reason"] == "Doc unchanged since code changed"
    assert data["section"] == "Authentication"


def test_staleness_result_to_dict_enriched():
    """Test StalenessResult with enriched fields."""
    result = StalenessResult(
        is_stale=True,
        reason="Doc unchanged",
        code_file="src/auth.py",
        doc_target="docs/api.md",
        last_code_change="2026-03-17",
        last_code_commit="abc1234",
        last_doc_update="2026-03-10",
        commits_since=[
            CommitInfo(sha="abc1234", date="2026-03-17", message="feat: add MFA"),
            CommitInfo(sha="def5678", date="2026-03-15", message="fix: timeout"),
        ],
        symbols_added=["mfa_verify", "mfa_setup"],
        symbols_removed=["old_auth"],
        code_diff="+ def new_func():",
    )

    data = result.to_dict(include_diff=False)
    assert data["last_code_change"] == "2026-03-17"
    assert data["last_code_commit"] == "abc1234"
    assert data["last_doc_update"] == "2026-03-10"
    assert len(data["commits_since"]) == 2
    assert data["symbols_added"] == ["mfa_verify", "mfa_setup"]
    assert data["symbols_removed"] == ["old_auth"]
    assert "code_diff" not in data  # Not included when include_diff=False

    data_with_diff = result.to_dict(include_diff=True)
    assert data_with_diff["code_diff"] == "+ def new_func():"


def test_get_commit_date():
    """Test getting commit date."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        commit = _git_init_and_commit(repo_root, {"test.py": "pass"}, "Initial")

        date = get_commit_date(repo_root, commit)
        assert date is not None
        # Date should be in YYYY-MM-DD format
        assert len(date) == 10
        assert date[4] == "-"


def test_get_commits_since():
    """Test getting commits since a given commit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create initial commit
        initial = _git_init_and_commit(repo_root, {"src/auth.py": "def login(): pass"}, "Initial")

        # Add more commits
        (repo_root / "src" / "auth.py").write_text("def login(): pass\ndef logout(): pass")
        _git_init_and_commit(repo_root, {}, "feat: add logout")

        (repo_root / "src" / "auth.py").write_text(
            "def login(): pass\ndef logout(): pass\ndef mfa(): pass"
        )
        _git_init_and_commit(repo_root, {}, "feat: add mfa")

        commits = get_commits_since(repo_root, "src/auth.py", initial, max_commits=5)

        assert len(commits) == 2
        # Most recent first
        assert "mfa" in commits[0].message
        assert "logout" in commits[1].message


def test_get_code_diff():
    """Test getting code diff."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        initial = _git_init_and_commit(repo_root, {"src/auth.py": "def login(): pass"}, "Initial")

        # Change the file
        (repo_root / "src" / "auth.py").write_text("def login(): pass\ndef logout(): pass")
        _git_init_and_commit(repo_root, {}, "Add logout")

        diff = get_code_diff(repo_root, "src/auth.py", initial)

        assert diff is not None
        assert "+def logout" in diff


def test_get_code_diff_truncation():
    """Test that diff is truncated at max_lines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        initial = _git_init_and_commit(repo_root, {"test.py": "# old"}, "Initial")

        # Create a file with many lines
        many_lines = "\n".join([f"line_{i} = {i}" for i in range(100)])
        (repo_root / "test.py").write_text(many_lines)
        _git_init_and_commit(repo_root, {}, "Many changes")

        diff = get_code_diff(repo_root, "test.py", initial, max_lines=10)

        assert diff is not None
        assert "truncated" in diff
        lines = diff.split("\n")
        # Should have 10 lines + truncation message
        assert len(lines) == 11


def test_check_staleness_enriched_basic():
    """Test enriched staleness check returns proper structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Initial commit
        _git_init_and_commit(
            repo_root,
            {
                "src/auth.py": "def login(): pass",
                "docs/api.md": "# API\n\n## Auth\n\nDocs here",
            },
            "Initial",
        )

        # Change code
        (repo_root / "src" / "auth.py").write_text("def login(): pass\ndef logout(): pass")
        _git_init_and_commit(repo_root, {}, "feat: add logout")

        target = LinkTarget(file="docs/api.md", section="Auth")
        result = check_staleness_enriched(repo_root, "src/auth.py", target)

        assert result.is_stale
        assert result.code_file == "src/auth.py"
        assert result.doc_target == "docs/api.md#Auth"
        assert result.last_code_change is not None
        assert result.last_code_commit is not None
        # Commits should include the logout change
        assert len(result.commits_since) >= 1


def test_check_staleness_enriched_with_symbols():
    """Test that symbol changes are detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Initial commit with a function
        _git_init_and_commit(
            repo_root,
            {
                "src/auth.py": "def login(): pass\ndef old_func(): pass",
                "docs/api.md": "# API",
            },
            "Initial",
        )

        # Change code - remove old_func, add new_func
        (repo_root / "src" / "auth.py").write_text("def login(): pass\ndef new_func(): pass")
        _git_init_and_commit(repo_root, {}, "Replace function")

        target = LinkTarget(file="docs/api.md")
        result = check_staleness_enriched(repo_root, "src/auth.py", target)

        assert result.is_stale
        assert "new_func" in result.symbols_added
        assert "old_func" in result.symbols_removed


def test_check_staleness_enriched_with_diff():
    """Test that diff is included when requested."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        _git_init_and_commit(
            repo_root,
            {"src/auth.py": "def login(): pass", "docs/api.md": "# API"},
            "Initial",
        )

        (repo_root / "src" / "auth.py").write_text("def login(): pass\ndef logout(): pass")
        _git_init_and_commit(repo_root, {}, "Add logout")

        target = LinkTarget(file="docs/api.md")

        # Without diff
        result_no_diff = check_staleness_enriched(
            repo_root, "src/auth.py", target, include_diff=False
        )
        assert result_no_diff.code_diff is None

        # With diff
        result_with_diff = check_staleness_enriched(
            repo_root, "src/auth.py", target, include_diff=True
        )
        assert result_with_diff.code_diff is not None
        assert "logout" in result_with_diff.code_diff


def test_check_staleness_enriched_fresh_doc():
    """Test that fresh docs don't get excessive enrichment."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        _git_init_and_commit(
            repo_root,
            {"src/auth.py": "def login(): pass", "docs/api.md": "# API"},
            "Initial",
        )

        # Update docs after code (doc is fresh)
        (repo_root / "docs" / "api.md").write_text("# API\n\nUpdated docs")
        _git_init_and_commit(repo_root, {}, "Update docs")

        target = LinkTarget(file="docs/api.md")
        result = check_staleness_enriched(repo_root, "src/auth.py", target)

        assert not result.is_stale
        # Fresh docs shouldn't have commits_since or symbol changes
        assert len(result.commits_since) == 0
        assert len(result.symbols_added) == 0
        assert len(result.symbols_removed) == 0
