# Input Strategy Reference

## Python/Hypothesis

| Type | Strategy |
|------|----------|
| `int` | `st.integers()` |
| `float` | `st.floats(allow_nan=False)` |
| `str` | `st.text()` |
| `bytes` | `st.binary()` |
| `bool` | `st.booleans()` |
| `list[T]` | `st.lists(strategy_for_T)` |
| `dict[K, V]` | `st.dictionaries(key_strategy, value_strategy)` |
| `set[T]` | `st.frozensets(strategy_for_T)` |
| `tuple[T, ...]` | `st.tuples(strategy_for_T, ...)` |
| `Optional[T]` | `st.none() \| strategy_for_T` |
| `Union[A, B]` | `st.one_of(strategy_a, strategy_b)` |
| Custom class | `st.builds(ClassName, field1=..., field2=...)` |
| Enum | `st.sampled_from(EnumClass)` |
| Constrained int | `st.integers(min_value=0, max_value=100)` |
| Email | `st.emails()` |
| UUID | `st.uuids()` |
| DateTime | `st.datetimes()` |
| Regex match | `st.from_regex(r"pattern")` |

### Composite Strategies

For complex types, use `@st.composite`:

```python
@st.composite
def valid_users(draw):
    name = draw(st.text(min_size=1, max_size=50))
    age = draw(st.integers(min_value=0, max_value=150))
    email = draw(st.emails())
    return User(name=name, age=age, email=email)
```

## JavaScript/fast-check

| Type | Strategy |
|------|----------|
| number | `fc.integer()` or `fc.float()` |
| string | `fc.string()` |
| boolean | `fc.boolean()` |
| array | `fc.array(itemArb)` |
| object | `fc.record({...})` |
| optional | `fc.option(arb)` |

### Example

```typescript
const userArb = fc.record({
  name: fc.string({ minLength: 1, maxLength: 50 }),
  age: fc.integer({ min: 0, max: 150 }),
  email: fc.emailAddress(),
});
```

## Rust/proptest

| Type | Strategy |
|------|----------|
| i32, u64, etc | `any::<i32>()` |
| String | `any::<String>()` or `"[a-z]+"` (regex) |
| Vec<T> | `prop::collection::vec(strategy, size)` |
| Option<T> | `prop::option::of(strategy)` |

### Example

```rust
proptest! {
    #[test]
    fn test_roundtrip(s in "[a-z]{1,20}") {
        let encoded = encode(&s);
        let decoded = decode(&encoded)?;
        prop_assert_eq!(s, decoded);
    }
}
```

## Go/rapid

```go
rapid.Check(t, func(t *rapid.T) {
    s := rapid.String().Draw(t, "s")
    n := rapid.IntRange(0, 100).Draw(t, "n")
    // test with s and n
})
```

## Best Practices

1. **Constrain early**: Build constraints into strategy, not `assume()`
   ```python
   # GOOD
   st.integers(min_value=1, max_value=100)

   # BAD
   st.integers().filter(lambda x: 1 <= x <= 100)
   ```

2. **Size limits**: Use `max_size` to prevent slow tests
   ```python
   st.lists(st.integers(), max_size=100)
   st.text(max_size=1000)
   ```

3. **Realistic data**: Make strategies match real-world constraints
   ```python
   # Real user ages, not arbitrary integers
   st.integers(min_value=0, max_value=150)
   ```

4. **Reuse strategies**: Define once, use across tests
   ```python
   valid_users = st.builds(User, ...)

   @given(valid_users)
   def test_one(user): ...

   @given(valid_users)
   def test_two(user): ...
   ```
