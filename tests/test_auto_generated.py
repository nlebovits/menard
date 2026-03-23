"""Tests for auto_generated flag functionality."""

import json
import subprocess
from argparse import Namespace

import pytest

from menard.cli import cmd_check, cmd_list_stale
from menard.toml_links import Link, LinkTarget, load_links


@pytest.fixture
def git_repo(tmp_path):
    """Create a git repository for testing."""
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
    return tmp_path


def test_load_links_with_auto_generated(tmp_path):
    """Test that load_links correctly parses auto_generated flag."""
    menard = tmp_path / ".menard"
    menard.mkdir()

    links_file = menard / "links.toml"
    links_file.write_text("""
[[link]]
code = "src/code.py"
docs = ["docs/doc.md"]
auto_generated = true

[[link]]
code = "src/other.py"
docs = ["docs/other.md"]
""")

    links = load_links(tmp_path)

    assert len(links) == 2
    assert links[0].code == "src/code.py"
    assert links[0].auto_generated is True
    assert links[1].code == "src/other.py"
    assert links[1].auto_generated is False


def test_auto_generated_link_skips_staleness_check(git_repo, monkeypatch):
    """Test that auto_generated=true skips staleness checks."""
    monkeypatch.chdir(git_repo)

    # Create project structure
    config = git_repo / "pyproject.toml"
    config.write_text("""
[tool.menard]
mode = "warn"
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
""")

    src = git_repo / "src"
    src.mkdir()
    code_file = src / "code.py"
    code_file.write_text("def hello(): pass")

    docs = git_repo / "docs"
    docs.mkdir()
    doc_file = docs / "doc.md"
    doc_file.write_text("# Documentation")

    # Create links with auto_generated flag
    menard = git_repo / ".menard"
    menard.mkdir()
    links = menard / "links.toml"
    links.write_text("""
[[link]]
code = "src/code.py"
docs = ["docs/doc.md"]
auto_generated = true
""")

    # Commit initial state
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Modify code file
    code_file.write_text("def hello(): pass\ndef world(): pass")

    # Stage the code change
    subprocess.run(["git", "add", "src/code.py"], cwd=git_repo, check=True, capture_output=True)

    # Run check command - should skip the auto-generated doc
    result = cmd_check(Namespace(staged_files=None, format="json"))

    # Even though code changed and doc didn't, check should pass because doc is auto-generated
    assert result == 0


def test_auto_generated_count_in_json_output(git_repo, monkeypatch, capsys):
    """Test that JSON output includes skipped_auto_generated count."""
    monkeypatch.chdir(git_repo)

    # Create project structure
    config = git_repo / "pyproject.toml"
    config.write_text("""
[tool.menard]
mode = "warn"
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
""")

    src = git_repo / "src"
    src.mkdir()

    # Create two code files
    (src / "auto.py").write_text("def auto(): pass")
    (src / "manual.py").write_text("def manual(): pass")

    docs = git_repo / "docs"
    docs.mkdir()
    (docs / "auto.md").write_text("# Auto")
    (docs / "manual.md").write_text("# Manual")

    # Create links - one auto_generated, one not
    menard = git_repo / ".menard"
    menard.mkdir()
    links = menard / "links.toml"
    links.write_text("""
[[link]]
code = "src/auto.py"
docs = ["docs/auto.md"]
auto_generated = true

[[link]]
code = "src/manual.py"
docs = ["docs/manual.md"]
""")

    # Commit initial state
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Modify both code files
    (src / "auto.py").write_text("def auto(): pass\ndef auto2(): pass")
    (src / "manual.py").write_text("def manual(): pass\ndef manual2(): pass")

    # Stage both
    subprocess.run(["git", "add", "src/"], cwd=git_repo, check=True, capture_output=True)

    # Run check command in JSON mode
    cmd_check(Namespace(staged_files=None, format="json"))

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    # Should have 1 stale doc (manual.md) and 1 skipped (auto.md)
    assert output["skipped_auto_generated"] == 1
    assert len(output["stale"]) == 1
    assert output["stale"][0]["code_file"] == "src/manual.py"


def test_auto_generated_count_in_text_output(git_repo, monkeypatch, capsys):
    """Test that text output mentions skipped auto-generated docs."""
    monkeypatch.chdir(git_repo)

    # Create project structure
    config = git_repo / "pyproject.toml"
    config.write_text("""
[tool.menard]
mode = "warn"
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
""")

    src = git_repo / "src"
    src.mkdir()
    code_file = src / "code.py"
    code_file.write_text("def hello(): pass")

    docs = git_repo / "docs"
    docs.mkdir()
    doc_file = docs / "doc.md"
    doc_file.write_text("# Documentation")

    # Create links with auto_generated flag
    menard = git_repo / ".menard"
    menard.mkdir()
    links = menard / "links.toml"
    links.write_text("""
[[link]]
code = "src/code.py"
docs = ["docs/doc.md"]
auto_generated = true
""")

    # Commit initial state
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Modify code file
    code_file.write_text("def hello(): pass\ndef world(): pass")

    # Stage the code change
    subprocess.run(["git", "add", "src/code.py"], cwd=git_repo, check=True, capture_output=True)

    # Run check command in text mode
    cmd_check(Namespace(staged_files=None, format="text"))

    captured = capsys.readouterr()

    # Output should mention that auto-generated docs were skipped
    assert "auto-generated docs skipped" in captured.out or "skipped" in captured.out.lower()


