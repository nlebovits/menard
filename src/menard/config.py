"""Configuration parsing from pyproject.toml."""

from dataclasses import dataclass, field
from pathlib import Path

from menard._compat import tomllib


@dataclass
class DocsyncConfig:
    """Configuration for menard behavior."""

    mode: str = "block"
    transitive_depth: int = 1
    enforce_symmetry: bool = True
    require_links: list[str] = field(default_factory=list)
    exempt: list[str] = field(default_factory=list)
    doc_paths: list[str] = field(default_factory=lambda: ["docs/**/*.md", "README.md"])
    exclude_docs: list[str] = field(default_factory=list)


def load_config(repo_root: Path) -> DocsyncConfig | None:
    """Load config from pyproject.toml. Returns None if not configured."""
    pyproject_path = repo_root / "pyproject.toml"

    # If pyproject.toml doesn't exist, not configured
    if not pyproject_path.exists():
        return None

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        # If we can't parse the file, not configured
        return None

    # Extract [tool.menard] section
    tool_section = data.get("tool", {})
    menard_section = tool_section.get("menard", {})

    # If section is missing, not configured
    if not menard_section:
        return None

    # Build config from section, using defaults for missing keys
    return DocsyncConfig(
        mode=menard_section.get("mode", "block"),
        transitive_depth=menard_section.get("transitive_depth", 1),
        enforce_symmetry=menard_section.get("enforce_symmetry", True),
        require_links=menard_section.get("require_links", []),
        exempt=menard_section.get("exempt", []),
        doc_paths=menard_section.get("doc_paths", ["docs/**/*.md", "README.md"]),
        exclude_docs=menard_section.get("exclude_docs", []),
    )
