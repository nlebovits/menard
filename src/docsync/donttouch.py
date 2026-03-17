"""Protected content guard - prevents modification of critical files, sections, and strings."""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pathspec

# Security limits
MAX_LINE_LENGTH = 10_000  # 10KB per line to prevent DoS


@dataclass
class ProtectionRules:
    """Parsed protection rules from .docsync/donttouch file."""

    file_patterns: pathspec.PathSpec  # Files/directories protected (gitignore-style)
    file_pattern_strings: list[str]  # Original pattern strings for display
    section_protections: dict[str, list[str]]  # {"README.md": ["License", "Contributing"]}
    global_literals: list[str]  # Strings that must exist somewhere
    scoped_literals: dict[str, list[str]]  # {"pyproject.toml": ["Apache-2.0"]}


@dataclass
class Violation:
    """A protection violation detected during commit."""

    type: str  # "protected_file", "protected_section", "protected_literal"
    file: str
    section: str | None = None
    literal: str | None = None
    reason: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        result = {"type": self.type, "file": self.file, "reason": self.reason}
        if self.section:
            result["section"] = self.section
        if self.literal:
            result["literal"] = self.literal
        return result


def load_donttouch(repo_root: Path) -> ProtectionRules | None:
    """
    Load and parse .docsync/donttouch file.
    Returns None if file doesn't exist.
    Prints warnings to stderr if file has errors.
    """
    donttouch_file = repo_root / ".docsync" / "donttouch"
    if not donttouch_file.exists():
        return None

    # Read file with proper error handling
    try:
        content = donttouch_file.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        print(
            f"⚠️  docsync: {donttouch_file} has invalid UTF-8 encoding: {e}",
            file=sys.stderr,
        )
        return None
    except PermissionError:
        print(f"⚠️  docsync: cannot read {donttouch_file}: permission denied", file=sys.stderr)
        return None
    except OSError as e:
        print(f"⚠️  docsync: cannot read {donttouch_file}: {e}", file=sys.stderr)
        return None

    file_patterns = []
    section_protections = {}
    global_literals = []
    scoped_literals = {}
    line_num = 0

    for line in content.splitlines():
        line_num += 1
        
        # Security: Check line length to prevent DoS
        if len(line) > MAX_LINE_LENGTH:
            print(
                f"⚠️  docsync: {donttouch_file}:{line_num} line too long "
                f"({len(line)} bytes, max {MAX_LINE_LENGTH}), skipping",
                file=sys.stderr,
            )
            continue
        
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Section protection: README.md#License
        if "#" in line and not line.startswith('"'):
            parts = line.split("#", 1)
            if len(parts) == 2:
                file_path = parts[0].strip()
                section_name = parts[1].strip()
                
                # Security: Prevent path traversal
                if ".." in file_path or file_path.startswith("/"):
                    print(
                        f"⚠️  docsync: {donttouch_file}:{line_num} "
                        f"path traversal attempt '{file_path}', skipping",
                        file=sys.stderr,
                    )
                    continue
                
                if file_path and section_name:
                    if file_path not in section_protections:
                        section_protections[file_path] = []
                    section_protections[file_path].append(section_name)
                    continue

        # File-scoped literal: pyproject.toml: "Apache-2.0"
        if ":" in line and '"' in line:
            match = re.match(r'^(.+?):\s*"(.+)"$', line)
            if match:
                file_path = match.group(1).strip()
                literal = match.group(2)
                
                # Security: Prevent path traversal
                if ".." in file_path or file_path.startswith("/"):
                    print(
                        f"⚠️  docsync: {donttouch_file}:{line_num} "
                        f"path traversal attempt '{file_path}', skipping",
                        file=sys.stderr,
                    )
                    continue
                
                if file_path not in scoped_literals:
                    scoped_literals[file_path] = []
                scoped_literals[file_path].append(literal)
                continue

        # Global literal: "Apache-2.0"
        if line.startswith('"') and line.endswith('"'):
            if len(line) < 2:
                continue  # Empty quotes
            literal = line[1:-1]  # Remove quotes
            # Handle escaped quotes
            literal = literal.replace('\\"', '"')
            if literal:  # Don't add empty literals
                global_literals.append(literal)
            continue

        # File/directory/glob pattern
        # Security: Prevent path traversal
        if ".." in line or line.startswith("/"):
            print(
                f"⚠️  docsync: {donttouch_file}:{line_num} "
                f"path traversal attempt '{line}', skipping",
                file=sys.stderr,
            )
            continue
        
        file_patterns.append(line)

    # Create PathSpec from patterns using gitignore-style matching
    spec = pathspec.PathSpec.from_lines("gitignore", file_patterns)

    return ProtectionRules(
        file_patterns=spec,
        file_pattern_strings=file_patterns,
        section_protections=section_protections,
        global_literals=global_literals,
        scoped_literals=scoped_literals,
    )


