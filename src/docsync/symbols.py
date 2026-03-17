"""AST-based symbol extraction for tracking public API changes."""

import ast
import contextlib
import hashlib
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum number of entries in the symbols cache (LRU eviction)
MAX_CACHE_SIZE = 500

# Timeout for git subprocess calls (seconds)
GIT_TIMEOUT = 5


@dataclass
class SymbolInfo:
    """Information about symbols in a Python file."""

    functions: list[str]  # Top-level function names
    classes: list[str]  # Top-level class names

    def to_dict(self) -> dict:
        return {"functions": self.functions, "classes": self.classes}

    @classmethod
    def from_dict(cls, data: dict) -> "SymbolInfo":
        return cls(functions=data.get("functions", []), classes=data.get("classes", []))


@dataclass
class SymbolDiff:
    """Diff between two versions of a file's symbols."""

    functions_added: list[str]
    functions_removed: list[str]
    classes_added: list[str]
    classes_removed: list[str]

    @property
    def has_changes(self) -> bool:
        return bool(
            self.functions_added
            or self.functions_removed
            or self.classes_added
            or self.classes_removed
        )

    def to_dict(self) -> dict:
        return {
            "functions_added": self.functions_added,
            "functions_removed": self.functions_removed,
            "classes_added": self.classes_added,
            "classes_removed": self.classes_removed,
        }


def extract_symbols(source: str) -> SymbolInfo:
    """
    Extract public symbols from Python source code.

    Public symbols are top-level functions and classes without a leading underscore.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return SymbolInfo(functions=[], classes=[])

    functions = []
    classes = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if not node.name.startswith("_"):
                functions.append(node.name)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(node.name)

    return SymbolInfo(functions=sorted(functions), classes=sorted(classes))


def extract_symbols_from_file(file_path: Path) -> SymbolInfo:
    """Extract symbols from a file on disk."""
    try:
        source = file_path.read_text(encoding="utf-8")
        return extract_symbols(source)
    except FileNotFoundError:
        return SymbolInfo(functions=[], classes=[])
    except PermissionError as e:
        logger.warning("Permission denied reading %s: %s", file_path, e)
        return SymbolInfo(functions=[], classes=[])
    except UnicodeDecodeError as e:
        logger.warning("Encoding error reading %s: %s", file_path, e)
        return SymbolInfo(functions=[], classes=[])
    except OSError as e:
        logger.warning("OS error reading %s: %s", file_path, e)
        return SymbolInfo(functions=[], classes=[])


def get_file_at_commit(repo_root: Path, file_path: str, commit: str) -> str | None:
    """Get file contents at a specific commit."""
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{file_path}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except subprocess.TimeoutExpired:
        logger.warning("git show timed out for %s at %s", file_path, commit)
        return None
    except subprocess.CalledProcessError:
        return None


def diff_symbols(old: SymbolInfo, new: SymbolInfo) -> SymbolDiff:
    """Compare two symbol sets and return what changed."""
    old_funcs = set(old.functions)
    new_funcs = set(new.functions)
    old_classes = set(old.classes)
    new_classes = set(new.classes)

    return SymbolDiff(
        functions_added=sorted(new_funcs - old_funcs),
        functions_removed=sorted(old_funcs - new_funcs),
        classes_added=sorted(new_classes - old_classes),
        classes_removed=sorted(old_classes - new_classes),
    )


def get_symbol_diff_between_commits(
    repo_root: Path, file_path: str, old_commit: str, new_commit: str = "HEAD"
) -> SymbolDiff | None:
    """
    Get the symbol diff for a file between two commits.

    Returns None if the file doesn't exist or can't be parsed at either commit.
    """
    old_source = get_file_at_commit(repo_root, file_path, old_commit)
    new_source = get_file_at_commit(repo_root, file_path, new_commit)

    if old_source is None and new_source is None:
        return None

    old_symbols = extract_symbols(old_source) if old_source else SymbolInfo([], [])
    new_symbols = extract_symbols(new_source) if new_source else SymbolInfo([], [])

    return diff_symbols(old_symbols, new_symbols)


# --- Caching with LRU eviction and atomic writes ---


def _get_content_hash(content: str) -> str:
    """Get a short hash of content for cache keys."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _get_symbols_cache_path(repo_root: Path) -> Path:
    """Get the path to the symbols cache file."""
    cache_dir = repo_root / ".docsync"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / "symbols_cache.json"


