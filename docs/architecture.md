# Architecture

This document describes docsync's internal architecture and core modules.

## Overview

docsync is built around a **bidirectional graph** that maps code files to documentation targets.

The graph enables:

- Fast lookups: "Which docs link to this code file?"
- Reverse lookups: "Which code files link to this doc?"
- Transitive staleness: "Did any imported code change?"

## File Structure

```
.docsync/
├── links.toml          # Source of truth for code↔doc links (COMMIT THIS)
└── cache/              # Import graph cache (IGNORE THIS)
    └── imports_*.json

pyproject.toml          # [tool.docsync] configuration
```

### What to Commit

**DO commit:**
- `.docsync/links.toml` - Shared source of truth
- `pyproject.toml` - Project configuration

**DON'T commit:**
- `.docsync/cache/` - Temporary import graph cache

Add to `.gitignore`:
```gitignore
.docsync/cache/
```

## Core Modules

| Module | Purpose |
|--------|---------|
| `cli.py` | Command-line interface and skill discovery |
| `config.py` | Configuration parsing from `pyproject.toml` |
| `toml_links.py` | TOML link file parsing and graph construction |
| `sections.py` | Markdown section parsing and line range extraction |
| `staleness.py` | Git diff-based section staleness detection |
| `graph.py` | Bidirectional graph construction |
| `imports.py` | Python import graph via AST parsing |
| `hook.py` | Pre-commit hook entry point |
| `donttouch.py` | Protected content guard |
| `coverage.py` | Documentation coverage reporting |
| `cache.py` | Import graph caching |

## Graph Structure

The docsync graph is a **bidirectional mapping** between code files and doc targets.

### Example Graph

Given these links:

```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication", "docs/auth.md"]

[[link]]
code = "src/models/user.py"
docs = ["docs/models.md#User Model"]
```

The graph is:

```python
{
  # Code → Docs
  "src/auth.py": {
    "docs/api.md#Authentication",
    "docs/auth.md"
  },
  "src/models/user.py": {
    "docs/models.md#User Model"
  },
  
  # Docs → Code (reverse)
  "docs/api.md#Authentication": {"src/auth.py"},
  "docs/auth.md": {"src/auth.py"},
  "docs/models.md#User Model": {"src/models/user.py"},
}
```

### Section-Specific Targets

Section targets (`docs/api.md#Authentication`) are **distinct nodes** from whole-file targets (`docs/api.md`).

This enables **targeted staleness checking** - only the specific section needs updating, not the entire file.

## Section Parsing

The `sections.py` module extracts markdown section headings and their line ranges.

### Algorithm

```python
def extract_sections(markdown_path):
    """Extract sections with their line ranges."""
    sections = []
    current_section = None
    
    for line_num, line in enumerate(read_file(markdown_path)):
        if line.startswith('#'):
            # Close previous section
            if current_section:
                current_section['end'] = line_num - 1
                sections.append(current_section)
            
            # Start new section
            heading = line.lstrip('#').strip()
            current_section = {
                'heading': heading,
                'start': line_num,
            }
    
    # Close final section
    if current_section:
        current_section['end'] = line_num
        sections.append(current_section)
    
    return sections
```

### Example

Given `docs/api.md`:

```markdown
# API Documentation

Introduction text...

## Authentication

Auth details (lines 5-30)

## Session Management

Session details (lines 32-60)
```

Output:

```python
[
  {'heading': 'API Documentation', 'start': 0, 'end': 3},
  {'heading': 'Authentication', 'start': 4, 'end': 30},
  {'heading': 'Session Management', 'start': 31, 'end': 60},
]
```

## Staleness Detection

The `staleness.py` module implements git diff-based staleness checking.

### Algorithm

```python
def is_doc_stale(code_file, doc_target):
    """Check if a doc target is stale."""
    # 1. Get last commit that changed the code file
    last_commit = git_last_commit(code_file)
    
    # 2. Run git diff from that commit to HEAD
    diff = git_diff(last_commit, 'HEAD', doc_target.file)
    
    # 3. Parse diff to get changed line numbers
    changed_lines = parse_diff_lines(diff)
    
    # 4. If target is section-specific, check line range overlap
    if doc_target.section:
        section_range = get_section_range(doc_target.file, doc_target.section)
        if any(line in section_range for line in changed_lines):
            return False  # Section was updated, not stale
        else:
            return True   # Section unchanged, stale
    else:
        # Whole-file target
        if changed_lines:
            return False  # File was updated
        else:
            return True   # File unchanged
```

### Why Git Diff?

**Alternatives considered:**

- File modification time - unreliable (git operations change mtime)
- Line-by-line comparison - doesn't capture "when was this written"
- Manual timestamps - error-prone, not version-controlled

**Git diff wins because:**

- Version-controlled (part of git history)
- Precise (line-level granularity)
- Fast (native git operation)
- Deterministic (same result every time)

## Import Graph

The `imports.py` module builds a Python import graph via AST parsing.

### Purpose

Enable **transitive staleness detection**:

- `src/auth.py` imports `src/crypto.py`
- `src/crypto.py` changed
- **Therefore** docs for `src/auth.py` may be stale

### Algorithm

```python
def build_import_graph(repo_root):
    """Build import graph via AST parsing."""
    graph = {}
    
    for py_file in find_python_files(repo_root):
        imports = extract_imports_ast(py_file)
        graph[py_file] = resolve_imports(imports, repo_root)
    
    return graph
```

### Caching

Import graphs are **expensive to compute** (AST parsing for every Python file).

The `cache.py` module caches graphs using:

- **SHA-based invalidation** - Cache key includes file content hash
- **Automatic cleanup** - Old cache entries removed on first miss

Cache location: `.docsync/cache/imports_<sha>.json`

## Protected Content

The `donttouch.py` module guards critical content from staleness checks.

### Data Structure

```python
{
  'sections': [
    'README.md#License',
    'docs/contributing.md#Code of Conduct',
  ],
  'literals': [
    'Python 3.11+',
    '#7730E1',
  ],
}
```

### Enforcement

When checking staleness:

```python
if doc_target in protected_sections:
    return False  # Never stale, skip check
```

When validating changes:

```python
if literal in protected_literals and literal_changed:
    warn(f"Protected literal changed: {literal}")
```

## Coverage Calculation

The `coverage.py` module reports documentation coverage.

### Algorithm

```python
def calculate_coverage(graph, config):
    """Calculate documentation coverage."""
    code_files = find_code_files(config.require_links, config.exempt)
    documented = [f for f in code_files if f in graph]
    
    coverage = len(documented) / len(code_files)
    
    return {
        'coverage': coverage,
        'total_files': len(code_files),
        'documented_files': len(documented),
        'undocumented_files': [f for f in code_files if f not in documented],
    }
```

### What Counts as "Documented"

A code file is documented if:

- It appears as a `code` field in any `[[link]]` entry
- Or matches a glob pattern in a `code` field

## Next Steps

- [**Contributing**](contributing.md) - Development setup
- [**Concepts**](concepts/links.md) - Understand the graph model
