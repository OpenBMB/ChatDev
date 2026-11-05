#!/usr/bin/env python3
"""Verify and seal the local ``sgar-runtime:rc1`` image into a lock file."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOOLS = PROJECT_ROOT / "Pool" / "resources" / "json" / "tools.json"
DEFAULT_DOCKERFILE = PROJECT_ROOT / "sgar_mvp" / "docker" / "Dockerfile.runtime"
DEFAULT_OUTPUT = PROJECT_ROOT / "sgar_mvp" / "config" / "rc1_runtime_lock.json"


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def run(command: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def required_runtime_inventory(tools: list[dict[str, Any]]) -> dict[str, Any]:
    python_packages: dict[str, str] = {}
    node_packages: dict[str, str] = {}
    commands: set[str] = set()
    for tool in tools:
        requirements = tool.get("runtime_requirements") or {}
        if requirements.get("runtime_profile") != "sgar-runtime":
            continue
        commands.update(str(item) for item in requirements.get("commands") or [])
        for item in requirements.get("python_packages") or []:
            if isinstance(item, dict) and item.get("name"):
                python_packages[str(item["name"])] = str(item.get("version") or "")
        for item in requirements.get("node_packages") or []:
            if isinstance(item, dict) and item.get("name"):
                node_packages[str(item["name"])] = str(item.get("version") or "")
    return {
        "python_packages": dict(sorted(python_packages.items())),
        "node_packages": dict(sorted(node_packages.items())),
        "commands": sorted(commands),
    }


def inspect_image(image: str) -> dict[str, Any]:
    proc = run(["docker", "image", "inspect", image])
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"image not found: {image}").strip())
    payload = json.loads(proc.stdout)
    if not payload:
        raise RuntimeError(f"Docker returned no inspection data for {image}")
    return payload[0]


def verify_container_inventory(image: str, required: dict[str, Any]) -> dict[str, Any]:
    code = r'''
import importlib.metadata, json, pathlib, shutil, sys
required=json.loads(sys.argv[1])
packages={}
missing_packages=[]
for name, expected in required["python_packages"].items():
    try: packages[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: missing_packages.append(name)
commands={name:shutil.which(name) for name in required["commands"]}
locks={}
for path in ("/opt/sgar-python-lock.txt","/opt/sgar-node-lock.json","/opt/sgar-language-lock.txt"):
    p=pathlib.Path(path)
    locks[path]=p.read_text(encoding="utf-8") if p.is_file() else ""
print(json.dumps({"python_version":sys.version.split()[0],"python_packages":packages,
 "missing_python_packages":missing_packages,"commands":commands,"locks":locks}))
'''
    proc = run(
        ["docker", "run", "--rm", image, "python", "-c", code, json.dumps(required)],
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "runtime inventory failed").strip())
    inventory = json.loads(proc.stdout)
    missing_commands = sorted(
        command for command, path in inventory["commands"].items() if not path
    )
    if inventory["missing_python_packages"] or missing_commands:
        raise RuntimeError(
            "RC1 image dependency verification failed: "
            f"missing_python={inventory['missing_python_packages']}, "
            f"missing_commands={missing_commands}"
        )
    node_lock = json.loads(inventory["locks"]["/opt/sgar-node-lock.json"] or "{}")
    dependencies = node_lock.get("dependencies") or {}
    missing_node = sorted(
        name for name in required["node_packages"] if name not in dependencies
    )
    if missing_node:
        raise RuntimeError(f"RC1 image is missing Node packages: {missing_node}")
    inventory["node_packages"] = {
        name: (dependencies.get(name) or {}).get("version")
        for name in sorted(required["node_packages"])
    }
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="sgar-runtime:rc1")
    parser.add_argument("--tools", type=Path, default=DEFAULT_TOOLS)
    parser.add_argument("--dockerfile", type=Path, default=DEFAULT_DOCKERFILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    tools = json.loads(args.tools.read_text(encoding="utf-8-sig"))
    required = required_runtime_inventory(tools)
    inspected = inspect_image(args.image)
    inventory = verify_container_inventory(args.image, required)
    locks = inventory.pop("locks")
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "image": args.image,
        "image_id": str(inspected.get("Id") or ""),
        "repo_digests": list(inspected.get("RepoDigests") or []),
        "dockerfile_sha256": sha256(args.dockerfile.read_bytes()),
        "required_inventory": required,
        "verified_inventory": inventory,
        "lock_hashes": {
            path: sha256(text.encode("utf-8")) for path, text in sorted(locks.items())
        },
        "language_lock": locks.get("/opt/sgar-language-lock.txt", ""),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("image", "image_id", "repo_digests")}, indent=2))
    print(f"Verified Python packages: {len(required['python_packages'])}")
    print(f"Verified Node packages: {len(required['node_packages'])}")
    print(f"Verified commands: {len(required['commands'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
