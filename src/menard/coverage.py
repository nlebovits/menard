"""Coverage report generation."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from menard.config import DocsyncConfig, load_config
from menard.graph import build_menard_graph


@dataclass
class CoverageReport:
    """Coverage report data."""

    total_required: int
    linked: int
    coverage_pct: float
    orphaned_docs: list[str] = field(default_factory=list)  # docs linking to non-existent code
    orphaned_code: list[str] = field(default_factory=list)  # required code with no doc links
    asymmetric_links: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # (file_a, file_b, direction)
    stale_docs: list[tuple[str, str, int, int, int]] = field(
        default_factory=list
    )  # (doc_file, code_file, doc_ts, code_ts, days_stale)
    markdown: str = ""  # formatted markdown table


def generate_coverage(repo_root: Path) -> CoverageReport:
    """Generate a full coverage report."""
    config = load_config(repo_root)
    if config is None:
        # Not configured - return empty report
        return CoverageReport(
            total_required=0,
            linked=0,
            coverage_pct=100.0,
            markdown="⚠️  menard not configured. Run 'menard init' to set up.\n",
        )
    graph = build_menard_graph(repo_root, config)

    # Find all files that should have links (from require_links globs)
    required_files = _get_required_files(repo_root, config)

    # Count linked files
    linked_files = {f for f in required_files if f in graph and graph[f]}

    total_required = len(required_files)
    linked = len(linked_files)
    coverage_pct = (linked / total_required * 100) if total_required > 0 else 100.0

    # Detect orphans
    orphaned_docs = _detect_orphaned_docs(graph, repo_root)
    orphaned_code = list(required_files - linked_files)

    # Detect asymmetric links (if enforce_symmetry is true)
    asymmetric_links = []
    if config.enforce_symmetry:
        asymmetric_links = _detect_asymmetric_links(graph, repo_root, config)

    # Detect stale docs
    stale_docs = _detect_stale_docs(graph, repo_root, config)

    # Format as markdown
    markdown = _format_markdown(
        total_required,
        linked,
        coverage_pct,
        orphaned_docs,
        orphaned_code,
        asymmetric_links,
        stale_docs,
    )

    return CoverageReport(
        total_required=total_required,
        linked=linked,
        coverage_pct=coverage_pct,
        orphaned_docs=orphaned_docs,
        orphaned_code=orphaned_code,
        asymmetric_links=asymmetric_links,
        stale_docs=stale_docs,
        markdown=markdown,
    )


def _get_required_files(repo_root: Path, config: DocsyncConfig) -> set[str]:
    """Get all files that should have doc links (matching require_links globs)."""
    from menard.graph import _match_globs

    required = set()
    for file_path in repo_root.rglob("*"):
        if not file_path.is_file():
            continue
        if _match_globs(file_path, config.require_links, repo_root) and not _match_globs(
            file_path, config.exempt, repo_root
        ):
            required.add(str(file_path.relative_to(repo_root)))
    return required


def _detect_orphaned_docs(graph: dict[str, set[str]], repo_root: Path) -> list[str]:
    """Find doc files that link to non-existent code files."""
    orphaned = []
    for file_path, links in graph.items():
        # Check if this file is a doc (has a markdown extension or similar)
        if not file_path.endswith(".md"):
            continue

        for linked_file in links:
            linked_abs = repo_root / linked_file
            if not linked_abs.exists():
                orphaned.append(f"{file_path} → {linked_file}")

    return orphaned


def _detect_asymmetric_links(
    graph: dict[str, set[str]], repo_root: Path, config: DocsyncConfig
) -> list[tuple[str, str, str]]:
    """
    Find asymmetric links where A links to B but B doesn't link back to A.
    Returns list of (file_a, file_b, direction) where direction describes the missing link.

    NOTE: With TOML-based links, all links are symmetric by definition (code -> docs mapping).
    This function is kept for API compatibility but returns empty list.
    """
    # TOML links are symmetric by design: each [[link]] entry defines
    # bidirectional relationships between code and docs
    return []


def _detect_stale_docs(
    graph: dict[str, set[str]], repo_root: Path, config: DocsyncConfig
) -> list[tuple[str, str, int, int, int]]:
    """
    Find doc files where linked code has been modified more recently.
    Returns list of (doc_file, code_file, doc_timestamp, code_timestamp, days_stale) tuples.
    """
    stale = []

    # Get all doc files from graph
    doc_files = {f for f in graph if _is_doc_file(f, config)}

    for doc_file in doc_files:
        doc_timestamp = _get_last_commit_time(repo_root, doc_file)
        if doc_timestamp is None:
            continue  # File not in git yet

        # Check all linked code files
        for linked_file in graph.get(doc_file, set()):
            # Skip if linked file is also a doc
            if _is_doc_file(linked_file, config):
                continue

            code_timestamp = _get_last_commit_time(repo_root, linked_file)
            if code_timestamp is None:
                continue  # File not in git yet

            # If ANY linked code file is newer, the doc is stale
            if code_timestamp > doc_timestamp:
                days_stale = (code_timestamp - doc_timestamp) // 86400  # seconds to days
                stale.append((doc_file, linked_file, doc_timestamp, code_timestamp, days_stale))

    return stale


def _is_doc_file(file_path: str, config: DocsyncConfig) -> bool:
    """Check if a file is a doc file based on doc_paths patterns."""
    from pathlib import PurePath

    from menard.graph import _match_pattern_parts

    pure_path = PurePath(file_path)

    for pattern in config.doc_paths:
        if "**" in pattern:
            parts = pattern.split("/")
            path_parts = pure_path.parts
            if _match_pattern_parts(path_parts, parts):
                return True
        else:
            if pure_path.match(pattern):
                return True

    return False


def _get_last_commit_time(repo_root: Path, file_path: str) -> int | None:
    """
    Get the Unix timestamp of the last commit that modified this file.
    Returns None if the file has no git history.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", file_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
        if output:
            return int(output)
        return None
    except (subprocess.CalledProcessError, ValueError):
        return None