def check_protections(
    repo_root: Path, staged_files: list[str], rules: ProtectionRules
) -> list[Violation]:
    """
    Check all protection rules against staged files.
    Returns list of violations found.
    """
    violations = []

    # Check 1: File/directory protection
    violations.extend(_check_file_protection(staged_files, rules.file_patterns))

    # Check 2: Section protection
    violations.extend(_check_section_protection(repo_root, staged_files, rules.section_protections))

    # Check 3: Literal string protection
    violations.extend(
        _check_literal_protection(
            repo_root, staged_files, rules.global_literals, rules.scoped_literals
        )
    )

    return violations


def _check_file_protection(staged_files: list[str], patterns: pathspec.PathSpec) -> list[Violation]:
    """Check if any staged file matches protected patterns."""
    violations = []
    for file in staged_files:
        if patterns.match_file(file):
            violations.append(
                Violation(
                    type="protected_file",
                    file=file,
                    reason="File is protected by .docsync/donttouch",
                )
            )
    return violations


def _check_section_protection(
    repo_root: Path, staged_files: list[str], protected_sections: dict[str, list[str]]
) -> list[Violation]:
    """Check if protected sections were modified."""
    from docsync.sections import parse_markdown_section

    violations = []

    for file in staged_files:
        if file not in protected_sections:
            continue

        # Get diff for this file
        diff_hunks = _get_file_diff_hunks(repo_root, file)
        if not diff_hunks:
            continue

        # Check each protected section
        for section_name in protected_sections[file]:
            section_range = parse_markdown_section(repo_root / file, section_name)
            if not section_range:
                # Section doesn't exist - warn user
                print(
                    f"⚠️  docsync: protected section '{section_name}' not found in {file}",
                    file=sys.stderr,
                )
                continue

            # Check if any diff hunk touches this section's line range
            if _diff_touches_lines(diff_hunks, section_range):
                violations.append(
                    Violation(
                        type="protected_section",
                        file=file,
                        section=section_name,
                        reason=f"Section '{section_name}' is protected",
                    )
                )

    return violations


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace for comparison (collapse multiple spaces/tabs to single space)."""
    return " ".join(text.split())


def _check_literal_protection(
    repo_root: Path,
    staged_files: list[str],
    global_literals: list[str],
    scoped_literals: dict[str, list[str]],
) -> list[Violation]:
    """
    Check if protected strings were removed from files.
    Uses whitespace-normalized comparison to prevent trivial bypasses.
    """
    violations = []

    # Check scoped literals first (more specific)
    for file in staged_files:
        if file not in scoped_literals:
            continue

        new_content = _get_staged_content(repo_root, file)
        if new_content is None:
            continue

        new_content_normalized = _normalize_whitespace(new_content)

        for literal in scoped_literals[file]:
            literal_normalized = _normalize_whitespace(literal)
            if literal_normalized not in new_content_normalized:
                violations.append(
                    Violation(
                        type="protected_literal",
                        file=file,
                        literal=literal,
                        reason=f"Required string '{literal}' removed from {file} (whitespace-normalized)",
                    )
                )

    # Check global literals (any file that previously contained them)
    for file in staged_files:
        old_content = _get_head_content(repo_root, file)
        new_content = _get_staged_content(repo_root, file)

        if old_content is None or new_content is None:
            continue

        old_content_normalized = _normalize_whitespace(old_content)
        new_content_normalized = _normalize_whitespace(new_content)

        for literal in global_literals:
            literal_normalized = _normalize_whitespace(literal)
            if (
                literal_normalized in old_content_normalized
                and literal_normalized not in new_content_normalized
            ):
                violations.append(
                    Violation(
                        type="protected_literal",
                        file=file,
                        literal=literal,
                        reason=f"Global protected string '{literal}' removed (whitespace-normalized)",
                    )
                )

    return violations


def _get_file_diff_hunks(repo_root: Path, file: str) -> list[tuple[int, int]]:
    """
    Get diff hunks for a staged file as list of (start_line, end_line) tuples.
    Uses git diff --cached to see staged changes.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "-U0", file],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    # Parse unified diff format to extract line ranges
    # Format: @@ -start,count +start,count @@
    hunks = []
    for line in result.stdout.splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2)) if match.group(2) else 1
                end = start + count - 1
                hunks.append((start, end))

    return hunks


def _diff_touches_lines(hunks: list[tuple[int, int]], section_range: tuple[int, int]) -> bool:
    """Check if any diff hunk overlaps with section's line range."""
    section_start, section_end = section_range
    for hunk_start, hunk_end in hunks:
        # Check for overlap
        if hunk_start <= section_end and hunk_end >= section_start:
            return True
    return False


def _get_staged_content(repo_root: Path, file: str) -> str | None:
    """Get staged content of a file."""
    try:
        result = subprocess.run(
            ["git", "show", f":{file}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None


def _get_head_content(repo_root: Path, file: str) -> str | None:
    """Get HEAD content of a file."""
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{file}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None
