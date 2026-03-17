# Staleness Detection

docsync uses **git diff analysis** to detect when documentation becomes stale.

## How It Works

The core insight: **If code changed but the linked doc section didn't, the doc is stale.**

### Detection Algorithm

For each code→doc link:

1. **Get the last commit** that changed the code file:
   ```bash
   git log -1 --format=%H -- src/auth.py
   ```

2. **Run git diff** from that commit to HEAD on the doc file:
   ```bash
   git diff <commit> HEAD -- docs/api.md
   ```

3. **Parse the diff** to see which lines changed

4. **Check if changed lines overlap** with the linked section's line range

5. **Verdict:**
   - Lines overlap → doc was updated → **not stale** ✓
   - No overlap → doc unchanged → **stale** ❌

### Example

Given this link:
```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]
```

And this section in `docs/api.md`:
```markdown
## Authentication    ← Line 45

The authentication module handles user login...

(content from lines 45-89)
```

**Scenario 1: Doc was updated**

```bash
$ git log -1 src/auth.py
commit abc123 "refactor: extract auth helpers"

$ git diff abc123 HEAD -- docs/api.md
@@ -50,3 +50,4 @@
 The authenticate() function now uses:
+- crypto.validate_token() for JWT validation
```

**Result:** Lines 50-51 changed (within range 45-89) → **not stale** ✓

**Scenario 2: Doc was NOT updated**

```bash
$ git diff abc123 HEAD -- docs/api.md
(no output - file unchanged)
```

**Result:** No lines changed → **stale** ❌

## Section-Level Precision

Section-specific links enable **targeted staleness detection**:

### Whole-File Link (Imprecise)

```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md"]
```

Any change to `docs/api.md` clears staleness for the entire file. Changing the "Session Management" section clears staleness for the "Authentication" section, even though `src/auth.py` only relates to authentication.

### Section Link (Precise)

```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]
```

Only changes to the Authentication section (lines 45-89) clear staleness. Updating other sections doesn't affect this link.

## Transitive Staleness

docsync can detect staleness through **import chains**.

### Example

Given these files:

```python
# src/auth.py
from .crypto import validate_token

def authenticate(token):
    return validate_token(token)
```

```python
# src/crypto.py
def validate_token(token):
    # ...implementation changed...
```

And this link:
```toml
[[link]]
code = "src/auth.py"
docs = ["docs/api.md#Authentication"]
```

**Scenario:** `src/crypto.py` changed, but `src/auth.py` didn't.

**Without transitive staleness:**
- `src/auth.py` unchanged → docs not stale ✓

**With transitive staleness:**
- `src/auth.py` imports `src/crypto.py`
- `src/crypto.py` changed
- **Therefore** `docs/api.md#Authentication` is stale ❌

### Configuration

Control transitive depth in `pyproject.toml`:

```toml
[tool.docsync]
transitive_depth = 1  # Check imports 1 level deep
```

- `transitive_depth = 0` - Disable transitive staleness
- `transitive_depth = 1` - Check direct imports only
- `transitive_depth = 2` - Check imports of imports

!!! warning
    Higher depths increase computation cost. Start with `transitive_depth = 1`.

## Commands

### check (Pre-Commit)

Check staged files for stale docs:

```bash
docsync check
```

Used in pre-commit hooks. Only examines docs linked to **staged files**.

**Fast and focused** - doesn't scan the entire repo.

### list-stale (Audit)

List ALL stale docs regardless of recent changes:

```bash
docsync list-stale
```

Used for periodic audits. Scans the entire repository.

**Comprehensive but slower** - examines every link.

### JSON Output

Both commands support `--format json` for machine consumption:

```bash
$ docsync list-stale --format json
{
  "stale": [
    {
      "code_file": "src/auth.py",
      "doc_target": "docs/api.md#Authentication",
      "section": "Authentication",
      "reason": "Section unchanged since src/auth.py changed"
    }
  ]
}
```

Perfect for AI agents and automation.

## Deterministic Checks + Probabilistic Updates

docsync provides **deterministic staleness detection** that AI agents use for **scoped, probabilistic updates**:

### Layer 1: Deterministic (docsync)

```bash
$ git commit -m "refactor: extract auth helpers"

docsync: ❌ commit blocked

Stale documentation detected:
  docs/api.md#Authentication (lines 45-89)
    Code: src/auth.py
    Reason: Section unchanged since src/auth.py changed
```

**Precise and machine-readable.** No AI guessing required.

### Layer 2: Probabilistic (AI Agent)

```bash
$ docsync list-stale --format json | ai-agent update-docs
```

AI gets exact coordinates:
```json
{
  "doc_target": "docs/api.md#Authentication",
  "section": "Authentication",
  "line_range": [45, 89]
}
```

The AI's task is **scoped precisely**:
- "Update lines 45-89 in docs/api.md"
- "Don't touch other sections"
- "The authenticate() function now calls crypto.validate_token()"

**Result:** Deterministic constraints make probabilistic updates reliable.


