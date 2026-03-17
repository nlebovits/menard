"""Tests for markdown section parsing."""

import tempfile
from pathlib import Path

from docsync.sections import (
    get_section_content,
    list_sections,
    parse_markdown_section,
    section_exists,
)


def test_parse_markdown_section_basic():
    """Test parsing a basic markdown section."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_file = Path(tmpdir) / "test.md"
        doc_file.write_text(
            """# Title

## Introduction

Some intro text.

## Usage

Usage docs here.

## API Reference

API docs.
"""
        )

        # Test finding a section
        result = parse_markdown_section(doc_file, "Usage")
        assert result == (7, 10)  # Includes content up to line before next heading

        # Test case-insensitive
        result = parse_markdown_section(doc_file, "usage")
        assert result == (7, 10)


def test_parse_markdown_section_last():
    """Test parsing the last section (goes to EOF)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_file = Path(tmpdir) / "test.md"
        doc_file.write_text(
            """# Title

## Section One

Text.

## Section Two

Final section.
More text.
"""
        )

        result = parse_markdown_section(doc_file, "Section Two")
        assert result == (7, 10)  # Goes to end of file


def test_parse_markdown_section_with_subsections():
    """Test parsing a section that contains subsections."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_file = Path(tmpdir) / "test.md"
        doc_file.write_text(
            """# Title

## Main Section

### Subsection A

Text A.

### Subsection B

Text B.

## Next Section

Text.
"""
        )

        # Main section should include its subsections
        result = parse_markdown_section(doc_file, "Main Section")
        assert result == (3, 12)  # Ends at line before "## Next Section"

        # Can also target subsections directly
        result = parse_markdown_section(doc_file, "Subsection A")
        assert result == (5, 8)  # Ends at line before "### Subsection B"


def test_parse_markdown_section_not_found():
    """Test parsing returns None for non-existent section."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_file = Path(tmpdir) / "test.md"
        doc_file.write_text(
            """# Title

## Section

Text.
"""
        )

        result = parse_markdown_section(doc_file, "NonExistent")
        assert result is None


def test_section_exists():
    """Test checking if a section exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_file = Path(tmpdir) / "test.md"
        doc_file.write_text(
            """# Title

## Authentication

Auth docs.
"""
        )

        assert section_exists(doc_file, "Authentication") is True
        assert section_exists(doc_file, "Missing") is False


def test_list_sections():
    """Test listing all sections in a document."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_file = Path(tmpdir) / "test.md"
        doc_file.write_text(
            """# API Documentation

## Authentication

Auth docs.

### Login

Login details.

## Models

Model docs.
"""
        )

        sections = list_sections(doc_file)

        # Should include level 2 and 3 headings, not level 1
        assert "Authentication" in sections
        assert "Login" in sections
        assert "Models" in sections
        assert "API Documentation" not in sections  # Level 1 excluded


def test_get_section_content():
    """Test extracting section content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_file = Path(tmpdir) / "test.md"
        doc_file.write_text(
            """# Title

## Usage

This is usage.

## Next

Text.
"""
        )

        content = get_section_content(doc_file, "Usage")
        assert content is not None
        assert "## Usage" in content
        assert "This is usage." in content
        assert "## Next" not in content  # Next section not included


def test_parse_markdown_section_with_anchor_ids():
    """Test parsing sections with explicit anchor IDs like {#auth}."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_file = Path(tmpdir) / "test.md"
        doc_file.write_text(
            """# Title

## Authentication {#auth-section}

Auth docs.

## Another Section

Text.
"""
        )

        # Should still find by heading text (anchor ID stripped)
        result = parse_markdown_section(doc_file, "Authentication")
        assert result == (3, 6)  # Ends at line before "## Another Section"

        # List sections should strip anchor IDs
        sections = list_sections(doc_file)
        assert "Authentication" in sections
        assert "Authentication {#auth-section}" not in sections


def test_parse_markdown_section_with_code_fences():
    """Test that # inside code blocks are not treated as headings (issue #25)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_file = Path(tmpdir) / "test.md"
        doc_file.write_text(
            """# Documentation

## Quick Start

```bash
# Install the package
pip install mypackage

# Run the tool
mypackage --help
```

That's how you install it.

## Configuration

Config goes here.
"""
        )

        # The Quick Start section should include the entire code block
        # and not end prematurely at "# Install the package"
        result = parse_markdown_section(doc_file, "Quick Start")
        assert result == (3, 14)  # Ends at line before "## Configuration"

        # Verify the section includes the code block content
        content = get_section_content(doc_file, "Quick Start")
        assert content is not None
        assert "# Install the package" in content
        assert "# Run the tool" in content
        assert "## Configuration" not in content
