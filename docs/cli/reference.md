# CLI Reference

Complete reference for all menard commands.

## Global Options

All commands support these options:

- `--help` - Show help message and exit

## Setup Commands

### init

Initialize menard configuration in your repository.

```bash
menard init
```

**Effect:**

- Adds `[tool.menard]` to `pyproject.toml`
- Creates `.menard/` directory
- Creates `.menard/links.toml` file

**When to use:** First time setting up menard in a project.

---



### bootstrap

Auto-generate links from conventions and content analysis.

```bash
menard bootstrap [--apply]
```

**Options:**

- `--apply` - Apply proposed links to `.menard/links.toml`

**Without `--apply`:** Shows proposed links for review.

**With `--apply`:** Writes links to `.menard/links.toml`.

**How it works:**

1. **Filename matching** - `src/auth.py` → `docs/auth.md`
2. **Content analysis** - Grep docs for code file references
3. **Import graph** - Suggest transitive links

**Example:**

```bash
$ menard bootstrap

Proposed 15 links:

  src/auth.py
    → docs/api.md
    → examples/quickstart.md#Login Flow  ⚠️

⚠️  Warning: 1 doc may be tutorial/guide (marked with ⚠️)
Review these carefully - automated links may not make sense for narrative docs.

To apply these links, run:
  menard bootstrap --apply
```

**When to use:** Initial link generation or discovering missing links.

---

## Validation Commands

### validate-links

Validate that all link references exist.

```bash
menard validate-links
```

**Checks:**

- Code files exist
- Doc files exist
- Sections exist in doc files

**Example output:**

```bash
✓ All 15 links are valid
```

Or with errors:
```bash
❌ Invalid links:
  src/auth.py → docs/api.md#NonExistent
    Section 'NonExistent' not found in docs/api.md
  
  src/missing.py → docs/api.md
    Code file 'src/missing.py' does not exist
```

**When to use:** After editing `.menard/links.toml`, before committing.

---

### coverage

Report documentation coverage.

```bash
menard coverage [--format text|json]
```

**Options:**

- `--format` - Output format (default: `text`)

**Example output (text):**

```bash
Documentation Coverage: 85.0%
  Total code files: 20
  Documented: 17
  Undocumented files:
    src/experimental.py
    src/legacy.py
    src/draft.py
```

**Example output (json):**

```json
{
  "coverage": 0.85,
  "total_files": 20,
  "documented_files": 17,
  "undocumented_files": [
    "src/experimental.py",
    "src/legacy.py",
    "src/draft.py"
  ]
}
```

**When to use:** Audits, reporting, tracking coverage over time.

---

## Staleness Commands

### check

Check staged files for doc freshness (CI/pre-commit).

```bash
menard check [--staged-files FILES] [--format text|json] [--show-diff] [--diff-lines N]
```

**Options:**

- `--staged-files` - Comma-separated list of files (overrides git staged)
- `--format` - Output format (default: `text`)
- `--show-diff` - Include git diff of changed code
- `--diff-lines N` - Max lines of diff to show (default: 30, implies `--show-diff`)

**Purpose:** Fast, focused check for pre-commit hooks and CI pipelines.

**Scope:** Only examines docs linked to **staged files** (or specified files).

**Example (text):**

```bash
$ menard check

menard: ❌ commit blocked

Stale documentation detected:
  docs/api.md#Authentication
    Code: src/auth.py
    Last code change: 2026-03-17 (abc1234)
    Last doc update: 2026-03-10
    Commits since doc updated:
      abc1234 (2026-03-17) feat: add MFA support
      def5678 (2026-03-15) fix: session timeout
    Changed: +2 symbols, -1 symbol
      Added: mfa_verify, mfa_setup
      Removed: legacy_auth
```

**Example (json):**

```json
{
  "stale": [
    {
      "code_file": "src/auth.py",
      "doc_target": "docs/api.md#Authentication",
      "section": "Authentication",
      "reason": "Section unchanged since src/auth.py changed",
      "last_code_change": "2026-03-17",
      "last_code_commit": "abc1234",
      "last_doc_update": "2026-03-10",
      "commits_since": [
        {"sha": "abc1234", "date": "2026-03-17", "message": "feat: add MFA support"}
      ],
      "symbols_added": ["mfa_verify", "mfa_setup"],
      "symbols_removed": ["legacy_auth"]
    }
  ]
}
```

**With `--show-diff`:**

```bash
$ menard check --show-diff

  docs/api.md#Authentication
    Code: src/auth.py
    ...
    Diff:
      +def mfa_verify(user_id: str, code: str) -> bool:
      +    """Verify MFA code."""
      -def legacy_auth(username: str) -> bool:
```

**Exit codes:**

- `0` - All docs fresh
- `1` - Stale docs found

**When to use:** Pre-commit hooks, CI pipelines, focused checks.

---

### list-stale

List ALL stale docs regardless of recent changes (audit).

```bash
menard list-stale [--format text|paths|json] [--show-diff] [--diff-lines N]
```

