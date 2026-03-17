"""Pre-commit hook entry point with TOML-based link checking."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from docsync.config import load_config
from docsync.donttouch import check_protections, load_donttouch
from docsync.graph import build_docsync_graph, get_linked_docs
from docsync.imports import build_import_graph
from docsync.staleness import is_doc_stale
from docsync.toml_links import LinkTarget


@dataclass
class HookResult:
    """Result of running the hook."""

    passed: bool
    stale_docs: list[dict]  # List of stale doc items
    missing_links: list[str]  # Files requiring links but missing them
    message: str  # Formatted output message


def run_hook(repo_root: Path, staged_files: list[str] | None = None) -> HookResult:
    """
    Main hook logic using TOML-based links and git diff staleness detection.

    Returns a HookResult with pass/fail and structured information about
    what's stale or missing.
    """
    # Get staged files first (needed for both protection and staleness checks)
    if staged_files is None:
        staged_files = _get_staged_files(repo_root)

    if not staged_files:
        return HookResult(
            passed=True,
            stale_docs=[],
            missing_links=[],
            message="docsync: no staged files",
        )

    # Check 1: Protected content (fast fail)
    protection_rules = load_donttouch(repo_root)
    if protection_rules:
        violations = check_protections(repo_root, staged_files, protection_rules)
        if violations:
            message_lines = ["⛔ Cannot commit: protected content modified\n"]

            # Group violations by type for clearer output
            file_violations = [v for v in violations if v.type == "protected_file"]
            section_violations = [v for v in violations if v.type == "protected_section"]
            literal_violations = [v for v in violations if v.type == "protected_literal"]

            if file_violations:
                message_lines.append("Protected files:")
                for v in file_violations:
                    message_lines.append(f"  • {v.file}")

            if section_violations:
                if file_violations:
                    message_lines.append("")
                message_lines.append("Protected sections:")
                for v in section_violations:
                    message_lines.append(f"  • {v.file}#{v.section}")

            if literal_violations:
                if file_violations or section_violations:
                    message_lines.append("")
                message_lines.append("Protected strings:")
                for v in literal_violations:
                    literal_preview = v.literal[:50] + "..." if len(v.literal) > 50 else v.literal
                    message_lines.append(f'  • {v.file}: "{literal_preview}"')

            message_lines.append("\nTo bypass: git commit --no-verify")
            message_lines.append("To modify rules: edit .docsync/donttouch")

            return HookResult(
                passed=False,
                stale_docs=[],
                missing_links=[],
                message="\n".join(message_lines),
            )

    # Load config
    config = load_config(repo_root)
    if config is None:
        return HookResult(
            passed=True,
            stale_docs=[],
            missing_links=[],
            message="docsync: not configured (skipping checks)",
        )

    # Build graphs
    docsync_graph = build_docsync_graph(repo_root, config)
    import_graph = {}
    if config.transitive_depth > 0:
        import_graph = build_import_graph(repo_root)

    stale_docs = []
    missing_links = []

    # Check each staged code file
    for staged_file in staged_files:
        # Skip doc files
        if _is_doc_file(staged_file, config):
            continue

        # Check if this file requires links
        requires_link = _matches_require_links(staged_file, config, repo_root)
        has_link = staged_file in docsync_graph

        if requires_link and not has_link:
            missing_links.append(staged_file)
            continue

        if not has_link:
            # File doesn't require link, skip
            continue

        # Get linked doc targets
        doc_targets = get_linked_docs(staged_file, docsync_graph, config)

        # Get transitive imports
        transitive_imports = []
        if config.transitive_depth > 0 and staged_file in import_graph:
            transitive_imports = list(import_graph[staged_file])

        # Check staleness for each doc target
        for doc_target_str in doc_targets:
            target = LinkTarget.parse(doc_target_str)
            is_stale, reason = is_doc_stale(repo_root, staged_file, target, transitive_imports)

            if is_stale:
                stale_docs.append(
                    {
                        "code_file": staged_file,
                        "doc_target": doc_target_str,
                        "doc_file": target.file,
                        "section": target.section,
                        "reason": reason,
                    }
                )

    # Determine pass/fail
    has_issues = bool(stale_docs or missing_links)
    passed = not has_issues or config.mode == "warn"

    # Format message
    message = _format_message(config, stale_docs, missing_links, passed)

    return HookResult(
        passed=passed,
        stale_docs=stale_docs,
        missing_links=missing_links,
        message=message,
    )


def _get_staged_files(repo_root: Path) -> list[str]:
    """Get list of staged files from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.strip().split("\n")
        return [f for f in files if f]
    except subprocess.CalledProcessError as e:
        print(f"Error getting staged files: {e}", file=sys.stderr)
        return []


def _is_doc_file(file_path: str, config) -> bool:
    """Check if a file matches any doc_paths pattern."""
    from pathlib import PurePath

    from docsync.graph import _match_pattern_parts

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


def _matches_require_links(file_path: str, config, repo_root: Path) -> bool:
    """Check if a file matches any require_links pattern."""
    from docsync.graph import _match_globs

    file = repo_root / file_path
    return _match_globs(file, config.require_links, repo_root)


def _format_message(config, stale_docs: list[dict], missing_links: list[str], passed: bool) -> str:
    """Format the output message."""
    if not stale_docs and not missing_links:
        return "docsync: ✓ all documentation is up to date"

    lines = []

    # Header
    if config.mode == "warn":
        lines.append("docsync: ⚠️  commit warning\n")
    else:
        lines.append("docsync: ❌ commit blocked\n")

    # Missing links
    if missing_links:
        lines.append("Files requiring documentation links:")
        for file in sorted(missing_links):
            lines.append(f"  {file}")
        lines.append("\nAdd links in .docsync/links.toml or run 'docsync bootstrap'")
        lines.append("")

    # Stale docs
    if stale_docs:
        lines.append("Stale documentation detected:")
        for item in stale_docs:
            if item["section"]:
                lines.append(f"  {item['doc_file']}#{item['section']}")
            else:
                lines.append(f"  {item['doc_file']}")
            lines.append(f"    Code: {item['code_file']}")
            lines.append(f"    Reason: {item['reason']}")
        lines.append("")

    # Footer
    if not passed:
        lines.append("Update the docs or use --no-verify to force commit.")

    return "\n".join(lines)


def main() -> int:
    """Entry point for pre-commit hook."""
    repo_root = Path.cwd()
    result = run_hook(repo_root)
    print(result.message)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
