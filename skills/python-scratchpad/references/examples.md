# Python Scratchpad Examples

Example: sum a list of numbers

```python
numbers = [14, 27, 31, 8]
print(sum(numbers))
```

Expected structured result with `run_python_script`:

```json
{
  "ok": true,
  "exit_code": 0,
  "stdout": "80\n",
  "stderr": ""
}
```

Example: convert JSON to a sorted compact structure

```python
import json

payload = {"b": 2, "a": 1, "nested": {"z": 3, "x": 2}}
print(json.dumps(payload, sort_keys=True))
```

Example: count words in text

```python
text = "agent skills can trigger targeted workflows"
print(len(text.split()))
```

Example: test a regex

```python
import re

text = "Order IDs: ORD-100, BAD-7, ORD-215"
matches = re.findall(r"ORD-\d+", text)
print(matches)
```
