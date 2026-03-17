"""Git diff-based staleness detection for documentation."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from docsync.sections import parse_markdown_section
from docsync.toml_links import LinkTarget


@dataclass
class CommitInfo:
    """Information about a single commit."""

    sha: str
    date: str  # ISO format YYYY-MM-DD
    message: str

    def to_dict(self) -> dict:
        return {"sha": self.sha, "date": self.date, "message": self.message}


@dataclass
class StalenessResult:
    """Enriched staleness check result with detailed information."""

    is_stale: bool
    reason: str
    code_file: str
    doc_target: str
    section: str | None = None

    # Enriched fields (issues #28, #31, #33)
    last_code_change: str | None = None  # ISO date
    last_code_commit: str | None = None  # SHA
    last_doc_update: str | None = None  # ISO date
    commits_since: list[CommitInfo] = field(default_factory=list)
    symbols_added: list[str] = field(default_factory=list)
    symbols_removed: list[str] = field(default_factory=list)
    code_diff: str | None = None  # Raw diff (only if requested)

    def to_dict(self, include_diff: bool = False) -> dict:
        """Convert to dictionary for JSON output."""
        result = {
            "code_file": self.code_file,
            "doc_target": self.doc_target,
            "reason": self.reason,
            "section": self.section,
        }

        # Add enriched fields if available
        if self.last_code_change:
            result["last_code_change"] = self.last_code_change
        if self.last_code_commit:
            result["last_code_commit"] = self.last_code_commit
        if self.last_doc_update:
            result["last_doc_update"] = self.last_doc_update
        if self.commits_since:
            result["commits_since"] = [c.to_dict() for c in self.commits_since]
        if self.symbols_added:
            result["symbols_added"] = self.symbols_added
        if self.symbols_removed:
            result["symbols_removed"] = self.symbols_removed
        if include_diff and self.code_diff:
            result["code_diff"] = self.code_diff

        return result


def get_last_commit(repo_root: Path, file_path: str) -> str | None:
    """Get the SHA of the last commit that modified a file."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", file_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        commit = result.stdout.strip()
        return commit if commit else None
    except subprocess.CalledProcessError:
        return None


