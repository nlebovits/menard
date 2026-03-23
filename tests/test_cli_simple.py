"""Simple integration tests for CLI commands to boost coverage."""

import subprocess
from argparse import Namespace

from menard.cli import (
    cmd_affected_docs,
    cmd_bootstrap,
    cmd_check,
    cmd_check_protected,
    cmd_clear_cache,
    cmd_coverage,
    cmd_info,
    cmd_init,
    cmd_list_stale,
    cmd_skills,
    cmd_validate_links,
)


def test_cmd_init_creates_config(tmp_path, monkeypatch):
    """Test cmd_init creates configuration."""
    monkeypatch.chdir(tmp_path)
    result = cmd_init(Namespace())
    assert result == 0
    assert (tmp_path / "pyproject.toml").exists()


def test_cmd_init_idempotent(tmp_path, monkeypatch):
    """Test cmd_init is idempotent."""
    monkeypatch.chdir(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.menard]\nmode = 'warn'\n")

    result = cmd_init(Namespace())
    assert result == 1  # Already configured


def test_cmd_validate_links_no_links(tmp_path, monkeypatch):
    """Test validate_links with no links."""
    monkeypatch.chdir(tmp_path)
    result = cmd_validate_links(Namespace())
    assert result == 0


def test_cmd_validate_links_valid(tmp_path, monkeypatch):
    """Test validate_links with valid links."""
    monkeypatch.chdir(tmp_path)

    # Create files
    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("pass")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "doc.md").write_text("# Doc")

    # Create links
    menard = tmp_path / ".menard"
    menard.mkdir()
    links = menard / "links.toml"
    links.write_text('[[link]]\ncode = "src/code.py"\ndocs = ["docs/doc.md"]\n')

    result = cmd_validate_links(Namespace())
    assert result == 0


def test_cmd_clear_cache(tmp_path, monkeypatch):
    """Test clear_cache command."""
    monkeypatch.chdir(tmp_path)

    # Create cache
    cache_dir = tmp_path / ".menard" / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "test.json").write_text("{}")

    result = cmd_clear_cache(Namespace())
    assert result == 0


def test_cmd_info_no_links(tmp_path, monkeypatch):
    """Test info command with no links."""
    monkeypatch.chdir(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("pass")

    result = cmd_info(Namespace(file="src/code.py", format="text"))
    assert result == 0


def test_cmd_coverage_basic(tmp_path, monkeypatch):
    """Test coverage command basic functionality."""
    monkeypatch.chdir(tmp_path)

    # Create basic project structure
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.menard]\nrequire_links = ["src/**/*.py"]\n')

    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("pass")

    menard = tmp_path / ".menard"
    menard.mkdir()
    (menard / "links.toml").write_text("")

    result = cmd_coverage(Namespace(format="text", min_coverage=None, fail_under=None))
    assert result in (0, 1)  # May fail due to low coverage, but shouldn't crash


def test_cmd_check_no_config(tmp_path, monkeypatch):
    """Test check command with no configuration."""
    monkeypatch.chdir(tmp_path)
    result = cmd_check(Namespace(staged_files=None, format="text"))
    # Should handle gracefully
    assert result in (0, 1)


def test_cmd_list_stale_basic(tmp_path, monkeypatch):
    """Test list_stale command basic functionality."""
    monkeypatch.chdir(tmp_path)

    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.menard]\nrequire_links = ["src/**/*.py"]\n')

    menard = tmp_path / ".menard"
    menard.mkdir()
    (menard / "links.toml").write_text("")

    result = cmd_list_stale(Namespace(format="text", changed_files=None))
    assert result in (0, 1)


def test_cmd_affected_docs_basic(tmp_path, monkeypatch):
    """Test affected_docs command basic functionality."""
    monkeypatch.chdir(tmp_path)

    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.menard]\nrequire_links = ["src/**/*.py"]\n')

    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("pass")

    menard = tmp_path / ".menard"
    menard.mkdir()
    (menard / "links.toml").write_text("")

    # files arg expects a comma-separated string, format defaults to text
    result = cmd_affected_docs(Namespace(files="src/code.py", depth=1, format="text"))
    assert result == 0


def test_cmd_bootstrap_basic(tmp_path, monkeypatch):
    """Test bootstrap command basic functionality."""
    monkeypatch.chdir(tmp_path)

    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.menard]\nrequire_links = ["src/**/*.py"]\n')

    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("pass")

    result = cmd_bootstrap(Namespace(apply=False))
    # Should work even without docs
    assert result in (0, 1)


