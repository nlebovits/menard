"""Markdown section parsing and line range extraction."""

import re
from pathlib import Path


def parse_markdown_section(file_path: Path, heading: str) -> tuple[int, int] | None:
    """
    Find line range for a markdown section identified by heading text.
    Returns (start_line, end_line) inclusive (1-indexed), or None if not found.

    The section starts at the heading line and ends at:
    - The line before the next heading of equal or higher level, OR
    - End of file if no such heading exists

    Heading matching is case-insensitive.

    Note: Lines starting with # inside code fences (```) are NOT treated as headings.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return None

    heading_level = None
    start_line = None
    in_code_fence = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Track code fence state
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue

        # Skip heading detection inside code fences (issue #25)
        if in_code_fence:
            continue

        # Check if this is a heading
        if stripped.startswith("#"):
            match = re.match(r"^(#+)\s+(.+)$", stripped)
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()

                # Remove any trailing anchor IDs like {#anchor}
                text = re.sub(r"\s*\{#[^}]+\}\s*$", "", text)

                if start_line is None:
                    # Looking for our target heading
                    if text.lower() == heading.lower():
                        heading_level = level
                        start_line = i
                else:
                    # We're past our section, check if this ends it
                    if level <= heading_level:
                        # Higher-level or same-level heading ends our section
                        return (start_line, i - 1)

    # If we found the heading but no closing heading, section goes to EOF
    if start_line is not None:
        return (start_line, len(lines))

    return None


def section_exists(file_path: Path, heading: str) -> bool:
    """Check if a section with the given heading exists in the file."""
    return parse_markdown_section(file_path, heading) is not None


def list_sections(file_path: Path) -> list[str]:
    """
    List all top-level and second-level section headings in a markdown file.
    Returns heading text (without # markers or anchor IDs).
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []

    sections = []
    for line in lines:
        if line.strip().startswith("#"):
            match = re.match(r"^(#+)\s+(.+)$", line.strip())
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()

                # Remove trailing anchor IDs
                text = re.sub(r"\s*\{#[^}]+\}\s*$", "", text)

                # Only include ## and ### level headings (not #)
                # Top-level # is usually the doc title
                if level in (2, 3):
                    sections.append(text)

    return sections


def get_section_content(file_path: Path, heading: str) -> str | None:
    """
    Extract the full content of a section (including the heading).
    Returns None if section doesn't exist.
    """
    line_range = parse_markdown_section(file_path, heading)
    if not line_range:
        return None

    start_line, end_line = line_range

    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return None

    # Extract lines (convert to 0-indexed)
    section_lines = lines[start_line - 1 : end_line]
    return "".join(section_lines)
