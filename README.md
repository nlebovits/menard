<p align="center">
  <img src=".github/branding/profile.png" alt="menard logo" width="200">
</p>

<p align="center">
  <a href="https://github.com/nlebovits/menard/actions/workflows/ci.yml"><img src="https://github.com/nlebovits/menard/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/menard/"><img src="https://img.shields.io/pypi/v/menard" alt="PyPI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
  <a href="https://github.com/nlebovits/menard/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

**menard** is a pre-commit hook and CLI tool that deterministically flags when code changes should trigger documentation updates. It outputs agent-friendly JSON with targeted information about what changed and which doc sections need review.

When working fast with tools like Claude, docs drift quickly. Agents excel at changing code but struggle to understand how code changes should trigger doc updates. menard addresses this with deterministic checks.

## Three Core Use Cases

**1. Track Doc Sync** - Block commits when linked documentation becomes stale. Define code→doc relationships, menard uses git diff to detect when docs need updates.

**2. Flag Protected Content Changes** - Prevent accidental changes to licenses, brand assets, and policies. Protected sections are never marked stale, protected literals trigger warnings.

**3. Audit for Deterministic Maintainability** - Score documentation structure for trackability using the audit skill in Claude Code. Get concrete suggestions for improvements.

**📚 [Full docs](https://nlebovits.github.io/menard/)** | **[Getting Started](https://nlebovits.github.io/menard/getting-started/)** | **[CLI Reference](https://nlebovits.github.io/menard/cli/reference/)**

## Quick Start

```bash
# Install
pip install menard  # or: uv add menard

# Initialize
menard init

# Audit docs for trackability (in Claude Code)
> Audit my documentation and apply the suggestions

# Auto-generate convention-based links
menard bootstrap --apply

# Validate and check coverage
menard validate-links
menard coverage

# Set up pre-commit hook
# See: https://nlebovits.github.io/menard/getting-started/#pre-commit-setup
pre-commit install
```

## License

Apache-2.0

## Contributing

[Contributing Guide](https://nlebovits.github.io/menard/contributing/)
