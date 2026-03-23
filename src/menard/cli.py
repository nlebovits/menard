"""CLI for menard - Documentation freshness enforcement."""

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from menard._compat import tomllib
from menard.config import load_config
from menard.donttouch import check_protections, load_donttouch
from menard.graph import build_menard_graph, get_linked_docs
from menard.imports import build_import_graph
from menard.reviewed import (
    SHA_SHORT_LENGTH,
    Review,
    clean_reviews,
    load_reviews,
    normalize_path,
    save_review,
)
from menard.staleness import check_staleness_enriched, get_last_commit, is_doc_stale
from menard.toml_links import (
    Link,
    LinkTarget,
    generate_links_toml,
    load_links,
    validate_links,
)

# Directories to exclude from source detection
EXCLUDED_DIRS = frozenset(
    {
        "tests",
        "test",
        "docs",
        "doc",
        "examples",
        "example",
        "scripts",
        "bin",
        "build",
        "dist",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        ".eggs",
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "vendor",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)


def _is_valid_package_pattern(pattern: str) -> bool:
    """Check if a pattern is valid (no wildcards in the package path)."""
    # Reject patterns with wildcards before the final /**/*.py
    prefix = pattern.removesuffix("/**/*.py")
    return "*" not in prefix and "?" not in prefix and "[" not in prefix


def detect_source_directories(repo_root: Path) -> list[str]:
    """Detect Python source directories in a project.

    Detection strategy:
    1. Check pyproject.toml for explicit package configuration (hatch, setuptools, poetry)
    2. Look for directories containing __init__.py (Python packages)
    3. Fall back to src/ if nothing found

    Returns a list of glob patterns like ["src/**/*.py", "mypackage/**/*.py"]

    Note: Namespace packages (without __init__.py) are not detected by strategy 2.
    Use pyproject.toml configuration for namespace packages.
    """
    patterns: list[str] = []

    # Strategy 1: Check pyproject.toml for package configuration
    pyproject_path = repo_root / "pyproject.toml"
    if pyproject_path.exists():
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)

            # Check [tool.hatch.build.targets.wheel] packages
            hatch_packages = (
                data.get("tool", {})
                .get("hatch", {})
                .get("build", {})
                .get("targets", {})
                .get("wheel", {})
                .get("packages", [])
            )
            for pkg in hatch_packages:
                pattern = f"{pkg}/**/*.py"
                if _is_valid_package_pattern(pattern):
                    patterns.append(pattern)

            # Check [tool.setuptools.packages]
            setuptools = data.get("tool", {}).get("setuptools", {})
            if "packages" in setuptools:
                for pkg in setuptools["packages"]:
                    pattern = f"{pkg}/**/*.py"
                    if _is_valid_package_pattern(pattern):
                        patterns.append(pattern)

            # Check [tool.setuptools.package-dir] - maps package names to paths
            if "package-dir" in setuptools:
                for _pkg_name, path in setuptools["package-dir"].items():
                    if path:  # Skip empty string (root package)
                        pattern = f"{path}/**/*.py"
                        if _is_valid_package_pattern(pattern):
                            patterns.append(pattern)

            # Check [tool.poetry.packages] - Poetry configuration
            poetry_packages = data.get("tool", {}).get("poetry", {}).get("packages", [])
            for pkg_config in poetry_packages:
                if isinstance(pkg_config, dict):
                    include = pkg_config.get("include", "")
                    from_dir = pkg_config.get("from", "")
                    if include:
                        path = f"{from_dir}/{include}" if from_dir else include
                        pattern = f"{path}/**/*.py"
                        if _is_valid_package_pattern(pattern):
                            patterns.append(pattern)

            if patterns:
                return patterns

        except (OSError, tomllib.TOMLDecodeError):
            # Fall through to directory scanning on parse errors
            pass

    # Strategy 2: Look for directories with __init__.py
    package_dirs: set[str] = set()

    try:
        for init_file in repo_root.rglob("__init__.py"):
            try:
                # Get the package directory (parent of __init__.py)
                pkg_dir = init_file.parent
                rel_path = pkg_dir.relative_to(repo_root)

                # Skip excluded directories
                parts = rel_path.parts
                if any(part.lower() in EXCLUDED_DIRS for part in parts):
                    continue

                # Skip hidden directories
                if any(part.startswith(".") for part in parts):
                    continue

                # Determine the package pattern based on structure
                if len(parts) >= 2 and parts[0].lower() == "src":
                    # src layout: src/mypackage/ -> use src/mypackage/**/*.py
                    # Find the actual package (first dir after src with __init__.py)
                    pkg_path = parts[0] + "/" + parts[1]
                    package_dirs.add(pkg_path)
                elif len(parts) >= 1:
                    # Flat layout: mypackage/ -> use mypackage/**/*.py
                    package_dirs.add(parts[0])

            except (OSError, ValueError):
                # Skip files we can't access or paths we can't resolve
                continue

    except OSError:
        # Handle permission errors or symlink issues during traversal
        pass

    # Convert to glob patterns
    for pkg_dir in sorted(package_dirs):
        patterns.append(f"{pkg_dir}/**/*.py")

    # Strategy 3: Fall back to src/ if nothing found
    if not patterns:
        patterns.append("src/**/*.py")

    return patterns


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize menard configuration."""
    repo_root = Path.cwd()
    pyproject_path = repo_root / "pyproject.toml"

    # Auto-detect source directories
    detected_patterns = detect_source_directories(repo_root)
    require_links_toml = ", ".join(f'"{p}"' for p in detected_patterns)

    if not pyproject_path.exists():
        print("⚠️  No pyproject.toml found. Creating minimal configuration...")
        pyproject_path.write_text(
            f"""[project]
name = "project"
version = "0.1.0"

[tool.menard]
mode = "block"
transitive_depth = 1
enforce_symmetry = true
require_links = [{require_links_toml}]
exempt = ["tests/**"]
doc_paths = ["docs/**/*.md", "README.md"]
"""
        )
        print(f"✓ Created {pyproject_path}")
    else:
        # Check if [tool.menard] exists
        content = pyproject_path.read_text()
        if "[tool.menard]" in content:
            print("⚠️  menard already configured in pyproject.toml")
            return 1

        # Append configuration
        with open(pyproject_path, "a") as f:
            f.write(
                f"""
