# Agent Skills

docsync provides Claude Code skills for intelligent documentation management.

## Audit Skill

The audit skill analyzes documentation for trackability and suggests improvements. It scores each doc file and section on **deterministic verifiability** — how well docsync can track and verify the content.

Available at `.claude/skills/audit.md`.

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

### Usage

**Invoke explicitly:**
```
> Run the docsync audit skill on all documentation
```

**Invoke contextually:**
```
> I just added docs/tutorial.md, can you check if it's trackable?
```

Claude will run the audit skill and provide specific recommendations for `links.toml` additions, `donttouch` protections, and doc restructuring.
