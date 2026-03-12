"""Caching for expensive operations like import graph building."""

import hashlib
import json
import subprocess
from pathlib import Path


def _get_repo_state_hash(repo_root: Path) -> str:
    """
    Get a hash representing the current state of Python files in the repo.
    Uses git ls-files for tracked files and their last commit hashes.
    Falls back to filesystem timestamps if not in a git repo.
    """
    try:
        # Try git first (fast and accurate)
        result = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            files = result.stdout.strip().split("\n")
            # Get the hash of all Python files' current state
            result = subprocess.run(
                ["git", "hash-object"] + files,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Hash of all file hashes
                combined = result.stdout.encode()
                return hashlib.sha256(combined).hexdigest()[:16]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: hash all .py file paths and mtimes
    py_files = sorted(repo_root.rglob("*.py"))
    content = []
    for f in py_files[:1000]:  # Limit to first 1000 files for performance
        try:
            stat = f.stat()
            content.append(f"{f.relative_to(repo_root)}:{stat.st_mtime}")
        except Exception:
            continue
    combined = "\n".join(content).encode()
    return hashlib.sha256(combined).hexdigest()[:16]


def get_cache_dir(repo_root: Path) -> Path:
    """Get or create the .docsync cache directory."""
    cache_dir = repo_root / ".docsync"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def load_import_graph_cache(repo_root: Path) -> dict[str, set[str]] | None:
    """
    Load cached import graph if available and valid.
    Returns None if cache is missing or stale.
    """
    cache_dir = get_cache_dir(repo_root)
    cache_file = cache_dir / "import_graph.json"
    state_file = cache_dir / "import_graph.state"

    if not cache_file.exists() or not state_file.exists():
        return None

    # Check if state matches
    try:
        current_state = _get_repo_state_hash(repo_root)
        cached_state = state_file.read_text().strip()

        if current_state != cached_state:
            # Stale cache
            return None

        # Load cached graph
        with open(cache_file) as f:
            data = json.load(f)

        # Convert lists back to sets
        graph = {k: set(v) for k, v in data.items()}
        return graph

    except Exception:
        # Any error reading cache, treat as miss
        return None


def save_import_graph_cache(repo_root: Path, graph: dict[str, set[str]]) -> None:
    """Save import graph to cache."""
    cache_dir = get_cache_dir(repo_root)
    cache_file = cache_dir / "import_graph.json"
    state_file = cache_dir / "import_graph.state"

    try:
        # Save state hash
        current_state = _get_repo_state_hash(repo_root)
        state_file.write_text(current_state)

        # Save graph (convert sets to lists for JSON)
        data = {k: list(v) for k, v in graph.items()}
        with open(cache_file, "w") as f:
            json.dump(data, f)

    except Exception:
        # Silently fail - caching is optional
        pass


def clear_cache(repo_root: Path) -> None:
    """Clear all caches."""
    cache_dir = repo_root / ".docsync"
    if cache_dir.exists():
        for cache_file in cache_dir.glob("*.json"):
            cache_file.unlink()
        for state_file in cache_dir.glob("*.state"):
            state_file.unlink()
