#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "tools" / "clawhub_featured_skills.json"
WORKSPACE_SKILLS_DIR = REPO_ROOT / "skills"


def load_manifest() -> dict:
    with MANIFEST_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def flatten_pack_skills(manifest: dict, pack_ids: list[str]) -> list[str]:
    packs = manifest.get("packs", [])
    indexed = {pack.get("id"): pack for pack in packs}
    selected: list[str] = []
    seen: set[str] = set()
    for pack_id in pack_ids:
        pack = indexed.get(pack_id)
        if not pack:
            raise SystemExit(f"Unknown pack: {pack_id}")
        for skill in pack.get("skills", []):
            if skill not in seen:
                seen.add(skill)
                selected.append(skill)
    return selected


def list_packs(manifest: dict) -> int:
    print("MovieDev ClawHub starter packs")
    for pack in manifest.get("packs", []):
        print(f"- {pack['id']}: {pack.get('title', pack['id'])}")
        print(f"  {pack.get('description', '')}")
        print(f"  skills: {len(pack.get('skills', []))}")
    return 0


def ensure_clawhub(*, allow_missing: bool = False) -> str:
    clawhub = shutil.which("clawhub")
    if clawhub:
        return clawhub
    if allow_missing:
        return "clawhub"
    raise SystemExit(
        "找不到 `clawhub` 命令。请先安装 OpenClaw / ClawHub CLI，再执行本脚本。"
    )


def install_skills(clawhub_bin: str, skills: list[str], dry_run: bool) -> int:
    WORKSPACE_SKILLS_DIR.mkdir(exist_ok=True)
    print(f"Workspace skills directory: {WORKSPACE_SKILLS_DIR}")
    print(f"Installing {len(skills)} skills")
    exit_code = 0

    for skill in skills:
        command = [clawhub_bin, "install", skill]
        print(f"$ {' '.join(command)}")
        if dry_run:
            continue
        result = subprocess.run(command, cwd=REPO_ROOT)
        if result.returncode != 0:
            exit_code = result.returncode
            print(f"[warn] install failed: {skill}", file=sys.stderr)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install curated ClawHub starter skills into the MovieDev workspace."
    )
    parser.add_argument(
        "--list-packs",
        action="store_true",
        help="List available curated starter packs and exit.",
    )
    parser.add_argument(
        "--pack",
        action="append",
        default=[],
        help="Pack id to install. Can be repeated. Defaults to 'starter'.",
    )
    parser.add_argument(
        "--skill",
        action="append",
        default=[],
        help="Install an additional explicit skill slug. Can be repeated.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print install commands without executing them.",
    )
    args = parser.parse_args()

    manifest = load_manifest()
    if args.list_packs:
        return list_packs(manifest)

    pack_ids = args.pack or ["starter"]
    selected = flatten_pack_skills(manifest, pack_ids)
    for skill in args.skill:
        normalized = str(skill or "").strip()
        if normalized and normalized not in selected:
            selected.append(normalized)

    if not selected:
        print("No skills selected.")
        return 0

    clawhub_bin = ensure_clawhub(allow_missing=args.dry_run)
    return install_skills(clawhub_bin, selected, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
