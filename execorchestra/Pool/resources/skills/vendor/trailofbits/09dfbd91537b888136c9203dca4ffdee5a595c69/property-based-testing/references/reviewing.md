# Reviewing Property-Based Tests

Evaluate quality of existing property-based tests and suggest improvements.

## Quick Reference

| Issue | Severity | Detection | Fix |
|-------|----------|-----------|-----|
| Tautological | CRITICAL | Assertion compares same expression | Rewrite with actual property |
| Vacuous | CRITICAL | Contradictory `assume()` calls | Remove or fix filters |
| Weak (no assertion) | HIGH | Test body has no assert | Add meaningful assertion |
| Reimplementation | HIGH | Assertion mirrors function logic | Use algebraic property instead |
| Over-filtered | MEDIUM | Many `assume()` calls | Redesign strategy |
| Missing edge cases | MEDIUM | No `@example` decorators | Add explicit edge cases |
| Poor settings | LOW | Missing or bad `@settings` | Add appropriate settings |

## Quality Issues

### Issue: Tautological Properties (CRITICAL)

Properties that are always true regardless of implementation.

```python
# BAD - compares function to itself
@given(st.lists(st.integers()))
def test_sort_tautology(xs):
    assert sorted(xs) == sorted(xs)  # Always true!

# BAD - tests nothing about the function
@given(st.integers())
def test_useless(x):
    result = compute(x)
    assert result == result  # Always true!
```

**Detection**: Assertions comparing same expression, or not using function result meaningfully.

### Issue: Vacuous Tests (CRITICAL)

Tests where assumptions filter out most/all inputs.

```python
# VACUOUS - impossible condition
@given(st.integers())
def test_vacuous(x):
    assume(x > 100)
    assume(x < 50)  # Impossible!
    assert compute(x) > 0

# VACUOUS - overly restrictive
@given(st.integers())
def test_too_filtered(x):
    assume(x == 42)  # Only tests one value!
    assert compute(x) == expected
```

**Detection**: Multiple `assume()` calls, `assume` with very narrow conditions.

### Issue: Weak Properties (HIGH)

Properties that only test minimal guarantees.

```python
# WEAK - only tests no crash
@given(st.text())
def test_only_no_crash(s):
    process(s)  # No assertion at all

# WEAK - only tests type
@given(st.integers())
def test_only_type(x):
    assert isinstance(compute(x), int)
```

**Detection**: Tests without assertions, or only `isinstance`/type checks.

### Issue: Reimplementing the Function (HIGH)

```python
# BAD - just reimplements the logic
@given(st.integers(), st.integers())
def test_reimplements(a, b):
    assert add(a, b) == a + b  # Tests nothing if add() is just a + b
```

**Detection**: Test assertion contains same logic as function under test.

### Issue: Poor Input Coverage (MEDIUM)

```python
# NARROW - misses edge cases
@given(st.integers(min_value=1, max_value=10))
def test_narrow_range(x):
    assert compute(x) >= 0  # What about 0? Negatives? Large values?

# MISSING - no edge case examples
@given(st.lists(st.integers()))
def test_no_explicit_edges(xs):
    # Should include @example([]) @example([1]) etc.
    assert len(sort(xs)) == len(xs)
```

### Issue: Missing Stronger Properties (MEDIUM)

```python
# EXISTS - but could be stronger
@given(st.lists(st.integers()))
def test_sort_length(xs):
    assert len(sort(xs)) == len(xs)
# MISSING: ordering property, element preservation
```

### Issue: Poor Settings (LOW)

```python
# TOO FEW - may miss bugs
@settings(max_examples=5)
def test_few_examples(x): ...

# NO DEADLINE - may hang in CI
@given(expensive_strategy())
def test_no_deadline(x): ...  # Could timeout
```

## Review Process

### 1. Locate Property-Based Tests

Search using library-specific patterns:

**Python/Hypothesis:**
```bash
rg "@given\(" --type py
rg "from hypothesis import" --type py
```

**JavaScript/fast-check:**
```bash
rg "fc\.(assert|property)" --type js --type ts
```

**Rust/proptest:**
```bash
rg "proptest!" --type rust
```

### 2. Analyze Each Test

Check for issues above, starting with critical then high severity.

### 3. Evaluate Shrinking Quality

Will tests shrink to minimal counterexamples? Complex strategies may produce hard-to-debug failures.

### 4. Check for Flakiness Potential

- Non-determinism in code under test
- Time-dependent assertions
- Global state dependencies
- Floating point comparisons without tolerance

### 5. Suggest Stronger Properties

Compare against property catalog - are stronger properties available but not tested?

## Test Health Score

| Category | Score | What to Check |
|----------|-------|---------------|
| Property Strength | X/5 | Roundtrip > Idempotence > Type > No crash |
| Input Coverage | X/5 | Edge cases, strategy breadth |
| Assertions | X/5 | Meaningful, not tautological |
| Settings | X/5 | Appropriate for context |

## Mutation Testing Verification

Suggest specific mutations to verify tests catch bugs:

```
To verify test_sort catches bugs:

1. Return input unchanged: `return xs`
   - Should fail: test_ordering

2. Drop last element: `return sorted(xs)[:-1]`
   - Should fail: test_length_preserved

3. Reverse order: `return sorted(xs, reverse=True)`
   - Should fail: test_ordering
```

## Quality Checklist

For each test, verify:
- [ ] Not tautological (assertion doesn't compare same expression)
- [ ] Strong assertion (not just "no crash")
- [ ] Not vacuous (inputs not over-filtered)
- [ ] Good coverage (edge cases via `@example`)
- [ ] No reimplementation of function logic
- [ ] Appropriate settings for context
- [ ] Good shrinking potential
- [ ] Deterministic (no flakiness risk)

## Red Flags

- **Marking tautologies as "fine"**: `assert x == x` is NEVER a valid test
- **Accepting "no crash" as sufficient**: Always push for stronger properties
- **Ignoring vacuous tests**: Tests with contradictory `assume()` provide false confidence
- **Not checking for reimplementation**: `assert add(a,b) == a + b` tests nothing if that's how `add` is implemented
