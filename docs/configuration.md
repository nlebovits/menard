# Configuration

## pyproject.toml

```toml
[tool.docsync]
require_links = ["src/**/*.py"]  # Code files that must have doc links
transitive_depth = 1             # Import chain depth for staleness detection
```

The `require_links` glob determines which code files need documentation. Files matching this pattern without a link in `links.toml` will show up in coverage reports.

Set `transitive_depth` to control how deep docsync follows imports when detecting staleness. If `src/auth.py` imports `src/crypto.py`, and crypto changes, should auth docs be marked stale? With depth 1, yes. With depth 0, no.

## links.toml

Define code→doc relationships in `.docsync/links.toml`:

```toml
# Single file → single doc
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]

# Section-level precision (recommended)
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]

# One code file → multiple doc sections
[[link]]
code = "src/models/user.py"
docs = [
  "docs/models.md#User Model",
  "docs/api.md#User Endpoints",
]

# Glob patterns
[[link]]
code = "src/models/*.py"
docs = ["docs/models.md"]
```

Section-level links are more precise. When you change `src/auth.py`, only the Authentication section needs updating, not the entire 500-line doc file.

docsync parses doc files to find section headings, extracts line ranges, then uses `git diff` to check if those specific lines changed. If the section's lines didn't change since the code changed, it's stale.

## Staleness Detection

docsync uses git diff analysis to detect stale docs. It checks in two places:

```bash
# 1. Check staged content first (same commit workflow)
git diff --cached -- docs/api.md

# 2. Fall back to git history
git log -1 --format=%H -- src/auth.py
git diff <commit> HEAD -- docs/api.md
```

When you stage both code and docs together, docsync detects the staged changes and passes. If docs aren't staged, it compares git history: if the diff shows changes overlapping with the section's line range, the doc was updated. If no overlap, it's stale.

This works transitively too. If `src/auth.py` imports `src/crypto.py`, and crypto changes, auth docs can be marked stale (controlled by `transitive_depth`).

**Section parsing:** When parsing markdown sections, docsync correctly handles code blocks. Lines starting with `#` inside code fences (` ``` `) are not treated as headings. This ensures sections containing bash scripts or other code with comment syntax are parsed with correct boundaries.

## donttouch

Protect critical content from staleness checks in `.docsync/donttouch`:

```
# Section protection - never mark these as stale
README.md#License
docs/contributing.md#Code of Conduct
CLAUDE.md#Terminology (ENFORCED)

# Literal protection - warn if these strings change
"Python 3.11+"
"Apache-2.0"
"#7730E1"
```

License text, brand colors, version requirements, and policies shouldn't be flagged just because related code changed. Protected sections are skipped during staleness checks. Protected literals trigger warnings if modified.

```bash
docsync list-protected
```

Shows all protected sections and literals.

## Bootstrap

Auto-generate link suggestions:

```bash
docsync bootstrap --apply
```

This uses filename matching (`src/auth.py` → `docs/auth.md`), content analysis (grep docs for code file references), and import graphs to propose links. Review suggestions carefully—bootstrap can't reliably infer links for human-facing docs like tutorials.

## Validation and Coverage

```bash
docsync validate-links  # Check all link targets exist
docsync coverage        # Show documentation coverage percentage
```

Validation catches typos and missing sections. Coverage shows what percentage of your `require_links` files have documentation.

## Commands

```bash
docsync check           # Pre-commit: validate links + check staged files for stale docs
docsync list-stale      # Audit: list ALL stale docs across entire repo
```

The `check` command runs during pre-commit and performs two validations:
1. Link validation - ensures all links in `links.toml` point to existing files/sections
2. Staleness detection - checks if staged code changes require doc updates

Both `check` and `list-stale` support `--format json` for machine consumption. The JSON output includes file paths, section names, line ranges, and git diffs—everything an AI agent needs to make scoped updates.