def _format_markdown(
    total_required: int,
    linked: int,
    coverage_pct: float,
    orphaned_docs: list[str],
    orphaned_code: list[str],
    asymmetric_links: list[tuple[str, str, str]],
    stale_docs: list[tuple[str, str, int, int, int]],
) -> str:
    """Format the coverage report as markdown."""
    lines = ["## menard Coverage Report\n"]

    # Calculate staleness metrics
    total_links = linked
    stale_count = len(stale_docs)
    stale_pct = (stale_count / total_links * 100) if total_links > 0 else 0.0

    # Categorize staleness severity
    critical_stale = sum(1 for _, _, _, _, days in stale_docs if days > 90)
    warning_stale = sum(1 for _, _, _, _, days in stale_docs if 30 < days <= 90)
    fresh_stale = sum(1 for _, _, _, _, days in stale_docs if days <= 30)

    # Summary table
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Required files | {total_required} |")
    lines.append(f"| Files with doc links | {linked} |")
    lines.append(f"| Coverage | {coverage_pct:.1f}% |")
    if stale_count > 0:
        lines.append(f"| Stale docs | {stale_count} ({stale_pct:.1f}%) |")
        if critical_stale > 0:
            lines.append(f"| Critical (>90 days) | {critical_stale} |")
        if warning_stale > 0:
            lines.append(f"| Warning (30-90 days) | {warning_stale} |")
        if fresh_stale > 0:
            lines.append(f"| Recent (<30 days) | {fresh_stale} |")
    lines.append("")

    # Orphaned docs
    if orphaned_docs:
        lines.append("### Orphaned Docs")
        lines.append("| Doc | Links to (missing) |")
        lines.append("|-----|--------------------|")
        for orphan_str in sorted(orphaned_docs):
            doc, missing = orphan_str.split(" → ")
            lines.append(f"| {doc} | {missing} |")
        lines.append("")

    # Orphaned code
    if orphaned_code:
        lines.append("### Orphaned Code")
        lines.append("| Code file | Status |")
        lines.append("|-----------|--------|")
        for code_file in sorted(orphaned_code):
            lines.append(f"| {code_file} | No doc links |")
        lines.append("")

    # Asymmetric links
    if asymmetric_links:
        lines.append("### Asymmetric Links")
        lines.append("| File A | File B | Missing direction |")
        lines.append("|--------|--------|-------------------|")
        for file_a, file_b, direction in sorted(asymmetric_links):
            lines.append(f"| {file_a} | {file_b} | {direction} |")
        lines.append("")

    # Stale docs
    if stale_docs:
        from datetime import datetime

        lines.append("### Stale Docs")
        lines.append("| Doc | Linked code (newer) | Doc modified | Code modified | Days stale |")
        lines.append("|-----|---------------------|--------------|---------------|------------|")
        for doc_file, code_file, doc_ts, code_ts, days_stale in sorted(
            stale_docs, key=lambda x: x[4], reverse=True
        ):  # Sort by days_stale descending
            doc_date = datetime.fromtimestamp(doc_ts).strftime("%Y-%m-%d")
            code_date = datetime.fromtimestamp(code_ts).strftime("%Y-%m-%d")
            lines.append(
                f"| {doc_file} | {code_file} | {doc_date} | {code_date} | {days_stale} days |"
            )
        lines.append("")

    return "\n".join(lines)