[tool.menard]
mode = "block"
transitive_depth = 1
enforce_symmetry = true
require_links = [{require_links_toml}]
exempt = ["tests/**"]
doc_paths = ["docs/**/*.md", "README.md"]
"""
            )
        print(f"✓ Added [tool.menard] to {pyproject_path}")

    # Report detected source directories
    if detected_patterns != ["src/**/*.py"]:
        print(f"✓ Detected source directories: {detected_patterns}")

    # Create .menard directory
    menard_dir = repo_root / ".menard"
    menard_dir.mkdir(exist_ok=True)
    print(f"✓ Created {menard_dir}/")

    # Create empty links.toml with helpful comments
    links_file = menard_dir / "links.toml"
    if not links_file.exists():
        links_file.write_text(
            """# .menard/links.toml
# Generated by menard init
#
# Define code-to-documentation links here.
# When code changes, menard checks if linked docs are stale.
#
# Examples:
#
# # Simple whole-file link
# [[link]]
# code = "src/auth.py"
# docs = ["docs/api.md"]
#
# # Section-specific link (more precise)
# [[link]]
# code = "src/auth.py"
# docs = ["docs/api.md#Authentication"]
#
# # Multiple docs for one code file
# [[link]]
# code = "src/models/user.py"
# docs = [
#   "docs/models.md#User Model",
#   "docs/api.md#User Endpoints",
# ]
#
# Run 'menard bootstrap' to auto-generate links from conventions.
"""
        )
        print(f"✓ Created {links_file}")
    else:
        print(f"⚠️  {links_file} already exists")

    print("\n✓ Initialization complete!")
    print("\nNext steps:")
    print("  1. Run 'menard bootstrap' to auto-generate links")
    print("  2. Edit .menard/links.toml to customize links")
    print("  3. Run 'menard check' to verify setup")

    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    """Migrate from inline comments to TOML links."""
    print("⚠️  Migration from inline comments is not yet implemented.")
    print("This project was designed for TOML-only links from the start.")
    print("\nTo create links, use:")
    print("  - menard bootstrap    # Auto-generate from conventions")
    print("  - Edit .menard/links.toml manually")
    return 1


def cmd_validate_links(args: argparse.Namespace) -> int:
    """Validate that all links reference existing files and sections."""
    repo_root = Path.cwd()
    links = load_links(repo_root)

    if not links:
        print("No links found in .menard/links.toml")
        return 0

    errors = validate_links(links, repo_root)

    if not errors:
        print(f"✓ All {len(links)} links are valid")
        return 0

    print(f"❌ Found {len(errors)} validation errors:\n")
    for error in errors:
        print(f"  {error}")

    return 1


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Auto-generate links from conventions and content analysis."""
    repo_root = Path.cwd()
    config = load_config(repo_root)

    if config is None:
        print("⚠️  menard not configured. Run 'menard init' first.")
        return 1

    if not config.require_links:
        print("⚠️  require_links is empty in [tool.menard]")
        print("Add patterns like: require_links = ['src/**/*.py']")
        return 1

    # Load existing links
    existing_links = load_links(repo_root)
    existing_code_files = {link.code for link in existing_links}

    # Find code files without links
    from menard.graph import _match_globs

    orphans = []
    for file_path in repo_root.rglob("*"):
        if not file_path.is_file():
            continue
        if not _match_globs(file_path, config.require_links, repo_root):
            continue
        if _match_globs(file_path, config.exempt, repo_root):
            continue

        rel_path = str(file_path.relative_to(repo_root))
        if rel_path not in existing_code_files:
            orphans.append(rel_path)

    if not orphans:
        print("✓ All code files have links")
        return 0

    print(f"Found {len(orphans)} code files without links")
    print("Analyzing conventions and content...\n")

    # Heuristic 1: Filename matching
    # src/auth.py -> docs/auth.md
    proposals = []
    for code_file in orphans:
        code_path = Path(code_file)
        base_name = code_path.stem  # e.g., "auth" from "auth.py"

        # Look for matching docs
        for doc_pattern in config.doc_paths:
            for doc_path in repo_root.glob(doc_pattern):
                if not doc_path.is_file():
                    continue
                # Skip docs matching exclude_docs patterns
                if _match_globs(doc_path, config.exclude_docs, repo_root):
                    continue

                doc_rel = str(doc_path.relative_to(repo_root))

                # Check if basename matches
                if doc_path.stem.lower() == base_name.lower():
                    proposals.append(Link(code=code_file, docs=[LinkTarget(file=doc_rel)]))
                    break

    # Heuristic 2: Content analysis (grep for code file references in docs)
    # This is expensive, so only do it if we have few proposals
    if len(proposals) < len(orphans):
        remaining = set(orphans) - {p.code for p in proposals}
        for code_file in remaining:
            code_path = Path(code_file)
            code_name = code_path.name

            # Search doc files for references to this code file
            for doc_pattern in config.doc_paths:
                for doc_path in repo_root.glob(doc_pattern):
                    if not doc_path.is_file():
                        continue
                    # Skip docs matching exclude_docs patterns
                    if _match_globs(doc_path, config.exclude_docs, repo_root):
                        continue

                    try:
                        content = doc_path.read_text()
                        if code_name in content or code_file in content:
                            doc_rel = str(doc_path.relative_to(repo_root))
                            # Check if this doc already has a proposal for this code
                            existing_proposal = next(
                                (p for p in proposals if p.code == code_file), None
                            )
                            if existing_proposal:
                                # Add this doc to existing proposal
                                existing_proposal.docs.append(LinkTarget(file=doc_rel))
                            else:
                                proposals.append(
                                    Link(code=code_file, docs=[LinkTarget(file=doc_rel)])
                                )
                            break
                    except Exception:
                        continue

    if not proposals:
        print("⚠️  No doc matches found for orphaned code files")
        print(f"\nOrphaned files ({len(orphans)}):")
        for orphan in orphans[:10]:
            print(f"  {orphan}")
        if len(orphans) > 10:
            print(f"  ... and {len(orphans) - 10} more")
        return 0

    # Detect human-facing docs that need manual attention
    human_facing_patterns = ["README", "quickstart", "tutorial", "guide", "example"]
    human_facing_docs = set()
    for link in proposals:
        for doc_target in link.docs:
            doc_lower = doc_target.file.lower()
            if any(pattern in doc_lower for pattern in human_facing_patterns):
                human_facing_docs.add(doc_target.file)

    # Print proposals
    print(f"Proposed {len(proposals)} links:\n")
    for link in proposals:
        doc_strs = [str(d) for d in link.docs]
        print(f"  {link.code}")
        for doc_str in doc_strs:
            marker = " ⚠️" if doc_str in human_facing_docs else ""
            print(f"    → {doc_str}{marker}")

    if human_facing_docs:
        print(
            f"\n⚠️  Warning: {len(human_facing_docs)} docs may be tutorials/guides (marked with ⚠️)"
        )
        print("Review these carefully - automated links may not make sense for narrative docs.")

    # Apply or show instructions
    if args.apply:
        links_file = repo_root / ".menard" / "links.toml"
        all_links = existing_links + proposals

        links_content = generate_links_toml(all_links)
        links_file.write_text(links_content)

        print(f"\n✓ Wrote {len(proposals)} new links to .menard/links.toml")
        print("Run 'menard validate-links' to verify")
    else:
        print("\nTo apply these links, run:")
        print("  menard bootstrap --apply")

    return 0


