<p align="center">
  <img src="../.github/branding/profile.png" alt="docsync logo" width="200">
</p>

# docsync

**Keep your code and documentation in sync with centralized linking and section-aware staleness detection.**

docsync is a pre-commit hook and CLI tool that ensures documentation stays fresh by tracking relationships between code files and their documentation.

## Key Features

- **Centralized TOML links** - Define code↔doc relationships in `.docsync/links.toml` (no inline comments!)
- **Section-level precision** - Link to specific doc sections (`docs/api.md#Authentication`) for targeted staleness checking
- **Git diff-based staleness** - Uses `git diff` to detect if doc sections were updated since code changed
- **Import-aware staleness** - Detects when docs are stale due to transitive code changes
- **Pre-commit enforcement** - Blocks commits when documentation is missing or outdated
- **Agent-native UX** - JSON output, deterministic checks, and scoped update tasks for AI agents
- **Auto-bootstrap** - Intelligently generates links from filename conventions and content analysis
- **Doc audit skill** - Claude Code skill that analyzes docs for trackability

## Quick Install

```bash
# Install with uv (recommended)
uv pip install git+https://github.com/nlebovits/docsync.git
```

## How It Works

docsync provides **deterministic staleness detection** that enables **scoped, reliable updates**:

1. **You define relationships** in `.docsync/links.toml`:
   ```toml
   [[link]]
   code = "src/auth.py"
   docs = ["docs/api.md#Authentication"]
   ```

2. **docsync detects staleness** via git diff analysis:
   ```bash
   $ git commit -m "refactor: extract auth helpers"
   
   docsync: ❌ commit blocked
   
   Stale documentation detected:
     docs/api.md#Authentication
       Code: src/auth.py
       Reason: Section unchanged since src/auth.py changed
   ```

3. **You update the precise section** - no guessing, no reading 500-line files:
   - Update lines 45-89 in `docs/api.md` (the Authentication section)
   - Don't touch other sections

## Next Steps

- [**Getting Started**](getting-started.md) - Installation and setup
- [**Tutorial**](tutorial.md) - Real-world onboarding workflow
- [**Concepts**](concepts/links.md) - How docsync works
- [**CLI Reference**](cli/reference.md) - All commands
