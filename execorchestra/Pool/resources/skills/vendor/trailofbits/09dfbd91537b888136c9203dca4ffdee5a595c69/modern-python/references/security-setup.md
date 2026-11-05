# Security Setup

Security tooling for Python projects: pre-commit hooks, CI auditing, and dependency scanning.

## Tool Installation

Install these tools before running the quick setup commands below.

### prek (pre-commit runner)

```bash
# Homebrew (recommended)
brew install prek

# Cargo
cargo install prek

# Standalone installer
curl --proto '=https' --tlsv1.2 -LsSf https://github.com/j178/prek/releases/latest/download/prek-installer.sh | sh
```

### Security tools

Pre-commit hooks auto-install tools when run via prek. For manual CLI usage:

```bash
# Homebrew (macOS/Linux)
brew install actionlint shellcheck

# Python tools via uv
uv tool install detect-secrets
uv tool install zizmor
```

Alternative installation methods:

- **actionlint**: `go install github.com/rhysd/actionlint/cmd/actionlint@latest`
- **zizmor**: `cargo install zizmor`
- **detect-secrets**: `pipx install detect-secrets`

## Quick Setup

```bash
# 1. Install security hooks
prek install

# 2. Initialize secrets baseline
detect-secrets scan > .secrets.baseline

# 3. Audit existing workflows
actionlint .github/workflows/
zizmor .github/workflows/
```

See [templates/pre-commit-config.yaml](../templates/pre-commit-config.yaml) for a complete hook configuration.

## Tool Matrix

| Tool | Runs | Catches |
|------|------|---------|
| **shellcheck** | pre-commit | Shell script bugs, quoting issues |
| **detect-secrets** | pre-commit | Leaked API keys, passwords, tokens |
| **actionlint** | pre-commit, CI | Workflow syntax errors, invalid refs |
| **zizmor** | pre-commit, CI | Workflow security issues, excessive permissions |
| **pip-audit** | CI, manual | Known CVEs in dependencies |
| **Dependabot** | scheduled | Outdated dependencies with vulnerabilities |

## Pre-commit Hooks

These run locally before each commit via prek.

### shellcheck - Shell Script Linting

Catches common shell scripting errors: unquoted variables, undefined variables, deprecated syntax.

```yaml
# In .pre-commit-config.yaml
- repo: https://github.com/koalaman/shellcheck-precommit
  rev: <latest>  # https://github.com/koalaman/shellcheck-precommit/tags
  hooks:
    - id: shellcheck
      args: [--severity=error]  # Start strict, adjust if needed
```

Common findings:
- `SC2086`: Unquoted variable expansion (word splitting risk)
- `SC2046`: Unquoted command substitution
- `SC2155`: Declare and assign separately to avoid masking return values

### detect-secrets - Secret Detection

Prevents accidentally committing API keys, passwords, and tokens.

```yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: <latest>  # https://github.com/Yelp/detect-secrets/releases
  hooks:
    - id: detect-secrets
      args: [--baseline, .secrets.baseline]
```

**First-time setup:**

```bash
# Generate baseline of existing "secrets" (false positives to ignore)
detect-secrets scan > .secrets.baseline

# Review the baseline - ensure no real secrets
cat .secrets.baseline

# Commit the baseline
git add .secrets.baseline
```

**When hook fails:**

```bash
# View the finding (non-interactive)
detect-secrets audit --report .secrets.baseline
```

If false positive: update baseline with `detect-secrets scan --update .secrets.baseline`
If real secret: remove from code and rotate the credential.

## CI Security

These run in GitHub Actions on every push/PR.

### actionlint - Workflow Syntax Validation

Catches syntax errors, invalid action references, and type mismatches before they fail in CI.

```yaml
- repo: https://github.com/rhysd/actionlint
  rev: <latest>  # https://github.com/rhysd/actionlint/releases
  hooks:
    - id: actionlint
```

Run manually:

```bash
actionlint .github/workflows/
```

Common findings:
- Invalid event triggers
- Undefined workflow inputs
- Shell syntax errors in `run:` blocks
- Invalid action version references

### zizmor - Workflow Security Audit

Finds security issues in GitHub Actions workflows: excessive permissions, injection risks, untrusted inputs.

```yaml
- repo: https://github.com/zizmorcore/zizmor-pre-commit
  rev: <latest>  # https://github.com/zizmorcore/zizmor-pre-commit/releases
  hooks:
    - id: zizmor
      args: [--persona=regular, --min-severity=medium, --min-confidence=medium]
```

Run manually:

```bash
zizmor .github/workflows/
```

**Fixing `excessive-permissions`:**

By default, workflows get `write` access to everything. Lock down with explicit permissions:

```yaml
# Read-only workflows (lint, test, audit)
permissions:
  contents: read

# Workflows that push or create releases
permissions:
  contents: write

# Workflows that comment on PRs
permissions:
  contents: read
  pull-requests: write
```

Common findings:
- `excessive-permissions`: No `permissions:` block
- `template-injection`: Using `${{ github.event.* }}` unsafely
- `unpinned-action`: Actions not pinned to SHA
- `dangerous-triggers`: `pull_request_target` with checkout

## Dependency Security

### pip-audit - Vulnerability Scanning

Checks installed packages against the Python Advisory Database (PyPA) for known CVEs.

**Setup:**

```toml
# pyproject.toml
[dependency-groups]
audit = ["pip-audit"]
```

**Usage:**

```bash
# Audit current environment
uv run pip-audit

# Audit without installing (faster for CI)
uv run pip-audit .

# Fix automatically (upgrades vulnerable packages)
uv run pip-audit --fix
```

**In CI:**

```yaml
- name: Security audit
  run: uv run pip-audit .
```

**When vulnerabilities found:**

1. Check if the CVE affects your usage (many are in unused code paths)
2. Update the package: `uv add <package>@latest`
3. If no fix available: evaluate risk, consider alternatives, or add to ignore list

### Dependabot - Automated Updates

Automatically creates PRs for outdated dependencies.

Copy [templates/dependabot.yml](../templates/dependabot.yml) to `.github/dependabot.yml`.

**How pip-audit and Dependabot work together:**

| Tool | Trigger | Scope |
|------|---------|-------|
| pip-audit | Every CI run | Known CVEs in current deps |
| Dependabot | Weekly schedule | All outdated deps, security + non-security |

- **pip-audit** catches: "You have a vulnerable version right now"
- **Dependabot** prevents: "You'll fall behind and accumulate vulnerabilities"

The 7-day cooldown protects against attackers publishing malicious updates and hoping for quick adoption before detection.

See [dependabot.md](./dependabot.md) for advanced configuration.

See [prek.md](./prek.md) for complete pre-commit hook configuration including security hooks.
