"""Tests for reviewed state storage and lookup."""

import json
import tempfile
from pathlib import Path

from docsync.reviewed import (
    Review,
    clean_reviews,
    find_review,
    is_review_valid,
    load_reviews,
    normalize_path,
    save_review,
)


def test_load_reviews_empty():
    """Test loading reviews when file doesn't exist returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        reviews = load_reviews(repo_root)
        assert reviews == []


def test_save_and_load_review():
    """Test saving a review and loading it back."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        (repo_root / ".docsync").mkdir()

        review = Review(
            code_file="src/auth.py",
            doc_target="docs/api.md#Authentication",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review="abc1234",
            reviewed_by="claude",
        )

        save_review(repo_root, review)

        reviews = load_reviews(repo_root)
        assert len(reviews) == 1
        assert reviews[0].code_file == "src/auth.py"
        assert reviews[0].doc_target == "docs/api.md#Authentication"
        assert reviews[0].code_commit_at_review == "abc1234"
        assert reviews[0].reviewed_by == "claude"


def test_is_review_valid_matching_commit():
    """Test review is valid when code commit hasn't changed."""
    review = Review(
        code_file="src/auth.py",
        doc_target="docs/api.md#Authentication",
        reviewed_at="2026-03-17T12:00:00Z",
        code_commit_at_review="abc1234",
    )
    # Same commit = review still valid
    assert is_review_valid(review, current_commit="abc1234") is True


def test_is_review_valid_different_commit():
    """Test review is invalid when code commit has changed."""
    review = Review(
        code_file="src/auth.py",
        doc_target="docs/api.md#Authentication",
        reviewed_at="2026-03-17T12:00:00Z",
        code_commit_at_review="abc1234",
    )
    # Different commit = review invalidated
    assert is_review_valid(review, current_commit="def5678") is False


def test_find_review_exists():
    """Test finding an existing review."""
    reviews = [
        Review(
            code_file="src/auth.py",
            doc_target="docs/api.md#Authentication",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review="abc1234",
        ),
        Review(
            code_file="src/models.py",
            doc_target="docs/models.md",
            reviewed_at="2026-03-18T12:00:00Z",
            code_commit_at_review="def5678",
        ),
    ]

    found = find_review(reviews, "src/auth.py", "docs/api.md#Authentication")
    assert found is not None
    assert found.code_commit_at_review == "abc1234"


def test_find_review_not_found():
    """Test finding a review that doesn't exist returns None."""
    reviews = [
        Review(
            code_file="src/auth.py",
            doc_target="docs/api.md#Authentication",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review="abc1234",
        ),
    ]

    found = find_review(reviews, "src/other.py", "docs/other.md")
    assert found is None


def test_save_review_replaces_existing():
    """Test saving a review for same code+doc replaces old review."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        (repo_root / ".docsync").mkdir()

        # Save first review
        review1 = Review(
            code_file="src/auth.py",
            doc_target="docs/api.md#Authentication",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review="abc1234",
            reviewed_by="alice",
        )
        save_review(repo_root, review1)

        # Save second review for same code+doc (newer commit)
        review2 = Review(
            code_file="src/auth.py",
            doc_target="docs/api.md#Authentication",
            reviewed_at="2026-03-18T12:00:00Z",
            code_commit_at_review="def5678",
            reviewed_by="bob",
        )
        save_review(repo_root, review2)

        # Should only have one review (replaced, not duplicated)
        reviews = load_reviews(repo_root)
        assert len(reviews) == 1
        assert reviews[0].code_commit_at_review == "def5678"
        assert reviews[0].reviewed_by == "bob"


def test_clean_reviews_removes_orphaned():
    """Test clean_reviews removes reviews for non-existent files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        (repo_root / ".docsync").mkdir()

        # Create one file that exists, one that doesn't
        (repo_root / "src").mkdir()
        (repo_root / "src" / "exists.py").write_text("# exists")

        # Save reviews for both
        save_review(
            repo_root,
            Review(
                code_file="src/exists.py",
                doc_target="docs/api.md",
                reviewed_at="2026-03-17T12:00:00Z",
                code_commit_at_review="abc1234",
            ),
        )
        save_review(
            repo_root,
            Review(
                code_file="src/deleted.py",  # This file doesn't exist
                doc_target="docs/api.md",
                reviewed_at="2026-03-17T12:00:00Z",
                code_commit_at_review="def5678",
            ),
        )

        assert len(load_reviews(repo_root)) == 2

        # Clean orphaned reviews
        removed = clean_reviews(repo_root)

        # Should have removed the orphaned one
        assert removed == 1
        reviews = load_reviews(repo_root)
        assert len(reviews) == 1
        assert reviews[0].code_file == "src/exists.py"


