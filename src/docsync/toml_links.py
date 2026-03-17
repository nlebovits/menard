"""TOML link file parsing and validation."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LinkTarget:
    """Represents a documentation target, optionally with a specific section."""

    file: str
    section: str | None = None

    @classmethod
    def parse(cls, target: str) -> "LinkTarget":
        """Parse a doc target string like 'docs/api.md#Authentication'."""
        if "#" in target:
            file_part, section_part = target.split("#", 1)
            return cls(file=file_part, section=section_part)
        return cls(file=target, section=None)

    def __str__(self) -> str:
        """Return canonical string representation."""
        if self.section:
            return f"{self.file}#{self.section}"
        return self.file


@dataclass
class Link:
    """Represents a code-to-docs link mapping."""

    code: str
    docs: list[LinkTarget]
    note: str | None = None


def load_links(repo_root: Path) -> list[Link]:
    """
    Load link mappings from .docsync/links.toml.
    Returns empty list if file doesn't exist.
    """
    links_file = repo_root / ".docsync" / "links.toml"

    if not links_file.exists():
        return []

    try:
        with open(links_file, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse {links_file}: {e}") from e

    # Parse link entries
    links = []
    for entry in data.get("link", []):
        code = entry.get("code")
        docs = entry.get("docs", [])
        note = entry.get("note")

        if not code:
            raise ValueError(f"Link entry missing 'code' field: {entry}")

        if not docs:
            raise ValueError(f"Link entry for '{code}' has no 'docs' field")

        # Parse doc targets
        doc_targets = [LinkTarget.parse(doc) for doc in docs]

        links.append(Link(code=code, docs=doc_targets, note=note))

    return links


def validate_links(links: list[Link], repo_root: Path) -> list[str]:
    """
    Validate that all referenced files and sections exist.
    Returns list of validation errors.
    """
    errors = []

    for link in links:
        # Check code file exists (handle globs specially)
        if "*" not in link.code:
            code_path = repo_root / link.code
            if not code_path.exists():
                errors.append(f"Code file not found: {link.code}")

        # Check doc files exist
        for doc_target in link.docs:
            doc_path = repo_root / doc_target.file
            if not doc_path.exists():
                errors.append(f"Doc file not found: {doc_target.file}")
                continue

            # Check section exists if specified
            if doc_target.section:
                from docsync.sections import list_sections, section_exists

                if not section_exists(doc_path, doc_target.section):
                    available = list_sections(doc_path)
                    error = f"Section '{doc_target.section}' not found in {doc_target.file}"

                    # Try to suggest a match
                    from difflib import get_close_matches

                    matches = get_close_matches(doc_target.section, available, n=1, cutoff=0.6)
                    if matches:
                        error += f"\n  Did you mean '{matches[0]}'?"
                    elif available:
                        error += f"\n  Available sections: {', '.join(available[:5])}"
                        if len(available) > 5:
                            error += f" (and {len(available) - 5} more)"

                    errors.append(error)

    return errors


def build_graph_from_links(links: list[Link], repo_root: Path) -> dict[str, set[str]]:
    """
    Build bidirectional graph from link mappings.
    Handles glob patterns in code paths by expanding them.
    Returns dict mapping file paths to sets of linked files.
    """
    from fnmatch import fnmatch

    graph: dict[str, set[str]] = {}

    for link in links:
        # Expand globs in code patterns
        code_files = []
        if "*" in link.code:
            # Find all matching files
            pattern = link.code
            for file_path in repo_root.rglob("*"):
                if file_path.is_file():
                    rel_path = str(file_path.relative_to(repo_root))
                    if fnmatch(rel_path, pattern):
                        code_files.append(rel_path)
        else:
            code_files = [link.code]

        # Add bidirectional links for each code file
        for code_file in code_files:
            for doc_target in link.docs:
                # Use the full target string (file#section or just file)
                doc_str = str(doc_target)

                graph.setdefault(code_file, set()).add(doc_str)
                graph.setdefault(doc_str, set()).add(code_file)

    return graph


def generate_links_toml(links: list[Link]) -> str:
    """
    Generate a formatted .docsync/links.toml file from link mappings.
    Used by bootstrap and migrate commands.
    """
    lines = [
        "# .docsync/links.toml",
        "# Generated by docsync - edit manually as needed",
        "#",
        "# Links define relationships between code files and documentation.",
        "# When code changes, docsync checks if linked docs are stale.",
        "",
    ]

    for link in links:
        lines.append("[[link]]")
        lines.append(f'code = "{link.code}"')

        # Format docs array
        if len(link.docs) == 1:
            lines.append(f'docs = ["{link.docs[0]}"]')
        else:
            lines.append("docs = [")
            for doc in link.docs:
                lines.append(f'  "{doc}",')
            lines.append("]")

        if link.note:
            lines.append(f'note = "{link.note}"')

        lines.append("")

    return "\n".join(lines)
