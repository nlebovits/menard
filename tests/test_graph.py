"""Tests for graph construction from TOML links."""

import tempfile
from pathlib import Path

from menard.config import DocsyncConfig
from menard.graph import build_menard_graph, get_linked_docs


def test_build_graph_from_toml():
    """Test building graph from .menard/links.toml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create links.toml
        menard_dir = repo_root / ".menard"
        menard_dir.mkdir()
        links_file = menard_dir / "links.toml"
        links_file.write_text(
            """
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]

[[link]]
code = "src/models/user.py"
docs = ["docs/models.md", "docs/api.md#User Endpoints"]
"""
        )

        config = DocsyncConfig(doc_paths=["docs/**/*.md"])
        graph = build_menard_graph(repo_root, config)

        # Check bidirectional links
        assert "docs/api.md" in graph["src/auth.py"]
        assert "src/auth.py" in graph["docs/api.md"]

        assert "docs/models.md" in graph["src/models/user.py"]
        assert "docs/api.md#User Endpoints" in graph["src/models/user.py"]

        assert "src/models/user.py" in graph["docs/models.md"]
        assert "src/models/user.py" in graph["docs/api.md#User Endpoints"]


def test_build_graph_empty_links():
    """Test building graph when no links file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        config = DocsyncConfig()
        graph = build_menard_graph(repo_root, config)

        assert graph == {}


def test_get_linked_docs():
    """Test getting linked docs for a code file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create links
        menard_dir = repo_root / ".menard"
        menard_dir.mkdir()
        links_file = menard_dir / "links.toml"
        links_file.write_text(
            """
[[link]]
code = "src/auth.py"
docs = ["docs/api.md", "docs/auth.md#Authentication"]
"""
        )

        config = DocsyncConfig(doc_paths=["docs/**/*.md"])
        graph = build_menard_graph(repo_root, config)

        docs = get_linked_docs("src/auth.py", graph, config)

        assert len(docs) == 2
        assert "docs/api.md" in docs
        assert "docs/auth.md#Authentication" in docs


def test_get_linked_docs_filters_non_docs():
    """Test that get_linked_docs filters out non-doc files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create a graph with mixed links
        menard_dir = repo_root / ".menard"
        menard_dir.mkdir()
        links_file = menard_dir / "links.toml"
        links_file.write_text(
            """
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]

[[link]]
code = "src/models/user.py"
docs = ["src/auth.py"]
"""
        )

        # Config only considers docs/**/*.md as doc files
        config = DocsyncConfig(doc_paths=["docs/**/*.md"])
        graph = build_menard_graph(repo_root, config)

        # For src/models/user.py, src/auth.py should NOT be included
        # (it's a code file, not a doc file)
        docs = get_linked_docs("src/models/user.py", graph, config)
        assert "src/auth.py" not in docs


def test_build_graph_with_glob_patterns():
    """Test building graph with glob patterns in code field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create some code files
        (repo_root / "src" / "models").mkdir(parents=True)
        (repo_root / "src" / "models" / "user.py").write_text("# user model")
        (repo_root / "src" / "models" / "post.py").write_text("# post model")

        # Create links with glob
        menard_dir = repo_root / ".menard"
        menard_dir.mkdir()
        links_file = menard_dir / "links.toml"
        links_file.write_text(
            """
[[link]]
code = "src/models/*.py"
docs = ["docs/models.md"]
"""
        )

        config = DocsyncConfig(doc_paths=["docs/**/*.md"])
        graph = build_menard_graph(repo_root, config)

        # Both model files should link to docs
        assert "docs/models.md" in graph["src/models/user.py"]
        assert "docs/models.md" in graph["src/models/post.py"]

        # Bidirectional
        assert "src/models/user.py" in graph["docs/models.md"]
        assert "src/models/post.py" in graph["docs/models.md"]


def test_build_graph_with_sections():
    """Test that section-specific links are preserved in graph."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        menard_dir = repo_root / ".menard"
        menard_dir.mkdir()
        links_file = menard_dir / "links.toml"
        links_file.write_text(
            """
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication", "docs/api.md#Sessions"]
"""
        )

        config = DocsyncConfig(doc_paths=["docs/**/*.md"])
        graph = build_menard_graph(repo_root, config)

        # Check that both section-specific targets are in graph
        assert "docs/api.md#Authentication" in graph["src/auth.py"]
        assert "docs/api.md#Sessions" in graph["src/auth.py"]

        # But NOT the whole file
        assert "docs/api.md" not in graph["src/auth.py"]
