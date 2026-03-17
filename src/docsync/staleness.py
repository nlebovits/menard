"""Git diff-based staleness detection for documentation."""

import subprocess
from pathlib import Path

from docsync.sections import parse_markdown_section
from docsync.toml_links import LinkTarget


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
    # Get the last commit that modified the code file
    code_commit = get_last_commit(repo_root, code_file)
    if not code_commit:
        # Code file has no git history (new file or not in repo)
        # Consider docs stale by default
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

    doc_path = repo_root / doc_target.file

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