def _count_all_stale_docs(repo_root: Path, config, graph: dict, import_graph: dict) -> int:
    """Count total stale docs across entire repo (for hint in check command)."""
    code_files = {k for k in graph if not any(k.endswith(ext) for ext in [".md", ".rst"])}
    stale_count = 0

    for code_file in code_files:
        doc_targets = get_linked_docs(code_file, graph, config)

        transitive_imports = []
        if config.transitive_depth > 0 and code_file in import_graph:
            transitive_imports = list(import_graph[code_file])

        for doc_target_str in doc_targets:
            target = LinkTarget.parse(doc_target_str)
            is_stale, _ = is_doc_stale(repo_root, code_file, target, transitive_imports)
            if is_stale:
                stale_count += 1

    return stale_count


def _format_skip_message(
    skipped_auto_generated: int, skipped_reviewed: int, skipped_ignored: int
) -> str:
    """Format a skip message for text output.

    Returns a string like " (2 auto-generated, 1 reviewed skipped)" or empty string.
    """
    skip_parts = []
    if skipped_auto_generated > 0:
        skip_parts.append(f"{skipped_auto_generated} auto-generated")
    if skipped_reviewed > 0:
        skip_parts.append(f"{skipped_reviewed} reviewed")
    if skipped_ignored > 0:
        skip_parts.append(f"{skipped_ignored} ignored")
    return f" ({', '.join(skip_parts)} skipped)" if skip_parts else ""


def _format_staleness_text(result, show_diff: bool = False) -> str:
    """Format a StalenessResult for text output."""
    lines = []

    # Header (doc_target already includes section if present)
    lines.append(f"  {result.doc_target}")
    lines.append(f"    Code: {result.code_file}")

    # Dates
    if result.last_code_change:
        commit_info = f"({result.last_code_commit})" if result.last_code_commit else ""
        lines.append(f"    Last code change: {result.last_code_change} {commit_info}")
    if result.last_doc_update:
        lines.append(f"    Last doc update: {result.last_doc_update}")

    # Commits since (already limited by check_staleness_enriched)
    if result.commits_since:
        lines.append("    Commits since doc updated:")
        for commit in result.commits_since:
            lines.append(f"      {commit.sha} ({commit.date}) {commit.message}")

    # Symbol changes
    if result.symbols_added or result.symbols_removed:
        added = len(result.symbols_added)
        removed = len(result.symbols_removed)
        summary_parts = []
        if added:
            summary_parts.append(f"+{added} symbol{'s' if added != 1 else ''}")
        if removed:
            summary_parts.append(f"-{removed} symbol{'s' if removed != 1 else ''}")
        lines.append(f"    Changed: {', '.join(summary_parts)}")
        if result.symbols_added:
            lines.append(f"      Added: {', '.join(result.symbols_added)}")
        if result.symbols_removed:
            lines.append(f"      Removed: {', '.join(result.symbols_removed)}")

    # Diff
    if show_diff and result.code_diff:
        lines.append("    Diff:")
        for diff_line in result.code_diff.split("\n")[:30]:
            lines.append(f"      {diff_line}")

    lines.append("")  # Blank line between items
    return "\n".join(lines)


