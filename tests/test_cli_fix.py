"""Tests for docsync fix CLI commands."""

import json
import subprocess
from argparse import Namespace
from unittest.mock import patch

from docsync.reviewed import Review, load_reviews, save_review
from docsync.toml_links import load_links


def test_cmd_fix_mark_reviewed_creates_review(tmp_path, monkeypatch):
    """Test fix mark-reviewed creates a review entry."""
    monkeypatch.chdir(tmp_path)

    # Create a git repo with a commit
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create code file and commit
    src = tmp_path / "src"
    src.mkdir()
    code_file = src / "auth.py"
    code_file.write_text("def login(): pass")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    # Create .docsync directory
    docsync = tmp_path / ".docsync"
    docsync.mkdir()

    # Import and call the command
    from docsync.cli import cmd_fix_mark_reviewed

    result = cmd_fix_mark_reviewed(
        Namespace(
            code="src/auth.py",
            doc="docs/api.md#Authentication",
            reviewed_by="claude",
            format="text",
        )
    )

    assert result == 0

    # Verify review was created
    reviews = load_reviews(tmp_path)
    assert len(reviews) == 1
    assert reviews[0].code_file == "src/auth.py"
    assert reviews[0].doc_target == "docs/api.md#Authentication"
    assert reviews[0].reviewed_by == "claude"
    assert len(reviews[0].code_commit_at_review) == 7  # Short SHA


def test_cmd_fix_mark_reviewed_json_output(tmp_path, monkeypatch, capsys):
    """Test fix mark-reviewed with JSON output."""
    monkeypatch.chdir(tmp_path)

    # Create a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("pass")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    docsync = tmp_path / ".docsync"
    docsync.mkdir()

    import json

    from docsync.cli import cmd_fix_mark_reviewed

    result = cmd_fix_mark_reviewed(
        Namespace(
            code="src/auth.py",
            doc="docs/api.md",
            reviewed_by="user",
            format="json",
        )
    )

    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "created"
    assert data["review"]["code_file"] == "src/auth.py"


def test_cmd_fix_ignore_adds_flag(tmp_path, monkeypatch):
    """Test fix ignore adds ignore=true to links.toml."""
    monkeypatch.chdir(tmp_path)

    # Create docsync dir with links
    docsync = tmp_path / ".docsync"
    docsync.mkdir()
    links_file = docsync / "links.toml"
    links_file.write_text(
        """[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]
"""
    )

    from docsync.cli import cmd_fix_ignore

    result = cmd_fix_ignore(
        Namespace(
            code="src/auth.py",
            doc="docs/api.md#Authentication",
            format="text",
        )
    )

    assert result == 0

    # Verify ignore flag was added
    links = load_links(tmp_path)
    assert len(links) == 1
    assert links[0].ignore is True


def test_cmd_fix_ignore_link_not_found(tmp_path, monkeypatch):
    """Test fix ignore fails gracefully when link doesn't exist."""
    monkeypatch.chdir(tmp_path)

    docsync = tmp_path / ".docsync"
    docsync.mkdir()
    (docsync / "links.toml").write_text("")

    from docsync.cli import cmd_fix_ignore

    result = cmd_fix_ignore(
        Namespace(
            code="src/nonexistent.py",
            doc="docs/api.md",
            format="text",
        )
    )

    assert result == 1  # Link not found


def test_cmd_clean_reviewed_removes_orphaned(tmp_path, monkeypatch):
    """Test clean-reviewed removes orphaned reviews."""
    monkeypatch.chdir(tmp_path)

    # Create one existing file
    src = tmp_path / "src"
    src.mkdir()
    (src / "exists.py").write_text("pass")

    # Create reviews for both existing and non-existing files
    docsync = tmp_path / ".docsync"
    docsync.mkdir()

    from docsync.reviewed import Review, save_review

    save_review(
        tmp_path,
        Review(
            code_file="src/exists.py",
            doc_target="docs/api.md",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review="abc1234",
        ),
    )
    save_review(
        tmp_path,
        Review(
            code_file="src/deleted.py",  # Doesn't exist
            doc_target="docs/api.md",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review="def5678",
        ),
    )

    from docsync.cli import cmd_clean_reviewed

    result = cmd_clean_reviewed(Namespace(all=False, format="text"))

    assert result == 0
    reviews = load_reviews(tmp_path)
    assert len(reviews) == 1
    assert reviews[0].code_file == "src/exists.py"


