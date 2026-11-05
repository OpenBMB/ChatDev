# Interpreting Property-Based Test Failures

How to analyze failures and determine if they represent genuine bugs.

## The Self-Reflection Problem

Property-based testing generates many failing examples. Not all failures are bugs:
- **Test bugs**: Property is wrong, strategy generates invalid inputs
- **Ambiguous specs**: Behavior undefined for edge cases
- **Genuine bugs**: Code violates documented guarantees

Before reporting a bug, **validate the failure** through systematic analysis.

## Failure Analysis Workflow

### 1. Reproduce with Minimal Example

Start with the shrunk failing input from the test output.

```python
# Hypothesis provides the minimal failing case
# Falsifying example: test_normalize(s='\x00')

# Create standalone reproducer
def test_reproduce():
    s = '\x00'
    result = normalize(normalize(s))
    assert result == normalize(s)  # Fails
```

Verify the failure is consistent, not flaky.

### 2. Ground the Property

Before assuming a bug, verify your property against authoritative sources:

| Source | What It Tells You |
|--------|-------------------|
| **Type annotations** | Return type constraints, nullability |
| **Docstrings** | Explicit guarantees, preconditions |
| **Function name** | Semantic expectations (e.g., `sort` implies ordering) |
| **Error handling** | What inputs should raise vs handle |
| **Existing unit tests** | Implicit contracts maintainers expect |
| **External docs/specs** | Protocol specs, format definitions |

**Example grounding check:**
```python
def normalize(s: str) -> str:
    """Normalize a string to NFC form.

    Args:
        s: Input string (any unicode)

    Returns:
        NFC-normalized string
    """
```

The docstring says "any unicode" - so null bytes should be valid input. The property is correctly grounded.

### 3. Check Strategy Realism

Does the strategy generate inputs the function should actually handle?

**Red flags:**
- Generating inputs outside documented domain
- Missing constraints that real callers would have
- Overly aggressive size/complexity

**Questions to ask:**
- Would real code pass this input?
- Does the docstring exclude this case?
- Is this a precondition violation, not a bug?

### 4. Classify the Failure

| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| Fails on edge case not mentioned in spec | Ambiguous specification | Clarify with maintainer before reporting |
| Fails on input that violates documented preconditions | Over-constrained strategy | Fix the strategy |
| Property contradicts docstring or type hints | Wrong property | Fix the property |
| Clear violation of documented guarantee | Genuine bug | Report with evidence |
| Behavior differs from similar functions | Possible inconsistency | Investigate further |

### 5. Decide Action

- **Test bug** → Fix the property or strategy, don't report
- **Ambiguous spec** → Open discussion issue, not bug report
- **Genuine bug** → Report with minimal reproducer and evidence

## Property Grounding Checklist

Before reporting a failure as a bug, verify:

- [ ] Property matches documented return type
- [ ] Property matches docstring guarantees
- [ ] Input is within documented domain (preconditions met)
- [ ] No `assume()` filtering out the failing case inappropriately
- [ ] Checked existing tests don't contradict your property
- [ ] Behavior contradicts docs, not just expectations

## Bug Report Template

When confident the failure is a genuine bug:

```markdown
## Summary
[One-line description of the bug]

## Minimal Reproducing Example
```python
# Shrunk by Hypothesis
from mylib import affected_function

def test_bug():
    # Minimal failing input
    result = affected_function('\x00')
    # Expected vs actual
    assert result >= 0  # Fails: got -1
```

## Expected Behavior
According to [docstring/spec/docs], the function should:
- [Specific guarantee that was violated]

## Actual Behavior
- [What actually happened]

## Evidence
- Docstring states: "[relevant quote]"
- Type signature promises: `-> PositiveInt`

## Environment
- Library version: X.Y.Z
- Python version: 3.X
- Platform: [OS]
```

## Real-World Failure Patterns

### Numerical Instability

**Symptom**: Distribution function returns negative probability.

```python
@given(st.floats(min_value=0, max_value=1e308))
def test_probability_non_negative(x):
    prob = compute_probability(x)
    assert prob >= 0  # Fails for x=1e-320
```

**Grounding check**: Docstring says "returns probability in [0, 1]".

**Classification**: Genuine bug - documented guarantee violated.

### Iterator Off-by-One

**Symptom**: Iterator skips elements or yields extra.

```python
@given(st.lists(st.integers()))
def test_iterator_yields_all(xs):
    result = list(custom_iterator(xs))
    assert result == xs  # Fails: missing last element
```

**Grounding check**: Iterator should yield all elements based on name/docs.

**Classification**: Genuine bug if documented to iterate fully.

### Hash/Equality Inconsistency

**Symptom**: Equal objects have different hashes.

```python
@given(valid_objects())
def test_hash_equality(obj):
    obj2 = create_equal_copy(obj)
    assert obj == obj2
    assert hash(obj) == hash(obj2)  # Fails
```

**Grounding check**: Python requires `a == b` implies `hash(a) == hash(b)`.

**Classification**: Genuine bug - violates language contract.

### Roundtrip Failure on Edge Cases

**Symptom**: Encode/decode doesn't preserve input.

```python
@given(st.text())
def test_roundtrip(s):
    assert decode(encode(s)) == s  # Fails for s='\uD800'
```

**Grounding check**: Is `'\uD800'` (lone surrogate) valid input?

**Classification**:
- If docs say "valid UTF-8 only" → Strategy bug, fix filter
- If docs say "any string" → Genuine bug, report it

### Format String Errors

**Symptom**: String formatting crashes on certain inputs.

```python
@given(st.text())
def test_format_safe(template):
    format_message(template)  # Raises on '{unclosed'
```

**Grounding check**: Does function claim to handle arbitrary strings?

**Classification**:
- If user-facing, should handle gracefully → Genuine bug
- If internal API with preconditions → Check preconditions met

## When NOT to Report

Do not report as bugs:

1. **Precondition violations**: If docs say "positive integers only" and you passed -1
2. **Undefined behavior**: Spec explicitly says behavior is undefined
3. **Implementation details**: Relying on undocumented internal behavior
4. **Platform-specific**: Bug only on unusual platform/version
5. **Test artifact**: Failure disappears with realistic constraints

## Confidence Threshold

Report only when you can answer YES to all:

1. Did you reproduce with a minimal example?
2. Did you verify the property against docs/types/docstrings?
3. Can you point to a specific documented guarantee that's violated?
4. Is the failing input within the documented domain?
5. Have you ruled out test bugs and ambiguous specs?

If uncertain on any point, open a discussion first, not a bug report.