def cmd_check(args: argparse.Namespace) -> int:
    """Check if docs linked to staged/specified files are stale (CI/pre-commit mode)."""
    from menard.reviewed import find_review, is_review_valid

    # Check mutual exclusion early
    use_all = getattr(args, "all", False)
    staged_files_arg = getattr(args, "staged_files", None)

    if use_all and staged_files_arg:
        print("Error: --all and --staged-files are mutually exclusive")
        return 1

    repo_root = Path.cwd()
    config = load_config(repo_root)

    if config is None:
        print("⚠️  menard not configured")
        return 1

    # Build graph
    graph = build_menard_graph(repo_root, config)
    if not graph:
        print("⚠️  No links defined in .menard/links.toml")
        return 0

    import subprocess

    if staged_files_arg:
        files_to_check = staged_files_arg.split(",")
    elif use_all:
        # Get all git-tracked files
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            files_to_check = result.stdout.strip().split("\n")
            files_to_check = [f for f in files_to_check if f]
        except subprocess.CalledProcessError:
            print("⚠️  Not in a git repository")
            return 1
    else:
        # Get staged files from git (default pre-commit behavior)
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            files_to_check = result.stdout.strip().split("\n")
            files_to_check = [f for f in files_to_check if f]
        except subprocess.CalledProcessError:
            print("⚠️  Not in a git repository or no staged files")
            return 0

    if not files_to_check:
        print("No files to check")
        return 0

    # Build import graph if transitive checking enabled
    import_graph = {}
    if config.transitive_depth > 0:
        import_graph = build_import_graph(repo_root)

    # Parse diff options
    show_diff = getattr(args, "show_diff", False)
    diff_lines = getattr(args, "diff_lines", 30)
    if diff_lines != 30:  # Non-default value implies show_diff
        show_diff = True

    # Load links to check auto_generated and ignore flags
    links = load_links(repo_root)

    # Load reviews for checking reviewed state
    reviews = load_reviews(repo_root)

    # Check each file
    stale_results = []
    skipped_auto_generated = 0
    skipped_reviewed = 0
    skipped_ignored = 0

    for file_path in files_to_check:
        doc_targets = get_linked_docs(file_path, graph, config)

        if not doc_targets:
            continue

        # Get transitive imports
        transitive_imports = []
        if config.transitive_depth > 0 and file_path in import_graph:
            transitive_imports = list(import_graph[file_path])

        # Check staleness for each doc target (enriched)
        for doc_target_str in doc_targets:
            # Check if this specific code→doc relationship is auto-generated or ignored
            # Note: count only once even if both flags are set (avoid double-counting)
            is_auto_generated = False
            is_ignored = False
            normalized_file_path = normalize_path(file_path)
            normalized_doc_target = normalize_path(doc_target_str)
            for link in links:
                if normalize_path(link.code) == normalized_file_path and any(
                    normalize_path(str(doc)) == normalized_doc_target for doc in link.docs
                ):
                    if link.auto_generated:
                        is_auto_generated = True
                        skipped_auto_generated += 1
                    elif link.ignore:
                        # Only count as ignored if not already counted as auto_generated
                        is_ignored = True
                        skipped_ignored += 1
                    break

            if is_auto_generated or is_ignored:
                continue

            # Check if this has been reviewed and review is still valid
            review = find_review(reviews, file_path, doc_target_str)
            if review:
                current_commit = get_last_commit(repo_root, file_path)
                if current_commit and is_review_valid(review, current_commit[:SHA_SHORT_LENGTH]):
                    skipped_reviewed += 1
                    continue

            target = LinkTarget.parse(doc_target_str)
            result = check_staleness_enriched(
                repo_root,
                file_path,
                target,
                transitive_imports,
                include_diff=show_diff,
                max_diff_lines=diff_lines,
                auto_generated=False,  # We already filtered out auto-generated
            )

            if result.is_stale:
                stale_results.append(result)

    if not stale_results:
        # Check passes - but hint if there are stale docs elsewhere
        if args.format != "json":
            total_stale = _count_all_stale_docs(repo_root, config, graph, import_graph)
            skip_msg = _format_skip_message(
                skipped_auto_generated, skipped_reviewed, skipped_ignored
            )

            if total_stale > 0:
                print(f"✓ Staged files have up-to-date documentation{skip_msg}")
                print(
                    f"  Hint: {total_stale} stale doc(s) exist elsewhere. "
                    "Run 'menard list-stale' for full audit."
                )
            else:
                print(f"✓ All documentation is up to date{skip_msg}")
        else:
            result = {
                "stale": [],
                "skipped_auto_generated": skipped_auto_generated,
                "skipped_reviewed": skipped_reviewed,
                "skipped_ignored": skipped_ignored,
            }
            print(json.dumps(result, indent=2))
        return 0

    # Report stale docs
    if args.format == "json":
        stale_dicts = [r.to_dict(include_diff=show_diff) for r in stale_results]
        result = {
            "stale": stale_dicts,
            "skipped_auto_generated": skipped_auto_generated,
            "skipped_reviewed": skipped_reviewed,
            "skipped_ignored": skipped_ignored,
        }
        print(json.dumps(result, indent=2))
    else:
        skip_msg = _format_skip_message(skipped_auto_generated, skipped_reviewed, skipped_ignored)
        print(f"❌ Found {len(stale_results)} stale documentation targets{skip_msg}:\n")
        for result in stale_results:
            print(_format_staleness_text(result, show_diff=show_diff))

    if config.mode == "block":
        return 1

    return 0


def cmd_list_stale(args: argparse.Namespace) -> int:
    """List all stale documentation across the entire repository (audit mode)."""
    from menard.reviewed import find_review, is_review_valid

    repo_root = Path.cwd()
    config = load_config(repo_root)

    if config is None:
        print("⚠️  menard not configured")
        return 1

    graph = build_menard_graph(repo_root, config)
    import_graph = {}
    if config.transitive_depth > 0:
        import_graph = build_import_graph(repo_root)

    # Parse diff options
    show_diff = getattr(args, "show_diff", False)
    diff_lines = getattr(args, "diff_lines", 30)
    if diff_lines != 30:  # Non-default value implies show_diff
        show_diff = True

    # Load links to check auto_generated and ignore flags
    links = load_links(repo_root)

    # Load reviews for checking reviewed state
    reviews = load_reviews(repo_root)

    # Check all code files in graph
    stale_results = []
    skipped_auto_generated = 0
    skipped_reviewed = 0
    skipped_ignored = 0
    code_files = {k for k in graph if not any(k.endswith(ext) for ext in [".md", ".rst"])}

    for code_file in code_files:
        doc_targets = get_linked_docs(code_file, graph, config)

        transitive_imports = []
        if config.transitive_depth > 0 and code_file in import_graph:
            transitive_imports = list(import_graph[code_file])

        for doc_target_str in doc_targets:
            # Check if this specific code→doc relationship is auto-generated or ignored
            # Note: count only once even if both flags are set (avoid double-counting)
            is_auto_generated = False
            is_ignored = False
            normalized_code_file = normalize_path(code_file)
            normalized_doc_target = normalize_path(doc_target_str)
            for link in links:
                if normalize_path(link.code) == normalized_code_file and any(
                    normalize_path(str(doc)) == normalized_doc_target for doc in link.docs
                ):
                    if link.auto_generated:
                        is_auto_generated = True
                        skipped_auto_generated += 1
                    elif link.ignore:
                        # Only count as ignored if not already counted as auto_generated
                        is_ignored = True
                        skipped_ignored += 1
                    break

            if is_auto_generated or is_ignored:
                continue

            # Check if this has been reviewed and review is still valid
            review = find_review(reviews, code_file, doc_target_str)
            if review:
                current_commit = get_last_commit(repo_root, code_file)
                if current_commit and is_review_valid(review, current_commit[:SHA_SHORT_LENGTH]):
                    skipped_reviewed += 1
                    continue

            target = LinkTarget.parse(doc_target_str)
            result = check_staleness_enriched(
                repo_root,
                code_file,
                target,
                transitive_imports,
                include_diff=show_diff,
                max_diff_lines=diff_lines,
                auto_generated=False,  # We already filtered out auto-generated
            )

            if result.is_stale:
                stale_results.append(result)

    if args.format == "json":
        stale_dicts = [r.to_dict(include_diff=show_diff) for r in stale_results]
        result = {
            "stale": stale_dicts,
            "skipped_auto_generated": skipped_auto_generated,
            "skipped_reviewed": skipped_reviewed,
            "skipped_ignored": skipped_ignored,
        }
        print(json.dumps(result, indent=2))
    elif args.format == "paths":
        # Just print unique doc paths
        doc_paths = {r.doc_target.split("#")[0] for r in stale_results}
        for doc_path in sorted(doc_paths):
            print(doc_path)
    else:
        skip_msg = _format_skip_message(skipped_auto_generated, skipped_reviewed, skipped_ignored)
        if not stale_results:
            print(f"✓ No stale documentation{skip_msg}")
        else:
            print(f"Found {len(stale_results)} stale documentation targets{skip_msg}:\n")
            for result in stale_results:
                print(_format_staleness_text(result, show_diff=show_diff))

    return 0


