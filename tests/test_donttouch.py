"""Tests for protected content guard."""

import subprocess
from pathlib import Path

from docsync.donttouch import Violation, check_protections, load_donttouch


def test_load_donttouch_missing_file(tmp_path):
    """Should return None if .docsync/donttouch doesn't exist."""
    result = load_donttouch(tmp_path)
    assert result is None


def test_load_donttouch_file_patterns(tmp_path):
    """Should parse file patterns."""
    donttouch = tmp_path / ".docsync" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text("LICENSE\n*.lock\n")

    rules = load_donttouch(tmp_path)
    assert rules is not None
    assert rules.file_patterns.match_file("LICENSE")
    assert rules.file_patterns.match_file("package.lock")


def test_load_donttouch_section_protection(tmp_path):
    """Should parse section protections."""
    donttouch = tmp_path / ".docsync" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text("README.md#License\nREADME.md#Contributing\n")

    rules = load_donttouch(tmp_path)
    assert rules is not None
    assert "README.md" in rules.section_protections
    assert "License" in rules.section_protections["README.md"]
    assert "Contributing" in rules.section_protections["README.md"]


def test_load_donttouch_scoped_literals(tmp_path):
    """Should parse file-scoped literals."""
    donttouch = tmp_path / ".docsync" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text('pyproject.toml: "Apache-2.0"\n')

    rules = load_donttouch(tmp_path)
    assert rules is not None
    assert "pyproject.toml" in rules.scoped_literals
    assert "Apache-2.0" in rules.scoped_literals["pyproject.toml"]


def test_load_donttouch_global_literals(tmp_path):
    """Should parse global literals."""
    donttouch = tmp_path / ".docsync" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text('"Apache 2.0 - see LICENSE for details"\n')

    rules = load_donttouch(tmp_path)
    assert rules is not None
    assert "Apache 2.0 - see LICENSE for details" in rules.global_literals


def test_check_file_protection(tmp_path):
    """Should detect protected file modifications."""
    donttouch = tmp_path / ".docsync" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text("LICENSE\n*.lock\n")

    rules = load_donttouch(tmp_path)
    violations = check_protections(tmp_path, ["LICENSE", "package.lock"], rules)

    assert len(violations) == 2
    assert violations[0].type == "protected_file"
    assert violations[0].file == "LICENSE"
    assert violations[1].file == "package.lock"


def test_check_section_protection(tmp_path):
    """Should detect protected section modifications."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create README with License section
    readme = tmp_path / "README.md"
    readme.write_text("# Project\n\n## License\n\nMIT License\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={"PRE_COMMIT_ALLOW_NO_CONFIG": "1", **subprocess.os.environ},
    )

    # Modify License section
    readme.write_text("# Project\n\n## License\n\nApache License\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)

    # Create protection rule
    donttouch = tmp_path / ".docsync" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text("README.md#License\n")

    rules = load_donttouch(tmp_path)
    violations = check_protections(tmp_path, ["README.md"], rules)

    assert len(violations) == 1
    assert violations[0].type == "protected_section"
    assert violations[0].file == "README.md"
    assert violations[0].section == "License"


def test_check_scoped_literal_protection(tmp_path):
    """Should detect removal of file-scoped literals."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create file with literal
    config = tmp_path / "pyproject.toml"
    config.write_text('license = "Apache-2.0"\n')
    subprocess.run(
        ["git", "add", "pyproject.toml"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={"PRE_COMMIT_ALLOW_NO_CONFIG": "1", **subprocess.os.environ},
    )

    # Remove literal
    config.write_text('license = "MIT"\n')
    subprocess.run(
        ["git", "add", "pyproject.toml"], cwd=tmp_path, check=True, capture_output=True
    )

    # Create protection rule
    donttouch = tmp_path / ".docsync" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text('pyproject.toml: "Apache-2.0"\n')

    rules = load_donttouch(tmp_path)
    violations = check_protections(tmp_path, ["pyproject.toml"], rules)

    assert len(violations) == 1
    assert violations[0].type == "protected_literal"
    assert violations[0].literal == "Apache-2.0"


def test_check_global_literal_protection(tmp_path):
    """Should detect removal of global literals."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create file with global literal
    readme = tmp_path / "README.md"
    readme.write_text("Apache 2.0 - see LICENSE for details\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={"PRE_COMMIT_ALLOW_NO_CONFIG": "1", **subprocess.os.environ},
    )

    # Remove literal
    readme.write_text("MIT - see LICENSE\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)

    # Create protection rule
    donttouch = tmp_path / ".docsync" / "donttouch"
    donttouch.parent.mkdir(parents=True)
    donttouch.write_text('"Apache 2.0 - see LICENSE for details"\n')

    rules = load_donttouch(tmp_path)
    violations = check_protections(tmp_path, ["README.md"], rules)

    assert len(violations) == 1
    assert violations[0].type == "protected_literal"
    assert violations[0].literal == "Apache 2.0 - see LICENSE for details"


def test_violation_to_dict():
    """Should convert Violation to dictionary."""
    v = Violation(
        type="protected_file", file="LICENSE", reason="File is protected"
    )
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
