"""Python import graph construction via AST parsing."""

import ast
from collections import deque
from pathlib import Path


def build_import_graph(
    repo_root: Path, source_roots: list[Path] | None = None
) -> dict[str, set[str]]:
    """
    Parse all .py files under repo_root and build a mapping:
      file (relative path) → set of in-project files it imports from.

    source_roots defaults to [repo_root / "src", repo_root] if not provided.
    Only resolves imports to files that actually exist in the project.

    Uses SHA-based caching in .menard/ directory for performance.
    """
    # Try to load from cache
    from menard.cache import load_import_graph_cache, save_import_graph_cache

    cached_graph = load_import_graph_cache(repo_root)
    if cached_graph is not None:
        return cached_graph

    # Cache miss - build the graph
    if source_roots is None:
        source_roots = [repo_root / "src", repo_root]

    # Ensure source roots exist
    source_roots = [sr for sr in source_roots if sr.exists()]

    graph: dict[str, set[str]] = {}

    # Find all Python files
    python_files = list(repo_root.rglob("*.py"))

    for py_file in python_files:
        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            # Can't read file, skip it
            continue

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Syntax error, skip this file
            continue

        # Extract imports
        imports = _extract_imports(tree, py_file, repo_root)

        # Resolve each import to an actual file
        importees = set()
        for module_name, is_relative, level in imports:
            resolved = _resolve_import(
                module_name, is_relative, level, py_file, repo_root, source_roots
            )
            if resolved:
                importees.add(resolved)

        if importees:
            rel_path = str(py_file.relative_to(repo_root))
            graph[rel_path] = importees

    # Save to cache before returning
    save_import_graph_cache(repo_root, graph)

    return graph


def _extract_imports(
    tree: ast.AST, file_path: Path, repo_root: Path
) -> list[tuple[str, bool, int]]:
    """
    Extract all imports from an AST.
    Returns list of (module_name, is_relative, level) tuples.
    """
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # import foo, bar
            for alias in node.names:
                imports.append((alias.name, False, 0))
        elif isinstance(node, ast.ImportFrom):
            # from foo import bar
            # from . import bar (relative)
            # from ..foo import bar (relative)
            module = node.module or ""
            level = node.level
            is_relative = level > 0
            imports.append((module, is_relative, level))

    return imports


def _resolve_import(
    module_name: str,
    is_relative: bool,
    level: int,
    importing_file: Path,
    repo_root: Path,
    source_roots: list[Path],
) -> str | None:
    """
    Resolve an import to an in-project file path (relative to repo_root).
    Returns None if the import doesn't resolve to an in-project file.
    """
    if is_relative:
        # Relative import: resolve relative to the importing file's package
        return _resolve_relative_import(module_name, level, importing_file, repo_root)
    else:
        # Absolute import: try each source root
        return _resolve_absolute_import(module_name, repo_root, source_roots)


def _resolve_relative_import(
    module_name: str, level: int, importing_file: Path, repo_root: Path
) -> str | None:
    """Resolve a relative import like 'from . import foo' or 'from ..bar import baz'."""
    # Start from the importing file's directory
    current = importing_file.parent

    # Go up 'level' directories (level 1 = current package, level 2 = parent package, etc.)
    for _ in range(level - 1):
        current = current.parent
        # Stop if we've gone outside the repo
        if not current.is_relative_to(repo_root):
            return None

    # Now resolve the module_name from current directory
    # from ..foo.bar import baz → current/foo/bar
    # from .. import baz → current
    module_path = current / module_name.replace(".", "/") if module_name else current

    # Try to find the actual file
    # Could be module_path.py or module_path/__init__.py
    candidates = [
        module_path.with_suffix(".py"),
        module_path / "__init__.py",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            try:
                return str(candidate.relative_to(repo_root))
            except ValueError:
                return None

    return None


def _resolve_absolute_import(
    module_name: str, repo_root: Path, source_roots: list[Path]
) -> str | None:
    """Resolve an absolute import like 'import foo.bar' or 'from foo.bar import baz'."""
    # Convert module name to path: foo.bar.baz → foo/bar/baz
    module_path_str = module_name.replace(".", "/")

    # Try each source root
    for source_root in source_roots:
        module_path = source_root / module_path_str

        # Try module_path.py or module_path/__init__.py
        candidates = [
            module_path.with_suffix(".py"),
            module_path / "__init__.py",
        ]

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                try:
                    return str(candidate.relative_to(repo_root))
                except ValueError:
                    # File is outside repo_root
                    continue

    return None


def get_dependents(file_path: str, import_graph: dict[str, set[str]], depth: int = 1) -> set[str]:
    """
    Given a file, find all files that transitively depend on it
    (i.e., files that import from it, files that import from those, etc.)
    up to `depth` hops.

    This INVERTS the import graph: if B imports A, then B is a dependent of A.

    Returns the set of dependent file paths (not including the input file itself).
    """
    if depth < 1:
        return set()

    # Invert the graph: for each file, what files import from it?
    reverse_graph: dict[str, set[str]] = {}
    for importer, importees in import_graph.items():
        for importee in importees:
            reverse_graph.setdefault(importee, set()).add(importer)

    # BFS from file_path up to depth hops
    visited = set()
    queue = deque([(file_path, 0)])
    dependents = set()

    while queue:
        current, current_depth = queue.popleft()

        if current in visited:
            continue
        visited.add(current)

        # Don't include the starting file itself
        if current != file_path:
            dependents.add(current)

        # If we haven't reached max depth, add this file's dependents to queue
        if current_depth < depth:
            for dependent in reverse_graph.get(current, set()):
                if dependent not in visited:
                    queue.append((dependent, current_depth + 1))

    return dependents