def cmd_affected_docs(args: argparse.Namespace) -> int:
    """Show docs affected by file changes."""
    repo_root = Path.cwd()
    config = load_config(repo_root)

    if config is None:
        print("⚠️  menard not configured")
        return 1

    graph = build_menard_graph(repo_root, config)
    files = args.files.split(",")

    affected = {}
    for file_path in files:
        doc_targets = get_linked_docs(file_path.strip(), graph, config)
        if doc_targets:
            affected[file_path] = list(doc_targets)

    if args.format == "json":
        print(json.dumps({"affected_docs": affected}, indent=2))
    elif args.format == "paths":
        all_docs = set()
        for docs in affected.values():
            all_docs.update(docs)
        for doc in sorted(all_docs):
            print(doc)
    else:
        if not affected:
            print("No documentation affected")
        else:
            for code_file, docs in affected.items():
                print(f"{code_file}:")
                for doc in docs:
                    print(f"  → {doc}")

    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    """Report documentation coverage."""
    repo_root = Path.cwd()
    config = load_config(repo_root)

    if config is None:
        print("⚠️  menard not configured")
        return 1

    from menard.graph import _match_globs

    # Find all code files that should have links
    code_files = []
    for file_path in repo_root.rglob("*"):
        if not file_path.is_file():
            continue
        if not _match_globs(file_path, config.require_links, repo_root):
            continue
        if _match_globs(file_path, config.exempt, repo_root):
            continue
        code_files.append(str(file_path.relative_to(repo_root)))

    # Load links
    links = load_links(repo_root)
    linked_code_files = {link.code for link in links}

    # Calculate coverage
    total = len(code_files)
    documented = len([f for f in code_files if f in linked_code_files])
    undocumented = [f for f in code_files if f not in linked_code_files]

    coverage = documented / total if total > 0 else 0.0

    if args.format == "json":
        result = {
            "coverage": coverage,
            "total_files": total,
            "documented_files": documented,
            "undocumented_files": undocumented,
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"Documentation Coverage: {coverage:.1%}")
        print(f"  Total code files: {total}")
        print(f"  Documented: {documented}")
        print(f"  Undocumented: {len(undocumented)}")

        if undocumented and len(undocumented) <= 10:
            print("\nUndocumented files:")
            for f in undocumented:
                print(f"  {f}")
        elif undocumented:
            print(f"\nUndocumented files (showing first 10 of {len(undocumented)}):")
            for f in undocumented[:10]:
                print(f"  {f}")

    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show information about a file's links."""
    repo_root = Path.cwd()
    file_path = args.file

    links = load_links(repo_root)
    graph = build_menard_graph(repo_root, None)  # type: ignore

    # Find links for this file
    related_links = []
    for link in links:
        if link.code == file_path or any(str(doc) == file_path for doc in link.docs):
            related_links.append(link)

    if args.format == "json":
        result = {
            "file": file_path,
            "links": [
                {"code": link.code, "docs": [str(d) for d in link.docs]} for link in related_links
            ],
            "connected_files": list(graph.get(file_path, set())),
        }
        print(json.dumps(result, indent=2))
    else:
        if not related_links:
            print(f"No links found for {file_path}")
        else:
            print(f"Links for {file_path}:\n")
            for link in related_links:
                print(f"  Code: {link.code}")
                for doc in link.docs:
                    print(f"    → {doc}")
                print()

    return 0


def cmd_clear_cache(args: argparse.Namespace) -> int:
    """Clear import graph cache."""
    repo_root = Path.cwd()
    cache_dir = repo_root / ".menard" / "cache"

    if cache_dir.exists():
        import shutil

        shutil.rmtree(cache_dir)
        print(f"✓ Cleared cache at {cache_dir}")
    else:
        print("No cache found")

    return 0


def cmd_check_protected(args: argparse.Namespace) -> int:
    """Check for violations in staged or all tracked files."""
    import subprocess

    repo_root = Path.cwd()
    use_all = getattr(args, "all", False)

    # Get files to check
    if use_all:
        # Get all git-tracked files
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            print("Error: Not in a git repository")
            return 1
        files_to_check = [f for f in result.stdout.strip().split("\n") if f]
        if not files_to_check:
            print("No tracked files")
            return 0
    else:
        # Get staged files (default pre-commit behavior)
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            print("Error: Not in a git repository")
            return 1
        files_to_check = [f for f in result.stdout.strip().split("\n") if f]
        if not files_to_check:
            print("No staged files")
            return 0

    # Load protection rules
    rules = load_donttouch(repo_root)
    if not rules:
        print("No .menard/donttouch file found")
        return 0

    # Check for violations
    violations = check_protections(repo_root, files_to_check, rules)

    if not violations:
        print("✓ No protection violations")
        return 0

    print(f"⛔ Found {len(violations)} violation(s):")
    for v in violations:
        if v.section:
            print(f"  {v.file}#{v.section}: {v.reason}")
        else:
            print(f"  {v.file}: {v.reason}")

    return 1


def cmd_list_protected(args: argparse.Namespace) -> int:
    """List all protection rules."""
    repo_root = Path.cwd()

    rules = load_donttouch(repo_root)
    if not rules:
        print("No .menard/donttouch file found")
        return 0

    # File patterns
    if rules.file_pattern_strings:
        print("Protected files:")
        for pattern in rules.file_pattern_strings:
            print(f"  {pattern}")

    # Section protections
    if rules.section_protections:
        print("\nProtected sections:")
        for file, sections in rules.section_protections.items():
            for section in sections:
                print(f"  {file}#{section}")

    # Scoped literals
    if rules.scoped_literals:
        print("\nFile-scoped literals:")
        for file, literals in rules.scoped_literals.items():
            for literal in literals:
                print(f'  {file}: "{literal}"')

    # Global literals
    if rules.global_literals:
        print("\nGlobal literals:")
        for literal in rules.global_literals:
            print(f'  "{literal}"')

    return 0


def _get_bundled_skills() -> dict:
    """Get skills shipped with the menard package.

    Returns:
        Dict mapping skill name to Traversable object.
    """
    try:
        skills_pkg = files("menard").joinpath("skills")
        return {
            p.name.removesuffix(".md"): p for p in skills_pkg.iterdir() if p.name.endswith(".md")
        }
    except (FileNotFoundError, TypeError):
        return {}


