"""Protected content guard - prevents modification of critical files, sections, and strings."""

from dataclasses import dataclass
from pathlib import Path

import pathspec


@dataclass
class ProtectionRules:
    """Parsed protection rules from .docsync/donttouch file."""

    file_patterns: pathspec.PathSpec
    section_protections: dict[str, list[str]]
    global_literals: list[str]
    scoped_literals: dict[str, list[str]]


def load_donttouch(repo_root: Path) -> ProtectionRules | None:
    """
    Load and parse .docsync/donttouch file.
    Returns None if file doesn't exist.
    """
    donttouch_file = repo_root / ".docsync" / "donttouch"
    if not donttouch_file.exists():
        return None

    try:
        content = donttouch_file.read_text(encoding="utf-8")
    except Exception:
        return None

    file_patterns = []
    section_protections = {}
    global_literals = []
    scoped_literals = {}

    for line in content.splitlines():
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # For now, treat everything as a file pattern
        file_patterns.append(line)

    # Create PathSpec from patterns using gitignore-style matching
    spec = pathspec.PathSpec.from_lines("gitignore", file_patterns)

    return ProtectionRules(
        file_patterns=spec,
        section_protections=section_protections,
        global_literals=global_literals,
        scoped_literals=scoped_literals,
    )
