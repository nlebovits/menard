# Contributing

## Development Setup

```bash
git clone https://github.com/nlebovits/menard.git
cd menard
uv sync --all-extras       # Install dependencies + dev extras
uv run pre-commit install  # Install pre-commit hooks
uv run pytest              # Run tests
uv run ruff check .        # Lint
uv run ruff format .       # Format
```

## Standards

- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`)
- **Versioning:** `uv run cz bump` ([commitizen](https://commitizen-tools.github.io/commitizen/))
- **Code style:** ruff (line length: 100)

## Code of Conduct

Be respectful and inclusive. Harassment or abusive behavior will not be tolerated.

## License

Apache-2.0
