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

## Fix Commands

These commands help resolve stale documentation without necessarily updating the docs.

### fix

Interactive mode to resolve stale documentation.

```bash
menard fix
```

**Purpose:** Walk through each stale doc interactively and choose how to resolve it.

**Interactive options for each stale item:**

- `u` - **Update** - Open the doc for editing (marks as needing update)
- `m` - **Mark reviewed** - "I looked at this, docs don't need changes" (ephemeral)
- `i` - **Ignore** - Permanently skip staleness checks for this link
- `s` - **Skip** - Do nothing for now
- `q` - **Quit** - Exit interactive mode

**Example session:**

```bash
$ menard fix

Stale: docs/api.md#Authentication
  Code: src/auth.py
  Last code change: 2026-03-17 (abc1234: feat: add logging)

  [u]pdate  [m]ark reviewed  [i]gnore  [s]kip  [q]uit
  > m
  ✓ Marked as reviewed

Stale: docs/models.md
  Code: src/models/user.py
  ...
```

**When to use:** Periodic cleanup of stale docs, especially after refactoring.

**Note:** Requires a TTY (interactive terminal). For scripting, use `fix-mark-reviewed` or `fix-ignore`.

---

### fix-mark-reviewed

Mark a code→doc relationship as reviewed (ephemeral).

```bash
menard fix-mark-reviewed --code FILE --doc TARGET [--reviewed-by NAME] [--format text|json]
```

**Options:**

- `--code` - Code file path (required)
- `--doc` - Doc target as `file#section` (required)
- `--reviewed-by` - Reviewer name (default: `user`)
- `--format` - Output format (default: `text`)

**Effect:** Records that the documentation was reviewed at the current code commit. The review is valid until the code file changes again.

**Example:**

```bash
$ menard fix-mark-reviewed --code src/auth.py --doc docs/api.md#Authentication
✓ Marked as reviewed at commit abc1234
```

**When to use:**

- Code change doesn't affect documented behavior (logging, internal refactors)
- Cosmetic code changes (formatting, comments)
- Changes to non-documented internals

**How it works:** Stores a review record with the current code commit SHA. When `list-stale` or `check` runs, it compares the stored commit against the current code state. If the code hasn't changed since the review, the link is considered fresh.

---

### fix-ignore

Permanently ignore a code→doc relationship.

```bash
menard fix-ignore --code FILE --doc TARGET [--format text|json]
```

**Options:**

- `--code` - Code file path (required)
- `--doc` - Doc target as `file#section` (required)
- `--format` - Output format (default: `text`)

**Effect:** Adds `ignore = true` to the link in `.menard/links.toml`. This permanently skips staleness checks for this relationship.

**Example:**

```bash
$ menard fix-ignore --code src/legacy.py --doc docs/legacy.md
✓ Added ignore=true to link in .menard/links.toml
```

**When to use:**

- The link was too broad and shouldn't exist
- Deprecated code that won't be updated
- Intentionally divergent documentation

**Note:** This modifies `links.toml`, so the change should be committed. Unlike `fix-mark-reviewed`, this is permanent until you manually remove the `ignore = true` flag.

---

### clean-reviewed

Clean up reviewed state.

```bash
menard clean-reviewed [--all] [--format text|json]
```

**Options:**

- `--all` - Remove all reviews, not just orphaned ones
- `--format` - Output format (default: `text`)

**Effect:** Removes review records for deleted files (orphaned reviews). With `--all`, removes all review records.

**Example:**

```bash
$ menard clean-reviewed
✓ Removed 3 review(s)

$ menard clean-reviewed --all
✓ Removed 12 review(s)
```

**When to use:** After deleting files that had reviews, or to reset all review state.

---

## Review Workflow

Understanding when to use `fix-mark-reviewed` vs `fix-ignore`:

### Decision Tree

```
Code changed, docs flagged stale
    │
    ├─► Does the doc need updating?
    │       │
    │       ├─► Yes → Update the doc, commit both
    │       │
    │       └─► No → Why not?
    │               │
    │               ├─► Code change doesn't affect docs
    │               │   (logging, internal refactor, cosmetic)
    │               │   → fix-mark-reviewed (ephemeral)
    │               │
    │               └─► This link shouldn't exist
    │                   (too broad, deprecated, intentional)
    │                   → fix-ignore (permanent)
```

### Example Scenario

```bash
$ menard list-stale
Found 1 stale documentation target:

  docs/reference/cli.md
    Code: portolan_cli/cli.py
    Last code change: 2026-03-20 (def456)
    Commits since doc updated:
      def456 (2026-03-20) chore: add debug logging
```

The change was just adding debug logging—docs don't need updating:

```bash
$ menard fix-mark-reviewed --code portolan_cli/cli.py --doc docs/reference/cli.md
✓ Marked as reviewed at commit def456

$ menard list-stale
✓ All documentation is up-to-date
```

Later, if `cli.py` changes again (a real feature), it will be flagged stale again. The review only lasts until the next code modification.

### Comparison

| Aspect | `fix-mark-reviewed` | `fix-ignore` |
|--------|---------------------|--------------|
| **Duration** | Until next code change | Permanent |
| **Stored in** | `.menard/reviewed.state` | `.menard/links.toml` |
| **Commit needed** | No (state file) | Yes (links.toml) |
| **Use case** | "This change doesn't need doc update" | "This link shouldn't trigger checks" |
| **Reversible** | Automatic (next change) | Manual (edit links.toml) |

---

## Utility Commands

### clear-cache

Clear the import graph cache.

```bash
menard clear-cache
```

**Effect:** Deletes `.menard/cache/` directory containing import graph cache.

**When to use:** After major refactoring, if cache seems stale, or to reclaim disk space.


