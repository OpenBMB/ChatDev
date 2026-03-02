# REST API Caller Examples

## Example 1: Public GET returning JSON

Use this for the demo joke API:

```python
import requests

url = "https://official-joke-api.appspot.com/random_joke"
response = requests.get(url, timeout=30)
response.raise_for_status()
payload = response.json()

print(f"Setup: {payload['setup']}")
print(f"Punchline: {payload['punchline']}")
```

## Example 2: GET with bearer token from environment

```python
import os
import requests

token = os.environ["MY_API_TOKEN"]
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("https://api.example.com/items", headers=headers, timeout=30)
response.raise_for_status()
print(response.text)
```

## Example 3: GET with query parameters

```python
import requests

params = {"q": "agent skills", "limit": 3}
response = requests.get("https://api.example.com/search", params=params, timeout=30)
response.raise_for_status()
print(response.json())
```
