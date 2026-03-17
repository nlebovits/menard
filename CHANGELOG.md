## v0.2.0 (2026-03-17)

### BREAKING CHANGES

- **Centralized TOML Links**: Replaced inline comments (`# docsync: docs/api.md`) with centralized `.docsync/links.toml` file
  - All code↔doc relationships now defined in one place
  - No more scattered inline comments in source files
  - Migration: Use `docsync bootstrap --apply` to auto-generate links from conventions

### Features

- **Section-Level Staleness Detection**: Link to specific doc sections for precise staleness checking
  - Syntax: `docs/api.md#Authentication` targets only that section
  - Uses `git diff` to detect if section content changed since code modification
  - Dramatically reduces AI update scope (44 lines instead of 500-line file)
  
- **Git Diff-Based Staleness**: Replaces timestamp comparison with actual diff analysis
  - Detects exact line ranges that changed in doc files
  - Section-aware: only marks sections stale if they weren't updated
  - More accurate than git blame for transitive staleness

- **Auto-Bootstrap with Content Analysis**: Intelligent link generation from multiple sources
  - Filename matching: `src/auth.py` → `docs/auth.md`
  - Content analysis: Grep docs for code file references
  - Import graph: Suggest transitive links
  - Warnings for human-facing docs (tutorials, guides) that need manual review

- **Link Validation**: New `docsync validate-links` command
  - Checks that all referenced files exist
  - Validates section headings exist in target docs
  - Fuzzy matching suggestions for renamed sections
  - Runs automatically during pre-commit

- **TOML Schema**: Structured link definitions
  ```toml
  [[link]]
  code = "src/auth.py"
  docs = ["docs/api.md#Authentication", "docs/auth.md"]
  note = "Optional human note"
  ```
  - Supports glob patterns: `src/models/*.py`
  - Multiple targets per code file
  - Bidirectional by default (no symmetry enforcement needed)

### Architecture Changes

- **New Modules**:
  - `toml_links.py`: TOML link file parsing, validation, graph construction
  - `sections.py`: Markdown section parsing and line range extraction
  - `staleness.py`: Git diff-based section staleness detection

- **Rewritten Modules**:
  - `graph.py`: Now builds from TOML instead of inline comments
  - `cli.py`: Complete rewrite with new commands (`bootstrap`, `validate-links`, `install-hook`)
  - `hook.py`: Uses TOML links and section-aware staleness

- **Removed**:
  - All inline comment parsing logic
  - `add-link` command (edit `.docsync/links.toml` directly)
  - Symmetry enforcement (structurally enforced by TOML)

### Developer Experience

- **Deterministic + Probabilistic Design**: docsync provides deterministic staleness detection for AI agents to make scoped, probabilistic updates
  - Layer 1: Exact staleness detection (file + section + line ranges)
  - Layer 2: AI uses coordinates for targeted doc updates
  - Result: 44-line update task instead of "update the docs somewhere"

- **JSON Output for Agents**: All commands support `--format json` with precise coordinates
  ```json
  {
    "doc_target": "docs/api.md#Authentication",
    "section": "Authentication",
    "code_file": "src/auth.py",
    "reason": "Section unchanged since src/auth.py changed"
  }
  ```

### Testing

- **New Test Modules**:
  - `test_toml_links.py`: TOML parsing, validation, graph building
  - `test_sections.py`: Markdown section parsing
  - `test_staleness.py`: Git diff staleness detection
  - `test_integration_toml.py`: End-to-end workflow tests

- **Removed Legacy Tests**: Deleted inline-comment-based tests
  - `test_cli.py`, `test_hook.py`, `test_integration.py` removed
  - Replaced with TOML-focused equivalents

- **Coverage**: 57 passing tests covering all new functionality

### Documentation

- **Updated README**: Complete rewrite for TOML-based architecture
  - Section-level linking examples
  - Git diff staleness explanation
  - Deterministic/probabilistic design philosophy
  - Bootstrap workflow and warnings
  - Migration notes from v0.1.x

### Notes

- **No Migration Tool**: Due to architectural differences, no automatic migration from inline comments
  - Recommended: Run `docsync bootstrap --apply` in existing repos
  - Manual: Extract inline comments to `.docsync/links.toml`

- **Version Control**: `.docsync/links.toml` MUST be committed (source of truth)
  - `.docsync/cache/` should remain in `.gitignore`

---

## v0.1.0 (2026-03-12)

### Features

- **Initial Release**: docsync with agent-native UX and caching
  - Bidirectional linking between code and documentation
  - Import-aware staleness detection
  - Pre-commit enforcement
  - SHA-based caching for import graphs
  - Agent-native commands (JSON output, batch operations)
  - Deferral system for temporary bypasses
  - Coverage tracking

- **Testing & CI/CD**
  - Comprehensive test suite (122 tests, 74% coverage)
  - GitHub Actions CI (Python 3.11 & 3.12)
  - Dependabot for dependency updates (grouped PRs)
  - Pre-commit hooks (ruff, pytest, commitizen)

- **Semantic Versioning**
  - Commitizen for conventional commits
  - Automated changelog generation
  - Version management across project files

### Bug Fixes

- Ruff formatter and linting compliance
