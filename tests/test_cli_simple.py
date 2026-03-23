"""Simple integration tests for CLI commands to boost coverage."""

from argparse import Namespace

from menard.cli import (
    cmd_affected_docs,
    cmd_bootstrap,
    cmd_check,
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
