# Agent Skills

menard ships Claude Code skills for intelligent documentation management. Skills are automatically available when you install menard.

## Discovering Skills

```bash
menard skills              # List all available skills
menard skills --format json  # JSON output
```

Skills can be **bundled** (shipped with menard) or **local** (in your project's `.claude/skills/` directory). Local skills with the same name override bundled ones.

## Customizing Bundled Skills

To customize a bundled skill:

```bash
menard skills --copy audit   # Copy to .claude/skills/audit.md
# Edit the local copy as needed
```

Use `--force` to overwrite an existing local skill.

---

## Audit Skill

The audit skill analyzes documentation for trackability, detects cross-document disagreements, and suggests improvements. It scores each doc file and section on **deterministic verifiability** — how well menard can track and verify the content.

**Source:** Bundled with menard (customizable via `menard skills --copy audit`).

### Phases

The audit runs in three phases. By default, all phases run sequentially.

| Phase | Flag | Description |
|-------|------|-------------|
| detect | `--phase=detect` | Find issues: coverage gaps, disagreements, orphaned docs |
| suggest | `--phase=suggest` | Generate fix recommendations |
| fix | `--phase=fix` | Apply deterministic patterns |

```bash
menard audit                    # Run all phases (default)
menard audit --phase=detect     # Stop after detection
menard audit --phase=suggest    # Stop after suggestions
```

Each phase outputs usable results if stopped early.

### Dry Run

Preview scope and estimated effort before running:

```bash
menard audit --dry-run
```

Output:
```
Menard audit scope:
  Files: README.md, CLAUDE.md, docs/*.md (14 files)
  Links: .menard/links.toml (23 relationships)

  Phases: detect -> suggest -> fix
  Estimated: ~18k tokens

  Run without --dry-run to proceed.
```

### Cross-Document Disagreement Detection

The audit detects conflicting claims across documentation files:

| Pattern | Example | Impact |
|---------|---------|--------|
| Version conflicts | README says 3.10+, CLAUDE.md says 3.11+ | Wrong version installed |
| Command conflicts | One doc shows `--output`, another shows `--fix-output` | Commands fail |
| Install conflicts | README says `pip`, CLAUDE.md says `uv` | Inconsistent onboarding |
| Default conflicts | "Default is 10" vs "Default is 100" | Unexpected behavior |

**Two-audience awareness:** The audit distinguishes between user-facing docs (README, docs/) and AI-facing docs (CLAUDE.md, context/, skills/). Cross-audience disagreements are particularly high-impact.

### Scoring Rubric

Each doc section receives a score (1-10):

| Score | Meaning | Characteristics |
|-------|---------|-----------------|
| 9-10  | **Highly trackable** | Tables, code blocks, single-file scope, in `links.toml` |
| 7-8   | **Trackable** | File references present, some structure, could use more links |
| 5-6   | **Partially trackable** | Mix of structure and prose, missing `links.toml` entries |
| 3-4   | **Poorly trackable** | Long prose, vague references, no links |
| 1-2   | **Untrackable** | Pure narrative, no code references, impossible to verify |

### Example Output

```
# docs/api.md
  Overall: 6/10 (partially trackable)

  ## Authentication (8/10)
    + Contains code examples
    + References src/auth.py
    ! src/auth.py not in links.toml - SUGGEST ADD

  ## Data Pipeline (3/10)
    x 400 words of prose, no tables or code blocks
    x References 7 code files, none in links.toml
    x No clear single-file scope - consider splitting

# Cross-Document Disagreements
  x DISAGREEMENT: Installation method
    README.md:15 says: `pip install mypackage`
    CLAUDE.md:8 says: `uv add mypackage`
    -> Pick one source of truth
```

### Usage

**Invoke explicitly:**
```
> Run the menard audit skill on all documentation
```

**With phase control:**
```
> Run menard audit --phase=detect only
```

**Invoke contextually:**
```
> I just added docs/tutorial.md, can you check if it's trackable?
```

Claude will run the audit skill and provide specific recommendations for `links.toml` additions, `donttouch` protections, and doc restructuring.

---

## Compress Skill

The compress skill makes documentation deterministically maintainable by replacing prose with pointers, auto-generating repeated content, and enforcing rules with hooks instead of prose.

**Source:** Bundled with menard (customizable via `menard skills --copy compress`).

### When to Use

Use this skill when:

- You already know your docs have issues (ran audit `--phase=detect`)
- Docs feel bloated and you want to reduce drift surface area
- You're seeing the same information in multiple places
- Rules exist only in prose and keep getting violated

**Target:** ~50% line reduction by replacing prose with deterministic references.

### Patterns

#### 1. Pointer Over Prose

Instead of writing instructions, point to the source of truth:

```markdown
# Prose (drifts)
Run ruff before committing. Use `uv run ruff check --fix .`

# Pointer (stays current)
**Code quality handled by pre-commit.** See `.pre-commit-config.yaml`.
```

#### 2. Auto-Generate Repeated Content

Use markers for content that appears in multiple places:

```markdown
<!-- BEGIN GENERATED: test-markers -->
| Marker | Description |
|--------|-------------|
| `@pytest.mark.slow` | Tests taking >5s |
<!-- END GENERATED: test-markers -->
```

One script generates the content; all docs stay synchronized.

#### 3. Enforce With Hooks, Not Prose

```yaml
# Prose-only rule (ignored)
"Never use fetch_arrow_table()"

# Pre-commit hook (enforced)
- id: duckdb-antipatterns
  entry: bash -c 'grep -rn "\.fetch_arrow_table()" && exit 1 || exit 0'
```

#### 4. Audit for Orphaned Docs

Detect documentation referencing things that no longer exist:

- Hooks mentioned but not in `.pre-commit-config.yaml`
- Files referenced but deleted
- Config values that changed

### Usage

**Standalone:**
```
> Run the compress skill on my documentation
```

**After audit:**
```
> Run audit --phase=detect, then compress to fix the issues
```

**Targeted:**
```
> Apply pointer-over-prose pattern to CLAUDE.md
```

---

## Skill Integration

The audit and compress skills work together:

```
audit --phase=detect    # Find problems
audit --phase=suggest   # Get recommendations
compress                # Apply deterministic patterns
```

Or run the full workflow:

```
audit                   # All phases: detect -> suggest -> fix
```
