"""
Validate All YAML Workflow Configurations

This tool performs strict validation on all YAML workflow configuration files
in the yaml_instance/ directory. It ensures configuration integrity and prevents
runtime errors by catching issues early in the development process.

Purpose:
- Validates YAML syntax and schema compliance for all workflow configurations
- Prevents invalid configurations from causing runtime failures
- Essential for CI/CD pipelines to ensure code quality
- Provides detailed error reporting for debugging

Usage:
    python tools/validate_all_yamls.py
    # or via Makefile:
    make validate-yamls
"""

import sys
import subprocess
from pathlib import Path


def validate_all():
    base_dir = Path("yaml_instance")
    if not base_dir.exists():
        print(f"Directory {base_dir} not found.")
        sys.exit(1)

    # Recursive search for all .yaml files
    files = sorted(list(base_dir.rglob("*.yaml")))

    if not files:
        print("No YAML files found.")
        return

    print(
        f"Found {len(files)} YAML files. Running FULL validation via check.check...\n"
    )

    passed = 0
    failed = 0
    failed_files = []

    for yaml_file in files:
        # Use relative path for cleaner output
        try:
            rel_path = yaml_file.relative_to(Path.cwd())
        except ValueError:
            rel_path = yaml_file

        # NOW we run check.check, which we just patched to have a main()
        # This performs the stricter load_config() validation
        cmd = [sys.executable, "-m", "check.check", "--path", str(yaml_file)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"{rel_path}")
                passed += 1
            else:
                print(f"{rel_path}")
                # Indent error output
                if result.stdout:
                    print("  stdout:", result.stdout.strip().replace("\n", "\n  "))
                # Validation errors usually print to stdout/stderr depending on impl
                # Our new main prints to stdout for success/failure message
                failed += 1
                failed_files.append(str(rel_path))
        except Exception as e:
            print(f"{rel_path} (Execution Failed)")
            print(f"  Error: {e}")
            failed += 1
            failed_files.append(str(rel_path))

    print("\n" + "=" * 40)
    print(f"YAML Validation Summary")
    print("=" * 40)
    print(f"Total Files: {len(files)}")
    print(f"Passed:      {passed}")
    print(f"Failed:      {failed}")

    if failed > 0:
        print("\nFailed Files:")
        for f in failed_files:
            print(f"- {f}")

    # Overall validation status
    print("\n" + "=" * 40)
    print("Overall Validation Status")
    print("=" * 40)

    if failed > 0:
        print("YAML validation: FAILED")
        sys.exit(1)
    else:
        print("All validations passed successfully.")
        sys.exit(0)


if __name__ == "__main__":
    validate_all()
