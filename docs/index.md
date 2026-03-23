<p align="center">
  <img src="assets/menard-logo/profile.png" alt="menard logo" width="200">
</p>

`menard` is a pre-commit hook and CLI tool that deterministically flags when code changes should trigger documentation updates. It outputs agent-friendly JSON with targeted information about what changed and which doc sections need review.

When working fast with tools like Claude, docs drift quickly. Agents excel at changing code but struggle to understand how code changes should trigger doc updates. `menard` addresses this with deterministic checks.

## Core Use Cases

### 1. Track Doc Drift

Define code → doc relationships in `.menard/links.toml`. menard uses git diffs to detect stale docs. Section-level tracking means changes to one part of a file won't trigger full doc rewrites.

```bash
git commit -m "refactor auth"
# ❌ Blocked: docs/api.md#Authentication unchanged since src/auth.py changed
```

### 2. Flag Protected Content Changes

Use `.menard/donttouch` to define which sections of your codebase should not be edited. Avoid accidental changes by over-eager agents by automatically triggering warnings when these sections are committed.

```bash
git commit -m "update requirements"
# ⚠️  Warning: Protected literal changed
#   "Python 3.10+" → "Python 3.9+"
#   This is protected in .menard/donttouch
```

### 3. Audit for Deterministic Maintainability

Use the [audit skill](skills.md) to analyze how easily your codebase and docs can be maintained with deterministic checks. The audit analyzes structure (tables, code blocks, headings), file references, section scope, and protected content. It provides concrete suggestions for `links.toml` additions, `donttouch` protections, and restructuring.

```
> Audit my documentation
```

### 4. Find Duplicate Content

Use [`menard brevity`](cli/reference.md#brevity) to find semantically similar sections across your docs using local embeddings. No API keys needed—runs entirely on your machine.

```bash
menard brevity --threshold 0.95
# README.md#License ↔ docs/index.md#License (1.00)
# README.md#Quick Start ↔ docs/getting-started.md#Quick Start (0.96)
```

## Agent-First Design

All output is designed for AI consumption. The `--format json` flag provides structured metadata—everything an agent needs to make scoped updates. The structured `doc_target` includes exact line ranges for precision edits. `suggested_action` tells agents whether to "update" (section exists) or "create" (doc/section missing).

## License

Apache-2.0