def _get_local_skills(repo_root: Path) -> dict:
    """Get project-local skills from .claude/skills/.

    Returns:
        Dict mapping skill name to Path object.
    """
    skills_dir = repo_root / ".claude" / "skills"
    if not skills_dir.exists():
        return {}
    return {p.stem: p for p in skills_dir.glob("*.md")}


def _parse_skill_content(content: str, name: str) -> dict:
    """Extract title and description from skill content."""
    lines = content.strip().split("\n")
    title = name
    description = ""

    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip()
            break
        elif not description and line.strip() and not line.startswith("#"):
            description = line.strip()
            break

    return {
        "title": title,
        "description": description[:100] + "..." if len(description) > 100 else description,
    }


def cmd_skills(args: argparse.Namespace) -> int:
    """List available Claude Code skills (bundled and local)."""
    repo_root = Path.cwd()

    # Handle --copy flag first
    copy_name = getattr(args, "copy", None)
    if copy_name:
        return _copy_skill(repo_root, copy_name, getattr(args, "force", False))

    # Gather skills from both sources (local overrides bundled)
    bundled = _get_bundled_skills()
    local = _get_local_skills(repo_root)

    # Merge: bundled first, then local overwrites
    all_skills_sources: dict[str, tuple[Any, str]] = {}
    for name, source in bundled.items():
        all_skills_sources[name] = (source, "bundled")
    for name, source in local.items():
        all_skills_sources[name] = (source, "local")

    if not all_skills_sources:
        if args.format == "json":
            print(json.dumps({"skills": []}))
        else:
            print("No skills found.")
            print("\nSkills are Claude Code extensions that provide specialized workflows.")
            print("To add skills, create .claude/skills/<name>.md files.")
        return 0

    # Build skill list
    skills = []
    for name in sorted(all_skills_sources.keys()):
        source, source_type = all_skills_sources[name]
        content = source.read_text()
        parsed = _parse_skill_content(content, name)

        skill_info = {
            "name": name,
            "title": parsed["title"],
            "description": parsed["description"],
            "source": source_type,
        }

        # Add path for local skills
        if source_type == "local":
            skill_info["path"] = str(Path(source).relative_to(repo_root))

        skills.append(skill_info)

    if args.format == "json":
        print(json.dumps({"skills": skills}, indent=2))
    else:
        print("Available Claude Code skills:\n")
        for skill in skills:
            source_indicator = f"[{skill['source']}]"
            print(f"  {skill['name']} {source_indicator}")
            if skill["description"]:
                print(f"    {skill['description']}")
            print()
        print("To use in Claude Code:")
        print("  Invoke via /skill-name or ask Claude to use the skill")
        print("\nTo customize a bundled skill:")
        print("  menard skills --copy <name>")

    return 0


def _copy_skill(repo_root: Path, skill_name: str, force: bool = False) -> int:
    """Copy a bundled skill to the local .claude/skills/ directory."""
    bundled = _get_bundled_skills()

    if skill_name not in bundled:
        print(f"Skill '{skill_name}' not found in bundled skills.")
        print(f"Available bundled skills: {', '.join(sorted(bundled.keys()))}")
        return 1

    # Create local skills directory if needed
    local_dir = repo_root / ".claude" / "skills"
    local_dir.mkdir(parents=True, exist_ok=True)

    # Check if local skill already exists
    local_path = local_dir / f"{skill_name}.md"
    if local_path.exists() and not force:
        print(f"Local skill already exists: {local_path}")
        print("Use --force to overwrite.")
        return 1

    # Copy content
    content = bundled[skill_name].read_text()
    local_path.write_text(content)

    print(f"Copied '{skill_name}' to {local_path}")
    print("You can now customize this skill locally.")
    return 0


def cmd_fix_mark_reviewed(args: argparse.Namespace) -> int:
    """Mark a code→doc relationship as reviewed."""
    from datetime import datetime, timezone

    repo_root = Path.cwd()

    # Normalize the code path for consistent handling
    code_path = normalize_path(args.code)

    # Validate that the code file exists
    code_file_path = repo_root / code_path
    if not code_file_path.exists():
        if args.format == "json":
            print(json.dumps({"error": f"Code file not found: {code_path}"}))
        else:
            print(f"❌ Code file not found: {code_path}")
        return 1

    # Get current commit for code file
    current_commit = get_last_commit(repo_root, code_path)
    if not current_commit:
        if args.format == "json":
            print(json.dumps({"error": f"Could not get commit for {code_path}"}))
        else:
            print(f"❌ Could not get commit for {code_path}")
            print("  (File may not be tracked by git)")
        return 1

    # Normalize the doc target as well
    doc_target = normalize_path(args.doc)

    # Create and save review
    review = Review(
        code_file=code_path,
        doc_target=doc_target,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        code_commit_at_review=current_commit[:SHA_SHORT_LENGTH],
        reviewed_by=args.reviewed_by,
    )
    save_review(repo_root, review)

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": "created",
                    "review": {
                        "code_file": review.code_file,
                        "doc_target": review.doc_target,
                        "code_commit_at_review": review.code_commit_at_review,
                        "reviewed_by": review.reviewed_by,
                    },
                }
            )
        )
    else:
        print(f"✓ Marked {code_path} → {doc_target} as reviewed")
        print(f"  Commit: {review.code_commit_at_review}")

    return 0


def cmd_fix_ignore(args: argparse.Namespace) -> int:
    """Add ignore=true to a link in links.toml."""
    repo_root = Path.cwd()

    links = load_links(repo_root)
    if not links:
        if args.format == "json":
            print(json.dumps({"error": "No links found"}))
        else:
            print("❌ No links found in .menard/links.toml")
        return 1

    # Find the matching link
    found = False
    for link in links:
        if link.code == args.code and any(str(d) == args.doc for d in link.docs):
            link.ignore = True
            found = True
            break

    if not found:
        if args.format == "json":
            print(json.dumps({"error": f"Link not found: {args.code} → {args.doc}"}))
        else:
            print(f"❌ Link not found: {args.code} → {args.doc}")
        return 1

    # Write back to links.toml
    links_file = repo_root / ".menard" / "links.toml"
    links_file.write_text(generate_links_toml(links))

    if args.format == "json":
        print(json.dumps({"status": "ignored", "code": args.code, "doc": args.doc}))
    else:
        print(f"✓ Added ignore=true to {args.code} → {args.doc}")

    return 0


