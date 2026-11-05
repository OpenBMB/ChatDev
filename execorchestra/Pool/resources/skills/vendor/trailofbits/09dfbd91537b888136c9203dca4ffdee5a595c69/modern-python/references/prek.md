# prek: Fast Pre-commit Hooks

[prek](https://github.com/j178/prek) is a fast, Rust-native drop-in replacement for pre-commit. It uses the same `.pre-commit-config.yaml` format and is fully compatible with existing configurations.

## Why prek over pre-commit?

| Feature | prek | pre-commit |
|---------|------|------------|
| Speed | ~7x faster hook installation | Slower |
| Dependencies | Single binary, no runtime needed | Requires Python |
| Disk usage | Shared toolchains between hooks | Isolated environments |
| Parallelism | Parallel repo cloning and hook execution | Sequential |
| Python management | Uses uv automatically | Manual Python setup |
| Monorepo support | Built-in workspace mode | Not supported |

**Already using prek:** CPython, Apache Airflow, FastAPI, Ruff, Home Assistant, and [many more](https://github.com/j178/prek#who-is-using-prek).

## Installation

See [security-setup.md](./security-setup.md#tool-installation) for installation options.

## Quick Start

### For Existing pre-commit Users

prek is fully compatible with `.pre-commit-config.yaml`. Just replace commands:

```bash
# Instead of: pre-commit install
prek install

# Instead of: pre-commit run --all-files
prek run --all-files

# Instead of: pre-commit autoupdate
prek auto-update
```

### New Setup

1. Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <latest>  # https://github.com/astral-sh/ruff-pre-commit/releases
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

2. Install and run:

```bash
# Install git hooks
prek install

# Run manually on all files
prek run --all-files

# Run specific hook
prek run ruff
```

## Configuration

For a complete, copy-paste-ready configuration, see [templates/pre-commit-config.yaml](../templates/pre-commit-config.yaml).

### Recommended `.pre-commit-config.yaml`

> **Note:** Versions shown as `<latest>` are placeholders. Always check the linked releases for current stable versions before use.

```yaml
# See https://pre-commit.com for more information
default_language_version:
  python: python3.12

repos:
  # Ruff - linting and formatting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <latest>  # https://github.com/astral-sh/ruff-pre-commit/releases
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # General file checks (prek builtin - faster, no external deps)
  - repo: builtin
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-merge-conflict

  # Security hooks - see security-setup.md for detailed guidance
  # Shell script linting
  - repo: https://github.com/koalaman/shellcheck-precommit
    rev: <latest>  # https://github.com/koalaman/shellcheck-precommit/tags
    hooks:
      - id: shellcheck
        args: [--severity=error]

  # Secret detection
  - repo: https://github.com/Yelp/detect-secrets
    rev: <latest>  # https://github.com/Yelp/detect-secrets/releases
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]

  # GitHub Actions linting
  - repo: https://github.com/rhysd/actionlint
    rev: <latest>  # https://github.com/rhysd/actionlint/releases
    hooks:
      - id: actionlint

  # GitHub Actions security audit
  - repo: https://github.com/zizmorcore/zizmor-pre-commit
    rev: <latest>  # https://github.com/zizmorcore/zizmor-pre-commit/releases
    hooks:
      - id: zizmor
        args: [--persona=regular, --min-severity=medium, --min-confidence=medium]
```

See [security-setup.md](./security-setup.md) for detailed guidance on each security hook.

### Using Built-in Hooks

prek includes Rust-native implementations of common hooks for extra speed:

```yaml
repos:
  - repo: builtin
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-toml
```

## Commands

| Command | Description |
|---------|-------------|
| `prek install` | Install git hooks |
| `prek uninstall` | Remove git hooks |
| `prek run` | Run hooks on staged files |
| `prek run --all-files` | Run on all files |
| `prek run --last-commit` | Run on last commit's files |
| `prek run HOOK [HOOK...]` | Run specific hook(s) |
| `prek run -d src/` | Run on files in directory |
| `prek auto-update` | Update hook versions |
| `prek list` | List configured hooks |
| `prek clean` | Remove cached environments |

## CI Configuration

### GitHub Actions

```yaml
name: Pre-commit
on: [push, pull_request]

jobs:
  prek:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>  # <latest> https://github.com/actions/checkout/releases
      - uses: j178/prek-action@<sha>  # <latest> https://github.com/j178/prek-action/releases
```

Or manually:

```yaml
- name: Install prek
  run: uv tool install prek

- name: Run hooks
  run: prek run --all-files
```

## Makefile Integration

```makefile
.PHONY: hooks hooks-install

hooks:
	prek run --all-files

hooks-install:
	prek install
```

## Migration from pre-commit

1. Install prek: `uv tool install prek`
2. Remove pre-commit: `pip uninstall pre-commit` or `uv tool uninstall pre-commit`
3. Re-install hooks: `prek install`
4. (Optional) Clean old environments: `rm -rf ~/.cache/pre-commit`

Your existing `.pre-commit-config.yaml` works unchanged.

## Best Practices

1. **Use `prek run --all-files` in CI** - Ensures all files are checked, not just changed ones
2. **Pin hook versions** - Use specific `rev` values, not branches
3. **Use `--cooldown-days` for auto-update** - Mitigates supply chain attacks: `prek auto-update --cooldown-days 7`
4. **Prefer built-in hooks** - Use `repo: builtin` for common checks (faster, offline)
5. **Run hooks before commit** - `prek install` sets this up automatically
6. **Initialize detect-secrets baseline** - Run `detect-secrets scan > .secrets.baseline` before first commit
