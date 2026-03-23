"""Reviewed state storage for menard fix command."""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Standard length for short commit SHAs
SHA_SHORT_LENGTH = 7


@dataclass
class Review:
    """A review marking a doc as up-to-date at a specific code commit."""

    code_file: str
    doc_target: str
    reviewed_at: str  # ISO format
    code_commit_at_review: str
    reviewed_by: str = "user"


def _get_reviews_path(repo_root: Path) -> Path:
    """Get path to reviewed.json file."""
    return repo_root / ".menard" / "reviewed.json"


def normalize_path(path: str) -> str:
    """Normalize a file path for consistent comparison.

    Strips leading ./ and normalizes path separators.
    """
    # Strip leading ./
    if path.startswith("./"):
        path = path[2:]
    # Normalize path separators (for Windows compatibility)
    path = path.replace("\\", "/")
    return path


def load_reviews(repo_root: Path) -> list[Review]:
    """Load reviews from .menard/reviewed.json.

    Returns empty list if file is missing or malformed.
    Logs warnings for malformed entries but continues loading valid ones.
    """
    reviews_path = _get_reviews_path(repo_root)
    if not reviews_path.exists():
        return []

    try:
        data = json.loads(reviews_path.read_text())
    except json.JSONDecodeError as e:
        logger.warning("Could not parse %s: %s", reviews_path, e)
        return []

    reviews = []
    for i, r in enumerate(data.get("reviews", [])):
        try:
            reviews.append(Review(**r))
        except TypeError as e:
            logger.warning("Skipping malformed review entry %d: %s", i, e)
            continue

    return reviews


def save_review(repo_root: Path, review: Review) -> None:
    """Save a review to .menard/reviewed.json, replacing any existing review for same code+doc."""
    reviews_path = _get_reviews_path(repo_root)

    # Ensure .menard directory exists
    reviews_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing reviews
    existing = load_reviews(repo_root)

    # Normalize paths for comparison
    review_code = normalize_path(review.code_file)
    review_doc = normalize_path(review.doc_target)

    # Remove any existing review for same code_file + doc_target
    existing = [
        r
        for r in existing
        if not (
            normalize_path(r.code_file) == review_code
            and normalize_path(r.doc_target) == review_doc
        )
    ]

    # Append new review
    existing.append(review)

    # Write back
    data = {"reviews": [asdict(r) for r in existing]}
    reviews_path.write_text(json.dumps(data, indent=2))


def is_review_valid(review: Review, current_commit: str) -> bool:
    """Check if a review is still valid (code hasn't changed since review)."""
    return review.code_commit_at_review == current_commit


def find_review(reviews: list[Review], code_file: str, doc_target: str) -> Review | None:
    """Find a review for a specific code_file + doc_target pair.

    Normalizes paths for comparison to handle ./prefix and path separator differences.
    """
    code_file = normalize_path(code_file)
    doc_target = normalize_path(doc_target)

    for review in reviews:
        if (
            normalize_path(review.code_file) == code_file
            and normalize_path(review.doc_target) == doc_target
        ):
            return review
    return None


def clean_reviews(repo_root: Path, remove_all: bool = False) -> int:
    """Remove orphaned reviews (code files that no longer exist).

    Args:
        repo_root: Repository root path
        remove_all: If True, remove all reviews regardless of file existence

    Returns:
        Number of reviews removed
    """
    reviews_path = _get_reviews_path(repo_root)
    if not reviews_path.exists():
        return 0

    # Optimization: for remove_all, just count lines and delete
    if remove_all:
        try:
            data = json.loads(reviews_path.read_text())
            count = len(data.get("reviews", []))
        except (json.JSONDecodeError, KeyError):
            count = 0
        reviews_path.unlink()
        return count

    reviews = load_reviews(repo_root)
    if not reviews:
        return 0

    # Keep only reviews where code file exists
    kept = [r for r in reviews if (repo_root / r.code_file).exists()]
    removed = len(reviews) - len(kept)

    if removed > 0:
        if kept:
            data = {"reviews": [asdict(r) for r in kept]}
            reviews_path.write_text(json.dumps(data, indent=2))
        else:
            reviews_path.unlink()

    return removed
