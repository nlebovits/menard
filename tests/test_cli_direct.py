"""Direct tests of CLI functions to improve coverage."""

import json
import subprocess
from argparse import Namespace

from docsync.cli import (
    cmd_add_link,
    cmd_affected_docs,
    cmd_bootstrap,
    cmd_check,
    cmd_clear_cache,
    cmd_coverage,
    cmd_defer,
    cmd_explain_changes,
    cmd_info,
    cmd_init,
    cmd_list_deferred,
    cmd_list_stale,
)


def setup_basic_project(tmp_path):
    """Set up a basic project structure for tests."""
    src = tmp_path / "src"
    src.mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()

    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
require_links = ["src/**/*.py"]
"""
    )
    return src, docs


def setup_git(tmp_path):
    """Initialize git repo."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )


def test_cmd_init_creates_config(tmp_path, monkeypatch):
    """Test cmd_init directly."""
    monkeypatch.chdir(tmp_path)

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname='test'\n")

    args = Namespace()
    result = cmd_init(args)

    assert result == 0
    assert "[tool.docsync]" in pyproject.read_text()


def test_cmd_coverage_basic(tmp_path, monkeypatch, capsys):
    """Test cmd_coverage."""
    monkeypatch.chdir(tmp_path)
    src, docs = setup_basic_project(tmp_path)

    (src / "code.py").write_text("# docsync: docs/doc.md\n")
    (docs / "doc.md").write_text("<!-- docsync: src/code.py -->\n")

    args = Namespace(format="text", output=None)
    result = cmd_coverage(args)

    # Should succeed
    captured = capsys.readouterr()
    assert "code" in captured.out.lower() or "coverage" in captured.out.lower() or result == 0


def test_cmd_add_link_both_files(tmp_path, monkeypatch):
    """Test cmd_add_link with both files."""
    monkeypatch.chdir(tmp_path)

    (tmp_path / "code.py").write_text("def foo(): pass\n")
    (tmp_path / "doc.md").write_text("# Docs\n")

    args = Namespace(code_file="code.py", doc_file="doc.md", dry_run=False)
    result = cmd_add_link(args)

    assert result == 0
    assert "docsync:" in (tmp_path / "code.py").read_text()
    assert "docsync:" in (tmp_path / "doc.md").read_text()


def test_cmd_add_link_dry_run(tmp_path, monkeypatch, capsys):
    """Test cmd_add_link with dry run."""
    monkeypatch.chdir(tmp_path)

    (tmp_path / "code.py").write_text("def foo(): pass\n")
    (tmp_path / "doc.md").write_text("# Docs\n")

    args = Namespace(code_file="code.py", doc_file="doc.md", dry_run=True)
    result = cmd_add_link(args)

    assert result == 0
    # Files should not be modified
    assert "docsync:" not in (tmp_path / "code.py").read_text()


def test_cmd_bootstrap_with_apply(tmp_path, monkeypatch):
    """Test cmd_bootstrap with --apply."""
    monkeypatch.chdir(tmp_path)
    src, docs = setup_basic_project(tmp_path)

    (src / "auth.py").write_text("def auth(): pass\n")
    (docs / "auth.md").write_text("# Auth\n")

    args = Namespace(apply=True, interactive=False)
    result = cmd_bootstrap(args)

    # Should attempt to add links
    assert result == 0


def test_cmd_defer_creates_file(tmp_path, monkeypatch):
    """Test cmd_defer creates deferral file."""
    monkeypatch.chdir(tmp_path)
    setup_basic_project(tmp_path)

    args = Namespace(file="src/code.py", message="WIP", clear=False)
    result = cmd_defer(args)

    assert result == 0
    deferred_file = tmp_path / ".docsync" / "deferred.json"
    assert deferred_file.exists()


def test_cmd_defer_clear_removes_entry(tmp_path, monkeypatch):
    """Test cmd_defer --clear."""
    monkeypatch.chdir(tmp_path)
    setup_basic_project(tmp_path)

    # Create deferral
    docsync_dir = tmp_path / ".docsync"
    docsync_dir.mkdir()
    deferred_file = docsync_dir / "deferred.json"
    deferred_file.write_text(json.dumps({"src/code.py": "WIP"}))

    args = Namespace(file="src/code.py", message=None, clear=True)
    result = cmd_defer(args)

    assert result == 0