def test_list_stale_skips_auto_generated(git_repo, monkeypatch, capsys):
    """Test that list-stale command also skips auto-generated docs."""
    monkeypatch.chdir(git_repo)

    # Create project structure
    config = git_repo / "pyproject.toml"
    config.write_text("""
[tool.menard]
mode = "warn"
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
""")

    src = git_repo / "src"
    src.mkdir()
    (src / "code.py").write_text("def hello(): pass")

    docs = git_repo / "docs"
    docs.mkdir()
    (docs / "doc.md").write_text("# Documentation")

    # Create links with auto_generated flag
    menard = git_repo / ".menard"
    menard.mkdir()
    links = menard / "links.toml"
    links.write_text("""
[[link]]
code = "src/code.py"
docs = ["docs/doc.md"]
auto_generated = true
""")

    # Commit initial state
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Modify code file
    (src / "code.py").write_text("def hello(): pass\ndef world(): pass")
    subprocess.run(["git", "add", "src/code.py"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add function"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Run list-stale in JSON mode
    cmd_list_stale(Namespace(format="json"))

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    # Should have 0 stale docs (because the only one is auto-generated)
    assert len(output["stale"]) == 0
    assert output["skipped_auto_generated"] == 1


def test_validation_still_runs_for_auto_generated(tmp_path):
    """Test that validation still checks auto-generated links."""
    from menard.toml_links import validate_links

    # Create the code file but not the doc file
    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("pass")

    # Create a link with auto_generated=true but invalid doc reference
    link = Link(code="src/code.py", docs=[LinkTarget.parse("docs/missing.md")], auto_generated=True)

    # Validation should still report the missing file
    errors = validate_links([link], tmp_path)

    assert len(errors) > 0
    assert "missing.md" in errors[0]


def test_multiple_links_same_code_file(git_repo, monkeypatch, capsys):
    """Test that when one code file has multiple links, only auto_generated ones are skipped."""
    monkeypatch.chdir(git_repo)

    # Create project structure
    config = git_repo / "pyproject.toml"
    config.write_text("""
[tool.menard]
mode = "warn"
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
""")

    src = git_repo / "src"
    src.mkdir()
    (src / "cli.py").write_text("def main(): pass")

    docs = git_repo / "docs"
    docs.mkdir()
    (docs / "reference.md").write_text("# CLI Reference")
    (docs / "tutorial.md").write_text("# Tutorial")

    # Create TWO links for the same code file
    # One is auto_generated, one is not
    menard = git_repo / ".menard"
    menard.mkdir()
    links = menard / "links.toml"
    links.write_text("""
[[link]]
code = "src/cli.py"
docs = ["docs/reference.md"]
auto_generated = true

[[link]]
code = "src/cli.py"
docs = ["docs/tutorial.md"]
""")

    # Commit initial state
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Modify code file
    (src / "cli.py").write_text("def main(): pass\ndef sub(): pass")

    # Stage the change
    subprocess.run(["git", "add", "src/cli.py"], cwd=git_repo, check=True, capture_output=True)

    # Run check in JSON mode
    cmd_check(Namespace(staged_files=None, format="json"))

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    # Should have 1 stale doc (tutorial.md) and 1 skipped (reference.md)
    assert output["skipped_auto_generated"] == 1, (
        f"Expected 1 skipped, got {output['skipped_auto_generated']}"
    )
    assert len(output["stale"]) == 1, f"Expected 1 stale, got {len(output['stale'])}"
    # Issue #34: doc_target is now a structured object
    assert output["stale"][0]["doc_target"]["file"] == "docs/tutorial.md"


def test_auto_generated_with_section_links(git_repo, monkeypatch, capsys):
    """Test auto_generated works correctly with section-specific links."""
    monkeypatch.chdir(git_repo)

    # Create project structure
    config = git_repo / "pyproject.toml"
    config.write_text("""
[tool.menard]
mode = "warn"
require_links = ["src/**/*.py"]
doc_paths = ["docs/**/*.md"]
""")

    src = git_repo / "src"
    src.mkdir()
    (src / "auth.py").write_text("def login(): pass")

    docs = git_repo / "docs"
    docs.mkdir()
    (docs / "api.md").write_text(
        "# API\n\n## Authentication\n\nAuth docs here.\n\n## Other\n\nOther docs."
    )

    # Link to section, mark as auto_generated
    menard = git_repo / ".menard"
    menard.mkdir()
    links = menard / "links.toml"
    links.write_text("""
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]
auto_generated = true
""")

    # Commit initial state
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    # Modify code
    (src / "auth.py").write_text("def login(): pass\ndef logout(): pass")
    subprocess.run(["git", "add", "src/auth.py"], cwd=git_repo, check=True, capture_output=True)

    # Run check in JSON mode
    cmd_check(Namespace(staged_files=None, format="json"))

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    # Section link should be skipped
    assert output["skipped_auto_generated"] == 1
    assert len(output["stale"]) == 0
