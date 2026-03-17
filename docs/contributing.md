# Contributing

Thank you for your interest in contributing to docsync!

## Development Setup

### Prerequisites

- **Python 3.11+** required
- **uv** package manager (recommended)
- **git** for version control

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/nlebovits/docsync.git
cd docsync

# Install dependencies with uv
uv sync

# Verify installation
uv run docsync --help
```

### Run Tests

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=docsync --cov-report=term-missing
```

### Linting and Formatting

```bash
# Check code style
uv run ruff check .

# Format code
uv run ruff format .
```

Fix linting issues automatically:

```bash
uv run ruff check --fix .
```

## Project Standards

### Code Style

- **Formatter:** ruff (line length: 100)
- **Linter:** ruff (select: E, W, F, I, UP, B, SIM, N)
- **Type hints:** Encouraged but not required

### Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git commit -m "feat(cli): add validate-links command"
git commit -m "fix(staleness): handle missing sections gracefully"
git commit -m "docs: update README with section-level examples"
```

**Types:**

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions or fixes
- `refactor:` - Code restructuring
- `chore:` - Maintenance tasks

**Scopes** (optional):

- `cli` - CLI commands
- `graph` - Graph construction
- `staleness` - Staleness detection
- `sections` - Section parsing

### Versioning

docsync uses [commitizen](https://commitizen-tools.github.io/commitizen/) for semantic versioning.

```bash
# Bump version and create changelog
uv run cz bump

# Bump to specific version
uv run cz bump --increment MAJOR|MINOR|PATCH
```

Version bumps are automated based on conventional commit messages:

- `feat:` → MINOR version bump
- `fix:` → PATCH version bump
- `BREAKING CHANGE:` → MAJOR version bump

## Testing

### Running Specific Tests

```bash
# Run a single test file
uv run pytest tests/test_staleness.py

# Run tests matching a pattern
uv run pytest -k "test_section"
```

### Writing Tests

Place tests in `tests/` directory, mirroring `src/docsync/` structure:

```
tests/
├── test_cli.py          # Tests for src/docsync/cli.py
├── test_staleness.py    # Tests for src/docsync/staleness.py
└── test_sections.py     # Tests for src/docsync/sections.py
```

Use `pytest` fixtures for common setup:

```python
import pytest
from pathlib import Path

@pytest.fixture
def sample_repo(tmp_path):
    """Create a sample git repository for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # ... setup git repo ...
    return repo

def test_staleness_detection(sample_repo):
    """Test staleness detection in a controlled repo."""
    # ... test implementation ...
```

## Adding New Features

### Checklist

When adding a new feature:

- [ ] Write tests first (TDD encouraged)
- [ ] Implement the feature
- [ ] Update documentation (`README.md`, `docs/`)
- [ ] Add CLI command if applicable
- [ ] Update `CHANGELOG.md` (automated via `cz bump`)
- [ ] Ensure tests pass: `uv run pytest`
- [ ] Ensure linting passes: `uv run ruff check .`
- [ ] Use conventional commit message

### Example: Adding a New Command

1. **Add argparse subcommand** in `src/docsync/cli.py`:

   ```python
   # In main()
   new_parser = subparsers.add_parser(
       "new-command",
       help="Description of new command"
   )
   new_parser.add_argument("--option", help="Optional argument")
   ```

2. **Implement handler**:

   ```python
   def handle_new_command(args, config):
       """Handle the new command."""
       # ... implementation ...
       return 0  # Success
   ```

3. **Wire up in main()**:

   ```python
   elif args.command == "new-command":
       return handle_new_command(args, config)
   ```

4. **Write tests**:

   ```python
   def test_new_command(sample_repo):
       result = run_cli(["new-command", "--option", "value"])
       assert result.exit_code == 0
   ```

5. **Update docs**:

   Add entry to `docs/cli/reference.md`.

## Pull Request Process

1. **Fork the repository**

2. **Create a feature branch**:

   ```bash
   git checkout -b feat/your-feature-name
   ```

3. **Make changes** following project standards

4. **Run tests and linting**:

   ```bash
   uv run pytest
   uv run ruff check .
   uv run ruff format .
   ```

5. **Commit with conventional message**:

   ```bash
   git commit -m "feat(cli): add new-command for X"
   ```

6. **Push to your fork**:

   ```bash
   git push origin feat/your-feature-name
   ```

7. **Open a Pull Request** against `main` branch

8. **Address review feedback**

## Code of Conduct

Please be respectful and inclusive in all interactions.

Harassment, discrimination, or abusive behavior will not be tolerated.

## License

By contributing to docsync, you agree that your contributions will be licensed under the Apache-2.0 License.

## Questions?

- **Issues:** [GitHub Issues](https://github.com/nlebovits/docsync/issues)
- **Discussions:** [GitHub Discussions](https://github.com/nlebovits/docsync/discussions)

## Next Steps

- [**Architecture**](architecture.md) - Understand the codebase
- [**CLI Reference**](cli/reference.md) - Command documentation
