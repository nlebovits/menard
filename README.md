<p align="center">
  <img src=".github/branding/profile.png" alt="docsync logo" width="200">
</p>

# docsync

**Keep your code and documentation in sync with centralized linking and section-aware staleness detection.**

docsync is a pre-commit hook and CLI tool that ensures documentation stays fresh by tracking relationships between code files and their documentation. It detects stale docs through git diff analysis, blocks commits when linked documentation is outdated, and provides agent-native commands for programmatic workflows.

## Features

- **Centralized TOML links**: Define code↔doc relationships in `.docsync/links.toml` (no inline comments!)
- **Section-level precision**: Link to specific doc sections (`docs/api.md#Authentication`) for targeted staleness checking
- **Git diff-based staleness**: Uses `git diff` to detect if doc sections were updated since code changed
- **Import-aware staleness**: Detects when docs are stale due to transitive code changes
- **Pre-commit enforcement**: Blocks commits when documentation is missing or outdated
- **Agent-native UX**: JSON output, deterministic checks, and scoped update tasks for AI agents
- **Auto-bootstrap**: Intelligently generates links from filename conventions and content analysis
- **Doc audit skill**: Claude Code skill that analyzes docs for trackability, suggests `links.toml` entries, `donttouch` rules, and restructuring

## Installation

```bash
# Install with uv (recommended)
uv pip install git+https://github.com/nlebovits/docsync.git

# Or with pip
pip install git+https://github.com/nlebovits/docsync.git
```

## Quick Start

### 1. Initialize in your repository

```bash
cd your-repo
docsync init
```

This creates:
- `[tool.docsync]` configuration in `pyproject.toml`
- `.docsync/links.toml` file for defining code-doc links
- `.docsync/` directory for cache storage

### 2. Define code-documentation links

Edit `.docsync/links.toml`:

```toml
# Simple whole-file link
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]

# Section-specific link (more precise!)
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]

# Multiple targets for one code file
[[link]]
code = "src/models/user.py"
docs = [
  "docs/models.md#User Model",
  "docs/api.md#User Endpoints",
]

# Glob patterns for directory-level links
[[link]]
code = "src/models/*.py"
docs = ["docs/models.md"]
```

Or use auto-generation:

```bash
docsync bootstrap --apply
```

### 3. Install the pre-commit hook

```bash
docsync install-hook
```

Now commits will be blocked if documentation is stale.

## How It Works: Deterministic Checks + Probabilistic Updates

docsync provides **deterministic staleness detection** that AI agents use for **scoped, probabilistic updates**:

### Layer 1: Deterministic Check (docsync)

```bash
$ git commit -m "refactor: extract auth helpers"

docsync: ❌ commit blocked

Stale documentation detected:
  docs/api.md#Authentication
    Code: src/auth.py
    Reason: Section unchanged since src/auth.py changed

  docs/api.md#Session Management
    Code: src/auth.py
    Reason: Section unchanged since src/crypto.py changed (transitive)
```

This is **precise and machine-readable**. No AI guessing required.

### Layer 2: Probabilistic Update (AI Agent)

```bash
$ docsync list-stale --format json | claude-agent update-docs
```

AI gets exact coordinates:

```json
{
  "stale": [
    {
      "code_file": "src/auth.py",
      "doc_target": "docs/api.md#Authentication",
      "section": "Authentication",
      "reason": "Section unchanged since src/auth.py changed"
    }
  ]
}
```

The AI's task is **scoped precisely**:
- "Update the Authentication section (lines 45-89) in docs/api.md"
- "Don't touch Session Management section"
- "The authenticate() function now calls crypto.validate_token()"

**Result**: Deterministic constraints make probabilistic updates reliable.

## Section-Level Staleness Detection

The key innovation: **section-specific links + git diff analysis**.

### Without sections (whole-file links):
```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]  # 500-line file with 15 sections
```

**Problem**: Any change to `src/auth.py` marks the entire 500-line doc as stale. AI agents have to read and potentially update all 15 sections.