def test_cmd_clean_reviewed_all(tmp_path, monkeypatch):
    """Test clean-reviewed --all removes everything."""
    monkeypatch.chdir(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("pass")

    docsync = tmp_path / ".docsync"
    docsync.mkdir()

    save_review(
        tmp_path,
        Review(
            code_file="src/auth.py",
            doc_target="docs/api.md",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review="abc1234",
        ),
    )

    from docsync.cli import cmd_clean_reviewed

    result = cmd_clean_reviewed(Namespace(all=True, format="text"))

    assert result == 0
    assert len(load_reviews(tmp_path)) == 0


def test_list_stale_skips_reviewed_items(tmp_path, monkeypatch, capsys):
    """Test that list-stale skips items that have been reviewed."""
    monkeypatch.chdir(tmp_path)

    # Create git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create code file
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("def login(): pass")

    # Create doc file
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api.md").write_text("# API\n\n## Authentication\n\nDocs here")

    # Commit code first
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    # Modify code (makes doc stale)
    (src / "auth.py").write_text("def login(): pass\ndef logout(): pass")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add logout"], cwd=tmp_path, capture_output=True)

    # Get current commit
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    current_commit = result.stdout.strip()[:7]

    # Create config and links
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.docsync]\nrequire_links = ["src/**/*.py"]\n')

    docsync = tmp_path / ".docsync"
    docsync.mkdir()
    (docsync / "links.toml").write_text(
        '[[link]]\ncode = "src/auth.py"\ndocs = ["docs/api.md#Authentication"]\n'
    )

    # Mark as reviewed at current commit
    save_review(
        tmp_path,
        Review(
            code_file="src/auth.py",
            doc_target="docs/api.md#Authentication",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review=current_commit,
        ),
    )

    # Run list-stale - should skip the reviewed item
    from docsync.cli import cmd_list_stale

    result = cmd_list_stale(
        Namespace(format="json", show_diff=False, diff_lines=30, changed_files=None)
    )

    captured = capsys.readouterr()
    data = json.loads(captured.out)

    # Should have 0 stale items (the one stale item was reviewed)
    assert len(data["stale"]) == 0
    assert data.get("skipped_reviewed", 0) == 1


def test_list_stale_skips_ignored_links(tmp_path, monkeypatch, capsys):
    """Test that list-stale skips links with ignore=true."""
    monkeypatch.chdir(tmp_path)

    # Create git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create code file
    src = tmp_path / "src"
    src.mkdir()
    (src / "generated.py").write_text("# auto-generated code")

    # Create doc file
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api.md").write_text("# API\n\n## Generated\n\nDocs here")

    # Commit
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    # Modify code (makes doc stale)
    (src / "generated.py").write_text("# auto-generated code v2")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "update"], cwd=tmp_path, capture_output=True)

    # Create config and links with ignore=true
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.docsync]\nrequire_links = ["src/**/*.py"]\n')

    docsync = tmp_path / ".docsync"
    docsync.mkdir()
    (docsync / "links.toml").write_text(
        '[[link]]\ncode = "src/generated.py"\ndocs = ["docs/api.md#Generated"]\nignore = true\n'
    )

    # Run list-stale - should skip the ignored link
    from docsync.cli import cmd_list_stale

    exit_code = cmd_list_stale(
        Namespace(format="json", show_diff=False, diff_lines=30, changed_files=None)
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    # Should have 0 stale items (the link is ignored)
    assert len(data["stale"]) == 0
    assert data.get("skipped_ignored", 0) == 1


def test_check_skips_reviewed_items(tmp_path, monkeypatch, capsys):
    """Test that check command skips reviewed items."""
    monkeypatch.chdir(tmp_path)

    # Create git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create code file
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("def login(): pass")

    # Create doc file
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api.md").write_text("# API\n\n## Authentication\n\nDocs here")

    # Commit
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    # Modify code
    (src / "auth.py").write_text("def login(): pass\ndef logout(): pass")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add logout"], cwd=tmp_path, capture_output=True)

    # Get current commit
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    current_commit = result.stdout.strip()[:7]

    # Create config and links
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.docsync]\nrequire_links = ["src/**/*.py"]\nmode = "block"\n')

    docsync = tmp_path / ".docsync"
    docsync.mkdir()
    (docsync / "links.toml").write_text(
        '[[link]]\ncode = "src/auth.py"\ndocs = ["docs/api.md#Authentication"]\n'
    )

    # Mark as reviewed
    save_review(
        tmp_path,
        Review(
            code_file="src/auth.py",
            doc_target="docs/api.md#Authentication",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review=current_commit,
        ),
    )

    # Stage the code file to simulate pre-commit
    subprocess.run(["git", "add", "src/auth.py"], cwd=tmp_path, capture_output=True)

    # Run check - should skip the reviewed item
    from docsync.cli import cmd_check

    result = cmd_check(
        Namespace(
            staged_files="src/auth.py",
            format="json",
            show_diff=False,
            diff_lines=30,
        )
    )

    captured = capsys.readouterr()
    data = json.loads(captured.out)

    # Should return 0 (no issues) and report skipped
    assert result == 0
    assert len(data["stale"]) == 0
    assert data.get("skipped_reviewed", 0) == 1


