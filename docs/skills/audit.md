# Audit Skill

The docsync audit skill analyzes your documentation for trackability and suggests improvements.

## Overview

The audit skill bridges the gap between "messy existing docs" and "docs that docsync can enforce."

It scores each doc file and section on **deterministic verifiability** — how well docsync can track and verify the content.

## When to Use

Use this skill when:

- **Onboarding** - After `docsync init`, before writing links
- **Periodic health checks** - Audit documentation coverage quarterly
- **After adding docs** - New docs need `links.toml` entries
- **Messy docs** - Documentation feels unstructured or hard to track

## What It Analyzes

The skill examines four dimensions:

### 1. Structure

**Good:**

- Tables with file paths, commands, or config values
- Code blocks with actual commands or snippets
- Clear headings creating logical sections
- Short, factual assertions

**Bad:**

- Long prose blocks (>300 words) without structure
- Flat text with no headings
- Narrative tutorials (hard to track against code)

### 2. File References

**Good:**

- Backtick-quoted paths: `` `src/auth.py` ``
- Clear code→doc mappings
- Already in `links.toml`

**Bad:**

- Implicit mentions in prose: "The auth module handles..."
- References not tracked in `links.toml`

### 3. Section Scope

**Good:**

- Each section maps to 1-2 code files
- Clear boundaries between sections
- Section headings match code concepts

**Bad:**

- Section references 7+ files
- No clear mapping between heading and code
- Mixed concerns in one section

### 4. Protected Content

**Good:**

- Licenses in `donttouch`
- Version requirements protected
- Brand colors protected
- Critical terminology enforced

**Bad:**

- Unprotected license sections
- Mutable version constraints
- No policy enforcement

## Scoring Rubric

Each doc section receives a score (1-10):

| Score | Meaning | Characteristics |
|-------|---------|-----------------|
| 9-10  | **Highly trackable** | Tables, code blocks, single-file scope, in `links.toml` |
| 7-8   | **Trackable** | File references present, some structure, could use more links |
| 5-6   | **Partially trackable** | Mix of structure and prose, missing `links.toml` entries |
| 3-4   | **Poorly trackable** | Long prose, vague references, no links |
| 1-2   | **Untrackable** | Pure narrative, no code references, impossible to verify |

## Example Audit Output

```
# docs/api.md
  Overall: 6/10 (partially trackable)

  ## Authentication (8/10)
    ✓ Contains code examples
    ✓ References src/auth.py
    ⚠ src/auth.py not in links.toml — SUGGEST ADD

  ## Data Pipeline (3/10)
    ✗ 400 words of prose, no tables or code blocks
    ✗ References 7 code files, none in links.toml
    ✗ No clear single-file scope — consider splitting

  ## License (9/10)
    ✓ Short, assertable content
    ⚠ Not in donttouch — SUGGEST PROTECT
```

## Suggestions

The audit skill provides actionable suggestions:

### links.toml Additions

```toml
# SUGGESTED: Add to .docsync/links.toml

[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]

[[link]]
code = "src/pipeline.py"
docs = ["docs/api.md#Data Pipeline"]
```

### donttouch Protections

```
# SUGGESTED: Add to .docsync/donttouch

# Legal text
README.md#License
docs/contributing.md#Code of Conduct

# Version constraint
"Python 3.11+"

# Brand identity
"#7730E1"
```

### Restructuring

```
SUGGESTED: Restructure docs/api.md#Data Pipeline

Current: 400-word prose block referencing 7 files
Better: Split into subsections, one per module:

  ## Data Pipeline
  ### Ingestion (`src/ingest.py`)
  ### Transform (`src/transform.py`)
  ### Output (`src/output.py`)

Then add section-specific links in links.toml.
```

## Usage in Claude Code

The audit skill is available as `.claude/skills/audit.md`.

### Invoke Explicitly

```
> Run the docsync audit skill on all documentation
```

### Invoke Contextually

```
> I just added docs/tutorial.md, can you check if it's trackable?
```

Claude will run the audit skill and provide specific recommendations.

## Workflow Integration

### Ideal Onboarding Flow

```bash
# 1. Initialize docsync
docsync init

# 2. Run audit in Claude Code
> Audit my documentation and apply the suggestions

# 3. Fill in convention-based links
docsync bootstrap --apply

# 4. Validate
docsync validate-links

# 5. Check coverage
docsync coverage

# 6. Install enforcement
docsync install-hook
```

The audit step (step 2) provides the foundation for meaningful `links.toml` entries.

## What the Skill Can't Do

The audit skill **cannot** determine:

- **Correctness** - Whether docs accurately describe code behavior
- **Completeness** - Whether all code features are documented
- **Clarity** - Whether docs are well-written for humans

It **only** measures **trackability** - how well docsync can verify freshness.

## Next Steps

- [**Tutorial**](../tutorial.md#step-5-run-the-audit-skill) - See audit in action
- [**Getting Started**](../getting-started.md) - Setup docsync
- [**Concepts**](../concepts/links.md) - Understand links