def cmd_clean_reviewed(args: argparse.Namespace) -> int:
    """Clean up reviewed state."""
    repo_root = Path.cwd()

    removed = clean_reviews(repo_root, remove_all=args.all)

    if args.format == "json":
        print(json.dumps({"removed": removed}))
    else:
        if removed > 0:
            print(f"✓ Removed {removed} review(s)")
        else:
            print("No reviews to clean")

    return 0


def _open_editor_at_line(file_path: Path, line: int) -> bool:
    """Open $EDITOR at the specified line. Returns True if successful."""
    import os
    import shlex
    import subprocess as sp

    editor_env = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))

    # Parse compound editor commands like "code --wait" or "vim -u NONE"
    try:
        editor_parts = shlex.split(editor_env)
    except ValueError:
        # Invalid shell syntax, try as single command
        editor_parts = [editor_env]

    if not editor_parts:
        editor_parts = ["vi"]

    # Get the basename of the editor for detection
    editor_basename = os.path.basename(editor_parts[0])

    # Common editor line number syntax (using exact basename matching)
    vim_editors = {"vim", "vi", "nvim", "neovim", "gvim", "mvim"}
    vscode_editors = {"code", "code-insiders", "codium", "vscodium"}
    plus_line_editors = {"nano", "emacs", "emacsclient", "pico", "joe", "jed"}

    if editor_basename in vim_editors:
        cmd = editor_parts + [f"+{line}", str(file_path)]
    elif editor_basename in vscode_editors:
        cmd = editor_parts + ["--goto", f"{file_path}:{line}"]
    elif editor_basename in plus_line_editors:
        cmd = editor_parts + [f"+{line}", str(file_path)]
    else:
        # Generic fallback - just open the file
        cmd = editor_parts + [str(file_path)]

    try:
        result = sp.run(cmd)
        return result.returncode == 0
    except Exception as e:
        print(f"  ❌ Could not open editor: {e}")
        return False