**Options:**

- `--format` - Output format (default: `text`)
  - `text` - Human-readable with enriched details
  - `paths` - Just file paths (one per line)
  - `json` - Machine-readable with full metadata
- `--show-diff` - Include git diff of changed code
- `--diff-lines N` - Max lines of diff to show (default: 30, implies `--show-diff`)

**Purpose:** Comprehensive audit of documentation staleness.

**Scope:** Scans the **entire repository** for any stale docs.

**Example (text):**

```bash
$ menard list-stale

Found 2 stale documentation targets:

  docs/api.md#Authentication
    Code: src/auth.py
    Last code change: 2026-03-17 (abc1234)
    Last doc update: 2026-03-10
    Commits since doc updated:
      abc1234 (2026-03-17) feat: add MFA support
      def5678 (2026-03-15) fix: session timeout
    Changed: +2 symbols, -1 symbol
      Added: mfa_verify, mfa_setup
      Removed: legacy_auth

  docs/models.md
    Code: src/models/user.py
    Last code change: 2026-03-16 (ghi9012)
    Last doc update: 2026-03-01
```

**Example (paths):**

```bash
docs/api.md
docs/models.md
```

**Example (json):**

```json
{
  "stale": [
    {
      "code_file": "src/auth.py",
      "doc_target": "docs/api.md#Authentication",
      "section": "Authentication",
      "reason": "Section unchanged since src/auth.py changed",
      "last_code_change": "2026-03-17",
      "last_code_commit": "abc1234",
      "last_doc_update": "2026-03-10",
      "commits_since": [
        {"sha": "abc1234", "date": "2026-03-17", "message": "feat: add MFA support"}
      ],
      "symbols_added": ["mfa_verify", "mfa_setup"],
      "symbols_removed": ["legacy_auth"]
    }
  ]
}
```

**When to use:** Periodic audits, reviews, finding all stale docs.

---

### affected-docs

Show docs affected by code changes.

```bash
menard affected-docs --files FILE1,FILE2,... [--format text|json]
```

**Options:**

- `--files` - Comma-separated list of code files
- `--format` - Output format (default: `text`)

**Purpose:** Discover which docs need updating when code changes.

**Example (text):**

```bash
$ menard affected-docs --files src/auth.py,src/crypto.py

Affected documentation:

  src/auth.py:
    → docs/api.md#Authentication
    → docs/architecture.md#Auth Module
  
  src/crypto.py:
    → docs/architecture.md#Crypto Module
    → docs/api.md#Session Management (transitive)
```

**Example (json):**

```json
{
  "affected_docs": {
    "src/auth.py": [
      "docs/api.md#Authentication",
      "docs/architecture.md#Auth Module"
    ],
    "src/crypto.py": [
      "docs/architecture.md#Crypto Module",
      "docs/api.md#Session Management"
    ]
  }
}
```

**When to use:** Planning updates, understanding impact of changes.

---

## Information Commands

### info

Show all links for a file.

```bash
menard info FILE [--format text|json]
```

**Options:**

- `--format` - Output format (default: `text`)

**Example (text):**

```bash
$ menard info src/auth.py

Links for src/auth.py:

  Documentation:
    → docs/api.md#Authentication
    → docs/architecture.md#Auth Module
    → CLAUDE.md#Authentication Patterns
  
  Imported by:
    ← src/api/routes.py
    ← src/cli/login.py
```

**Example (json):**

```json
{
  "file": "src/auth.py",
  "docs": [
    "docs/api.md#Authentication",
    "docs/architecture.md#Auth Module",
    "CLAUDE.md#Authentication Patterns"
  ],
  "imported_by": [
    "src/api/routes.py",
    "src/cli/login.py"
  ]
}
```

**When to use:** Understanding relationships, debugging links.

---

### list-protected

List protected sections and literals.

```bash
menard list-protected [--format text|json]
```

**Options:**

- `--format` - Output format (default: `text`)

**Example (text):**

```bash
Protected sections:
  README.md#License
  docs/contributing.md#Code of Conduct
  CLAUDE.md#Terminology

Global literals:
  "Python 3.11+"
  "#7730E1"
```

**Example (json):**

```json
{
  "protected_sections": [
    "README.md#License",
    "docs/contributing.md#Code of Conduct"
  ],
  "protected_literals": [
    "Python 3.11+",
    "#7730E1"
  ]
}
```

**When to use:** Auditing protected content, understanding policies.

---

### skills

List available Claude Code skills.

```bash
menard skills
```

**Example output:**

```bash
Available Claude Code skills:

  audit - Analyze documentation for trackability
    Location: .claude/skills/audit.md
    Usage: Ask Claude to "audit the documentation"
```

**When to use:** Discovering available skills, integration with Claude Code.

---

## Utility Commands

### clear-cache

Clear the import graph cache.

```bash
menard clear-cache
```

**Effect:** Deletes `.menard/cache/` directory containing import graph cache.

**When to use:** After major refactoring, if cache seems stale, or to reclaim disk space.


