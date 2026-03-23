"""Tests for semantic duplicate detection (brevity module)."""

from pathlib import Path

import numpy as np
import pytest


class TestDuplicatePair:
    """Tests for the DuplicatePair dataclass."""

    def test_duplicate_pair_has_required_fields(self):
        """DuplicatePair should have source, target, similarity, and line_ranges."""
        from menard.brevity import DuplicatePair

        pair = DuplicatePair(
            source="README.md#Quick Start",
            target="docs/getting-started.md#Installation",
            similarity=0.87,
            source_lines=(1, 10),
            target_lines=(5, 15),
        )

        assert pair.source == "README.md#Quick Start"
        assert pair.target == "docs/getting-started.md#Installation"
        assert pair.similarity == 0.87
        assert pair.source_lines == (1, 10)
        assert pair.target_lines == (5, 15)


class TestCosineSimilarity:
    """Tests for cosine similarity calculation."""

    def test_identical_vectors_have_similarity_one(self):
        """Identical normalized vectors should have similarity 1.0."""
        from menard.brevity import cosine_similarity

        vec = np.array([0.6, 0.8])  # Already normalized (0.6^2 + 0.8^2 = 1)
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors_have_similarity_zero(self):
        """Orthogonal vectors should have similarity 0.0."""
        from menard.brevity import cosine_similarity

        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 1.0])
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)

    def test_opposite_vectors_have_similarity_negative_one(self):
        """Opposite vectors should have similarity -1.0."""
        from menard.brevity import cosine_similarity

        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([-1.0, 0.0])
        assert cosine_similarity(vec1, vec2) == pytest.approx(-1.0)


class TestFindDuplicates:
    """Tests for the find_duplicates function."""

    def test_finds_similar_sections_above_threshold(self):
        """Should find section pairs with similarity above threshold."""
        from menard.brevity import find_duplicates

        # Normalized vectors - vec_a and vec_b are nearly identical
        vec_a = np.array([0.99, 0.14])
        vec_a = vec_a / np.linalg.norm(vec_a)
        vec_b = np.array([0.98, 0.15])
        vec_b = vec_b / np.linalg.norm(vec_b)
        vec_c = np.array([0.14, 0.99])
        vec_c = vec_c / np.linalg.norm(vec_c)

        embeddings = {
            "doc1.md#Section A": (vec_a, (1, 10)),
            "doc2.md#Section B": (vec_b, (1, 5)),
            "doc3.md#Section C": (vec_c, (1, 8)),
        }

        duplicates = find_duplicates(embeddings, threshold=0.99)

        assert len(duplicates) == 1
        pair = duplicates[0]
        assert pair.similarity >= 0.99
        assert "Section A" in pair.source or "Section A" in pair.target
        assert "Section B" in pair.source or "Section B" in pair.target

    def test_returns_empty_list_when_no_duplicates(self):
        """Should return empty list when no sections are similar."""
        from menard.brevity import find_duplicates

        # All orthogonal vectors
        embeddings = {
            "doc1.md#A": (np.array([1.0, 0.0, 0.0]), (1, 5)),
            "doc2.md#B": (np.array([0.0, 1.0, 0.0]), (1, 5)),
            "doc3.md#C": (np.array([0.0, 0.0, 1.0]), (1, 5)),
        }

        duplicates = find_duplicates(embeddings, threshold=0.8)
        assert duplicates == []

    def test_does_not_compare_section_to_itself(self):
        """Should not report a section as duplicate of itself."""
        from menard.brevity import find_duplicates

        embeddings = {
            "doc1.md#A": (np.array([1.0, 0.0]), (1, 5)),
        }

        duplicates = find_duplicates(embeddings, threshold=0.5)
        assert duplicates == []

    def test_results_sorted_by_similarity_descending(self):
        """Duplicate pairs should be sorted by similarity, highest first."""
        from menard.brevity import find_duplicates

        embeddings = {
            "a.md#X": (np.array([1.0, 0.0, 0.0]), (1, 5)),
            "b.md#Y": (np.array([0.95, 0.05, 0.0]), (1, 5)),  # ~0.95 similarity with X
            "c.md#Z": (np.array([0.85, 0.15, 0.0]), (1, 5)),  # ~0.85 similarity with X
        }

        duplicates = find_duplicates(embeddings, threshold=0.8)

        assert len(duplicates) >= 2
        for i in range(len(duplicates) - 1):
            assert duplicates[i].similarity >= duplicates[i + 1].similarity