def test_clean_reviews_all():
    """Test clean_reviews with remove_all=True removes everything."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        (repo_root / ".docsync").mkdir()
        (repo_root / "src").mkdir()
        (repo_root / "src" / "auth.py").write_text("# code")

        # Save some reviews
        save_review(
            repo_root,
            Review(
                code_file="src/auth.py",
                doc_target="docs/api.md",
                reviewed_at="2026-03-17T12:00:00Z",
                code_commit_at_review="abc1234",
            ),
        )

        assert len(load_reviews(repo_root)) == 1

        # Clean all
        removed = clean_reviews(repo_root, remove_all=True)

        assert removed == 1
        assert len(load_reviews(repo_root)) == 0


def test_load_reviews_malformed_json():
    """Test load_reviews handles malformed JSON gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        docsync_dir = repo_root / ".docsync"
        docsync_dir.mkdir()

        # Write invalid JSON
        (docsync_dir / "reviewed.json").write_text("{ invalid json }")

        # Should return empty list, not crash
        reviews = load_reviews(repo_root)
        assert reviews == []


def test_load_reviews_missing_fields():
    """Test load_reviews handles entries with missing required fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        docsync_dir = repo_root / ".docsync"
        docsync_dir.mkdir()

        # Write JSON with one valid and one invalid entry
        data = {
            "reviews": [
                {
                    "code_file": "src/auth.py",
                    "doc_target": "docs/api.md",
                    "reviewed_at": "2026-03-17T12:00:00Z",
                    "code_commit_at_review": "abc1234",
                },
                {
                    # Missing code_file
                    "doc_target": "docs/api.md",
                    "reviewed_at": "2026-03-17T12:00:00Z",
                },
            ]
        }
        (docsync_dir / "reviewed.json").write_text(json.dumps(data))

        # Should load the valid entry and skip the invalid one
        reviews = load_reviews(repo_root)
        assert len(reviews) == 1
        assert reviews[0].code_file == "src/auth.py"


def test_save_review_creates_docsync_directory():
    """Test save_review creates .docsync directory if missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Do NOT create .docsync directory
        assert not (repo_root / ".docsync").exists()

        review = Review(
            code_file="src/auth.py",
            doc_target="docs/api.md",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review="abc1234",
        )

        # Should not crash, should create directory
        save_review(repo_root, review)

        assert (repo_root / ".docsync").exists()
        assert (repo_root / ".docsync" / "reviewed.json").exists()

        reviews = load_reviews(repo_root)
        assert len(reviews) == 1


def test_normalize_path():
    """Test normalize_path strips leading ./ and normalizes separators."""
    assert normalize_path("./src/auth.py") == "src/auth.py"
    assert normalize_path("src/auth.py") == "src/auth.py"
    assert normalize_path("././src/auth.py") == "./src/auth.py"  # Only strips one ./
    assert normalize_path("src\\auth.py") == "src/auth.py"  # Windows separators


def test_find_review_with_path_normalization():
    """Test find_review matches paths with different formats."""
    reviews = [
        Review(
            code_file="src/auth.py",
            doc_target="docs/api.md#Authentication",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review="abc1234",
        ),
    ]

    # Should find review when searching with ./prefix
    found = find_review(reviews, "./src/auth.py", "./docs/api.md#Authentication")
    assert found is not None
    assert found.code_commit_at_review == "abc1234"


def test_save_review_normalizes_paths():
    """Test save_review properly deduplicates with normalized paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        (repo_root / ".docsync").mkdir()

        # Save with ./prefix
        review1 = Review(
            code_file="./src/auth.py",
            doc_target="./docs/api.md",
            reviewed_at="2026-03-17T12:00:00Z",
            code_commit_at_review="abc1234",
        )
        save_review(repo_root, review1)

        # Save same file without prefix - should replace, not duplicate
        review2 = Review(
            code_file="src/auth.py",
            doc_target="docs/api.md",
            reviewed_at="2026-03-18T12:00:00Z",
            code_commit_at_review="def5678",
        )
        save_review(repo_root, review2)

        reviews = load_reviews(repo_root)
        assert len(reviews) == 1
        assert reviews[0].code_commit_at_review == "def5678"