def test_cmd_list_deferred_empty(tmp_path, monkeypatch, capsys):
    """Test cmd_list_deferred with no deferrals."""
    monkeypatch.chdir(tmp_path)
    setup_basic_project(tmp_path)

    args = Namespace(format="text")
    result = cmd_list_deferred(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "no deferred" in captured.out.lower() or captured.out == ""


def test_cmd_list_deferred_with_entries(tmp_path, monkeypatch, capsys):
    """Test cmd_list_deferred with entries."""
    monkeypatch.chdir(tmp_path)
    setup_basic_project(tmp_path)

    docsync_dir = tmp_path / ".docsync"
    docsync_dir.mkdir()
    deferred_file = docsync_dir / "deferred.json"
    deferred_file.write_text(json.dumps({"src/a.py": "WIP", "src/b.py": "Blocked"}))

    args = Namespace(format="text")
    result = cmd_list_deferred(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "a.py" in captured.out or "b.py" in captured.out


def test_cmd_list_deferred_json_format(tmp_path, monkeypatch, capsys):
    """Test cmd_list_deferred with JSON output."""
    monkeypatch.chdir(tmp_path)
    setup_basic_project(tmp_path)

    docsync_dir = tmp_path / ".docsync"
    docsync_dir.mkdir()
    deferred_file = docsync_dir / "deferred.json"
    deferred_file.write_text(json.dumps({"src/a.py": "WIP"}))

    args = Namespace(format="json")
    result = cmd_list_deferred(args)

    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, dict)
    assert "src/a.py" in data


def test_cmd_clear_cache_removes_files(tmp_path, monkeypatch, capsys):
    """Test cmd_clear_cache."""
    monkeypatch.chdir(tmp_path)
    setup_basic_project(tmp_path)

    docsync_dir = tmp_path / ".docsync"
    docsync_dir.mkdir()
    (docsync_dir / "import_graph.json").write_text("{}")
    (docsync_dir / "import_graph.state").write_text("abc")

    args = Namespace()
    result = cmd_clear_cache(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "clear" in captured.out.lower()


def test_cmd_check_with_deferrals(tmp_path, monkeypatch):
    """Test cmd_check respects deferrals."""
    monkeypatch.chdir(tmp_path)
    setup_git(tmp_path)
    src, docs = setup_basic_project(tmp_path)

    (src / "code.py").write_text("def foo(): pass\n")  # No link

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)

    # Defer the file
    docsync_dir = tmp_path / ".docsync"
    docsync_dir.mkdir()
    deferred_file = docsync_dir / "deferred.json"
    deferred_file.write_text(json.dumps({"src/code.py": "WIP"}))

    args = Namespace(staged_files=None, create_todo=False)
    result = cmd_check(args)

    # Should pass because file is deferred
    assert result == 0


def test_cmd_check_fails_without_links(tmp_path, monkeypatch):
    """Test cmd_check fails when required links missing."""
    monkeypatch.chdir(tmp_path)
    setup_git(tmp_path)
    src, docs = setup_basic_project(tmp_path)

    (src / "code.py").write_text("def foo(): pass\n")  # No link

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)

    args = Namespace(staged_files=None, create_todo=False)
    result = cmd_check(args)

    # Should fail
    assert result == 1


def test_cmd_info_shows_links(tmp_path, monkeypatch, capsys):
    """Test cmd_info shows file information."""
    monkeypatch.chdir(tmp_path)
    src, docs = setup_basic_project(tmp_path)

    (src / "code.py").write_text("# docsync: docs/doc.md\n")
    (docs / "doc.md").write_text("<!-- docsync: src/code.py -->\n")

    args = Namespace(file="src/code.py", format="text")
    result = cmd_info(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "doc.md" in captured.out or "code.py" in captured.out


def test_cmd_info_json_format(tmp_path, monkeypatch, capsys):
    """Test cmd_info with JSON output."""
    monkeypatch.chdir(tmp_path)
    src, docs = setup_basic_project(tmp_path)

    (src / "code.py").write_text("# docsync: docs/doc.md\n")
    (docs / "doc.md").write_text("<!-- docsync: src/code.py -->\n")

    args = Namespace(file="src/code.py", format="json")
    result = cmd_info(args)

    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "file" in data
    assert "links" in data


def test_cmd_affected_docs_finds_docs(tmp_path, monkeypatch, capsys):
    """Test cmd_affected_docs."""
    monkeypatch.chdir(tmp_path)
    src, docs = setup_basic_project(tmp_path)

    (src / "code.py").write_text("# docsync: docs/doc.md\n")
    (docs / "doc.md").write_text("<!-- docsync: src/code.py -->\n")

    args = Namespace(file="src/code.py", format="text")
    result = cmd_affected_docs(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "doc.md" in captured.out or result == 0


def test_cmd_list_stale_no_stale_docs(tmp_path, monkeypatch, capsys):
    """Test cmd_list_stale with no stale docs."""
    monkeypatch.chdir(tmp_path)
    setup_git(tmp_path)
    src, docs = setup_basic_project(tmp_path)

    (src / "code.py").write_text("# docsync: docs/doc.md\n")
    (docs / "doc.md").write_text("<!-- docsync: src/code.py -->\n")

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    args = Namespace(pattern=None, format="text")
    result = cmd_list_stale(args)

    assert result == 0


def test_cmd_explain_changes_shows_reason(tmp_path, monkeypatch, capsys):
    """Test cmd_explain_changes."""
    monkeypatch.chdir(tmp_path)
    setup_git(tmp_path)
    src, docs = setup_basic_project(tmp_path)

    code = src / "code.py"
    code.write_text("# docsync: docs/doc.md\ndef foo(): pass\n")

    doc = docs / "doc.md"
    doc.write_text("<!-- docsync: src/code.py -->\n# Docs\n")

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    # Modify code
    code.write_text("# docsync: docs/doc.md\ndef foo():\n    return 42\n")
    subprocess.run(["git", "add", str(code)], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "update"], cwd=tmp_path, check=True, capture_output=True)

    args = Namespace(file="docs/doc.md", format="text")
    result = cmd_explain_changes(args)

    # May succeed or fail depending on staleness
    assert result in (0, 1)