class TestEmbedSections:
    """Tests for section embedding with fastembed."""

    def test_embeds_all_sections_from_docs(self, tmp_path: Path, monkeypatch):
        """Should embed all sections from all doc files."""
        monkeypatch.chdir(tmp_path)

        # Create docs with sections
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text(
            "# Guide\n## Installation\nInstall stuff.\n## Usage\nUse it.\n"
        )
        (tmp_path / "README.md").write_text("# README\n## Quick Start\nGet started fast.\n")

        doc_paths = ["docs/**/*.md", "README.md"]

        from menard.brevity import embed_sections

        result = embed_sections(tmp_path, doc_paths, model_name="BAAI/bge-small-en-v1.5")

        # Should have 3 sections: Installation, Usage, Quick Start
        assert len(result) == 3
        assert any("Installation" in key for key in result)
        assert any("Usage" in key for key in result)
        assert any("Quick Start" in key for key in result)

        # Each embedding should be a numpy array with 384 dimensions
        for _key, (embedding, lines) in result.items():
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape == (384,)
            assert isinstance(lines, tuple)
            assert len(lines) == 2

    def test_returns_empty_dict_when_no_docs(self, tmp_path: Path, monkeypatch):
        """Should return empty dict when no doc files exist."""
        monkeypatch.chdir(tmp_path)

        from menard.brevity import embed_sections

        result = embed_sections(tmp_path, ["docs/**/*.md"], model_name="BAAI/bge-small-en-v1.5")

        assert result == {}

    def test_skips_docs_without_sections(self, tmp_path: Path, monkeypatch):
        """Should skip docs that have no sections (only title)."""
        monkeypatch.chdir(tmp_path)

        # Doc with only a title, no sections
        (tmp_path / "empty.md").write_text("# Title Only\nSome content without sections.\n")

        from menard.brevity import embed_sections

        result = embed_sections(tmp_path, ["empty.md"], model_name="BAAI/bge-small-en-v1.5")

        assert result == {}


class TestEmbeddingsCache:
    """Tests for embedding cache functionality."""

    def test_save_and_load_embeddings_cache(self, tmp_path: Path, monkeypatch):
        """Should save and load embeddings from cache."""
        monkeypatch.chdir(tmp_path)

        from menard.brevity import load_embeddings_cache, save_embeddings_cache

        embeddings = {
            "doc.md#Section": (np.array([0.1, 0.2, 0.3]), (1, 10)),
        }

        save_embeddings_cache(tmp_path, embeddings, model_name="test-model")
        loaded = load_embeddings_cache(tmp_path, model_name="test-model")

        assert loaded is not None
        assert "doc.md#Section" in loaded
        assert np.allclose(loaded["doc.md#Section"][0], embeddings["doc.md#Section"][0])

    def test_cache_returns_none_when_missing(self, tmp_path: Path, monkeypatch):
        """Should return None when cache doesn't exist."""
        monkeypatch.chdir(tmp_path)

        from menard.brevity import load_embeddings_cache

        loaded = load_embeddings_cache(tmp_path, model_name="test-model")
        assert loaded is None

    def test_cache_invalidated_when_model_changes(self, tmp_path: Path, monkeypatch):
        """Cache should be invalid when using different model name."""
        monkeypatch.chdir(tmp_path)

        from menard.brevity import load_embeddings_cache, save_embeddings_cache

        embeddings = {
            "doc.md#Section": (np.array([0.1, 0.2, 0.3]), (1, 10)),
        }

        save_embeddings_cache(tmp_path, embeddings, model_name="model-a")
        loaded = load_embeddings_cache(tmp_path, model_name="model-b")

        assert loaded is None  # Different model = cache miss


