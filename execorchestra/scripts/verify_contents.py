"""Verify distributed files without importing framework dependencies."""
from pathlib import Path
import hashlib
import json


def main():
    project = Path(__file__).resolve().parents[1]
    root = project if (project / "SHA256SUMS").is_file() else project.parent
    failures = []
    checked = 0
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            failures.append(relative)
            continue
        checked += 1
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(relative)
    print(json.dumps({"checked": checked, "mismatches": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