### With sections (targeted links):
```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]  # Specific 44-line section
```

**Solution**: Only the Authentication section is marked stale. AI gets a 44-line update task with precise scope.

### How staleness is detected:

1. Get the last commit that changed `src/auth.py`
2. Run `git diff <that_commit> HEAD -- docs/api.md`
3. Parse the diff to see which lines changed
4. Check if any changed lines fall within the Authentication section's line range
5. If yes → section was updated, not stale. If no → stale.

This is **accurate**: updating a different section doesn't clear staleness for Authentication.

## Commands

### Setup & Validation

| Command | Description |
|---------|-------------|
| `docsync init` | Initialize configuration and links file |
| `docsync install-hook` | Install pre-commit hook |
| `docsync bootstrap [--apply]` | Auto-generate links from conventions |
| `docsync validate-links` | Check that all link references exist |

### Staleness Checking

| Command | Description |
|---------|-------------|
| `docsync check [--format json]` | Check staged files for doc freshness (CI/pre-commit) |
| `docsync list-stale [--format json\|paths]` | List ALL stale docs regardless of recent changes (audit) |
| `docsync affected-docs --files <paths>` | Show docs affected by code changes |

**When to use each:**
- **`check`**: Use in pre-commit hooks and CI pipelines. Only examines docs linked to staged/specified files. Fast and focused.
- **`list-stale`**: Use for periodic audits and reviews. Scans the entire repository for any stale documentation. Comprehensive but slower.

### Information & Coverage

| Command | Description |
|---------|-------------|
| `docsync info <file> [--format json]` | Show all links for a file |
| `docsync coverage [--format json]` | Report documentation coverage |

### Utilities

| Command | Description |
|---------|-------------|
| `docsync clear-cache` | Clear import graph cache |

## Doc Audit Skill (Claude Code)

docsync includes a **Claude Code skill** that analyzes your documentation for trackability and suggests improvements. This bridges the gap between "messy existing docs" and "docs that docsync can actually enforce."

### What the Audit Analyzes

| Signal | Good | Bad |
|--------|------|-----|
| **Structure** | Tables, code blocks, clear headings | Long prose blocks, flat text |
| **Scope** | Section maps to one code file | Section references 7+ files |
| **Coverage** | File paths in `links.toml` | Implicit file references in prose |
| **Protection** | License/version in `donttouch` | Critical content unprotected |

### Usage

In Claude Code, the audit skill is available as `/audit` or by asking Claude to audit your docs:

```
> Audit the documentation in this repo for docsync trackability
```

The skill will:
1. **Score** each doc file and section (1-10)
2. **Suggest** `links.toml` entries from file path mentions in prose
3. **Suggest** `donttouch` rules for licenses, versions, critical sections
4. **Suggest** restructuring (prose → tables, section splits)

### Ideal Onboarding Flow

```bash
docsync init                    # Creates config, .docsync/ directory
# Then in Claude Code:
> Audit my docs and apply the suggestions
docsync bootstrap               # Fill in convention-based links
docsync install-hook            # Start enforcing
```

### Skill Location

The audit skill lives at `.claude/skills/audit.md` and can be customized for your project's specific patterns.

## Configuration

Edit `[tool.docsync]` in `pyproject.toml`:

```toml
[tool.docsync]
# Enforcement mode
mode = "block"  # or "warn" (non-blocking)

# Transitive staleness depth
transitive_depth = 1  # Check imports 1 level deep

# Code patterns that MUST have doc links
require_links = ["src/**/*.py"]

# Files/directories to ignore
exempt = ["tests/**", "scripts/**"]

# What counts as a "doc file"
doc_paths = ["docs/**/*.md", "README.md"]
```

## Bootstrap: Auto-Generation with Warnings

`docsync bootstrap` intelligently proposes links using:

1. **Filename matching**: `src/auth.py` → `docs/auth.md`
2. **Content analysis**: Grep docs for references to code files
3. **Import graph**: Transitive link suggestions

**Important**: Bootstrap can't reliably infer links for **human-facing docs** (tutorials, examples, guides, READMEs). These need manual entries:

```bash
$ docsync bootstrap

Proposed 15 links:

  src/auth.py
    → docs/api.md
    → examples/quickstart.md#Login Flow  ⚠️

⚠️  Warning: 1 doc may be tutorial/guide (marked with ⚠️)
Review these carefully - automated links may not make sense for narrative docs.

To apply these links, run:
  docsync bootstrap --apply
```

## JSON Output for AI Agents

All commands support `--format json` for machine consumption:

```bash
# Get stale docs with precise information
$ docsync list-stale --format json
{
  "stale": [
    {
      "code_file": "src/auth.py",
      "doc_target": "docs/api.md#Authentication",
      "section": "Authentication",
      "reason": "Section unchanged since src/auth.py changed"
    }
  ]
}

# Get coverage report
$ docsync coverage --format json
{
  "coverage": 0.85,
  "total_files": 20,
  "documented_files": 17,
  "undocumented_files": ["src/experimental.py", "src/legacy.py", "src/draft.py"]
}

# Find affected docs for a code change
$ docsync affected-docs --files src/auth.py --format json
{
  "affected_docs": {
    "src/auth.py": ["docs/api.md#Authentication", "docs/auth.md"]
  }
}
```

## Caching

docsync caches import graphs in `.docsync/cache/` for performance. Add to `.gitignore`:

```gitignore
.docsync/cache/
```

Cache is automatically invalidated when Python files change (SHA-based).

**Important**: Commit `.docsync/links.toml` to version control. It's the shared source of truth for code-doc relationships.

## Development

```bash
# Clone and install
git clone https://github.com/nlebovits/docsync.git
cd docsync
uv sync

# Run tests
uv run pytest

# Run linting
uv run ruff check .

# Run formatter
uv run ruff format .
```

### Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git commit -m "feat(cli): add validate-links command"
git commit -m "fix(staleness): handle missing sections gracefully"
git commit -m "docs: update README with section-level examples"
```

### Versioning

```bash
# Bump version and create changelog
uv run cz bump

# Bump to specific version
uv run cz bump --increment MAJOR|MINOR|PATCH
```

## Architecture

### File Structure

```
.docsync/
├── links.toml          # Source of truth for code↔doc links (COMMIT THIS)
└── cache/              # Import graph cache (IGNORE THIS)
    └── imports_*.json

pyproject.toml          # [tool.docsync] configuration
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `cli.py` | Command-line interface |
| `config.py` | Configuration parsing from pyproject.toml |
| `toml_links.py` | TOML link file parsing and graph construction |
| `sections.py` | Markdown section parsing and line range extraction |
| `staleness.py` | Git diff-based section staleness detection |
| `graph.py` | Bidirectional graph construction |
| `imports.py` | Python import graph via AST parsing |
| `hook.py` | Pre-commit hook entry point |
| `donttouch.py` | Protected content guard |
| `coverage.py` | Documentation coverage reporting |
| `cache.py` | Import graph caching |

### Graph Structure

The docsync graph is a bidirectional mapping:

```python
{
  "src/auth.py": {"docs/api.md#Authentication", "docs/auth.md"},
  "docs/api.md#Authentication": {"src/auth.py"},
  "docs/auth.md": {"src/auth.py"},
}
```

Section-specific targets (`docs/api.md#Authentication`) are **distinct nodes** from whole-file targets (`docs/api.md`).

## Migration from v0.1.x (Inline Comments)

If you used the old inline comment system (`# docsync: docs/api.md`), there is no automatic migration tool since the new architecture is fundamentally different. You have two options:

1. **Start fresh**: Run `docsync bootstrap --apply` to auto-generate links
2. **Manual migration**: Extract inline comments into `.docsync/links.toml` following the schema

The new system is more powerful and agent-native, but requires adopting the centralized TOML approach.

## License

Apache-2.0 - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please ensure:
- Tests pass: `uv run pytest`
- Linting passes: `uv run ruff check .`
- Conventional commits: `feat:`, `fix:`, `docs:`, etc.