def cmd_fix_interactive(args: argparse.Namespace) -> int:
    """Interactive mode to resolve stale documentation."""
    from datetime import datetime, timezone

    from menard.reviewed import find_review, is_review_valid

    # Check if stdin is a TTY (interactive terminal)
    if not sys.stdin.isatty():
        print("❌ Interactive mode requires a terminal (TTY)")
        print("  For non-interactive use, try:")
        print("    menard fix-mark-reviewed --code FILE --doc TARGET")
        print("    menard fix-ignore --code FILE --doc TARGET")
        return 1

    repo_root = Path.cwd()
    config = load_config(repo_root)

    if config is None:
        print("⚠️  menard not configured")
        return 1

    graph = build_menard_graph(repo_root, config)
    if not graph:
        print("⚠️  No links defined in .menard/links.toml")
        return 0

    import_graph = {}
    if config.transitive_depth > 0:
        import_graph = build_import_graph(repo_root)

    # Load links and reviews
    links = load_links(repo_root)
    reviews = load_reviews(repo_root)

    # Collect stale items (similar to list-stale but without skipping reviewed)
    stale_items = []
    code_files = {k for k in graph if not any(k.endswith(ext) for ext in [".md", ".rst"])}

    for code_file in code_files:
        doc_targets = get_linked_docs(code_file, graph, config)

        transitive_imports = []
        if config.transitive_depth > 0 and code_file in import_graph:
            transitive_imports = list(import_graph[code_file])

        for doc_target_str in doc_targets:
            # Skip auto-generated and ignored
            skip_this = False
            for link in links:
                if (
                    link.code == code_file
                    and any(str(doc) == doc_target_str for doc in link.docs)
                    and (link.auto_generated or link.ignore)
                ):
                    skip_this = True
                    break
            if skip_this:
                continue

            # Skip if already reviewed and valid
            review = find_review(reviews, code_file, doc_target_str)
            if review:
                current_commit = get_last_commit(repo_root, code_file)
                if current_commit and is_review_valid(review, current_commit[:SHA_SHORT_LENGTH]):
                    continue

            target = LinkTarget.parse(doc_target_str)
            result = check_staleness_enriched(
                repo_root,
                code_file,
                target,
                transitive_imports,
                include_diff=False,
                auto_generated=False,
            )

            if result.is_stale:
                stale_items.append(result)

    if not stale_items:
        print("✓ No stale documentation to fix")
        return 0

    print(f"Found {len(stale_items)} stale documentation target(s)\n")

    # Process each stale item interactively
    for i, item in enumerate(stale_items, 1):
        print(f"[{i}/{len(stale_items)}] Stale: {item.doc_target}")
        print(f"  Code: {item.code_file}")
        if item.symbols_added or item.symbols_removed:
            changes = []
            if item.symbols_added:
                changes.append(f"+{', '.join(item.symbols_added)}")
            if item.symbols_removed:
                changes.append(f"-{', '.join(item.symbols_removed)}")
            print(f"  Changed: {', '.join(changes)}")
        print()
        print("  [u] Update section (opens editor)")
        print("  [m] Mark as reviewed")
        print("  [s] Skip")
        print("  [i] Add to ignore list")
        print()

        while True:
            try:
                choice = input("  Choice: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n\nAborted.")
                return 1

            if choice == "u":
                # Open editor at the section
                doc_path = repo_root / item.doc_target.split("#")[0]
                line = item.line_range[0] if item.line_range else 1
                if _open_editor_at_line(doc_path, line):
                    print("  ✓ Editor closed")
                    # After editing, mark as reviewed
                    current_commit = get_last_commit(repo_root, item.code_file)
                    if current_commit:
                        review = Review(
                            code_file=item.code_file,
                            doc_target=item.doc_target,
                            reviewed_at=datetime.now(timezone.utc).isoformat(),
                            code_commit_at_review=current_commit[:SHA_SHORT_LENGTH],
                            reviewed_by="user",
                        )
                        save_review(repo_root, review)
                        print("  ✓ Marked as reviewed")
                break

            elif choice == "m":
                # Mark as reviewed
                current_commit = get_last_commit(repo_root, item.code_file)
                if current_commit:
                    review = Review(
                        code_file=item.code_file,
                        doc_target=item.doc_target,
                        reviewed_at=datetime.now(timezone.utc).isoformat(),
                        code_commit_at_review=current_commit[:SHA_SHORT_LENGTH],
                        reviewed_by="user",
                    )
                    save_review(repo_root, review)
                    print("  ✓ Marked as reviewed")
                else:
                    print("  ❌ Could not get commit for code file")
                break

            elif choice == "s":
                print("  → Skipped")
                break

            elif choice == "i":
                # Add ignore=true to the link
                for link in links:
                    if link.code == item.code_file and any(
                        str(d) == item.doc_target for d in link.docs
                    ):
                        link.ignore = True
                        break
                links_file = repo_root / ".menard" / "links.toml"
                links_file.write_text(generate_links_toml(links))
                print("  ✓ Added to ignore list")
                break

            else:
                print("  Invalid choice. Enter u, m, s, or i.")

        print()

    print("Done!")
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="menard: Keep code and documentation in sync",
        epilog="Tip: Run 'menard skills' to see available Claude Code skills.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # init
    subparsers.add_parser("init", help="Initialize menard configuration")

    # migrate
    subparsers.add_parser("migrate", help="Migrate from inline comments to TOML (legacy)")

    # validate-links
    subparsers.add_parser("validate-links", help="Validate all link references")

    # bootstrap
    bootstrap_parser = subparsers.add_parser("bootstrap", help="Auto-generate links")
    bootstrap_parser.add_argument("--apply", action="store_true", help="Apply proposed links")

    # check
    check_parser = subparsers.add_parser(
        "check",
        help="Check staged files for doc freshness (CI/pre-commit)",
        description=(
            "Check if documentation linked to staged files is stale. "
            "Use this for pre-commit hooks and CI pipelines. "
            "To audit ALL stale docs regardless of staged changes, use 'list-stale'."
        ),
    )
    check_parser.add_argument("--staged-files", help="Comma-separated list of files")
    check_parser.add_argument(
        "--all",
        action="store_true",
        help="Check all git-tracked files (for manual audits/CI)",
    )
    check_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )
    check_parser.add_argument(
        "--show-diff", action="store_true", help="Include git diff of changed code"
    )
    check_parser.add_argument(
        "--diff-lines",
        type=int,
        default=30,
        help="Max lines of diff to show (default: 30, implies --show-diff)",
    )

    # list-stale
    stale_parser = subparsers.add_parser(
        "list-stale",
        help="List ALL stale docs regardless of recent changes (audit)",
        description=(
            "Scan the entire repository and list all stale documentation. "
            "Use this for audits and periodic reviews. "
            "For pre-commit/CI checks on staged files only, use 'check'."
        ),
    )
    stale_parser.add_argument(
        "--format", choices=["text", "paths", "json"], default="text", help="Output format"
    )
    stale_parser.add_argument(
        "--show-diff", action="store_true", help="Include git diff of changed code"
    )
    stale_parser.add_argument(
        "--diff-lines",
        type=int,
        default=30,
        help="Max lines of diff to show (default: 30, implies --show-diff)",
    )

    # affected-docs
    affected_parser = subparsers.add_parser("affected-docs", help="Show affected docs")
    affected_parser.add_argument("--files", required=True, help="Comma-separated file paths")
    affected_parser.add_argument(
        "--format", choices=["text", "paths", "json"], default="text", help="Output format"
    )

    # coverage
    coverage_parser = subparsers.add_parser("coverage", help="Report documentation coverage")
    coverage_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    # info
    info_parser = subparsers.add_parser("info", help="Show file link information")
    info_parser.add_argument("file", help="File to analyze")
    info_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    # clear-cache
    subparsers.add_parser("clear-cache", help="Clear import graph cache")

    # check-protected
    check_protected_parser = subparsers.add_parser(
        "check-protected", help="Check staged files for protection violations"
    )
    check_protected_parser.add_argument(
        "--all",
        action="store_true",
        help="Check all git-tracked files (for manual audits/CI)",
    )

    # list-protected
    subparsers.add_parser("list-protected", help="List all protection rules")

    # skills
    skills_parser = subparsers.add_parser(
        "skills",
        help="List available Claude Code skills",
        description="Show Claude Code skills (bundled with menard and project-local).",
    )
    skills_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )
    skills_parser.add_argument(
        "--copy",
        metavar="NAME",
        help="Copy a bundled skill to .claude/skills/ for customization",
    )
    skills_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing local skill when using --copy",
    )

    # fix (interactive)
    subparsers.add_parser(
        "fix",
        help="Interactive mode to resolve stale documentation",
        description="Interactively resolve stale documentation. "
        "For each stale item, choose to update, mark as reviewed, skip, or ignore.",
    )

    # fix mark-reviewed
    fix_mark_parser = subparsers.add_parser(
        "fix-mark-reviewed",
        help="Mark a code→doc relationship as reviewed",
        description="Mark documentation as reviewed at current code commit. "
        "The review will be valid until the code file changes.",
    )
    fix_mark_parser.add_argument("--code", required=True, help="Code file path")
    fix_mark_parser.add_argument("--doc", required=True, help="Doc target (file#section)")
    fix_mark_parser.add_argument(
        "--reviewed-by", default="user", help="Reviewer name (default: user)"
    )
    fix_mark_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    # fix ignore
    fix_ignore_parser = subparsers.add_parser(
        "fix-ignore",
        help="Permanently ignore a code→doc relationship",
        description="Add ignore=true to a link in links.toml. "
        "This permanently skips staleness checks for this relationship.",
    )
    fix_ignore_parser.add_argument("--code", required=True, help="Code file path")
    fix_ignore_parser.add_argument("--doc", required=True, help="Doc target (file#section)")
    fix_ignore_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    # clean-reviewed
    clean_reviewed_parser = subparsers.add_parser(
        "clean-reviewed",
        help="Clean up reviewed state",
        description="Remove orphaned reviews (for deleted files) or all reviews.",
    )
    clean_reviewed_parser.add_argument("--all", action="store_true", help="Remove all reviews")
    clean_reviewed_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "init": cmd_init,
        "migrate": cmd_migrate,
        "validate-links": cmd_validate_links,
        "bootstrap": cmd_bootstrap,
        "check": cmd_check,
        "list-stale": cmd_list_stale,
        "affected-docs": cmd_affected_docs,
        "coverage": cmd_coverage,
        "info": cmd_info,
        "clear-cache": cmd_clear_cache,
        "check-protected": cmd_check_protected,
        "list-protected": cmd_list_protected,
        "skills": cmd_skills,
        "fix": cmd_fix_interactive,
        "fix-mark-reviewed": cmd_fix_mark_reviewed,
        "fix-ignore": cmd_fix_ignore,
        "clean-reviewed": cmd_clean_reviewed,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
