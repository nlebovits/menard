"""Tests for protected content guard."""

import os
import subprocess
from contextlib import contextmanager

from menard.donttouch import Violation, check_protections, load_donttouch

# Git variables that leak from pre-commit hooks and cause test isolation issues
_GIT_ENV_VARS = {
    "GIT_INDEX_FILE",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_AUTHOR_DATE",
    "GIT_COMMITTER_DATE",
}


def _clean_git_env() -> dict:
    """Return a clean environment without git variables that leak from pre-commit hooks.

    Pre-commit hooks set GIT_INDEX_FILE and other variables that cause
    subprocess git operations to use the wrong index when creating isolated
    test repos.
    """
    return {k: v for k, v in os.environ.items() if k not in _GIT_ENV_VARS}


@contextmanager
def _isolated_git_env():
    """Context manager that temporarily removes git env vars from os.environ.

    Use this when calling functions that internally run git commands
    and need isolation from the pre-commit hook environment.
    """
    saved = {k: os.environ.pop(k) for k in _GIT_ENV_VARS if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


def test_load_donttouch_missing_file(tmp_path):
    """Should return None if .menard/donttouch doesn't exist."""
    result = load_donttouch(tmp_path)
    assert result is None


def test_load_donttouch_file_patterns(tmp_path):
    """Should parse file patterns."""
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text("LICENSE\n*.lock\n")

    rules = load_donttouch(tmp_path)
    assert rules is not None
    assert rules.file_patterns.match_file("LICENSE")
    assert rules.file_patterns.match_file("package.lock")


def test_load_donttouch_section_protection(tmp_path):
    """Should parse section protections."""
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text("README.md#License\nREADME.md#Contributing\n")

    rules = load_donttouch(tmp_path)
    assert rules is not None
    assert "README.md" in rules.section_protections
    assert "License" in rules.section_protections["README.md"]
    assert "Contributing" in rules.section_protections["README.md"]


def test_load_donttouch_scoped_literals(tmp_path):
    """Should parse file-scoped literals."""
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text('pyproject.toml: "Apache-2.0"\n')

    rules = load_donttouch(tmp_path)
    assert rules is not None
    assert "pyproject.toml" in rules.scoped_literals
    assert "Apache-2.0" in rules.scoped_literals["pyproject.toml"]


def test_load_donttouch_global_literals(tmp_path):
    """Should parse global literals."""
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text('"Apache 2.0 - see LICENSE for details"\n')

    rules = load_donttouch(tmp_path)
    assert rules is not None
    assert "Apache 2.0 - see LICENSE for details" in rules.global_literals


def test_check_file_protection(tmp_path):
    """Should detect protected file modifications."""
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text("LICENSE\n*.lock\n")

    rules = load_donttouch(tmp_path)
    assert rules is not None
    violations = check_protections(tmp_path, ["LICENSE", "package.lock"], rules)

    assert len(violations) == 2
    assert violations[0].type == "protected_file"
    assert violations[0].file == "LICENSE"
    assert violations[1].file == "package.lock"


def test_check_section_protection(tmp_path):
    """Should detect protected section modifications."""
    # Use clean env to avoid pre-commit hook variable leaks
    env = _clean_git_env()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )

    # Create README with License section
    readme = tmp_path / "README.md"
    readme.write_text("# Project\n\n## License\n\nApache-2.0 License\n")
    subprocess.run(
        ["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True, env=env
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={**env, "PRE_COMMIT_ALLOW_NO_CONFIG": "1"},
    )

    # Modify License section
    readme.write_text("# Project\n\n## License\n\nApache License\n")
    subprocess.run(
        ["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True, env=env
    )

    # Create protection rule
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text("README.md#License\n")

    rules = load_donttouch(tmp_path)
    assert rules is not None

    # Use isolated env so check_protections' git commands use the temp repo's index
    with _isolated_git_env():
        violations = check_protections(tmp_path, ["README.md"], rules)

    assert len(violations) == 1
    assert violations[0].type == "protected_section"
    assert violations[0].file == "README.md"
    assert violations[0].section == "License"


def test_check_scoped_literal_protection(tmp_path):
    """Should detect removal of file-scoped literals."""
    # Use clean env to avoid pre-commit hook variable leaks
    env = _clean_git_env()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )

    # Create file with literal
    config = tmp_path / "pyproject.toml"
    config.write_text('license = "Apache-2.0"\n')
    subprocess.run(
        ["git", "add", "pyproject.toml"], cwd=tmp_path, check=True, capture_output=True, env=env
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={**env, "PRE_COMMIT_ALLOW_NO_CONFIG": "1"},
    )

    # Remove literal
    config.write_text("# No license field\n")
    subprocess.run(
        ["git", "add", "pyproject.toml"], cwd=tmp_path, check=True, capture_output=True, env=env
    )

    # Create protection rule
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text('pyproject.toml: "Apache-2.0"\n')

    rules = load_donttouch(tmp_path)
    assert rules is not None

    # Use isolated env so check_protections' git commands use the temp repo's index
    with _isolated_git_env():
        violations = check_protections(tmp_path, ["pyproject.toml"], rules)

    assert len(violations) == 1
    assert violations[0].type == "protected_literal"
    assert violations[0].literal == "Apache-2.0"


def test_check_global_literal_protection(tmp_path):
    """Should detect removal of global literals."""
    # Use clean env to avoid pre-commit hook variable leaks
    env = _clean_git_env()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )

    # Create file with global literal
    readme = tmp_path / "README.md"
    readme.write_text("Apache 2.0 - see LICENSE for details\n")
    subprocess.run(
        ["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True, env=env
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={**env, "PRE_COMMIT_ALLOW_NO_CONFIG": "1"},
    )

    # Remove literal
    readme.write_text("Apache-2.0 - see LICENSE\n")
    subprocess.run(
        ["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True, env=env
    )

    # Create protection rule
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text('"Apache 2.0 - see LICENSE for details"\n')

    rules = load_donttouch(tmp_path)
    assert rules is not None

    # Use isolated env so check_protections' git commands use the temp repo's index
    with _isolated_git_env():
        violations = check_protections(tmp_path, ["README.md"], rules)

    assert len(violations) == 1
    assert violations[0].type == "protected_literal"
    assert violations[0].literal == "Apache 2.0 - see LICENSE for details"


def test_violation_to_dict():
    """Should convert Violation to dictionary."""
    v = Violation(type="protected_file", file="LICENSE", reason="File is protected")
    assert v.to_dict() == {
        "type": "protected_file",
        "file": "LICENSE",
        "reason": "File is protected",
    }

    v2 = Violation(
        type="protected_section",
        file="README.md",
        section="License",
        reason="Section is protected",
    )
    assert v2.to_dict() == {
        "type": "protected_section",
        "file": "README.md",
        "section": "License",
        "reason": "Section is protected",
    }


def test_whitespace_normalization(tmp_path):
    """Should normalize whitespace in literal comparison."""
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text('README.md: "Apache 2.0 License"\n')

    # Use clean env to avoid pre-commit hook variable leaks
    env = _clean_git_env()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )

    # Create README with normal whitespace
    readme = tmp_path / "README.md"
    readme.write_text("Apache 2.0 License\n")
    subprocess.run(
        ["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True, env=env
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial", "--no-verify"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )

    # Modify with extra whitespace (should still be protected due to normalization)
    readme.write_text("Apache  2.0  License\n")  # Double spaces
    subprocess.run(
        ["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True, env=env
    )

    rules = load_donttouch(tmp_path)
    assert rules is not None
    # Should NOT violate because whitespace is normalized
    violations = check_protections(tmp_path, ["README.md"], rules)
    assert len(violations) == 0


def test_path_traversal_rejection(tmp_path, capsys):
    """Should reject path traversal attempts."""
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text("../../etc/passwd\n../../../secrets\n/etc/shadow\n")

    rules = load_donttouch(tmp_path)
    assert rules is not None
    captured = capsys.readouterr()

    # Should have warnings
    assert "path traversal" in captured.err
    # Should not add any patterns
    assert len(rules.file_pattern_strings) == 0


def test_line_length_limit(tmp_path, capsys):
    """Should reject lines exceeding MAX_LINE_LENGTH."""
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)

    # Create a line that's too long
    long_line = "A" * 20000  # 20KB
    donttouch.write_text(f"{long_line}\nLICENSE\n")

    rules = load_donttouch(tmp_path)
    assert rules is not None
    captured = capsys.readouterr()

    # Should have warning about long line
    assert "line too long" in captured.err
    # Should still process valid lines
    assert "LICENSE" in rules.file_pattern_strings


def test_parse_error_handling(tmp_path, capsys):
    """Should handle file read errors gracefully."""
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)

    # Create file with invalid UTF-8
    donttouch.write_bytes(b"LICENSE\n\xff\xfe\nREADME.md\n")

    rules = load_donttouch(tmp_path)
    captured = capsys.readouterr()

    # Should return None and print error
    assert rules is None
    assert "invalid UTF-8" in captured.err


def test_empty_literal_rejection(tmp_path):
    """Should reject empty literals."""
    donttouch = tmp_path / ".menard" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text('""')

    rules = load_donttouch(tmp_path)
    assert rules is not None
    assert len(rules.global_literals) == 0
