# Refactoring for Property-Based Testing

Identify code that could be refactored to enable or improve property-based testing.

## Quick Reference

| Pattern | Problem | Solution | Properties Enabled |
|---------|---------|----------|-------------------|
| I/O mixed with logic | Can't test without mocks | Extract pure core | Multiple |
| Encode without decode | No roundtrip possible | Add inverse operation | Roundtrip |
| Hardcoded config | Can't test edge cases | Inject dependencies | Full coverage |
| In-place mutation | Hard to verify before/after | Return new value | Comparison properties |
| String building | Can't verify structure | Structured + render | Roundtrip |
| Implicit invariants | Can't test constraints | Make explicit with validation | Invariant |

## Refactoring Patterns

### 1. Extract Pure Core from Impure Functions (High Impact)

**Pattern**: Functions that mix I/O with logic

```python
# BEFORE - hard to test
def process_order(order_id: str) -> None:
    order = db.fetch(order_id)           # I/O
    discount = calculate_discount(order)  # Pure logic
    total = apply_discount(order, discount)  # Pure logic
    db.save(order_id, total)             # I/O

# AFTER - pure core extracted
def calculate_order_total(order: Order, rules: DiscountRules) -> Decimal:
    """Pure function - easy to property test."""
    discount = calculate_discount(order, rules)
    return apply_discount(order, discount)

def process_order(order_id: str) -> None:
    """Thin I/O wrapper."""
    order = db.fetch(order_id)
    total = calculate_order_total(order, get_discount_rules())
    db.save(order_id, total)
```

**Detection**: `rg "def \w+\(" -A 20 | grep -E "(open\(|db\.|requests\.|fetch|save)"`

### 2. Add Missing Inverse Operations (High Impact)

**Pattern**: One-way operations that should have pairs

```python
# BEFORE - only encode
def encode_message(msg: dict) -> bytes:
    return msgpack.packb(msg)

# AFTER - add decode for roundtrip testing
def encode_message(msg: dict) -> bytes:
    return msgpack.packb(msg)

def decode_message(data: bytes) -> dict:
    return msgpack.unpackb(data)
```

**Detection**: Find encode without decode, serialize without deserialize

### 3. Replace Hardcoded Dependencies (Medium Impact)

**Pattern**: Functions using globals or hardcoded config

```python
# BEFORE
def validate_input(data: str) -> bool:
    return len(data) <= CONFIG.max_length

# AFTER - dependencies injected
def validate_input(data: str, max_length: int) -> bool:
    return len(data) <= max_length
```

**Detection**: `rg "(CONFIG\.|SETTINGS\.|os\.environ)"`

### 4. Return Values Instead of Mutating (Medium Impact)

**Pattern**: Methods that mutate in place

```python
# BEFORE
def sort_tasks(tasks: list[Task]) -> None:
    tasks.sort(key=lambda t: t.priority)

# AFTER - returns new list
def sorted_tasks(tasks: list[Task]) -> list[Task]:
    return sorted(tasks, key=lambda t: t.priority)
```

**Detection**: `rg "-> None:" -A 10 | grep -E "\.(sort|append|extend)"`

### 5. Convert String Building to Structured + Render (Medium Impact)

**Pattern**: Manual string concatenation

```python
# BEFORE
def build_query(table: str, filters: dict) -> str:
    q = f"SELECT * FROM {table}"
    if filters:
        q += " WHERE " + " AND ".join(...)
    return q

# AFTER - structured representation
@dataclass
class Query:
    table: str
    filters: dict

def render_query(q: Query) -> str: ...
def parse_query(sql: str) -> Query: ...  # Add inverse!
```

### 6. Add Validators/Generators for Predicates (Lower Impact)

**Pattern**: `is_valid()` exists but no way to generate valid inputs

```python
# BEFORE
def is_valid_email(s: str) -> bool:
    return EMAIL_REGEX.match(s) is not None

# AFTER - add generator
@st.composite
def valid_emails(draw):
    local = draw(st.from_regex(r'[a-z][a-z0-9]{1,20}'))
    domain = draw(st.sampled_from(['gmail.com', 'example.com']))
    return f"{local}@{domain}"
```

**Detection**: `rg "def is_\w+\(" --type py`

### 7. Make Implicit Invariants Explicit (Lower Impact)

**Pattern**: Constraints in comments but not enforced

```python
# BEFORE - constraint only in docstring
def allocate_buffer(size: int) -> bytes:
    """Size must be positive and <= 1MB."""
    return bytes(size)

# AFTER - enforced
MAX_BUFFER_SIZE = 1024 * 1024

def allocate_buffer(size: int) -> bytes:
    if not (0 < size <= MAX_BUFFER_SIZE):
        raise ValueError(f"size must be in (0, {MAX_BUFFER_SIZE}]")
    return bytes(size)
```

**Detection**: `rg "(must be|should be|always|never)" --type py`

## Evaluation Criteria

For each refactoring opportunity:

| Factor | Questions |
|--------|-----------|
| Properties enabled | What tests become possible? Roundtrip > Idempotence > No crash |
| Effort | Low/Medium/High - how much code change? |
| Risk | Breaking changes? API impact? |
| Backwards compatibility | Can old callers still work? |

## Prioritization

1. Strength of properties enabled (roundtrip > idempotence > no crash)
2. Effort required (prefer low-effort wins)
3. Risk level (prefer safe changes)

## Red Flags

- **Breaking the API without warning**: Flag breaking changes clearly and offer backwards-compatible alternatives
- **Over-engineering**: Not every function needs to be perfectly testable - prioritize high-value code
- **Ignoring existing tests**: Run existing tests after refactoring to verify behavior unchanged
- **Missing the forest for the trees**: If a module needs wholesale restructuring, say so rather than suggesting 20 small changes
- **Not considering effort vs value**: A complex refactoring enabling only "no crash" isn't worth it
