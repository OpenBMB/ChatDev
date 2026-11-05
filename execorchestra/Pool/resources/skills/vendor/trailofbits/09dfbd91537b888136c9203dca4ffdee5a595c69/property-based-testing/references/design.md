# Property-Driven Development

Design features by defining properties upfront as executable specifications, before implementation.

## When to Use

- Designing a new feature from scratch
- Building something with clear algebraic properties (serialization, validation, transformations)
- Complex domain where edge cases are likely
- User wants to think through requirements rigorously before coding

## Process

### Phase 1: Understand the Feature

Gather information:
- **Purpose**: What problem does this solve?
- **Inputs**: What data does it accept? What makes inputs valid?
- **Outputs**: What does it produce? What guarantees?
- **Constraints**: What must always be true?
- **Edge cases**: Boundary conditions?
- **Relationships**: Inverse operations? Compositions?

### Phase 2: Identify Candidate Properties

Work through these discovery questions:

| Question | Property Type | Example |
|----------|---------------|---------|
| Does it have an inverse operation? | Roundtrip | `decode(encode(x)) == x` |
| Is applying it twice the same as once? | Idempotence | `f(f(x)) == f(x)` |
| What quantities are preserved? | Invariants | Length, sum, count |
| Is order of arguments irrelevant? | Commutativity | `f(a, b) == f(b, a)` |
| Can operations be regrouped? | Associativity | `f(f(a,b), c) == f(a, f(b,c))` |
| Is there a neutral element? | Identity | `f(x, 0) == x` |
| Is there an oracle/reference impl? | Oracle | `new(x) == old(x)` |
| Can output be easily verified? | Hard/Easy | `is_sorted(sort(x))` |

### Phase 3: Define Input Domain

Specify valid inputs as strategies. The strategy IS the specification.

**Key principle**: Build constraints INTO the strategy, not via `assume()`.

```python
@st.composite
def valid_registration_requests(draw):
    """Generate valid registration requests - this documents the domain."""
    username = draw(st.text(
        min_size=3,
        max_size=20,
        alphabet=st.characters(whitelist_categories=('L', 'N'))
    ))
    email = draw(st.emails())
    password = draw(st.text(min_size=8, max_size=100))
    age = draw(st.integers(min_value=13, max_value=150))

    return RegistrationRequest(
        username=username,
        email=email,
        password=password,
        age=age
    )
```

### Phase 4: Write Property Tests (Before Implementation)

Create tests that will fail initially:

```python
class TestFeatureSpec:
    """Property-based specification - should FAIL until implemented."""

    @given(valid_inputs())
    def test_core_property(self, x):
        """[What this guarantees]."""
        result = feature(x)
        assert property_holds(result)
```

### Phase 5: Iterate on Design

Properties reveal design questions:
- "What about deleted users?"
- "Case-sensitive?"
- "Which algorithm?"
- "Stable sort or not?"

Surface these questions early, before implementation.

## Property Strength Hierarchy

Build properties incrementally from weak to strong:

### Level 1: Basic (Weak)
```python
@given(valid_inputs())
def test_no_crash(x):
    process(x)  # Just don't crash
```

### Level 2: Type Preservation
```python
@given(valid_inputs())
def test_returns_type(x):
    assert isinstance(process(x), ExpectedType)
```

### Level 3: Invariants
```python
@given(valid_inputs())
def test_invariant(x):
    result = process(x)
    assert invariant_holds(result)
```

### Level 4: Full Specification (Strong)
```python
@given(valid_inputs())
def test_complete(x):
    result = process(x)
    assert satisfies_all_requirements(result)
```

## Strategy Design Principles

### 1. Build Constraints Into Strategy
```python
# GOOD - constraints in strategy
@given(st.integers(min_value=1, max_value=100))
def test_with_valid_range(x): ...

# BAD - constraints via assume
@given(st.integers())
def test_with_assume(x):
    assume(1 <= x <= 100)  # High rejection rate
```

### 2. Match Real-World Constraints
```python
valid_users = st.builds(
    User,
    name=st.text(min_size=1, max_size=100),
    age=st.integers(min_value=0, max_value=150),
    email=st.emails(),
)
```

### 3. Include Edge Cases Explicitly
```python
@given(valid_lists())
@example([])           # Empty
@example([1])          # Single element
@example([1, 1, 1])    # Duplicates
def test_with_edges(xs): ...
```

## Common Design Questions Raised

Properties often reveal design gaps:

| Property Attempt | Question Raised |
|------------------|-----------------|
| Roundtrip for users | What about deleted/deactivated users? |
| Duplicate rejection | Case-sensitive? Unicode normalization? |
| Password storage | Which algorithm? Salted? Configurable? |
| Ordering guarantee | Stable sort? Tie-breaking rules? |

## Red Flags

- **Writing tautological properties**: Don't reimplement the function logic in the test
  ```python
  # BAD - tests nothing
  assert add(a, b) == a + b

  # GOOD - tests algebraic properties
  assert add(a, 0) == a  # identity
  assert add(a, b) == add(b, a)  # commutativity
  ```
- **Starting too strong**: Build from weak to strong properties
- **Ignoring design questions**: Properties that feel awkward often reveal design gaps
- **Overly complex strategies**: If your input strategy is 50 lines, the domain model might need simplification
- **Not involving the user**: Design questions should be discussed, not assumed

## Checklist

- [ ] Properties are not tautological
- [ ] At least one strong property defined
- [ ] Input strategy documents valid inputs
- [ ] Design questions have been surfaced
- [ ] Tests will actually FAIL without implementation
