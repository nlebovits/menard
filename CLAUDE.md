# Claude Code Instructions for docsync

## Package Management

**ALWAYS use `uv` for package management. NEVER use `pip`.**

```bash
# Install dependencies
uv sync

# Add a dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Run commands in the virtual environment
uv run pytest
uv run ruff check .

# Install the package in editable mode
uv pip install -e .
```

## Project Standards

- Python 3.11+ required
- Use Conventional Commits (`feat:`, `fix:`, `docs:`, etc.)
- Format with ruff: `uv run ruff format .`
- Lint with ruff: `uv run ruff check .`
- Test with pytest: `uv run pytest`
- Version with commitizen: `uv run cz bump`

## Architecture Principles

- **Agent-native design**: JSON output, deterministic checks, scoped tasks
- **Section-level precision**: Link to specific doc sections, not whole files
- **Centralized linking**: All code↔doc relationships in `.docsync/links.toml`
- **Git-based staleness**: Use `git diff` to detect stale documentation
- **Single source of truth**: No duplication between README and docs site
