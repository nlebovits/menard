"""Tests for TOML link file parsing and validation."""

import tempfile
from pathlib import Path

import pytest

from menard.toml_links import (
    Link,
    LinkTarget,
    build_graph_from_links,
    generate_links_toml,
    load_links,
    validate_links,
)


def test_link_target_parse_whole_file():
    """Test parsing a whole-file doc target."""
    target = LinkTarget.parse("docs/api.md")
    assert target.file == "docs/api.md"
    assert target.section is None
    assert str(target) == "docs/api.md"


def test_link_target_parse_section():
    """Test parsing a section-specific doc target."""
    target = LinkTarget.parse("docs/api.md#Authentication")
    assert target.file == "docs/api.md"
    assert target.section == "Authentication"
    assert str(target) == "docs/api.md#Authentication"


def test_load_links_empty():
    """Test loading links when file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        links = load_links(repo_root)
        assert links == []


def test_load_links_valid():
    """Test loading a valid links.toml file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        menard_dir = repo_root / ".menard"
        menard_dir.mkdir()

        links_file = menard_dir / "links.toml"
        links_file.write_text(
            """
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]

[[link]]
code = "src/models/user.py"
docs = ["docs/models.md#User Model", "docs/api.md#User Endpoints"]
"""
        )

        links = load_links(repo_root)
        assert len(links) == 2

        # First link
        assert links[0].code == "src/auth.py"
        assert len(links[0].docs) == 1
        assert links[0].docs[0].file == "docs/api.md"
        assert links[0].docs[0].section is None

        # Second link
        assert links[1].code == "src/models/user.py"
        assert len(links[1].docs) == 2
        assert links[1].docs[0].section == "User Model"
        assert links[1].docs[1].section == "User Endpoints"


def test_load_links_invalid_toml():
    """Test loading an invalid TOML file raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        menard_dir = repo_root / ".menard"
        menard_dir.mkdir()

        links_file = menard_dir / "links.toml"
        links_file.write_text("invalid toml [[[")

        with pytest.raises(ValueError, match="Failed to parse"):
            load_links(repo_root)


def test_validate_links_all_valid():
    """Test validating links when all files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create files
        (repo_root / "src").mkdir()
        (repo_root / "src" / "auth.py").write_text("# code")
        (repo_root / "docs").mkdir()
        (repo_root / "docs" / "api.md").write_text("## Authentication\n\nAuth docs")

        links = [
            Link(
                code="src/auth.py",
                docs=[LinkTarget(file="docs/api.md", section="Authentication")],
            )
        ]

        errors = validate_links(links, repo_root)
        assert errors == []


def test_validate_links_missing_code_file():
    """Test validation fails when code file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create the doc file (so we only get code file error)
        (repo_root / "docs").mkdir()
        (repo_root / "docs" / "api.md").write_text("# API")

        links = [Link(code="src/missing.py", docs=[LinkTarget(file="docs/api.md")])]

        errors = validate_links(links, repo_root)
        assert len(errors) == 1
        assert "Code file not found" in errors[0]
        assert "src/missing.py" in errors[0]


def test_validate_links_missing_doc_file():
    """Test validation fails when doc file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        (repo_root / "src").mkdir()
        (repo_root / "src" / "auth.py").write_text("# code")

        links = [Link(code="src/auth.py", docs=[LinkTarget(file="docs/missing.md")])]

        errors = validate_links(links, repo_root)
        assert len(errors) == 1
        assert "Doc file not found" in errors[0]


def test_validate_links_missing_section():
    """Test validation fails when section doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        (repo_root / "src").mkdir()
        (repo_root / "src" / "auth.py").write_text("# code")
        (repo_root / "docs").mkdir()
        (repo_root / "docs" / "api.md").write_text("## Other Section\n\nDocs")

        links = [
            Link(
                code="src/auth.py",
                docs=[LinkTarget(file="docs/api.md", section="Missing Section")],
            )
        ]

        errors = validate_links(links, repo_root)
        assert len(errors) == 1
        assert "Section 'Missing Section' not found" in errors[0]


def test_build_graph_from_links():
    """Test building bidirectional graph from links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        links = [
            Link(code="src/auth.py", docs=[LinkTarget(file="docs/api.md")]),
            Link(
                code="src/models/user.py",
                docs=[LinkTarget(file="docs/models.md", section="User Model")],
            ),
        ]

        graph = build_graph_from_links(links, repo_root)

        # Check bidirectional links
        assert "docs/api.md" in graph["src/auth.py"]
        assert "src/auth.py" in graph["docs/api.md"]

        assert "docs/models.md#User Model" in graph["src/models/user.py"]
        assert "src/models/user.py" in graph["docs/models.md#User Model"]


def test_generate_links_toml():
    """Test generating TOML content from links."""
    links = [
        Link(code="src/auth.py", docs=[LinkTarget(file="docs/api.md")]),
        Link(
            code="src/models/user.py",
            docs=[
                LinkTarget(file="docs/models.md", section="User Model"),
                LinkTarget(file="docs/api.md", section="User Endpoints"),
            ],
            note="Manual link for complex model",
        ),
    ]

    toml_content = generate_links_toml(links)

    assert "[[link]]" in toml_content
    assert 'code = "src/auth.py"' in toml_content
    assert 'docs = ["docs/api.md"]' in toml_content
    assert 'code = "src/models/user.py"' in toml_content
    assert 'note = "Manual link for complex model"' in toml_content


def test_load_links_with_ignore():
    """Test loading links with ignore flag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        menard_dir = repo_root / ".menard"
        menard_dir.mkdir()

        links_file = menard_dir / "links.toml"
        links_file.write_text(
            """
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]

[[link]]
code = "src/generated.py"
docs = ["docs/generated.md"]
ignore = true
"""
        )

        links = load_links(repo_root)
        assert len(links) == 2
        assert links[0].ignore is False  # default
        assert links[1].ignore is True


def test_generate_links_toml_with_ignore():
    """Test generating TOML with ignore flag."""
    links = [
        Link(code="src/auth.py", docs=[LinkTarget(file="docs/api.md")]),
        Link(code="src/generated.py", docs=[LinkTarget(file="docs/gen.md")], ignore=True),
    ]

    toml_content = generate_links_toml(links)

    assert "ignore = true" in toml_content
    # Should NOT have ignore = false for non-ignored links
    assert "ignore = false" not in toml_content
