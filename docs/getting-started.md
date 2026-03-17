# Getting Started

This guide walks you through setting up docsync in your project.

## Installation

### Using uv (Recommended)

```bash
uv pip install git+https://github.com/nlebovits/docsync.git
```

### Using pip

```bash
pip install git+https://github.com/nlebovits/docsync.git
```

## Initialize in Your Repository

Navigate to your repository and run:

```bash
cd your-repo
docsync init
```

This creates:

- `[tool.docsync]` configuration in `pyproject.toml`
- `.docsync/links.toml` file for defining code-doc links
- `.docsync/` directory for cache storage

## Define Code-Documentation Links

Edit `.docsync/links.toml` to establish relationships between code and docs:

### Simple Whole-File Link

```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]
```

When `src/auth.py` changes, `docs/api.md` must be updated.

### Section-Specific Link (Recommended)

```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]
```

More precise! Only the `Authentication` section needs updating when `src/auth.py` changes.

### Multiple Targets

```toml
[[link]]
code = "src/models/user.py"
docs = [
  "docs/models.md#User Model",
  "docs/api.md#User Endpoints",
]
```

One code file can link to multiple doc sections.

### Glob Patterns

```toml
[[link]]
code = "src/models/*.py"
docs = ["docs/models.md"]
```

All Python files in `src/models/` link to `docs/models.md`.

## Auto-Generate Links

Instead of writing links manually, use bootstrap:

```bash
docsync bootstrap --apply
```

This intelligently proposes links using:

- **Filename matching**: `src/auth.py` → `docs/auth.md`
- **Content analysis**: Grep docs for references to code files
- **Import graph**: Transitive link suggestions

!!! warning
    Bootstrap can't reliably infer links for human-facing docs (tutorials, examples, READMEs). Review all suggestions carefully.

## Install the Pre-Commit Hook

```bash
docsync install-hook
```

Now commits will be blocked if documentation is stale:

```bash
$ git add src/auth.py
$ git commit -m "refactor: extract auth helpers"

docsync: ❌ commit blocked

Stale documentation detected:
  docs/api.md#Authentication
    Code: src/auth.py
    Reason: Section unchanged since src/auth.py changed
```

## Validate Your Setup

### Check All Links Are Valid

```bash
docsync validate-links
```

Expected output:
```
✓ All 10 links are valid
```

### Check Documentation Coverage

```bash
docsync coverage
```

Expected output:
```
Documentation Coverage: 85.0%
  Total code files: 20
  Documented: 17
  Undocumented files:
    src/experimental.py
    src/legacy.py
    src/draft.py
```

## What's Next?

- [**Tutorial**](tutorial.md) - See a real-world onboarding workflow
- [**Concepts**](concepts/links.md) - Understand how links work
- [**CLI Reference**](cli/reference.md) - Explore all commands
- [**Configuration**](configuration.md) - Customize docsync behavior
