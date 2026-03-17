# Tutorial: Real-World Onboarding Workflow

This tutorial shows the complete docsync onboarding workflow based on an actual session onboarding `portolan-cli` to docsync.

You'll see every command, the issues encountered, and how they were resolved.

## Step 1: Initialize docsync

```bash
$ docsync init
✓ Added [tool.docsync] to pyproject.toml
✓ Created .docsync/
✓ Created .docsync/links.toml
```

### Issue Encountered

The default config used `src/**/*.py` but the project uses `portolan_cli/`. Had to manually fix:

```toml
# pyproject.toml - before (wrong)
[tool.docsync]
require_links = ["src/**/*.py"]

# pyproject.toml - after (correct)
[tool.docsync]
require_links = ["portolan_cli/**/*.py"]
```

!!! note
    This issue is tracked in [#9](https://github.com/nlebovits/docsync/issues/9). Future versions will auto-detect the source directory from `pyproject.toml`.

## Step 2: Check Initial Coverage

```bash
$ docsync coverage
Documentation Coverage: 0.0%
  Total code files: 60
  Documented: 0
```

No links defined yet, so coverage is 0%.

## Step 3: Create Initial links.toml

Identified key code→doc relationships:

```toml
# .docsync/links.toml

# CLI reference (auto-generated via mkdocs-click)
[[link]]
code = "portolan_cli/cli.py"
docs = ["docs/reference/cli.md"]

# Configuration docs
[[link]]
code = "portolan_cli/config.py"
docs = ["docs/reference/configuration.md"]

[[link]]
code = "portolan_cli/conversion_config.py"
docs = ["docs/reference/configuration.md#Conversion Configuration"]

# Output module documented in contributing guide
[[link]]
code = "portolan_cli/output.py"
docs = ["docs/contributing.md#Code Standards"]

# Core modules linked to design principles
[[link]]
code = "portolan_cli/scan.py"
docs = ["CLAUDE.md#Design Principles"]
```

## Step 4: Validate and Check Coverage

```bash
$ docsync validate-links
✓ All 10 links are valid

$ docsync coverage
Documentation Coverage: 16.7%
  Total code files: 60
  Documented: 10
```

Coverage improved from 0% to 16.7% with 10 links.

## Step 5: Run the Audit Skill

Following `.claude/skills/audit.md`, analyzed each doc file for:

- **Structure** - Headings, tables, code blocks
- **File references** - Backtick-quoted paths
- **Section scope** - Does each section map to code?
- **Protected content** - Licenses, terminology

### Audit Findings

The audit skill identified:

1. **Suggested links from file path mentions**:
   - `portolan_cli/output.py` mentioned in `CLAUDE.md#Standardized Terminal Output`
   - `portolan_cli/json_output.py` referenced in `docs/reference/cli.md`

2. **Protected sections** to add to `.docsync/donttouch`:
   - License sections (must not change without decision)
   - Brand colors in `BRANDING.md`
   - Python version requirement

3. **Restructuring suggestions**:
   - Convert command flag table to structured format
   - Split large architecture section into subsections

## Step 6: Create donttouch Protections

```bash
$ cat .docsync/donttouch
# License sections must not change without explicit decision
README.md#License
docs/contributing.md#License

# Code of Conduct is policy
docs/contributing.md#Code of Conduct

# Terminology is enforced project-wide
CLAUDE.md#Terminology (ENFORCED)

# Brand colors must be consistent
docs/BRANDING.md#Color Palette

# Version requirements
"Python 3.10+"
```

These sections and literals are now protected from accidental changes.

## Step 7: Add Audit-Suggested Links

```toml
# Additional links from audit

[[link]]
code = "portolan_cli/output.py"
docs = ["CLAUDE.md#Standardized Terminal Output"]

[[link]]
code = "portolan_cli/json_output.py"
docs = ["CLAUDE.md#Design Principles"]

[[link]]
code = "portolan_cli/status.py"
docs = ["docs/reference/cli.md"]

# ... 6 more links
```

## Step 8: Final Coverage

```bash
$ docsync coverage
Documentation Coverage: 26.7%
  Total code files: 60
  Documented: 16

$ docsync list-protected
Protected sections:
  README.md#License
  docs/contributing.md#License
  docs/contributing.md#Code of Conduct
  CLAUDE.md#Terminology (ENFORCED)
  docs/BRANDING.md#Color Palette

Global literals:
  "Python 3.10+"
```

Coverage improved from 16.7% to 26.7% with audit-suggested links.

## Step 9: Add Pre-Commit Hook

```yaml
# .pre-commit-config.yaml
- id: docsync-check
  name: check docs freshness
  entry: bash -c '$HOME/.local/bin/docsync check'
  language: system
  files: ^(portolan_cli/.*\.py|docs/.*\.md|CLAUDE\.md)$
  pass_filenames: false
```

!!! note
    Had to use `bash -c '$HOME/...'` workaround due to pyenv shim issues - see [#10](https://github.com/nlebovits/docsync/issues/10).

## Step 10: Test the Workflow

Made a change to `portolan_cli/cli.py`:

```bash
$ git add portolan_cli/cli.py
$ git commit -m "feat: add --verbose flag"

docsync: ❌ commit blocked

Stale documentation detected:
  docs/reference/cli.md
    Code: portolan_cli/cli.py
    Reason: File unchanged since portolan_cli/cli.py changed
```

Updated `docs/reference/cli.md` (mkdocs-click auto-generates from docstrings), then:

```bash
$ git add docs/reference/cli.md
$ git commit -m "feat: add --verbose flag"
✓ docsync check passed
```

## Summary

Starting from 0% coverage, the workflow achieved:

- **26.7% coverage** (16 of 60 files documented)
- **Protected content** via `.docsync/donttouch`
- **Pre-commit enforcement** via hook
- **Audit-driven improvements** from Claude Code skill

This demonstrates docsync's value: **deterministic staleness detection** enables **reliable, scoped documentation updates**.

## Next Steps

- [**Concepts**](concepts/links.md) - Understand how links work
- [**Configuration**](configuration.md) - Customize docsync behavior
- [**Skills**](skills/audit.md) - Learn about the audit skill
