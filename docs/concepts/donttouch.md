# Protected Content

The `.docsync/donttouch` file protects critical content from accidental changes.

## Why Protected Content?

Some documentation content is **policy, not implementation details**:

- **Licenses** - Legal text that must not change without review
- **Version requirements** - "Python 3.11+" is a project constraint
- **Brand assets** - Color palettes, logos must stay consistent
- **Code of Conduct** - Community policy
- **Terminology** - Enforced project-wide naming conventions

These should **never be marked as stale** just because related code changed.

## Format

The `.docsync/donttouch` file has two types of protections:

### Section Protection

Protect specific doc sections:

```
# Comments are allowed
README.md#License
docs/contributing.md#Code of Conduct
CLAUDE.md#Terminology (ENFORCED)
```

**Effect:** docsync will **never** mark these sections as stale, even if linked code changes.

### Literal Protection

Protect specific strings across all docs:

```
"Python 3.11+"
"Apache-2.0"
"#7730E1"
```

**Effect:** docsync will warn if these literals are changed.

## Example

Given this `.docsync/donttouch`:

```
# License sections are legal text
README.md#License
docs/contributing.md#License

# Brand colors must match BRANDING.md
docs/index.md#Colors
mkdocs.yml#palette

# Version requirement is a constraint
"Python 3.11+"
```

### Scenario 1: Section Protection

```toml
# .docsync/links.toml
[[link]]
code = "setup.py"
docs = ["README.md#License"]
```

Even when `setup.py` changes, `README.md#License` is **never** marked stale (it's protected).

### Scenario 2: Literal Protection

Someone changes `"Python 3.11+"` to `"Python 3.10+"` in `README.md`:

```bash
$ docsync check

⚠️  Warning: Protected literal changed
  "Python 3.11+" → "Python 3.10+"
  In: README.md
  
  This is a protected literal in .docsync/donttouch
  Ensure this change is intentional.
```

## Commands

### List Protected Content

```bash
docsync list-protected
```

Output:
```
Protected sections:
  README.md#License
  docs/contributing.md#License
  docs/contributing.md#Code of Conduct
  CLAUDE.md#Terminology (ENFORCED)
  docs/BRANDING.md#Color Palette

Global literals:
  "Python 3.11+"
  "Apache-2.0"
  "#7730E1"
```

### JSON Output

```bash
$ docsync list-protected --format json
{
  "protected_sections": [
    "README.md#License",
    "docs/contributing.md#Code of Conduct"
  ],
  "protected_literals": [
    "Python 3.11+",
    "Apache-2.0"
  ]
}
```

## Best Practices

### What to Protect

**Do protect:**
- Legal text (licenses, CoC)
- Brand assets (colors, logos)
- Version requirements
- Enforced terminology
- Project policies

**Don't protect:**
- Implementation details
- Code examples
- API documentation
- Tutorials

### Audit Skill Integration

The docsync audit skill automatically suggests `donttouch` protections when analyzing your docs:

```bash
# In Claude Code
> Run the docsync audit skill
```

The audit will identify:
- License sections
- Version requirements
- Brand references
- Policy sections

And suggest adding them to `.docsync/donttouch`.

## Next Steps

- [**Tutorial**](../tutorial.md#step-6-create-donttouch-protections) - See donttouch in action
- [**Skills**](../skills/audit.md) - Learn about the audit skill
