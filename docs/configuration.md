# Configuration

docsync is configured via `[tool.docsync]` in `pyproject.toml`.

## Default Configuration

Created by `docsync init`:

```toml
[tool.docsync]
mode = "block"
transitive_depth = 1
enforce_symmetry = true
require_links = []
exempt = []
doc_paths = ["docs/**/*.md", "README.md"]
```

## Options

### mode

**Type:** `str`  
**Default:** `"block"`  
**Values:** `"block"` | `"warn"`

Controls enforcement behavior:

- **`block`** - Commits are blocked when docs are stale (exit code 1)
- **`warn`** - Print warnings but allow commits (exit code 0)

**Example:**

```toml
[tool.docsync]
mode = "warn"  # Non-blocking for initial onboarding
```

**When to use `warn`:** Onboarding a legacy project with lots of stale docs. Gradually increase coverage before switching to `block`.

---

### transitive_depth

**Type:** `int`  
**Default:** `1`  
**Values:** `0` | `1` | `2` | ...

How deep to check imports for transitive staleness:

- **`0`** - Disable transitive staleness (only direct code→doc links)
- **`1`** - Check direct imports only
- **`2`** - Check imports of imports
- **Higher** - Exponentially expensive, rarely useful

**Example:**

```toml
[tool.docsync]
transitive_depth = 0  # Disable transitive checks
```

**Trade-off:**

- Higher depth = more accurate staleness detection
- Higher depth = slower performance

**Recommendation:** Start with `1`. Increase only if you miss important transitive staleness.

---

### enforce_symmetry

**Type:** `bool`  
**Default:** `true`

Whether to require symmetric links (code→doc implies doc→code).

**Example:**

```toml
[tool.docsync]
enforce_symmetry = false  # Allow one-way links
```

**Effect of `true`:**

If `src/auth.py` links to `docs/api.md`, then `docs/api.md` must also link back to `src/auth.py` (in the graph representation).

**When to disable:** Rarely. Symmetry ensures graph consistency.

---

### require_links

**Type:** `list[str]`  
**Default:** `[]`

Glob patterns for code files that **must** have documentation links.

**Example:**

```toml
[tool.docsync]
require_links = ["src/**/*.py"]  # All source files must be documented
```

**Effect:**

Files matching these patterns will trigger errors if not linked to any docs.

**Use cases:**

- Enforce documentation coverage for production code
- Exclude tests, scripts, experiments from requirement

**Example with exclusions:**

```toml
[tool.docsync]
require_links = ["src/**/*.py"]
exempt = ["src/experimental/**", "src/legacy/**"]
```

---

### exempt

**Type:** `list[str]`  
**Default:** `[]`

Glob patterns for code files to **ignore** entirely.

**Example:**

```toml
[tool.docsync]
exempt = [
  "tests/**",
  "scripts/**",
  "src/experimental/**",
]
```

**Effect:**

Files matching these patterns:

- Are not counted in coverage
- Don't trigger staleness checks
- Can't be linked in `.docsync/links.toml`

**Use cases:**

- Exclude test files
- Exclude scripts and tooling
- Exclude experimental code

---

### doc_paths

**Type:** `list[str]`  
**Default:** `["docs/**/*.md", "README.md"]`

Glob patterns for files that are considered "documentation."

**Example:**

```toml
[tool.docsync]
doc_paths = [
  "docs/**/*.md",
  "README.md",
  "CHANGELOG.md",
  "CLAUDE.md",
  "*.rst",  # Include reStructuredText
]
```

**Effect:**

Only files matching these patterns can be link targets.

**Use cases:**

- Add reStructuredText (`.rst`) files
- Include `CLAUDE.md` for AI agent instructions
- Include `CHANGELOG.md` for version history

---

## Example Configurations

### Strict (Production)

```toml
[tool.docsync]
mode = "block"
transitive_depth = 1
enforce_symmetry = true
require_links = ["src/**/*.py"]  # All source files must be documented
exempt = ["tests/**", "scripts/**"]
doc_paths = ["docs/**/*.md", "README.md", "CLAUDE.md"]
```

All source code must have docs. Commits blocked on staleness.

---

### Permissive (Onboarding)

```toml
[tool.docsync]
mode = "warn"  # Non-blocking
transitive_depth = 0  # Disable transitive checks
enforce_symmetry = false
require_links = []  # No coverage requirements
exempt = ["tests/**", "scripts/**", "src/legacy/**"]
doc_paths = ["docs/**/*.md", "README.md"]
```

Warnings only. Good for gradual adoption.

---

### Hybrid (Incremental)

```toml
[tool.docsync]
mode = "block"
transitive_depth = 1
enforce_symmetry = true
require_links = [
  "src/core/**/*.py",  # Core modules must be documented
  "src/api/**/*.py",   # API modules must be documented
]
exempt = [
  "tests/**",
  "scripts/**",
  "src/experimental/**",
  "src/legacy/**",
]
doc_paths = ["docs/**/*.md", "README.md", "CLAUDE.md"]
```

Enforce docs for critical modules. Exempt legacy and experimental code.

---

## Next Steps

- [**CLI Reference**](cli/reference.md) - Command options
- [**Getting Started**](getting-started.md) - Setup walkthrough