class TestCLIIntegration:
    """Integration tests for the brevity CLI command."""

    def test_cmd_brevity_returns_zero_when_no_duplicates(self, tmp_path: Path, monkeypatch):
        """Command should return 0 when no duplicates found."""
        monkeypatch.chdir(tmp_path)

        # Create config
        config = tmp_path / "pyproject.toml"
        config.write_text('[tool.menard]\ndoc_paths = ["docs/**/*.md"]\n')

        # Create docs with very different content
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("# A\n## Apples\nApples are red fruits that grow on trees.\n")
        (docs / "b.md").write_text(
            "# B\n## Quantum Physics\nQuantum mechanics describes subatomic particles.\n"
        )

        from argparse import Namespace

        from menard.cli import cmd_brevity

        result = cmd_brevity(Namespace(threshold=0.95, format="text", model=None, no_cache=True))

        assert result == 0

    def test_cmd_brevity_returns_one_when_duplicates_found(self, tmp_path: Path, monkeypatch):
        """Command should return 1 when duplicates found (advisory)."""
        monkeypatch.chdir(tmp_path)

        # Create config
        config = tmp_path / "pyproject.toml"
        config.write_text('[tool.menard]\ndoc_paths = ["docs/**/*.md"]\n')

        # Create docs with nearly identical content
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text(
            "# A\n## Installation Guide\nTo install the package, run pip install mypackage.\n"
        )
        (docs / "b.md").write_text(
            "# B\n## Setup Instructions\nTo install the package, run pip install mypackage.\n"
        )

        from argparse import Namespace

        from menard.cli import cmd_brevity

        result = cmd_brevity(Namespace(threshold=0.8, format="text", model=None, no_cache=True))

        # With very similar content, should find duplicates
        assert result == 1

    def test_cmd_brevity_json_format(self, tmp_path: Path, monkeypatch, capsys):
        """Command should output valid JSON when format=json."""
        monkeypatch.chdir(tmp_path)

        config = tmp_path / "pyproject.toml"
        config.write_text('[tool.menard]\ndoc_paths = ["docs/**/*.md"]\n')

        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("# A\n## Topic\nContent about a topic.\n")

        import json
        from argparse import Namespace

        from menard.cli import cmd_brevity

        cmd_brevity(Namespace(threshold=0.8, format="json", model=None, no_cache=True))

        captured = capsys.readouterr()
        # Should be valid JSON
        data = json.loads(captured.out)
        assert "duplicates" in data
        assert "threshold" in data
        assert "sections_analyzed" in data


class TestBrevityExclude:
    """Tests for brevity exclusion patterns."""

    def test_matches_file_pattern(self):
        """Should match file-level patterns."""
        from menard.cli import _matches_brevity_exclude

        assert _matches_brevity_exclude("CLAUDE.md#Section", ["CLAUDE.md"])
        assert _matches_brevity_exclude("docs/api.md#Auth", ["docs/api.md"])
        assert not _matches_brevity_exclude("README.md#Section", ["CLAUDE.md"])

    def test_matches_section_wildcard(self):
        """Should match section wildcards like *#License."""
        from menard.cli import _matches_brevity_exclude

        assert _matches_brevity_exclude("README.md#License", ["*#License"])
        assert _matches_brevity_exclude("docs/index.md#License", ["*#License"])
        assert not _matches_brevity_exclude("README.md#Quick Start", ["*#License"])

    def test_matches_full_section_pattern(self):
        """Should match full file#section patterns."""
        from menard.cli import _matches_brevity_exclude

        assert _matches_brevity_exclude("README.md#Quick Start", ["README.md#Quick Start"])
        assert not _matches_brevity_exclude("README.md#License", ["README.md#Quick Start"])

    def test_matches_glob_patterns(self):
        """Should match glob patterns."""
        from menard.cli import _matches_brevity_exclude

        assert _matches_brevity_exclude("docs/api.md#Auth", ["docs/*"])
        assert _matches_brevity_exclude("docs/nested/file.md#Section", ["docs/**/*.md"])
        assert not _matches_brevity_exclude("README.md#Section", ["docs/*"])
