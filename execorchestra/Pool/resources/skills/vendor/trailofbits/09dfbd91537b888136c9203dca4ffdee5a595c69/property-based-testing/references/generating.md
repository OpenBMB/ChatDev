# Generating Property-Based Tests

How to create complete, runnable property-based tests.

## Process

### 1. Analyze Target Function

- Read function signature, types, and docstrings
- Understand input types and constraints
- Identify output type and expected behavior
- Note preconditions or invariants
- Check existing example-based tests as hints

### 2. Design Input Strategies

Create appropriate generator strategies for each input parameter.

**Principles**:
- Build constraints INTO the strategy, not via `assume()`
- Use realistic size limits to prevent slow tests
- Match real-world constraints

### 3. Identify Applicable Properties

| Property | When to Use | Test Pattern |
|----------|-------------|--------------|
| Roundtrip | encode/decode pairs | `assert decode(encode(x)) == x` |
| Idempotence | normalization, sorting | `assert f(f(x)) == f(x)` |
| Invariant | any transformation | `assert invariant(f(x))` |
| No exception | all functions (weak) | Function completes without raising |
| Type preservation | typed functions | `assert isinstance(f(x), ExpectedType)` |
| Length preservation | collections | `assert len(f(xs)) == len(xs)` |
| Element preservation | sorting, shuffling | `assert set(f(xs)) == set(xs)` |
| Ordering | sorting | `assert all(f(xs)[i] <= f(xs)[i+1] ...)` |
| Oracle | when reference exists | `assert f(x) == reference_impl(x)` |
| Commutativity | binary ops | `assert f(a, b) == f(b, a)` |

### 4. Generate Test Code

Create test functions with:
- Clear docstrings explaining what each property verifies
- Appropriate `@settings` for the context
- `@example` decorators for critical edge cases

### 5. Include Edge Cases

Always add explicit examples:
```python
@example([])           # Empty
@example([1])          # Single element
@example([1, 1, 1])    # Duplicates
@example("")           # Empty string
@example(0)            # Zero
@example(-1)           # Negative
```

## Settings Recommendations

```python
# Development (fast feedback)
@settings(max_examples=10)

# CI (thorough)
@settings(max_examples=200)

# Nightly/Release (exhaustive)
@settings(max_examples=1000, deadline=None)
```

## Example Test Patterns

### Roundtrip (Encode/Decode)

```python
@given(valid_messages())
def test_roundtrip(msg):
    """Encoding then decoding returns original."""
    assert decode(encode(msg)) == msg
```

### Idempotence

```python
@given(st.text())
def test_normalize_idempotent(s):
    """Normalizing twice equals normalizing once."""
    assert normalize(normalize(s)) == normalize(s)
```

### Sorting Properties

```python
@given(st.lists(st.integers()))
@example([])
@example([1])
@example([1, 1, 1])
def test_sort(xs):
    result = sort(xs)
    # Length preserved
    assert len(result) == len(xs)
    # Elements preserved
    assert sorted(result) == sorted(xs)
    # Ordered
    assert all(result[i] <= result[i+1] for i in range(len(result)-1))
    # Idempotent
    assert sort(result) == result
```

### Validator + Normalizer

```python
@given(valid_inputs())
def test_normalized_is_valid(x):
    """Normalized inputs pass validation."""
    assert is_valid(normalize(x))
```

## Complete Example (Python/Hypothesis)

```python
"""Property-based tests for message_codec module."""
from hypothesis import given, strategies as st, settings, example
import pytest

from myapp.codec import encode_message, decode_message, Message, DecodeError

# Custom strategy for Message objects
messages = st.builds(
    Message,
    id=st.uuids(),
    content=st.text(max_size=1000),
    priority=st.integers(min_value=1, max_value=10),
    tags=st.lists(st.text(max_size=50), max_size=20),
)


class TestMessageCodecProperties:
    """Property-based tests for message encoding/decoding."""

    @given(messages)
    def test_roundtrip(self, msg: Message):
        """Encoding then decoding returns the original message."""
        encoded = encode_message(msg)
        decoded = decode_message(encoded)
        assert decoded == msg

    @given(messages)
    def test_encode_deterministic(self, msg: Message):
        """Same message always encodes to same bytes."""
        assert encode_message(msg) == encode_message(msg)

    @given(messages)
    def test_encoded_is_bytes(self, msg: Message):
        """Encoding produces bytes."""
        assert isinstance(encode_message(msg), bytes)

    @given(st.binary())
    def test_decode_invalid_raises_or_succeeds(self, data: bytes):
        """Random bytes either decode or raise DecodeError."""
        try:
            decode_message(data)
        except DecodeError:
            pass  # Expected for invalid input
```

## Running Tests

```bash
# Run all property tests
pytest test_file.py -v

# Run with more examples (CI)
pytest test_file.py --hypothesis-seed=0 -v

# Run with statistics
pytest test_file.py --hypothesis-show-statistics
```

## Checklist Before Finishing

- [ ] Tests are not tautological (don't reimplement the function)
- [ ] At least one strong property (not just "no crash")
- [ ] Edge cases covered with `@example` decorators
- [ ] Strategy constraints are realistic, not over-filtered
- [ ] Settings appropriate for context (dev vs CI)
- [ ] Docstrings explain what each property verifies
- [ ] Tests actually run and pass (or fail for expected reasons)

## Red Flags

- **Reimplementing the function**: If your assertion contains the same logic as the function under test, you've written a tautology
  ```python
  # BAD - this tests nothing
  assert add(a, b) == a + b
  ```
- **Only testing "no crash"**: This is the weakest property - always look for stronger ones first
- **Overly constrained strategies**: If you're using multiple `assume()` calls, redesign the strategy instead
- **Missing edge cases**: No `@example` decorators for empty, single-element, or boundary values
- **No settings**: Missing `@settings` for CI - tests may be too slow or not thorough enough

## When Tests Fail

See [{baseDir}/references/interpreting-failures.md]({baseDir}/references/interpreting-failures.md) for how to interpret failures and determine if they represent genuine bugs vs test errors vs ambiguous specifications.