def get_changed_lines(repo_root: Path, file_path: str, since_commit: str) -> set[int]:
    """
    Get line numbers that changed in file_path between since_commit and HEAD.
    Returns set of 1-indexed line numbers.
    """
    try:
        # Get unified diff with line numbers
        result = subprocess.run(
            ["git", "diff", since_commit, "HEAD", "--unified=0", "--", file_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        diff_output = result.stdout
    except subprocess.CalledProcessError:
        return set()

    changed_lines = set()

    # Parse diff hunks to extract changed line numbers
    # Format: @@ -old_start,old_count +new_start,new_count @@
    for line in diff_output.split("\n"):
        if line.startswith("@@"):
            # Extract the +new_start,new_count part
            parts = line.split("@@")[1].strip().split()
            for part in parts:
                if part.startswith("+"):
                    # Parse +start,count or just +start
                    range_str = part[1:]  # Remove the +
                    if "," in range_str:
                        start, count = range_str.split(",")
                        start = int(start)
                        count = int(count)
                        # Add all lines in this range
                        for i in range(start, start + count):
                            changed_lines.add(i)
                    else:
                        # Single line change
                        changed_lines.add(int(range_str))

    return changed_lines


def get_staged_changes(repo_root: Path, file_path: str) -> set[int] | None:
    """
    Get line numbers that are staged (changed in index) for file_path.
    Returns set of 1-indexed line numbers, or None if file is not staged.

    This allows checking if documentation is being updated in the same commit
    as the code change (issue #20).
    """
    try:
        # Check if file is staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        staged_files = result.stdout.strip().split("\n")
        if file_path not in staged_files:
            return None

        # Get diff of staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--unified=0", "--", file_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        diff_output = result.stdout
    except subprocess.CalledProcessError:
        return None

    changed_lines = set()

    # Parse diff hunks (same format as get_changed_lines)
    for line in diff_output.split("\n"):
        if line.startswith("@@"):
            parts = line.split("@@")[1].strip().split()
            for part in parts:
                if part.startswith("+"):
                    range_str = part[1:]
                    if "," in range_str:
                        start, count = range_str.split(",")
                        start = int(start)
                        count = int(count)
                        for i in range(start, start + count):
                            changed_lines.add(i)
                    else:
                        changed_lines.add(int(range_str))

    return changed_lines


def get_commit_date(repo_root: Path, commit: str) -> str | None:
    """Get the date of a commit in ISO format (YYYY-MM-DD)."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", commit],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or None
    except subprocess.CalledProcessError:
        return None


def get_commits_since(
    repo_root: Path, file_path: str, since_commit: str, max_commits: int = 5
) -> list[CommitInfo]:
    """
    Get commits that modified a file since a given commit.

    Returns list of CommitInfo, most recent first, up to max_commits.
    """
    try:
        # Get commits that modified file_path since since_commit
        result = subprocess.run(
            [
                "git",
                "log",
                f"{since_commit}..HEAD",
                "--format=%H|%cs|%s",
                f"-{max_commits}",
                "--",
                file_path,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
        if not output:
            return []

        commits = []
        for line in output.split("\n"):
            if "|" in line:
                parts = line.split("|", 2)
                if len(parts) == 3:
                    commits.append(CommitInfo(sha=parts[0][:7], date=parts[1], message=parts[2]))

        return commits
    except subprocess.CalledProcessError:
        return []


def get_code_diff(
    repo_root: Path, file_path: str, since_commit: str, max_lines: int = 30
) -> str | None:
    """
    Get the git diff of a file since a commit.

    Returns the diff truncated to max_lines, or None if no diff.
    """
    try:
        result = subprocess.run(
            ["git", "diff", since_commit, "HEAD", "--", file_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        diff = result.stdout.strip()
        if not diff:
            return None

        lines = diff.split("\n")
        if len(lines) > max_lines:
            truncated = "\n".join(lines[:max_lines])
            remaining = len(lines) - max_lines
            return f"{truncated}\n... (truncated, {remaining} more lines)"

        return diff
    except subprocess.CalledProcessError:
        return None


def is_doc_stale(
    repo_root: Path, code_file: str, doc_target: LinkTarget, transitive_files: list[str] = None
) -> tuple[bool, str]:
    """
    Check if a documentation target is stale relative to code changes.

    Returns (is_stale, reason) tuple:
    - is_stale: True if doc needs updating
    - reason: Human-readable explanation

    For section-specific targets (doc_target.section is not None):
    - Only checks if that section has been updated since code changed
    - Uses git diff to determine which lines changed

    For whole-file targets:
    - Uses simple timestamp comparison (file modification time)

    If transitive_files is provided, also checks if any of those files changed
    and whether the doc was updated since.
    """
    doc_path = repo_root / doc_target.file

    # Get the last commit that modified the code file
    code_commit = get_last_commit(repo_root, code_file)
    if not code_commit:
        # Code file has no git history (new file or not in repo)
        # But first check if docs are being updated in this commit (staged)
        if doc_target.section:
            section_range = parse_markdown_section(doc_path, doc_target.section)
            if section_range:
                start_line, end_line = section_range
                staged_lines = get_staged_changes(repo_root, doc_target.file)
                if staged_lines is not None:
                    section_updated_in_stage = any(
                        start_line <= line <= end_line for line in staged_lines
                    )
                    if section_updated_in_stage:
                        return False, "Section being updated in this commit (staged)"
        else:
            staged_lines = get_staged_changes(repo_root, doc_target.file)
            if staged_lines is not None and len(staged_lines) > 0:
                return False, "Doc being updated in this commit (staged)"

        return True, f"{code_file} is new or untracked"

    # Check all files that could trigger staleness (code + transitive imports)
    all_code_files = [code_file] + (transitive_files or [])
    most_recent_code_commit = code_commit
    most_recent_code_file = code_file

    for file in all_code_files:
        commit = get_last_commit(repo_root, file)
        if commit and commit != most_recent_code_commit:
            # Check if this commit is newer
            try:
                result = subprocess.run(
                    ["git", "rev-list", "--count", f"{commit}..HEAD"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                if int(result.stdout.strip()) == 0:
                    # This commit is at or after HEAD (shouldn't happen)
                    continue

                # Check which commit is more recent
                result = subprocess.run(
                    ["git", "rev-list", "--count", f"{most_recent_code_commit}..{commit}"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                if int(result.stdout.strip()) > 0:
                    # This commit is more recent
                    most_recent_code_commit = commit
                    most_recent_code_file = file
            except subprocess.CalledProcessError:
                continue

    if doc_target.section:
        # Section-specific staleness check
        section_range = parse_markdown_section(doc_path, doc_target.section)
        if not section_range:
            # Section doesn't exist - validation error, not staleness
            return False, f"Section '{doc_target.section}' not found"

        start_line, end_line = section_range

        # Check 1: Is the doc file staged with changes to this section? (issue #20)
        staged_lines = get_staged_changes(repo_root, doc_target.file)
        if staged_lines is not None:
            # Doc file is staged - check if staged changes include this section
            section_updated_in_stage = any(start_line <= line <= end_line for line in staged_lines)
            if section_updated_in_stage:
                return False, "Section being updated in this commit (staged)"

        # Check 2: Get lines that changed in doc since code changed (committed history)
        changed_lines = get_changed_lines(repo_root, doc_target.file, most_recent_code_commit)

        # Check if any changed lines fall within the section
        section_updated = any(start_line <= line <= end_line for line in changed_lines)

        if section_updated:
            return False, f"Section updated since {most_recent_code_file} changed"
        else:
            return True, f"Section unchanged since {most_recent_code_file} changed"
    else:
        # Whole-file staleness check

        # Check 1: Is the doc file staged? (issue #20)
        staged_lines = get_staged_changes(repo_root, doc_target.file)
        if staged_lines is not None and len(staged_lines) > 0:
            # Doc file is staged with changes
            return False, "Doc being updated in this commit (staged)"

        # Check 2: Simple timestamp comparison (committed history)
        doc_commit = get_last_commit(repo_root, doc_target.file)
        if not doc_commit:
            return True, f"{doc_target.file} is new or untracked"

        # Check if doc was updated after code
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{most_recent_code_commit}..{doc_commit}"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            commits_between = int(result.stdout.strip())
            if commits_between > 0:
                return False, f"Doc updated after {most_recent_code_file} changed"
            else:
                return True, f"Doc unchanged since {most_recent_code_file} changed"
        except subprocess.CalledProcessError:
            # Can't determine order, assume stale
            return True, "Unable to determine commit order"


def check_staleness_enriched(
    repo_root: Path,
    code_file: str,
    doc_target: LinkTarget,
    transitive_files: list[str] | None = None,
    include_diff: bool = False,
    max_diff_lines: int = 30,
    max_commits: int = 5,
) -> StalenessResult:
    """
    Check staleness with enriched information (issues #28, #31, #33).

    Returns a StalenessResult with:
    - Basic staleness info (is_stale, reason)
    - Last code change date and commit
    - Last doc update date
    - Commits since doc was last updated
    - Symbol changes (functions/classes added/removed)
    - Code diff (if include_diff=True)
    """
    # Get basic staleness result first
    is_stale, reason = is_doc_stale(repo_root, code_file, doc_target, transitive_files)

    result = StalenessResult(
        is_stale=is_stale,
        reason=reason,
        code_file=code_file,
        doc_target=str(doc_target),
        section=doc_target.section,
    )

    # Get the commit info for enrichment
    code_commit = get_last_commit(repo_root, code_file)
    if not code_commit:
        return result

    # Find the most recent code commit (same logic as is_doc_stale)
    all_code_files = [code_file] + (transitive_files or [])
    most_recent_code_commit = code_commit
    most_recent_code_file = code_file

    for file in all_code_files:
        commit = get_last_commit(repo_root, file)
        if commit and commit != most_recent_code_commit:
            try:
                check = subprocess.run(
                    ["git", "rev-list", "--count", f"{most_recent_code_commit}..{commit}"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                if int(check.stdout.strip()) > 0:
                    most_recent_code_commit = commit
                    most_recent_code_file = file
            except subprocess.CalledProcessError:
                continue

    # Enrich with dates
    result.last_code_commit = most_recent_code_commit[:7]
    result.last_code_change = get_commit_date(repo_root, most_recent_code_commit)

    # Get doc commit date
    doc_commit = get_last_commit(repo_root, doc_target.file)
    if doc_commit:
        result.last_doc_update = get_commit_date(repo_root, doc_commit)

    # Only get detailed info if stale
    if not is_stale:
        return result

    # Get commits that changed the code file since doc was last updated
    if doc_commit:
        result.commits_since = get_commits_since(
            repo_root, most_recent_code_file, doc_commit, max_commits
        )
    else:
        # Doc has no history, get recent commits on code file
        result.commits_since = get_commits_since(
            repo_root, most_recent_code_file, "HEAD~10", max_commits
        )

    # Get symbol changes (AST diff)
    if doc_commit and most_recent_code_file.endswith(".py"):
        try:
            from docsync.symbols import get_symbol_diff_cached

            symbol_diff = get_symbol_diff_cached(
                repo_root, most_recent_code_file, doc_commit, "HEAD"
            )
            if symbol_diff:
                result.symbols_added = symbol_diff.functions_added + symbol_diff.classes_added
                result.symbols_removed = symbol_diff.functions_removed + symbol_diff.classes_removed
        except Exception:
            # AST parsing failed, continue without symbol info
            pass

    # Get code diff if requested
    if include_diff and doc_commit:
        result.code_diff = get_code_diff(
            repo_root, most_recent_code_file, doc_commit, max_diff_lines
        )

    return result
