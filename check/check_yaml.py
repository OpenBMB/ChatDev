"""Lightweight schema validation leveraging typed config loaders."""

import argparse
from pathlib import Path
from typing import Any, List, Optional

from entity.configs import ConfigError, DesignConfig
from utils.io_utils import read_yaml


def validate_design(data: Any, set_defaults: bool = True, fn_module_ref: Optional[str] = None) -> List[str]:
    """Validate raw YAML data using the typed config loader.
    
    Note: This function validates schema structure only, without resolving
    environment variable placeholders like ${VAR}. This allows workflows to
    be saved even when environment variables are not yet configured - they
    will be resolved at runtime.
    """
    try:
        if not isinstance(data, dict):
            raise ConfigError("YAML root must be a mapping", path="root")
        # Use DesignConfig.from_dict directly to skip placeholder resolution
        # Users may configure environment variables at runtime
        DesignConfig.from_dict(data)
        return []
    except ConfigError as exc:
        return [str(exc)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate workflow YAML structure against the typed config loader")
    parser.add_argument("path", help="Path to the workflow YAML file")
    args = parser.parse_args()

    data = read_yaml(args.path)
    errors = validate_design(data)
    if errors:
        print("Design validation failed:")
        for err in errors:
            print(f"- {err}")
        raise SystemExit(1)
    print("Design validation successful.")


if __name__ == "__main__":
    main()
