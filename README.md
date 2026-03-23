<p align="center">
  <img src=".github/branding/profile.png" alt="menard logo" width="200">
</p>

<p align="center">
  <a href="https://github.com/nlebovits/menard/actions/workflows/ci.yml"><img src="https://github.com/nlebovits/menard/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/nlebovits/menard"><img src="https://codecov.io/gh/nlebovits/menard/branch/main/graph/badge.svg" alt="codecov"></a>
  <a href="https://pypi.org/project/menard/"><img src="https://img.shields.io/pypi/v/menard" alt="PyPI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
  <a href="https://github.com/nlebovits/menard/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

**menard** is a pre-commit hook and CLI tool that deterministically flags when code changes should trigger documentation updates. It outputs agent-friendly JSON with targeted information about what changed and which doc sections need review.

When working fast with tools like Claude, docs drift quickly. Agents excel at changing code but struggle to understand how code changes should trigger doc updates. menard addresses this with deterministic checks.

**📚 [Full docs](https://nlebovits.github.io/menard/)** | **[Getting Started](https://nlebovits.github.io/menard/getting-started/)** | **[CLI Reference](https://nlebovits.github.io/menard/cli/reference/)**

## Core Use Cases

### 1. Track Doc Drift

Define code → doc relationships in `.menard/links.toml`. menard uses git diffs to detect stale docs. Section-level tracking means changes to one part of a file won't trigger full doc rewrites.

```bash
git commit -m "refactor auth"
# ❌ Blocked: docs/api.md#Authentication unchanged since src/auth.py changed
```

### 2. Flag Protected Content Changes

Use `.menard/donttouch` to define sections that shouldn't be edited. Avoid accidental changes by over-eager agents with automatic warnings.

```bash
git commit -m "update requirements"
# ⚠️  Warning: Protected literal changed
#   "Python 3.10+" → "Python 3.9+"
#   This is protected in .menard/donttouch
```

### 3. Audit for Deterministic Maintainability

Use the [audit skill](https://nlebovits.github.io/menard/skills/) to analyze how easily your docs can be maintained with deterministic checks. Get concrete suggestions for `links.toml` additions, `donttouch` protections, and restructuring.

```
> Audit my documentation
```

### 4. Find Duplicate Content

Use `menard brevity` to find semantically similar sections across your docs using local embeddings. No API keys needed—runs entirely on your machine.

```bash
menard brevity --threshold 0.95
# README.md#License ↔ docs/index.md#License (1.00)
# README.md#Quick Start ↔ docs/getting-started.md#Quick Start (0.96)
```

## Quick Start

```bash
# Install
uv add menard

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

# Optional: Find duplicate content with embeddings
uv add menard[brevity]
menard brevity --threshold 0.95
```

## License

Apache-2.0

## Contributing

[Contributing Guide](https://nlebovits.github.io/menard/contributing/)