def test_cmd_fix_interactive_mark_reviewed(tmp_path, monkeypatch, capsys):
    """Test interactive fix with 'm' (mark reviewed) action."""
    monkeypatch.chdir(tmp_path)

    # Create git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create code file
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("def login(): pass")

    # Create doc file
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api.md").write_text("# API\n\n## Authentication\n\nDocs here")

    # Commit
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    # Modify code (makes doc stale)
    (src / "auth.py").write_text("def login(): pass\ndef logout(): pass")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add logout"], cwd=tmp_path, capture_output=True)

    # Create config and links
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.docsync]\nrequire_links = ["src/**/*.py"]\n')

    docsync = tmp_path / ".docsync"
    docsync.mkdir()
    (docsync / "links.toml").write_text(
        '[[link]]\ncode = "src/auth.py"\ndocs = ["docs/api.md#Authentication"]\n'
    )

    # Mock stdin to simulate user pressing 'm' (mark reviewed) and TTY check
    from docsync.cli import cmd_fix_interactive

    with patch("builtins.input", return_value="m"), patch("sys.stdin.isatty", return_value=True):
        result = cmd_fix_interactive(Namespace())

    assert result == 0

    # Verify review was created
    reviews = load_reviews(tmp_path)
    assert len(reviews) == 1
    assert reviews[0].code_file == "src/auth.py"


def test_cmd_fix_interactive_skip(tmp_path, monkeypatch, capsys):
    """Test interactive fix with 's' (skip) action."""
    monkeypatch.chdir(tmp_path)

    # Create git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create code file
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("def login(): pass")

    # Create doc file
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api.md").write_text("# API\n\n## Authentication\n\nDocs here")

    # Commit
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    # Modify code
    (src / "auth.py").write_text("def login(): pass\ndef logout(): pass")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add logout"], cwd=tmp_path, capture_output=True)

    # Create config and links
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.docsync]\nrequire_links = ["src/**/*.py"]\n')

    docsync = tmp_path / ".docsync"
    docsync.mkdir()
    (docsync / "links.toml").write_text(
        '[[link]]\ncode = "src/auth.py"\ndocs = ["docs/api.md#Authentication"]\n'
    )

    # Mock stdin to simulate user pressing 's' (skip) and TTY check
    from docsync.cli import cmd_fix_interactive

    with patch("builtins.input", return_value="s"), patch("sys.stdin.isatty", return_value=True):
        result = cmd_fix_interactive(Namespace())

    assert result == 0

    # No review should be created
    assert len(load_reviews(tmp_path)) == 0


def test_cmd_fix_interactive_ignore(tmp_path, monkeypatch):
    """Test interactive fix with 'i' (ignore) action."""
    monkeypatch.chdir(tmp_path)

    # Create git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create code file
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("def login(): pass")

    # Create doc file
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api.md").write_text("# API\n\n## Authentication\n\nDocs here")

    # Commit
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    # Modify code
    (src / "auth.py").write_text("def login(): pass\ndef logout(): pass")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add logout"], cwd=tmp_path, capture_output=True)

    # Create config and links
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.docsync]\nrequire_links = ["src/**/*.py"]\n')

    docsync = tmp_path / ".docsync"
    docsync.mkdir()
    (docsync / "links.toml").write_text(
        '[[link]]\ncode = "src/auth.py"\ndocs = ["docs/api.md#Authentication"]\n'
    )

    # Mock stdin to simulate user pressing 'i' (ignore) and TTY check
    from docsync.cli import cmd_fix_interactive

    with patch("builtins.input", return_value="i"), patch("sys.stdin.isatty", return_value=True):
        result = cmd_fix_interactive(Namespace())

    assert result == 0

    # Link should now have ignore=true
    links = load_links(tmp_path)
    assert len(links) == 1
    assert links[0].ignore is True


