# Getting Started

## Installation

```bash
pip install menard  # or: uv add menard
```

## Quick Start

```bash
# Initialize
menard init

# Audit docs for trackability (in Claude Code)
> Audit my documentation and apply the suggestions

# Auto-generate convention-based links
menard bootstrap --apply

# Validate and check coverage
menard validate-links
menard coverage
```

## Pre-Commit Setup

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: menard-check
        name: menard-check
        entry: uv run menard check
        language: system
        pass_filenames: false
        always_run: true
```

Then install:

```bash
pre-commit install
```

Now commits will block if docs are stale:

```bash
git commit -m "refactor auth"
# ❌ Blocked: docs/api.md#Authentication unchanged since src/auth.py changed
```

## Real-World Example

This walkthrough shows the complete menard onboarding workflow from an actual session onboarding `portolan-cli`.

### Step 1: Initialize

```bash
$ menard init
✓ Created .menard/links.toml
✓ Added [tool.menard] to pyproject.toml
```

Fix the source directory if needed:

```toml
# pyproject.toml
[tool.menard]
require_links = ["portolan_cli/**/*.py"]  # Not src/
```

### Step 2: Check Coverage

```bash
$ menard coverage
Documentation Coverage: 0.0%
  Total code files: 60
  Documented: 0
```

### Step 3: Create Initial Links

Identify key code→doc relationships:

```toml
# .menard/links.toml

[[link]]
code = "portolan_cli/cli.py"
docs = ["docs/reference/cli.md"]

[[link]]
code = "portolan_cli/config.py"
docs = ["docs/reference/configuration.md"]

[[link]]
code = "portolan_cli/conversion_config.py"
docs = ["docs/reference/configuration.md#Conversion Configuration"]
```

### Step 4: Run Audit Skill

In Claude Code:

```
> Audit my documentation and apply the suggestions
```

The audit identifies:

- Suggested links from file path mentions
- Protected sections for `.menard/donttouch`
- Restructuring recommendations

### Step 5: Add Protections

```bash
$ cat .menard/donttouch
# License sections
README.md#License
docs/contributing.md#License

# Brand colors
docs/BRANDING.md#Color Palette

# Version requirements
"Python 3.10+"
```

### Step 6: Bootstrap Additional Links

```bash
$ menard bootstrap --apply
Found 8 suggested links
Applied all suggestions to .menard/links.toml
```

### Step 7: Final Coverage

```bash
$ menard coverage
Documentation Coverage: 26.7%
  Total code files: 60
  Documented: 16
```

### Step 8: Test the Workflow

Make a change to code:

```bash
$ git add portolan_cli/cli.py
$ git commit -m "feat: add --verbose flag"

menard: ❌ commit blocked

Stale documentation detected:
  docs/reference/cli.md
    Code: portolan_cli/cli.py
    Reason: File unchanged since portolan_cli/cli.py changed
```

Update docs, then commit succeeds:

```bash
$ git add docs/reference/cli.md
$ git commit -m "feat: add --verbose flag"
✓ menard check passed
```
