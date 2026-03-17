<p align="center">
  <img src=".github/branding/profile.png" alt="docsync logo" width="200">
</p>

`docsync` is a pre-commit hook and CLI tool that deterministically flags when code changes should trigger documentation updates. It outputs agent-friendly JSON with targeted information about what changed and which doc sections need review.

When working fast with tools like Claude, docs drift quickly. Agents excel at changing code but struggle to understand how code changes should trigger doc updates. `docsync` addresses this with deterministic checks:

1. **Pre-commit enforcement**: Flags code changes that should trigger docs updates. Outputs JSON with file paths, sections, and git diffs. Commits block until docs are updated.

2. **Audit skill**: Scores documentation structure for trackability. Identifies which docs can be deterministically verified and which rely on manual review. Makes concrete recommendations.

All output is AI-first; `docsync` assumes Claude (or another agent) will consume and act on it.

**📚 [Full docs](https://nlebovits.github.io/docsync/)** | **[Tutorial](https://nlebovits.github.io/docsync/tutorial/)** | **[CLI Reference](https://nlebovits.github.io/docsync/cli/reference/)**

## Quick Start

```bash
# Install
uv pip install git+https://github.com/nlebovits/docsync.git

# Initialize (creates .docsync/links.toml and pyproject.toml config)
docsync init

# Define relationships: code file → doc section
echo '[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]' >> .docsync/links.toml

# Enable pre-commit enforcement
docsync install-hook

# Now commits block if docs are stale:
git commit -m "refactor auth"
# ❌ Blocked: docs/api.md#Authentication unchanged since src/auth.py changed
```

## License

Apache-2.0

## Contributing

See [Contributing Guide](https://nlebovits.github.io/docsync/contributing/)
