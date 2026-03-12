# docsync

**Keep your code and documentation in sync with bidirectional linking and import-aware staleness detection.**

docsync is a pre-commit hook and CLI tool that ensures documentation stays fresh by tracking relationships between code files and their documentation. It detects stale docs through git timestamps and import graphs, blocks commits when linked documentation is missing, and provides agent-native commands for programmatic workflows.

## Features

- **Bidirectional linking**: Code files reference docs, docs reference code
- **Import-aware staleness**: Detects when docs are stale due to transitive code changes
- **Pre-commit enforcement**: Blocks commits when documentation is missing or outdated
- **SHA-based caching**: Fast import graph analysis on large repositories
- **Agent-native UX**: JSON output, batch operations, and programmatic commands
- **Deferral system**: Temporarily bypass checks with tracked reasons
- **Coverage tracking**: Identify undocumented code files

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

This creates `.docsync.toml` with default configuration:

```toml
[docsync]
code_globs = ["src/**/*.py"]
doc_globs = ["docs/**/*.md"]
require_links = ["src/**/*.py"]
```

### 2. Link code and documentation

In your code files, add docsync comments:

```python
# docsync: docs/api.md
def authenticate(username, password):
    """Authenticate user credentials."""
    pass
```

In your documentation, reference code:

```markdown
# Authentication API

The authentication flow is implemented in `src/auth.py`.

<!-- docsync: src/auth.py -->
```

### 3. Install the pre-commit hook

```bash
docsync install-hook
```

Now commits will be blocked if:
- Code files lack required documentation links
- Documentation is stale (older than linked code or its imports)

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `docsync init` | Initialize configuration file |
| `docsync install-hook` | Install pre-commit hook |
| `docsync check` | Verify all links present and docs fresh |
| `docsync coverage` | Report documentation coverage |
| `docsync bootstrap` | Suggest missing links for undocumented code |

### Agent-Native Commands

Designed for programmatic use with `--format json` output:

| Command | Description |
|---------|-------------|
| `docsync list-stale [pattern]` | List stale documentation files |
| `docsync affected-docs <file>` | Find docs affected by code changes |
| `docsync info <file>` | Show all links for a file |
| `docsync explain-changes <file>` | Explain why docs are stale |
| `docsync defer <file> -m "reason"` | Temporarily bypass checks |
| `docsync list-deferred` | Show all deferred files |

### Utility Commands

| Command | Description |
|---------|-------------|
| `docsync clear-cache` | Clear import graph cache |

## Configuration

Edit `.docsync.toml` to customize behavior:

```toml
[docsync]
# Glob patterns for code files
code_globs = ["src/**/*.py", "lib/**/*.rb"]

# Glob patterns for documentation files
doc_globs = ["docs/**/*.md", "*.md"]

# Code patterns that MUST have doc links (subset of code_globs)
require_links = ["src/**/*.py"]

# Files/directories to ignore
ignore_globs = ["tests/**", "scripts/**"]
```

## Caching

docsync caches import graphs in `.docsync/` for performance. Add to `.gitignore`:

```gitignore
.docsync/
```

Cache is automatically invalidated when Python files change (using git SHA hashing).

## JSON Output for Agents

Most commands support `--format json` for machine-readable output:

```bash
# Get stale docs as JSON
docsync list-stale --format json
# [{"file": "docs/api.md", "reason": "code changed", "age_days": 3}]

# Get coverage report as JSON
docsync coverage --format json
# {"coverage": 0.75, "total_code_files": 20, "documented_files": 15, ...}

# Find affected docs for a code change
docsync affected-docs src/auth.py --format json
# {"code_file": "src/auth.py", "affected_docs": ["docs/api.md", "docs/auth.md"]}
```

## Deferral Workflow

Temporarily bypass checks for files that can't be documented immediately:

```bash
# Defer a file with reason
docsync defer src/experimental.py -m "WIP feature, docs pending design review"

# List all deferrals
docsync list-deferred

# Clear deferral when ready
docsync defer src/experimental.py --clear
```

Deferrals are tracked in `.docsync/deferred.json` (should be committed).

## Development

```bash
# Clone and install
git clone https://github.com/nlebovits/docsync.git
cd docsync
uv sync

# Run tests with coverage
uv run pytest --cov=src/docsync --cov-report=term

# Run linting
uv run ruff check .

# Run formatter
uv run ruff format .

# Install pre-commit hooks (recommended)
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
```

### Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/) enforced by [Commitizen](https://commitizen-tools.github.io/commitizen/).

Commit message format:
```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

Examples:
```bash
git commit -m "feat(cli): add list-stale command with JSON output"
git commit -m "fix(cache): handle git errors gracefully"
git commit -m "docs: update installation instructions"
```

### Versioning and Releases

Use commitizen to bump versions:
```bash
# Bump version and create changelog
uv run cz bump

# Bump to specific version
uv run cz bump --increment MAJOR|MINOR|PATCH

# Dry run
uv run cz bump --dry-run
```

This will:
- Update version in `pyproject.toml` and `.cz.toml`
- Generate/update `CHANGELOG.md`
- Create a git tag
- Commit the changes

### Testing

The project has comprehensive test coverage (70%+) including:
- Unit tests for all core modules
- Integration tests for end-to-end workflows  
- CLI command tests via subprocess

Run specific test suites:
```bash
# Unit tests only
uv run pytest tests/test_*.py -k "not integration"

# Integration tests only
uv run pytest tests/test_integration*.py

# With verbose output
uv run pytest -v
```

### CI/CD

- **GitHub Actions**: Runs tests, linting, formatting on Python 3.11 and 3.12
- **Dependabot**: Weekly dependency updates (grouped in single PR)
- **Pre-commit hooks**: Enforces conventional commits, formatting, linting, and 70% coverage threshold
- **Semantic versioning**: Automated via commitizen with changelog generation

## How It Works

1. **Graph Building**: Parses docsync comments to build a bidirectional graph of code ↔ doc relationships
2. **Import Analysis**: Builds Python import graph using AST parsing (cached with SHA-based invalidation)
3. **Staleness Detection**: Compares git timestamps across the graph to detect stale documentation
4. **Transitive Detection**: If `a.py` imports `b.py` and `b.py` changes, docs for `a.py` become stale
5. **Pre-commit Enforcement**: Blocks commits when staged code lacks documentation or docs are stale

## License

Apache 2.0 - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please ensure:
- Tests pass: `uv run pytest`
- Linting passes: `uv run ruff check .`
- Conventional commits: `feat:`, `fix:`, `docs:`, etc.