def _load_symbols_cache(repo_root: Path) -> dict[str, dict]:
    """Load the symbols cache from disk."""
    cache_path = _get_symbols_cache_path(repo_root)
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path) as f:
            data = json.load(f)
            # Validate structure
            if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
                return data
            logger.warning("Invalid cache structure in %s, resetting", cache_path)
            return {}
    except json.JSONDecodeError as e:
        logger.warning("Corrupted cache file %s: %s", cache_path, e)
        return {}
    except PermissionError as e:
        logger.warning("Permission denied reading cache %s: %s", cache_path, e)
        return {}
    except OSError as e:
        logger.warning("Error reading cache %s: %s", cache_path, e)
        return {}


def _save_symbols_cache(repo_root: Path, cache: dict[str, dict]) -> None:
    """
    Save the symbols cache to disk atomically.

    Uses write-to-temp-then-rename pattern to prevent corruption from
    concurrent writes or crashes.
    """
    cache_path = _get_symbols_cache_path(repo_root)
    try:
        # Write to a temp file in the same directory (same filesystem for atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=cache_path.parent, prefix=".symbols_cache_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(cache, f)
            # Atomic rename (on POSIX systems)
            os.replace(temp_path, cache_path)
        except Exception:
            # Clean up temp file on error
            with contextlib.suppress(OSError):
                os.unlink(temp_path)
            raise
    except PermissionError as e:
        logger.warning("Permission denied writing cache %s: %s", cache_path, e)
    except OSError as e:
        logger.warning("Error writing cache %s: %s", cache_path, e)


def _evict_lru(cache: dict[str, dict], max_size: int) -> dict[str, dict]:
    """
    Evict oldest entries from cache to maintain max_size.

    Since we don't track access time, we evict the first entries
    (which are oldest by insertion order in Python 3.7+ dicts).
    """
    if len(cache) <= max_size:
        return cache

    # Keep only the most recent entries
    items = list(cache.items())
    evict_count = len(items) - max_size
    return dict(items[evict_count:])


def get_symbols_cached(repo_root: Path, content: str) -> SymbolInfo:
    """
    Get symbols for content, using cache if available.

    Cache is keyed by content hash, so same content always returns cached result.
    Uses LRU eviction to prevent unbounded cache growth.
    """
    content_hash = _get_content_hash(content)
    cache = _load_symbols_cache(repo_root)

    if content_hash in cache:
        # Move to end (most recently used) by reinserting
        entry = cache.pop(content_hash)
        cache[content_hash] = entry
        return SymbolInfo.from_dict(entry)

    symbols = extract_symbols(content)
    cache[content_hash] = symbols.to_dict()

    # Evict old entries if cache is too large
    cache = _evict_lru(cache, MAX_CACHE_SIZE)

    _save_symbols_cache(repo_root, cache)

    return symbols


def get_symbol_diff_cached(
    repo_root: Path, file_path: str, old_commit: str, new_commit: str = "HEAD"
) -> SymbolDiff | None:
    """
    Get symbol diff between commits, using cache for symbol extraction.
    """
    old_source = get_file_at_commit(repo_root, file_path, old_commit)
    new_source = get_file_at_commit(repo_root, file_path, new_commit)

    if old_source is None and new_source is None:
        return None

    old_symbols = get_symbols_cached(repo_root, old_source) if old_source else SymbolInfo([], [])
    new_symbols = get_symbols_cached(repo_root, new_source) if new_source else SymbolInfo([], [])

    return diff_symbols(old_symbols, new_symbols)