def test_list_stale_partial_review_multi_doc_link(tmp_path, monkeypatch, capsys):
    """Test that reviewing one doc in a multi-doc link only skips that specific doc."""
    monkeypatch.chdir(tmp_path)

    # Create git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create code file
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("def login(): pass")

    # Create doc file with two sections
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api.md").write_text("# API\n\n## Login\n\nLogin docs\n\n## Logout\n\nLogout docs")

    # Commit
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    # Modify code (makes both docs stale)
    (src / "auth.py").write_text("def login(): pass\ndef logout(): pass")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add logout"], cwd=tmp_path, capture_output=True)

    # Get current commit
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    current_commit = result.stdout.strip()[:7]

    # Create config and links (one code file to TWO doc sections)
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.docsync]\nrequire_links = ["src/**/*.py"]\n')

    docsync = tmp_path / ".docsync"
    docsync.mkdir()
    (docsync / "links.toml").write_text(
        '[[link]]\ncode = "src/auth.py"\ndocs = ["docs/api.md#Login", "docs/api.md#Logout"]\n'
    )

    # Mark only Login as reviewed
    save_review(
        tmp_path,
        Review(
            code_file="src/auth.py",
            doc_target="docs/api.md#Login",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review=current_commit,
        ),
    )

    # Run list-stale - should still show Logout as stale but skip Login
    from docsync.cli import cmd_list_stale

    cmd_list_stale(Namespace(format="json", show_diff=False, diff_lines=30, changed_files=None))

    captured = capsys.readouterr()
    data = json.loads(captured.out)

    # Should have 1 stale (Logout) and 1 reviewed skipped (Login)
    assert len(data["stale"]) == 1
    # doc_target in JSON is a dict with file and section
    stale_doc = data["stale"][0]["doc_target"]
    assert stale_doc["file"] == "docs/api.md"
    assert stale_doc["section"] == "Logout"
    assert data.get("skipped_reviewed", 0) == 1


def test_cmd_fix_mark_reviewed_validates_file_exists(tmp_path, monkeypatch, capsys):
    """Test that fix mark-reviewed validates the code file exists."""
    monkeypatch.chdir(tmp_path)

    # Create git repo but NO code file
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    from docsync.cli import cmd_fix_mark_reviewed

    result = cmd_fix_mark_reviewed(
        Namespace(
            code="src/nonexistent.py",
            doc="docs/api.md",
            reviewed_by="user",
            format="text",
        )
    )

    # Should fail because file doesn't exist
    assert result == 1
    captured = capsys.readouterr()
    assert "Code file not found" in captured.out


def test_cmd_fix_mark_reviewed_normalizes_paths(tmp_path, monkeypatch):
    """Test that fix mark-reviewed normalizes paths properly."""
    monkeypatch.chdir(tmp_path)

    # Create git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create code file
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("def login(): pass")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    from docsync.cli import cmd_fix_mark_reviewed

    # Use ./prefix in paths
    result = cmd_fix_mark_reviewed(
        Namespace(
            code="./src/auth.py",
            doc="./docs/api.md",
            reviewed_by="user",
            format="text",
        )
    )

    assert result == 0

    # Review should be stored with normalized paths
    reviews = load_reviews(tmp_path)
    assert len(reviews) == 1
    assert reviews[0].code_file == "src/auth.py"
    assert reviews[0].doc_target == "docs/api.md"


def test_cmd_fix_interactive_fails_on_non_tty(tmp_path, monkeypatch, capsys):
    """Test that fix interactive fails gracefully when stdin is not a TTY."""
    monkeypatch.chdir(tmp_path)

    # Create config
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.docsync]\nrequire_links = ["src/**/*.py"]\n')

    docsync = tmp_path / ".docsync"
    docsync.mkdir()
    (docsync / "links.toml").write_text("")

    # Mock stdin.isatty() to return False using monkeypatch
    import sys

    from docsync.cli import cmd_fix_interactive

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    result = cmd_fix_interactive(Namespace())

    assert result == 1
    captured = capsys.readouterr()
    assert "requires a terminal" in captured.out
    assert "fix-mark-reviewed" in captured.out  # Should suggest alternatives
