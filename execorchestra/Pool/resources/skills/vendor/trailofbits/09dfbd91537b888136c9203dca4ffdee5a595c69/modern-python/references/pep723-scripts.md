# PEP 723: Inline Script Metadata

PEP 723 allows embedding dependency metadata directly in Python scripts, eliminating the need for separate `requirements.txt` or `pyproject.toml` files for simple scripts.

## When to Use PEP 723

**Use for:**
- Single-file scripts with external dependencies
- Quick automation scripts
- Utility scripts shared between projects
- Scripts that need to be self-contained

**Don't use for:**
- Multi-file projects (use `pyproject.toml`)
- Reusable packages/libraries
- Projects requiring complex configuration

## Basic Syntax

The metadata block uses TOML format embedded in a special comment:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "rich",
# ]
# ///

import requests
from rich import print

response = requests.get("https://api.example.com/data")
print(response.json())
```

## Running Scripts

```bash
# With uv (recommended)
uv run script.py

# Script handles its own dependencies automatically
./script.py  # If shebang is set
```

## Metadata Fields

### Required Python Version

```python
# /// script
# requires-python = ">=3.11"
# ///
```

### Dependencies

```python
# /// script
# dependencies = [
#     "requests",
#     "click",
#     "rich",
# ]
# ///
```

### Private Package Index

```python
# /// script
# dependencies = ["httpx"]
#
# [tool.uv]
# extra-index-url = ["https://pypi.company.com/simple/"]
# ///
```

## Complete Example

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "rich",
#     "typer",
# ]
# ///

"""Fetch and display API data with nice formatting."""

import httpx
import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer()


@app.command()
def fetch(url: str, format: str = "table"):
    """Fetch data from URL and display it."""
    with httpx.Client() as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()

    if format == "table" and isinstance(data, list):
        table = Table()
        if data:
            for key in data[0].keys():
                table.add_column(key)
            for item in data:
                table.add_row(*[str(v) for v in item.values()])
        console.print(table)
    else:
        console.print_json(data=data)


if __name__ == "__main__":
    app()
```

## Creating Scripts with uv

```bash
# Create new script with metadata
uv init --script myscript.py

# Add dependency to existing script
uv add --script myscript.py requests

# Remove dependency from script
uv remove --script myscript.py requests
```

## Shebang Options

### Basic (requires uv in PATH)

```python
#!/usr/bin/env -S uv run --script
```

### With specific Python version

```python
#!/usr/bin/env -S uv run --python 3.12 --script
```

### Quiet mode (suppress uv output)

```python
#!/usr/bin/env -S uv run --quiet --script
```

## Examples by Use Case

### Data Processing Script

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "openpyxl"]
# ///

import pandas as pd
import sys

df = pd.read_excel(sys.argv[1])
print(df.describe())
```

### Web Scraping Script

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx", "beautifulsoup4", "lxml"]
# ///

import httpx
from bs4 import BeautifulSoup

response = httpx.get("https://example.com")
soup = BeautifulSoup(response.text, "lxml")
print(soup.title.string)
```

### CLI Tool Script

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer", "rich"]
# ///

import typer
from rich import print

app = typer.Typer()

@app.command()
def greet(name: str):
    print(f"[green]Hello, {name}![/green]")

if __name__ == "__main__":
    app()
```

### Async Script

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///

import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        urls = ["https://api1.example.com", "https://api2.example.com"]
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
        for r in responses:
            print(r.status_code)

asyncio.run(main())
```

## Best Practices

1. **Always specify `requires-python`** - Ensures compatibility
2. **Pin major versions for Python** - Use `>=3.11` not `==3.11`
3. **Omit version constraints for dependencies** - Use `uv add --script` to add dependencies; let uv select versions
4. **Keep scripts focused** - One script, one purpose
5. **Add docstring** - Document what the script does
6. **Use type hints** - Improves readability and catches errors

## Limitations

- No support for dependency groups
- No support for editable installs
- No support for local dependencies (use relative imports)
- No lockfile (versions may vary between runs)

For projects needing these features, use a full `pyproject.toml` setup instead.
