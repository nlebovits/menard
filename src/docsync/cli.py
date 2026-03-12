"""Command-line interface for docsync."""

import argparse
import sys
from pathlib import Path

from docsync.coverage import generate_coverage
from docsync.graph import parse_links
from docsync.hook import run_hook

# Comment syntax mapping for different file extensions
COMMENT_STYLES = {
    ".py": "# docsync: {paths}",
    ".js": "// docsync: {paths}",
    ".ts": "// docsync: {paths}",
    ".jsx": "// docsync: {paths}",
    ".tsx": "// docsync: {paths}",
    ".go": "// docsync: {paths}",
    ".rs": "// docsync: {paths}",
    ".c": "// docsync: {paths}",
    ".h": "// docsync: {paths}",
    ".cpp": "// docsync: {paths}",
    ".rb": "# docsync: {paths}",
    ".sh": "# docsync: {paths}",
    ".sql": "-- docsync: {paths}",
    ".lua": "-- docsync: {paths}",
    ".md": "<!-- docsync: {paths} -->",
    ".html": "<!-- docsync: {paths} -->",
}


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize docsync in a repository."""
    repo_root = Path.cwd()
    pyproject = repo_root / "pyproject.toml"

    # Check if pyproject.toml exists
    if not pyproject.exists():
        print("Error: pyproject.toml not found in current directory")
        return 1

    # Check if [tool.docsync] section exists
    content = pyproject.read_text()
    if "[tool.docsync]" not in content:
        # Append default config
        with open(pyproject, "a") as f:
            f.write(
                '\n\n[tool.docsync]\nmode = "block"\ntransitive_depth = 1\n'
                "enforce_symmetry = true\nrequire_links = []\nexempt = []\n"
                'doc_paths = ["docs/**/*.md", "README.md"]\n'
            )
        print("Added [tool.docsync] section to pyproject.toml")

    # Set up git hook
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        print("Warning: .git directory not found. Skipping hook installation.")
        return 0

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_file = hooks_dir / "pre-commit"

    # Check if hook already contains docsync
    if hook_file.exists():
        existing = hook_file.read_text()
        if "docsync" in existing:
            print("docsync hook already installed")
        else:
            # Append to existing hook
            with open(hook_file, "a") as f:
                f.write("\n# docsync\ndocsync check\n")
            print("Appended docsync check to existing pre-commit hook")
    else:
        # Create new hook
        hook_file.write_text("#!/bin/sh\ndocsync check\n")
        hook_file.chmod(0o755)
        print("Created pre-commit hook")

    print("docsync initialized successfully!")
    print()
    print("ACTION REQUIRED: Configure which files need documentation")
    print()
    print("Current configuration has require_links = [] (empty)")
    print("You must specify which files require documentation links.")
    print()
    print("Edit [tool.docsync] in pyproject.toml and add patterns:")
    print()
    print("  For Python projects:")
    print('    require_links = ["src/**/*.py"]')
    print()
    print("  For JavaScript/TypeScript projects:")
    print('    require_links = ["lib/**/*.js", "lib/**/*.ts"]')
    print()
    print("  For Rust projects:")
    print('    require_links = ["src/**/*.rs", "crates/**/*.rs"]')
    print()
    print("After updating require_links, run:")
    print("  - 'docsync bootstrap' to find files needing docs")
    print("  - 'docsync coverage' to see current coverage")
    print()
    print("RECOMMENDED: Add .docsync/ to .gitignore (cache directory)")
    print()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Run the pre-commit hook check."""
    from docsync.config import load_config

    repo_root = Path.cwd()
    config = load_config(repo_root)

    if config is None:
        print("⚠️  docsync not configured. Run 'docsync init' to set up.")
        return 0  # Exit 0 so git commit isn't blocked

    if not config.require_links:
        print("ACTION REQUIRED: require_links is empty")
        print()
        print("Configuration has require_links = [] (empty).")
        print("No files are being checked for documentation links.")
        print()
        print("Fix by editing [tool.docsync] in pyproject.toml:")
        print('  require_links = ["src/**/*.py"]  # For Python projects')
        print()
        print("Commit allowed to proceed (configuration issue, not code issue).")
        print()
        return 0  # Exit 0 so git commit isn't blocked

    # If staged_files provided (for testing), use them
    staged_files = args.staged_files.split(",") if args.staged_files else None

    result = run_hook(repo_root, staged_files=staged_files)

    # --create-todo flag: Generate .docsync-todo.json
    if getattr(args, "create_todo", False) and not result.passed:
        import json

        todos = []

        # Add direct dependencies
        for code, docs in result.direct_missing.items():
            for doc in docs:
                todos.append(
                    {
                        "type": "direct",
                        "code_file": code,
                        "doc_file": doc,
                        "action": f"Update {doc} (linked to {code})",
                    }
                )

        # Add transitive dependencies
        for code, dependents in result.transitive_missing.items():
            for dep, dep_docs in dependents.items():
                for doc in dep_docs:
                    todos.append(
                        {
                            "type": "transitive",
                            "changed_file": code,
                            "affected_file": dep,
                            "doc_file": doc,
                            "action": f"Update {doc} (linked to {dep}, affected by {code})",
                        }
                    )

        todo_file = repo_root / ".docsync-todo.json"
        with open(todo_file, "w") as f:
            json.dump({"todos": todos}, f, indent=2)

        print(f"\nCreated {todo_file} with {len(todos)} tasks")

    # JSON output format
    if getattr(args, "format", "text") == "json":
        import json

        output = {
            "status": "passed" if result.passed else "blocked",
            "direct_deps": [
                {"code": code, "docs": list(docs)} for code, docs in result.direct_missing.items()
            ],
            "transitive_deps": [
                {
                    "changed_file": code,
                    "affects": [
                        {"code": dep, "docs": list(dep_docs)}
                        for dep, dep_docs in dependents.items()
                    ],
                }
                for code, dependents in result.transitive_missing.items()
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        print(result.message)

    return 0 if result.passed else 1


def cmd_coverage(args: argparse.Namespace) -> int:
    """Generate coverage report."""
    from docsync.config import load_config

    repo_root = Path.cwd()
    config = load_config(repo_root)

    if config is None:
        print("⚠️  docsync not configured. Run 'docsync init' to set up.")
        return 1

    if not config.require_links:
        print("ACTION REQUIRED: Cannot generate coverage - require_links is empty")
        print()
        print("Configuration has require_links = [] (empty).")
        print("No files are configured to require documentation links.")
        print()
        print("NEXT STEPS:")
        print("  1. Edit [tool.docsync] in pyproject.toml")
        print("  2. Add glob patterns to require_links")
        print()
        print("Examples:")
        print('  require_links = ["src/**/*.py"]              # Python')
        print('  require_links = ["lib/**/*.js", "lib/**/*.ts"]  # JavaScript/TypeScript')
        print('  require_links = ["crates/**/*.rs"]           # Rust')
        print()
        print("Then run 'docsync coverage' again.")
        print()
        return 1

    output_format = getattr(args, "format", "text")

    if output_format == "json":
        import json

        from docsync.coverage import _detect_stale_docs
        from docsync.graph import build_docsync_graph

        graph = build_docsync_graph(repo_root, config)
        stale_docs = _detect_stale_docs(graph, repo_root, config)

        # Build links from graph (only code files with doc links)
        from docsync.coverage import _is_doc_file

        links = []
        for file_path, linked_files in graph.items():
            if not _is_doc_file(file_path, config):
                # This is a code file
                doc_links = [f for f in linked_files if _is_doc_file(f, config)]
                if doc_links:
                    links.append({"code": file_path, "docs": doc_links})

        output = {
            "links": links,
            "stale_docs": [
                {
                    "doc_file": doc_file,
                    "code_file": code_file,
                    "doc_timestamp": doc_ts,
                    "code_timestamp": code_ts,
                    "days_stale": days_stale,
                    "severity": (
                        "critical"
                        if days_stale > 90
                        else "warning"
                        if days_stale > 30
                        else "recent"
                    ),
                }
                for doc_file, code_file, doc_ts, code_ts, days_stale in stale_docs
            ],
            "summary": {
                "total_links": len(links),
                "stale_count": len(stale_docs),
                "critical_stale": sum(1 for _, _, _, _, days in stale_docs if days > 90),
                "warning_stale": sum(1 for _, _, _, _, days in stale_docs if 30 < days <= 90),
            },
        }
        print(json.dumps(output, indent=2))
    else:
        report = generate_coverage(repo_root)

        output = report.markdown
        if args.output:
            Path(args.output).write_text(output)
            print(f"Coverage report written to {args.output}")
        else:
            print(output)

    return 0


def cmd_add_link(args: argparse.Namespace) -> int:
    """Add a bidirectional link between files (supports globs for code_file)."""
    repo_root = Path.cwd()

    # Check if code_file is a glob pattern
    if "*" in args.code_file:
        return _add_link_glob(args, repo_root)

    # Single file mode
    code_file = (repo_root / args.code_file).resolve()
    doc_file = (repo_root / args.doc_file).resolve()

    # Verify both files exist
    if not code_file.exists():
        print(f"Error: {code_file} does not exist")
        return 1
    if not doc_file.exists():
        print(f"Error: {doc_file} does not exist")
        return 1

    # Get relative paths from repo root
    try:
        code_rel = str(code_file.relative_to(repo_root.resolve()))
        doc_rel = str(doc_file.relative_to(repo_root.resolve()))
    except ValueError:
        print("Error: Files must be within the repository")
        return 1

    # Parse existing links
    code_links = parse_links(code_file, repo_root)
    doc_links = parse_links(doc_file, repo_root)

    # Check if link already exists
    if doc_rel in code_links and code_rel in doc_links:
        print(f"Link already exists: {code_rel} ↔ {doc_rel}")
        return 0

    # Dry run mode - just show what would be done
    if getattr(args, "dry_run", False):
        print("DRY RUN - No files will be modified")
        print()
        if doc_rel not in code_links:
            print(f"Would add to {code_rel}:")
            print(f"  {_preview_link_addition(code_file, doc_rel, code_links)}")
            print()
        if code_rel not in doc_links:
            print(f"Would add to {doc_rel}:")
            print(f"  {_preview_link_addition(doc_file, code_rel, doc_links)}")
            print()
        return 0

    # Add link to code file
    if doc_rel not in code_links:
        _add_link_to_file(code_file, doc_rel, code_links)
        print(f"Added link to {code_file}: {doc_rel}")

    # Add link to doc file
    if code_rel not in doc_links:
        _add_link_to_file(doc_file, code_rel, doc_links)
        print(f"Added link to {doc_file}: {code_rel}")

    return 0


def _add_link_glob(args: argparse.Namespace, repo_root: Path) -> int:
    """Handle glob patterns in add-link command."""
    from docsync.graph import parse_links

    # Expand glob pattern
    code_files = list(repo_root.glob(args.code_file))

    if not code_files:
        print(f"Error: No files match pattern '{args.code_file}'")
        return 1

    # Verify doc file exists
    doc_file = (repo_root / args.doc_file).resolve()
    if not doc_file.exists():
        print(f"Error: {doc_file} does not exist")
        return 1

    doc_rel = str(doc_file.relative_to(repo_root.resolve()))

    # Preview or apply
    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        print(f"DRY RUN - Would link {len(code_files)} files to {doc_rel}")
        print()

    added_count = 0
    skipped_count = 0

    for code_file in code_files:
        try:
            code_rel = str(code_file.relative_to(repo_root.resolve()))
        except ValueError:
            continue  # Skip files outside repo

        code_links = parse_links(code_file, repo_root)
        doc_links = parse_links(doc_file, repo_root)

        # Check if link already exists
        if doc_rel in code_links and code_rel in doc_links:
            skipped_count += 1
            if dry_run:
                print(f"  [skip] {code_rel} (already linked)")
            continue

        if dry_run:
            print(f"  [add]  {code_rel}")
        else:
            # Add links
            if doc_rel not in code_links:
                _add_link_to_file(code_file, doc_rel, code_links)
            if code_rel not in doc_links:
                _add_link_to_file(doc_file, code_rel, doc_links)
            added_count += 1

    if not dry_run:
        print(f"Linked {added_count} file(s) to {doc_rel}")
        if skipped_count > 0:
            print(f"Skipped {skipped_count} file(s) (already linked)")

    return 0


def _preview_link_addition(file_path: Path, new_link: str, existing_links: list[str]) -> str:
    """Preview what the docsync header would look like after adding a link."""
    ext = file_path.suffix
    comment_template = COMMENT_STYLES.get(ext, "# docsync: {paths}")

    if existing_links:
        all_links = existing_links + [new_link]
        return comment_template.format(paths=", ".join(all_links))
    else:
        return comment_template.format(paths=new_link)


def _add_link_to_file(file_path: Path, new_link: str, existing_links: list[str]) -> None:
    """Add a docsync link to a file."""
    content = file_path.read_text()
    lines = content.split("\n")

    # Determine comment style
    ext = file_path.suffix
    comment_template = COMMENT_STYLES.get(ext, "# docsync: {paths}")

    if existing_links:
        # File already has a docsync header, append to it
        all_links = existing_links + [new_link]
        new_header = comment_template.format(paths=", ".join(all_links))

        # Find and replace the existing header
        for i, line in enumerate(lines):
            if "docsync:" in line:
                lines[i] = new_header
                break
    else:
        # No existing header, insert new one
        new_header = comment_template.format(paths=new_link)

        # Insert at line 1, or line 2 if line 1 is a shebang
        insert_pos = 1 if lines and lines[0].startswith("#!") else 0
        lines.insert(insert_pos, new_header)

    file_path.write_text("\n".join(lines))


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Propose initial docsync links based on heuristics."""
    repo_root = Path.cwd()

    # Load config to get require_links
    from docsync.config import load_config
    from docsync.graph import build_docsync_graph

    config = load_config(repo_root)

    if config is None:
        print("⚠️  docsync not configured. Run 'docsync init' to set up.")
        return 1

    if not config.require_links:
        print("ACTION REQUIRED: Cannot bootstrap - require_links is empty")
        print()
        print("Configuration has require_links = [] (empty).")
        print("Bootstrap needs to know which files should have documentation.")
        print()
        print("NEXT STEPS:")
        print("  1. Edit [tool.docsync] in pyproject.toml")
        print("  2. Add patterns to require_links")
        print()
        print("Examples:")
        print('  require_links = ["src/**/*.py"]              # Python')
        print('  require_links = ["lib/**/*.js", "lib/**/*.ts"]  # JavaScript/TypeScript')
        print('  require_links = ["crates/**/*.rs"]           # Rust')
        print()
        print("Then run 'docsync bootstrap' again.")
        print()
        return 1

    existing_graph = build_docsync_graph(repo_root, config)

    # Find all code files without links
    from docsync.graph import _match_globs

    orphans = []
    for file_path in repo_root.rglob("*"):
        if not file_path.is_file():
            continue
        if not _match_globs(file_path, config.require_links, repo_root):
            continue
        if _match_globs(file_path, config.exempt, repo_root):
            continue

        rel_path = str(file_path.relative_to(repo_root))
        if rel_path not in existing_graph or not existing_graph[rel_path]:
            orphans.append(file_path)

    if not orphans:
        print("No orphaned code files found. All files have doc links!")
        return 0

    # Propose links based on heuristics with progress indicator
    print(f"Analyzing {len(orphans)} files...")
    proposals = []
    for i, code_file in enumerate(orphans, 1):
        if len(orphans) > 10 and i % 10 == 0:
            print(f"  [{i}/{len(orphans)}]")
        matches = _find_doc_matches(code_file, repo_root, config)
        if matches:
            proposals.append((code_file, matches[0]))  # Take first match

    if not proposals:
        print("No matching docs found for orphaned code files.")
        print(f"\nOrphaned files ({len(orphans)}):")
        for orphan in orphans:
            print(f"  {orphan.relative_to(repo_root)}")
        return 0

    # Interactive mode
    if getattr(args, "interactive", False):
        print(f"\nReviewing {len(proposals)} proposed links (y=yes, n=no, q=quit):")
        approved = []
        for code_file, doc_file in proposals:
            code_rel = code_file.relative_to(repo_root)
            doc_rel = doc_file.relative_to(repo_root)
            response = input(f"  {code_rel} → {doc_rel} [y/n/q]: ").strip().lower()
            if response == "q":
                break
            elif response == "y":
                approved.append((code_file, doc_file))

        if approved:
            print(f"\nApplying {len(approved)} approved links...")
            for code_file, doc_file in approved:
                from docsync.graph import parse_links

                code_rel = str(code_file.relative_to(repo_root))
                doc_rel = str(doc_file.relative_to(repo_root))
                code_links = parse_links(code_file, repo_root)
                doc_links = parse_links(doc_file, repo_root)
                if doc_rel not in code_links:
                    _add_link_to_file(code_file, doc_rel, code_links)
                if code_rel not in doc_links:
                    _add_link_to_file(doc_file, code_rel, doc_links)
            print(f"✓ Applied {len(approved)} links")
        return 0

    # Non-interactive: Print proposals
    print(f"\nProposed {len(proposals)} links:")
    for code_file, doc_file in proposals:
        code_rel = code_file.relative_to(repo_root)
        doc_rel = doc_file.relative_to(repo_root)
        print(f"  {code_rel} → {doc_rel}")

    # Apply if --apply flag set
    if getattr(args, "apply", False):
        print("\nApplying links...")
        for code_file, doc_file in proposals:
            # Use the add-link logic
            from docsync.graph import parse_links

            code_rel = str(code_file.relative_to(repo_root))
            doc_rel = str(doc_file.relative_to(repo_root))

            code_links = parse_links(code_file, repo_root)
            doc_links = parse_links(doc_file, repo_root)

            if doc_rel not in code_links:
                _add_link_to_file(code_file, doc_rel, code_links)
            if code_rel not in doc_links:
                _add_link_to_file(doc_file, code_rel, doc_links)

        print(f"Applied {len(proposals)} links")
    else:
        print("\nTo apply these links, run: docsync bootstrap --apply")

    return 0


def _find_doc_matches(code_file: Path, repo_root: Path, config) -> list[Path]:
    """Find potential doc matches for a code file based on heuristics."""
    matches = []
    code_stem = code_file.stem  # filename without extension
    code_dir = code_file.parent

    # Collect all doc files
    from docsync.graph import _match_globs

    doc_files = []
    for file_path in repo_root.rglob("*"):
        if not file_path.is_file():
            continue
        if _match_globs(file_path, config.doc_paths, repo_root):
            doc_files.append(file_path)

    # Semantic mappings for common patterns
    semantic_mappings = {
        "cli": ["usage", "command", "commands"],
        "client": ["api", "reference"],
        "server": ["api", "reference"],
        "models": ["schema", "data", "model"],
        "utils": ["helpers", "utilities"],
        "helpers": ["utilities", "utils"],
        "config": ["configuration", "settings"],
        "auth": ["authentication", "security"],
        "permissions": ["authorization", "security"],
        "api": ["api", "reference"],
    }

    # Heuristic 1: Exact filename matching (case-insensitive)
    for doc_file in doc_files:
        doc_stem = doc_file.stem
        if code_stem.lower() == doc_stem.lower():
            matches.append(doc_file)

    # Heuristic 2: Semantic mapping
    if not matches:
        code_lower = code_stem.lower()
        for code_pattern, doc_patterns in semantic_mappings.items():
            if code_pattern in code_lower:
                for doc_file in doc_files:
                    doc_lower = doc_file.stem.lower()
                    for pattern in doc_patterns:
                        if pattern in doc_lower:
                            matches.append(doc_file)
                            break

    # Heuristic 3: Partial filename matching (contains)
    if not matches:
        for doc_file in doc_files:
            doc_stem = doc_file.stem
            if code_stem.lower() in doc_stem.lower() or doc_stem.lower() in code_stem.lower():
                matches.append(doc_file)

    # Heuristic 4: Module pattern (*_search.py, *_client.py → api.rst)
    if not matches:
        code_lower = code_stem.lower()
        if any(
            code_lower.endswith(suffix)
            for suffix in ["_search", "_client", "_service", "_handler", "_controller"]
        ):
            for doc_file in doc_files:
                if "api" in doc_file.stem.lower() or "reference" in doc_file.stem.lower():
                    matches.append(doc_file)

    # Heuristic 5: Directory matching
    if not matches:
        for doc_file in doc_files:
            if doc_file.parent == code_dir or doc_file.parent == code_dir / "docs":
                matches.append(doc_file)

    # Heuristic 6: README in same directory
    if not matches:
        readme = code_dir / "README.md"
        if readme.exists():
            matches.append(readme)

    return matches


def cmd_list_stale(args: argparse.Namespace) -> int:
    """List all stale documentation files."""
    from docsync.config import load_config
    from docsync.coverage import _detect_stale_docs

    repo_root = Path.cwd()
    config = load_config(repo_root)
    if config is None:
        print("docsync not configured. Run 'docsync init' first.")
        return 1

    if not config.require_links:
        print("Warning: require_links is empty. No links to check.")
        return 1

    from docsync.graph import build_docsync_graph

    graph = build_docsync_graph(repo_root, config)
    stale_docs = _detect_stale_docs(graph, repo_root, config)

    if not stale_docs:
        print("No stale docs found!")
        return 0

    output_format = getattr(args, "format", "text")

    if output_format == "paths":
        # Just file paths, one per line
        for doc_file, _, _, _, _ in stale_docs:
            print(doc_file)
    elif output_format == "json":
        import json

        output = [
            {
                "doc_file": doc_file,
                "code_file": code_file,
                "doc_timestamp": doc_ts,
                "code_timestamp": code_ts,
                "days_stale": days_stale,
                "severity": (
                    "critical" if days_stale > 90 else "warning" if days_stale > 30 else "recent"
                ),
            }
            for doc_file, code_file, doc_ts, code_ts, days_stale in stale_docs
        ]
        print(json.dumps(output, indent=2))
    else:
        # Text format with details
        from datetime import datetime

        print(f"Found {len(stale_docs)} stale docs:\n")
        for doc_file, code_file, doc_ts, code_ts, days_stale in stale_docs:
            doc_date = datetime.fromtimestamp(doc_ts).strftime("%Y-%m-%d")
            code_date = datetime.fromtimestamp(code_ts).strftime("%Y-%m-%d")
            severity = (
                "⚠️ CRITICAL"
                if days_stale > 90
                else "⚠️  WARNING"
                if days_stale > 30
                else "ℹ️  RECENT"
            )
            print(f"{severity} {doc_file}")
            print(f"  Linked to: {code_file}")
            print(f"  Doc modified: {doc_date}")
            print(f"  Code modified: {code_date}")
            print(f"  Days stale: {days_stale}\n")

    return 0


def cmd_affected_docs(args: argparse.Namespace) -> int:
    """Get all affected docs for a set of changed files."""
    import glob as glob_module

    from docsync.config import load_config
    from docsync.imports import build_import_graph

    repo_root = Path.cwd()
    config = load_config(repo_root)
    if config is None:
        print("docsync not configured. Run 'docsync init' first.")
        return 1

    if not config.require_links:
        print("Warning: require_links is empty. No links to check.")
        return 1

    files = getattr(args, "files", [])
    if not files:
        print("No files specified. Use: docsync affected-docs --files <pattern>")
        return 1

    # Expand globs
    expanded_files = []
    for pattern in files:
        if "*" in pattern:
            matches = glob_module.glob(str(repo_root / pattern), recursive=True)
            expanded_files.extend(Path(m).relative_to(repo_root) for m in matches)
        else:
            expanded_files.append(Path(pattern))

    # Find affected docs (direct + transitive)
    from docsync.coverage import _is_doc_file
    from docsync.graph import build_docsync_graph

    graph = build_docsync_graph(repo_root, config)
    import_graph = build_import_graph(repo_root)

    affected_docs = set()
    for file_path in expanded_files:
        code_file = str(file_path)

        # Direct links from graph
        if code_file in graph:
            for linked_file in graph[code_file]:
                if _is_doc_file(linked_file, config):
                    affected_docs.add(linked_file)

        # Transitive links via imports
        for target_file in import_graph.get(code_file, []):
            if target_file in graph:
                for linked_file in graph[target_file]:
                    if _is_doc_file(linked_file, config):
                        affected_docs.add(linked_file)

    if not affected_docs:
        print("No affected docs found for specified files.")
        return 0

    output_format = getattr(args, "format", "paths")

    if output_format == "json":
        import json

        output = {
            "changed_files": [str(f) for f in expanded_files],
            "affected_docs": sorted(affected_docs),
        }
        print(json.dumps(output, indent=2))
    else:
        # paths format (one per line)
        for doc in sorted(affected_docs):
            print(doc)

    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show comprehensive info about a file (links, timestamps, imports, staleness)."""
    import subprocess

    from docsync.config import load_config
    from docsync.coverage import _detect_stale_docs
    from docsync.imports import build_import_graph

    repo_root = Path.cwd()
    config = load_config(repo_root)
    if config is None:
        print("docsync not configured. Run 'docsync init' first.")
        return 1

    file_path = getattr(args, "file", None)
    if not file_path:
        print("No file specified. Use: docsync info <file>")
        return 1

    # Handle both absolute and relative paths
    path_obj = Path(file_path)
    code_file = str(path_obj.relative_to(repo_root)) if path_obj.is_absolute() else str(path_obj)

    # Get linked docs from graph
    from docsync.coverage import _is_doc_file
    from docsync.graph import build_docsync_graph

    graph = build_docsync_graph(repo_root, config)
    linked_docs = [f for f in graph.get(code_file, []) if _is_doc_file(f, config)]

    # Get imports
    import_graph = build_import_graph(repo_root)
    imports = list(import_graph.get(code_file, []))

    # Get timestamps
    file_full_path = repo_root / code_file
    if not file_full_path.exists():
        print(f"File not found: {code_file}")
        return 1

    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", str(file_full_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    code_timestamp = int(result.stdout.strip()) if result.stdout.strip() else 0

    # Check staleness for linked docs (reuse the graph we already built)
    stale_docs = _detect_stale_docs(graph, repo_root, config)
    stale_for_this_file = [
        (doc_file, doc_ts, code_ts, days_stale)
        for doc_file, linked_code, doc_ts, code_ts, days_stale in stale_docs
        if linked_code == code_file
    ]

    output_format = getattr(args, "format", "text")

    if output_format == "json":
        import json
        from datetime import datetime

        output = {
            "file": code_file,
            "timestamp": code_timestamp,
            "last_modified": (
                datetime.fromtimestamp(code_timestamp).isoformat() if code_timestamp else None
            ),
            "linked_docs": linked_docs,
            "imports": imports,
            "stale_docs": [
                {
                    "doc_file": doc_file,
                    "doc_timestamp": doc_ts,
                    "code_timestamp": code_ts,
                    "days_stale": days_stale,
                    "severity": (
                        "critical"
                        if days_stale > 90
                        else "warning"
                        if days_stale > 30
                        else "recent"
                    ),
                }
                for doc_file, doc_ts, code_ts, days_stale in stale_for_this_file
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        # Text format
        from datetime import datetime

        print(f"File: {code_file}")
        if code_timestamp:
            timestamp_str = datetime.fromtimestamp(code_timestamp).strftime("%Y-%m-%d %H:%M:%S")
            print(f"Last modified: {timestamp_str}")
        print()

        print(f"Linked docs ({len(linked_docs)}):")
        if linked_docs:
            for doc in linked_docs:
                print(f"  - {doc}")
        else:
            print("  (none)")
        print()

        print(f"Imports ({len(imports)}):")
        if imports:
            for imp in imports:
                print(f"  - {imp}")
        else:
            print("  (none)")
        print()

        if stale_for_this_file:
            print(f"Stale docs ({len(stale_for_this_file)}):")
            for doc_file, doc_ts, _code_ts, days_stale in stale_for_this_file:
                doc_date = datetime.fromtimestamp(doc_ts).strftime("%Y-%m-%d")
                severity = (
                    "⚠️ CRITICAL"
                    if days_stale > 90
                    else "⚠️  WARNING"
                    if days_stale > 30
                    else "ℹ️  RECENT"
                )
                print(f"  {severity} {doc_file} ({days_stale} days stale, last updated {doc_date})")
        else:
            print("No stale docs for this file.")

    return 0


def cmd_explain_changes(args: argparse.Namespace) -> int:
    """Show git diff summary between doc and code to understand what changed."""
    import re
    import subprocess

    from docsync.config import load_config

    repo_root = Path.cwd()
    config = load_config(repo_root)
    if config is None:
        print("docsync not configured. Run 'docsync init' first.")
        return 1

    file_path = getattr(args, "file", None)
    if not file_path:
        print("No file specified. Use: docsync explain-changes <file>")
        return 1

    # Handle both absolute and relative paths
    path_obj = Path(file_path)
    code_file = str(path_obj.relative_to(repo_root)) if path_obj.is_absolute() else str(path_obj)

    # Get linked docs from graph
    from docsync.coverage import _is_doc_file
    from docsync.graph import build_docsync_graph

    graph = build_docsync_graph(repo_root, config)
    linked_docs = [f for f in graph.get(code_file, []) if _is_doc_file(f, config)]

    if not linked_docs:
        print(f"No linked docs found for {code_file}")
        return 1

    # Get the timestamp of the first linked doc (assume all docs updated together)
    doc_file = linked_docs[0]
    doc_full_path = repo_root / doc_file

    if not doc_full_path.exists():
        print(f"Doc file not found: {doc_file}")
        return 1

    # Get doc last modified timestamp
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", str(doc_full_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    doc_timestamp = int(result.stdout.strip()) if result.stdout.strip() else 0

    if not doc_timestamp:
        print(f"Could not determine last modification time for {doc_file}")
        return 1

    from datetime import datetime

    doc_date = datetime.fromtimestamp(doc_timestamp).strftime("%Y-%m-%d")

    # Get git log of code file since doc was last updated
    result = subprocess.run(
        [
            "git",
            "log",
            f"--since={doc_timestamp}",
            "--format=%H",
            "--",
            str(repo_root / code_file),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    commits = result.stdout.strip().split("\n") if result.stdout.strip() else []

    if not commits:
        print(f"No changes to {code_file} since {doc_file} was last updated ({doc_date})")
        return 0

    # Get unified diff for the time range
    result = subprocess.run(
        [
            "git",
            "log",
            f"--since={doc_timestamp}",
            "-p",
            "--",
            str(repo_root / code_file),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    diff_output = result.stdout

    # Parse diff to find function/class changes
    functions_modified = set()
    functions_added = set()
    functions_removed = set()

    # Simple regex patterns for Python functions/classes
    func_pattern = re.compile(r"^[+-]\s*(?:def|class)\s+(\w+)")

    for line in diff_output.split("\n"):
        match = func_pattern.match(line)
        if match:
            func_name = match.group(1)
            if line.startswith("+"):
                functions_added.add(func_name)
            elif line.startswith("-"):
                functions_removed.add(func_name)
            else:
                functions_modified.add(func_name)

    # Functions that appear in both added and removed are modifications
    truly_modified = functions_added & functions_removed
    functions_added -= truly_modified
    functions_removed -= truly_modified
    functions_modified.update(truly_modified)

    print(f"Changes to {code_file} since {doc_file} was last updated ({doc_date}):\n")
    print(f"Commits: {len(commits)}")

    if functions_modified:
        print("\nModified functions/classes:")
        for func in sorted(functions_modified):
            print(f"  • {func}")

    if functions_added:
        print("\nAdded functions/classes:")
        for func in sorted(functions_added):
            print(f"  + {func}")

    if functions_removed:
        print("\nRemoved functions/classes:")
        for func in sorted(functions_removed):
            print(f"  - {func}")

    if not (functions_modified or functions_added or functions_removed):
        print(
            "\nNo function/class signature changes detected (changes may be in implementation only)"
        )

    print("\nAffected documentation:")
    for doc in linked_docs:
        print(f"  → {doc}")

    return 0


def cmd_defer(args: argparse.Namespace) -> int:
    """Mark a file as 'docs will be updated in next commit'."""
    import json

    from docsync.config import load_config

    repo_root = Path.cwd()
    config = load_config(repo_root)
    if config is None:
        print("docsync not configured. Run 'docsync init' first.")
        return 1

    file_path = getattr(args, "file", None)
    clear_deferral = getattr(args, "clear", False)

    if not file_path:
        print("No file specified. Use: docsync defer <file>")
        return 1

    # Handle both absolute and relative paths
    path_obj = Path(file_path)
    code_file = str(path_obj.relative_to(repo_root)) if path_obj.is_absolute() else str(path_obj)
    deferred_file = repo_root / ".docsync-deferred.json"

    # Load existing deferrals
    if deferred_file.exists():
        with open(deferred_file) as f:
            deferrals = json.load(f)
    else:
        deferrals = {}

    # Handle --clear option
    if clear_deferral:
        if code_file in deferrals:
            del deferrals[code_file]

            # Save or delete file if empty
            if deferrals:
                with open(deferred_file, "w") as f:
                    json.dump(deferrals, f, indent=2)
            else:
                deferred_file.unlink()

            print(f"Cleared deferral for {code_file}")
        else:
            print(f"No deferral found for {code_file}")
        return 0

    # Add/update deferral
    message = getattr(args, "message", None)
    if not message:
        print("Error: --message is required when deferring (use --clear to remove deferral)")
        return 1

    from datetime import datetime

    deferrals[code_file] = {
        "message": message,
        "deferred_at": datetime.now().isoformat(),
    }

    # Save
    with open(deferred_file, "w") as f:
        json.dump(deferrals, f, indent=2)

    print(f"Deferred doc updates for {code_file}")
    print(f"Message: {message}")
    print(
        "\nThis file will be exempt from docsync check until you run 'docsync defer --clear <file>'"
    )

    return 0


def cmd_list_deferred(args: argparse.Namespace) -> int:
    """List all deferred updates."""
    import json

    repo_root = Path.cwd()
    deferred_file = repo_root / ".docsync-deferred.json"

    if not deferred_file.exists():
        print("No deferred updates found.")
        return 0

    with open(deferred_file) as f:
        deferrals = json.load(f)

    if not deferrals:
        print("No deferred updates found.")
        return 0

    output_format = getattr(args, "format", "text")

    if output_format == "json":
        print(json.dumps(deferrals, indent=2))
    else:
        from datetime import datetime

        print(f"Deferred updates ({len(deferrals)}):\n")
        for code_file, info in deferrals.items():
            deferred_at = datetime.fromisoformat(info["deferred_at"]).strftime("%Y-%m-%d %H:%M:%S")
            print(f"• {code_file}")
            print(f"  Message: {info['message']}")
            print(f"  Deferred at: {deferred_at}\n")

    return 0


def cmd_clear_cache(args: argparse.Namespace) -> int:
    """Clear import graph cache."""
    from docsync.cache import clear_cache

    repo_root = Path.cwd()
    clear_cache(repo_root)
    print("Cache cleared successfully.")
    print("\nNext import graph build will be slower but reflect latest changes.")
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="docsync: Documentation freshness enforcement via dependency graphs"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # init command
    subparsers.add_parser("init", help="Initialize docsync in a repository")

    # check command
    check_parser = subparsers.add_parser("check", help="Run pre-commit hook check")
    check_parser.add_argument(
        "--staged-files", help="Comma-separated list of staged files (for testing)"
    )
    check_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )
    check_parser.add_argument(
        "--create-todo",
        action="store_true",
        help="Create .docsync-todo.json with actionable tasks for agents",
    )

    # coverage command
    coverage_parser = subparsers.add_parser("coverage", help="Generate coverage report")
    coverage_parser.add_argument("--output", "-o", help="Write report to file")
    coverage_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    # add-link command
    add_link_parser = subparsers.add_parser("add-link", help="Add bidirectional link between files")
    add_link_parser.add_argument("code_file", help="Code file path")
    add_link_parser.add_argument("doc_file", help="Doc file path")
    add_link_parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without modifying files"
    )

    # bootstrap command
    bootstrap_parser = subparsers.add_parser("bootstrap", help="Propose initial docsync links")
    bootstrap_parser.add_argument("--apply", action="store_true", help="Apply proposed links")
    bootstrap_parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode: review and approve/skip each suggestion",
    )

    # list-stale command
    stale_parser = subparsers.add_parser("list-stale", help="List stale documentation files")
    stale_parser.add_argument(
        "--format", choices=["text", "paths", "json"], default="text", help="Output format"
    )

    # affected-docs command
    affected_parser = subparsers.add_parser(
        "affected-docs", help="List docs affected by changed files"
    )
    affected_parser.add_argument(
        "--files", required=True, help="Comma-separated file paths or globs"
    )
    affected_parser.add_argument(
        "--format", choices=["text", "paths", "json"], default="text", help="Output format"
    )

    # info command
    info_parser = subparsers.add_parser("info", help="Show comprehensive file information")
    info_parser.add_argument("file", help="File to analyze")
    info_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    # explain-changes command
    explain_parser = subparsers.add_parser(
        "explain-changes", help="Explain what changed between code and docs"
    )
    explain_parser.add_argument("file", help="Code file to analyze")
    explain_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    # defer command
    defer_parser = subparsers.add_parser("defer", help="Defer doc updates temporarily")
    defer_parser.add_argument("file", help="File to defer")
    defer_parser.add_argument("--message", "-m", help="Reason for deferring")
    defer_parser.add_argument("--clear", action="store_true", help="Clear deferral for this file")

    # list-deferred command
    subparsers.add_parser("list-deferred", help="List all deferred updates")

    # clear-cache command
    subparsers.add_parser("clear-cache", help="Clear import graph cache")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handlers
    commands = {
        "init": cmd_init,
        "check": cmd_check,
        "coverage": cmd_coverage,
        "add-link": cmd_add_link,
        "bootstrap": cmd_bootstrap,
        "list-stale": cmd_list_stale,
        "affected-docs": cmd_affected_docs,
        "info": cmd_info,
        "explain-changes": cmd_explain_changes,
        "defer": cmd_defer,
        "list-deferred": cmd_list_deferred,
        "clear-cache": cmd_clear_cache,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
