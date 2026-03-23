<p align="center">
  <img src="img/favicon.png" alt="docsync logo" width="200">
</p>

docsync is a pre-commit hook and CLI tool that deterministically flags when code changes should trigger documentation updates. It outputs agent-friendly JSON with targeted information about what changed and which doc sections need review.

When working fast with tools like Claude, docs drift quickly. Agents excel at changing code but struggle to understand how code changes should trigger doc updates. docsync addresses this with deterministic checks.

## Three Core Use Cases

### 1. Track Doc Sync

Block commits when linked documentation becomes stale:

```bash
git commit -m "refactor auth"
# ❌ Blocked: docs/api.md#Authentication unchanged since src/auth.py changed
```

Define code→doc relationships in `.docsync/links.toml`, then docsync uses git diff to detect when docs need updates. Works at section-level precision—changing one part of a doc doesn't clear staleness for unrelated sections.

[Configuration →](configuration.md)

### 2. Flag Protected Content Changes

Prevent accidental changes to licenses, brand assets, and policies:

```bash
git commit -m "update requirements"
# ⚠️  Warning: Protected literal changed
#   "Python 3.11+" → "Python 3.10+"
#   This is protected in .docsync/donttouch
```

Protected sections are never marked stale, even if linked code changes. Protected literals trigger warnings when modified.

[Configuration →](configuration.md#donttouch)

### 3. Audit for Deterministic Maintainability

Score documentation structure for trackability using the audit skill in Claude Code:

```
> Audit my documentation
```

The audit analyzes structure (tables, code blocks, headings), file references, section scope, and protected content. It provides concrete suggestions for `links.toml` additions, `donttouch` protections, and restructuring.

[Agent Skills →](skills.md)

## Quick Start

```bash
# Install
uv pip install git+https://github.com/nlebovits/docsync.git

# Initialize
docsync init

# Audit docs for trackability (in Claude Code)
> Audit my documentation and apply the suggestions

# Auto-generate convention-based links
docsync bootstrap --apply

# Mark auto-generated docs (e.g., from mkdocs-click) to skip staleness
# Edit .docsync/links.toml and add: auto_generated = true

# Validate and check coverage
docsync validate-links
docsync coverage

# Check for stale docs (JSON output for agents)
docsync list-stale --format json

# Set up pre-commit hook
pre-commit install
```

For detailed setup instructions, see [Getting Started →](getting-started.md)

## Agent-First Design

All output is designed for AI consumption. The `--format json` flag provides structured metadata—everything an agent needs to make scoped updates:

```json
{
  "stale": [{
    "code_file": "src/auth.py",
    "doc_target": {
      "file": "docs/api.md",
      "section": "Authentication",
      "line_range": [45, 89]
    },
    "code_last_modified": "2026-03-17",
    "doc_last_modified": "2026-03-08",
    "commits_since": [{
      "sha": "abc123",
      "date": "2026-03-17",
      "message": "feat: add logout"
    }],
    "severity": null,
    "auto_generated": false,
    "suggested_action": "update",
    "reason": "Section unchanged since src/auth.py changed"
  }]
}
```

The structured `doc_target` includes exact line ranges for precision edits. `suggested_action` tells agents whether to "update", "create", or "review" the doc section.

## License

Apache-2.0

## Contributing

[Contributing Guide →](contributing.md)

