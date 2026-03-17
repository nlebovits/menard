# Links

docsync uses a centralized TOML file to define code-documentation relationships.

## Why Centralized Links?

**No inline comments in code.** Instead of polluting source files with `# docsync: docs/api.md`, all relationships live in `.docsync/links.toml`.

Benefits:

- **Single source of truth** - All links in one place
- **Clean codebase** - No documentation metadata in source files
- **Easy auditing** - See all relationships at a glance
- **Version controlled** - Links are tracked in git
- **Agent-friendly** - Machines can parse TOML easily

## Link Format

Each link defines a code→doc relationship:

```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]
```

### Code Field

The `code` field specifies which source file(s) to track:

**Single file:**
```toml
code = "src/auth.py"
```

**Glob pattern:**
```toml
code = "src/models/*.py"
```

All Python files in `src/models/` are linked to the specified docs.

### Docs Field

The `docs` field is an **array** of documentation targets. Each target can be:

**Whole file:**
```toml
docs = ["docs/api.md"]
```

**Specific section:**
```toml
docs = ["docs/api.md#Authentication"]
```

Links to the `Authentication` section (identified by heading).

**Multiple targets:**
```toml
docs = [
  "docs/api.md#User Endpoints",
  "docs/models.md#User Model",
  "CLAUDE.md#User Management",
]
```

One code file can link to multiple doc sections.

## Section-Level Links

Section-specific links are **more precise** than whole-file links:

### Without Sections

```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]  # 500-line file with 15 sections
```

**Problem:** Any change to `src/auth.py` marks the entire 500-line doc as stale.

### With Sections

```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]  # Specific 44-line section
```

**Solution:** Only the Authentication section is marked stale. Other sections remain fresh.

### How It Works

docsync:

1. Parses `docs/api.md` to find the `Authentication` heading
2. Extracts the line range (e.g., lines 45-89)
3. When checking staleness, runs `git diff` on those specific lines
4. If lines 45-89 changed → section was updated, not stale
5. If lines 45-89 unchanged → section is stale

This is **accurate**: updating a different section doesn't clear staleness for Authentication.

## Glob Patterns

Use glob patterns to link entire directories:

```toml
[[link]]
code = "src/models/*.py"
docs = ["docs/models.md"]
```

Matches:
- `src/models/user.py`
- `src/models/post.py`
- `src/models/comment.py`

**Recursive globs:**
```toml
code = "src/**/*.py"
```

Matches all Python files under `src/`, recursively.

## Multiple Links for One File

You can define multiple links for the same code file:

```toml
# General API docs
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]

# Implementation details
[[link]]
code = "src/auth.py"
docs = ["docs/architecture.md#Auth Module"]

# Claude Code instructions
[[link]]
code = "src/auth.py"
docs = ["CLAUDE.md#Authentication Patterns"]
```

When `src/auth.py` changes, **all three docs** must be updated.

## Validation

Check that all link targets exist:

```bash
docsync validate-links
```

Output:
```
✓ All 15 links are valid
```

Or if issues found:
```
❌ Invalid links:
  src/auth.py → docs/api.md#NonExistent
    Section 'NonExistent' not found in docs/api.md
```

## Next Steps

- [**Staleness Detection**](staleness.md) - How docsync detects stale docs
- [**Configuration**](../configuration.md) - Customize link requirements
