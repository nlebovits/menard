<p align="center">
  <img src=".github/branding/profile.png" alt="docsync logo" width="200">
</p>

# docsync

**Keep your code and documentation in sync with centralized linking and section-aware staleness detection.**

[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://nlebovits.github.io/docsync/)

docsync is a pre-commit hook and CLI tool that ensures documentation stays fresh by tracking relationships between code files and their documentation.

## Quick Install

```bash
# Install with uv (recommended)
uv pip install git+https://github.com/nlebovits/docsync.git

# Or with pip
pip install git+https://github.com/nlebovits/docsync.git
```

## Features

- **Centralized TOML links** - No inline comments, all relationships in `.docsync/links.toml`
- **Section-level precision** - Link to specific doc sections for targeted staleness checking
- **Git diff-based staleness** - Detect if doc sections were updated since code changed
- **Pre-commit enforcement** - Block commits when documentation is outdated
- **Agent-native JSON output** - Deterministic checks for AI agents
- **Auto-bootstrap** - Intelligently generate links from conventions
- **Doc audit skill** - Claude Code skill for trackability analysis

## Documentation

**📚 [Full documentation →](https://nlebovits.github.io/docsync/)**

- [Getting Started](https://nlebovits.github.io/docsync/getting-started/) - Installation and setup
- [Tutorial](https://nlebovits.github.io/docsync/tutorial/) - Real-world onboarding workflow
- [CLI Reference](https://nlebovits.github.io/docsync/cli/reference/) - All commands
- [Configuration](https://nlebovits.github.io/docsync/configuration/) - Customize behavior

## Quick Start

```bash
# Initialize in your repository
docsync init

# Define code-doc links in .docsync/links.toml
# [[link]]
# code = "src/auth.py"
# docs = ["docs/api.md#Authentication"]

# Install pre-commit hook
docsync install-hook

# Check for stale docs
docsync check
```

## How It Works

docsync provides **deterministic staleness detection** via git diff analysis:

1. You define relationships in `.docsync/links.toml`
2. docsync detects when code changes but linked docs don't
3. Commits are blocked until docs are updated

See the [Tutorial](https://nlebovits.github.io/docsync/tutorial/) for a complete walkthrough.

## License

Apache-2.0

## Contributing

Contributions welcome! See [Contributing Guide](https://nlebovits.github.io/docsync/contributing/) for details.