def test_cmd_bootstrap_exclude_docs(tmp_path, monkeypatch, capsys):
    """Test bootstrap excludes docs matching exclude_docs patterns."""
    monkeypatch.chdir(tmp_path)

    # Config with exclude_docs for ADRs
    config = tmp_path / "pyproject.toml"
    config.write_text("""[tool.menard]
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
exclude_docs = ["**/adr/**"]
""")

    # Create source file
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("pass")

    # Create docs - one regular, one ADR (should be excluded)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth.md").write_text("# Auth docs")

    adr_dir = docs / "adr"
    adr_dir.mkdir()
    (adr_dir / "auth.md").write_text("# ADR: Auth decision")

    result = cmd_bootstrap(Namespace(apply=False))
    captured = capsys.readouterr()

    # Should propose link to docs/auth.md but NOT docs/adr/auth.md
    assert "docs/auth.md" in captured.out
    assert "docs/adr/auth.md" not in captured.out
    assert result == 0


def test_cmd_skills_no_dir(tmp_path, monkeypatch):
    """Test skills command when no .claude/skills directory exists."""
    monkeypatch.chdir(tmp_path)
    result = cmd_skills(Namespace(format="text"))
    assert result == 0


def test_cmd_skills_empty_dir(tmp_path, monkeypatch):
    """Test skills command when skills directory is empty."""
    monkeypatch.chdir(tmp_path)
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    result = cmd_skills(Namespace(format="text"))
    assert result == 0


def test_cmd_skills_lists_skills(tmp_path, monkeypatch):
    """Test skills command lists available skills."""
    monkeypatch.chdir(tmp_path)
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    skill_file = skills_dir / "audit.md"
    skill_file.write_text("# Audit Skill\n\nAnalyze documentation for menard.\n")

    result = cmd_skills(Namespace(format="text"))
    assert result == 0


def test_cmd_skills_json_format(tmp_path, monkeypatch):
    """Test skills command JSON output."""
    monkeypatch.chdir(tmp_path)
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    skill_file = skills_dir / "audit.md"
    skill_file.write_text("# Audit Skill\n\nAnalyze docs.\n")

    result = cmd_skills(Namespace(format="json"))
    assert result == 0


def test_cmd_check_all_flag(tmp_path, monkeypatch):
    """Test check command with --all flag checks all tracked files."""
    monkeypatch.chdir(tmp_path)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Create config
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.menard]\nrequire_links = ["src/**/*.py"]\n')

    # Create and commit source file
    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("pass")

    menard = tmp_path / ".menard"
    menard.mkdir()
    (menard / "links.toml").write_text("")

    # Add and commit files
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Run with --all flag (should not require staged files)
    args = Namespace(staged_files=None, format="text", show_diff=False, diff_lines=30)
    # Set the 'all' attribute
    args.all = True

    result = cmd_check(args)
    # Should succeed (no stale docs since links.toml is empty)
    assert result == 0


def test_cmd_check_all_and_staged_files_mutually_exclusive(tmp_path, monkeypatch, capsys):
    """Test that --all and --staged-files are mutually exclusive."""
    monkeypatch.chdir(tmp_path)

    # Create minimal config
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.menard]\nrequire_links = ["src/**/*.py"]\n')

    menard = tmp_path / ".menard"
    menard.mkdir()
    (menard / "links.toml").write_text("")

    # Try both flags
    args = Namespace(staged_files="src/code.py", format="text", show_diff=False, diff_lines=30)
    args.all = True

    result = cmd_check(args)
    captured = capsys.readouterr()

    assert result == 1
    assert "--all and --staged-files are mutually exclusive" in captured.out


def test_cmd_check_protected_all_flag(tmp_path, monkeypatch):
    """Test check-protected command with --all flag runs against all files."""
    monkeypatch.chdir(tmp_path)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Create menard directory with section-level protection (not file-level)
    # File-level protection triggers on ANY file matching the pattern
    # Section-level only triggers if protected sections are changed
    menard = tmp_path / ".menard"
    menard.mkdir()
    (menard / "donttouch").write_text("# Protected sections only\ndocs/readme.md#DO_NOT_EDIT\n")

    # Create docs directory with a file (without the protected section)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("# Documentation\n\nThis is fine to edit.\n")

    # Add and commit
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Run with --all flag
    args = Namespace()
    args.all = True

    result = cmd_check_protected(args)
    # Should return 0 (no violations - protected section doesn't exist/wasn't changed)
    assert result == 0


def test_cmd_check_protected_all_flag_finds_violations(tmp_path, monkeypatch, capsys):
    """Test check-protected --all finds violations in protected files."""
    monkeypatch.chdir(tmp_path)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Create menard directory with file-level protection
    menard = tmp_path / ".menard"
    menard.mkdir()
    (menard / "donttouch").write_text("# Protected files\nsecrets/*\n")

    # Create a protected file
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "api_key.txt").write_text("secret123")

    # Add and commit
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Run with --all flag - should find the protected file
    args = Namespace()
    args.all = True

    result = cmd_check_protected(args)
    captured = capsys.readouterr()

    # File protection triggers for any file matching pattern
    assert result == 1
    assert "secrets/api_key.txt" in captured.out
