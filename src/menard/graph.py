"""Docsync graph construction from TOML link files."""

from pathlib import Path, PurePath

from menard.config import DocsyncConfig
from menard.toml_links import build_graph_from_links, load_links


def build_menard_graph(repo_root: Path, config: DocsyncConfig) -> dict[str, set[str]]:
    """
    Build bidirectional graph from .menard/links.toml.
    Returns dict mapping file paths to sets of linked files.

    Graph nodes include:
    - Code file paths (e.g., "src/auth.py")
    - Doc file paths (e.g., "docs/api.md")
    - Section-specific targets (e.g., "docs/api.md#Authentication")

    Links are bidirectional: if code links to doc, doc links back to code.
    """
    links = load_links(repo_root)
    return build_graph_from_links(links, repo_root)


def _match_globs(file_path: Path, patterns: list[str], base_path: Path) -> bool:
    """Check if file_path matches any of the glob patterns."""
    if not patterns:
        return False

    rel_path = file_path.relative_to(base_path)
    pure_path = PurePath(rel_path)

    for pattern in patterns:
        if "**" in pattern:
            parts = pattern.split("/")
            path_parts = pure_path.parts
            if _match_pattern_parts(path_parts, parts):
                return True
        else:
            if pure_path.match(pattern):
                return True
    return False


def _match_pattern_parts(path_parts: tuple[str, ...], pattern_parts: list[str]) -> bool:
    """Match path parts against pattern parts, handling ** wildcards."""
    if not pattern_parts:
        return not path_parts

    if not path_parts:
        return all(p == "**" for p in pattern_parts)

    if pattern_parts[0] == "**":
        if _match_pattern_parts(path_parts, pattern_parts[1:]):
            return True
        return _match_pattern_parts(path_parts[1:], pattern_parts)

    if pattern_parts[0] == "*":
        return _match_pattern_parts(path_parts[1:], pattern_parts[1:])

    if "*" in pattern_parts[0] or "?" in pattern_parts[0]:
        import fnmatch

        if fnmatch.fnmatch(path_parts[0], pattern_parts[0]):
            return _match_pattern_parts(path_parts[1:], pattern_parts[1:])
        return False

    if path_parts[0] == pattern_parts[0]:
        return _match_pattern_parts(path_parts[1:], pattern_parts[1:])

    return False


def get_linked_docs(file_path: str, graph: dict[str, set[str]], config: DocsyncConfig) -> set[str]:
    """
    Given a code file path, return all doc targets linked to it.
    Doc targets can be whole files or section-specific (e.g., "docs/api.md#Auth").
    """
    linked = graph.get(file_path, set())

    # Filter to only doc files/targets
    doc_targets = set()
    for linked_item in linked:
        # Extract the file part (before # if present)
        doc_file = linked_item.split("#")[0] if "#" in linked_item else linked_item
        pure_path = PurePath(doc_file)

        for pattern in config.doc_paths:
            if "**" in pattern:
                parts = pattern.split("/")
                path_parts = pure_path.parts
                if _match_pattern_parts(path_parts, parts):
                    doc_targets.add(linked_item)
                    break
            else:
                if pure_path.match(pattern):
                    doc_targets.add(linked_item)
                    break

    return doc_targets
