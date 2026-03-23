# Claude Code Instructions for menard

## Package Management

**ALWAYS use `uv` for package management. NEVER use `pip`.**

```bash
uv sync              # Install dependencies
uv add package-name  # Add dependency
uv run pytest        # Run tests
uv run ruff check .  # Lint
uv run ruff format . # Format
```

## Project Standards

- Python 3.10+ required
- Conventional Commits: `feat:`, `fix:`, `docs:`
- Version with commitizen: `uv run cz bump`

## Architecture

### File Structure

```
.menard/
├── links.toml          # Code↔doc relationships (COMMIT)
└── cache/              # Import graph cache (IGNORE)

pyproject.toml          # [tool.menard] config
```

Add to `.gitignore`: `.menard/cache/`

### Core Modules

| Module | Purpose |
|--------|---------|
| `cli.py` | CLI and skill discovery |
| `config.py` | Parse `pyproject.toml` |
| `toml_links.py` | Parse links, build graph |
| `sections.py` | Extract markdown sections + line ranges |
| `staleness.py` | Git diff-based staleness detection |
| `graph.py` | Bidirectional graph construction |
| `imports.py` | Python import graph (AST) |
| `hook.py` | Pre-commit hook entry |
| `donttouch.py` | Protected content guard |
| `coverage.py` | Coverage reporting |
| `cache.py` | Import graph caching (SHA-based) |

### Design Principles

- **Agent-native**: JSON output, deterministic checks, scoped tasks
- **Section-level precision**: Link to `docs/api.md#Authentication`, not whole files
- **Centralized linking**: All relationships in `.menard/links.toml`
- **Git-based staleness**: Use `git diff` to detect stale docs
- **Bidirectional graph**: Fast lookups (code→docs, docs→code)

### Staleness Detection Algorithm

```python
def is_doc_stale(code_file, doc_target):
    last_commit = git_last_commit(code_file)
    diff = git_diff(last_commit, 'HEAD', doc_target.file)
    changed_lines = parse_diff_lines(diff)
    
    if doc_target.section:
        section_range = get_section_range(doc_target.file, doc_target.section)
        return not any(line in section_range for line in changed_lines)
    else:
        return not changed_lines
```

**Why git diff?** Version-controlled, precise (line-level), fast, deterministic.

### Import Graph (Transitive Staleness)

```python
# src/auth.py imports src/crypto.py
# src/crypto.py changed
# Therefore: docs for src/auth.py may be stale
```

Built via AST parsing. Cached in `.menard/cache/imports_<sha>.json` (SHA-based invalidation).
