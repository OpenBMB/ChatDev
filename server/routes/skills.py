import json
import asyncio
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from runtime.node.agent.skills.manager import (
    AgentSkillManager,
    BUNDLED_SKILLS_ROOT,
    WORKSPACE_SKILLS_ROOT,
)
from runtime.node.agent.tool.tool_manager import ToolManager
from server.models import ClawHubInstallRequest

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "tools" / "clawhub_featured_skills.json"
MCP_PRESETS_PATH = REPO_ROOT / "tools" / "mcp_featured_presets.json"
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_clawhub_skills.py"


def load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        raise HTTPException(status_code=404, detail="ClawHub starter manifest not found")
    with MANIFEST_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_mcp_presets() -> dict:
    if not MCP_PRESETS_PATH.is_file():
        return {"presets": []}
    with MCP_PRESETS_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def probe_mcp_endpoint(server_url: str, *, timeout: float = 0.6) -> dict:
    try:
        parsed = urlparse(server_url)
        host = parsed.hostname
        port = parsed.port
        if not host:
            return {"online": False, "reason": "missing_host"}
        if port is None:
            port = 443 if parsed.scheme == "https" else 80
        with socket.create_connection((host, port), timeout=timeout):
            return {"online": True, "reason": "reachable"}
    except Exception as exc:
        return {"online": False, "reason": exc.__class__.__name__}


def probe_mcp_protocol(server_url: str, *, timeout: float = 1.5) -> dict:
    manager = ToolManager()
    try:
        tools = asyncio.run(
            manager._fetch_mcp_tools_http(
                server_url,
                timeout=timeout,
                attempts=1,
            )
        )
        return {
            "protocol_ready": True,
            "tool_count": len(tools),
            "protocol_reason": "list_tools_ok",
        }
    except Exception as exc:
        return {
            "protocol_ready": False,
            "tool_count": 0,
            "protocol_reason": exc.__class__.__name__,
        }


def list_discovered_skills() -> list[dict]:
    manager = AgentSkillManager()
    skills = manager.discover()
    return [
        {
            "name": skill.name,
            "description": skill.description,
            "path": str(skill.skill_file),
            "source": _detect_skill_source(skill.skill_file),
        }
        for skill in sorted(skills, key=lambda item: item.name.lower())
    ]


def _detect_skill_source(skill_file: Path) -> str:
    resolved = skill_file.resolve()
    try:
        resolved.relative_to(WORKSPACE_SKILLS_ROOT)
        return "workspace"
    except ValueError:
        pass
    try:
        resolved.relative_to(BUNDLED_SKILLS_ROOT)
        return "bundled"
    except ValueError:
        return "unknown"


@router.get("/api/skills/clawhub/packs")
def get_clawhub_packs():
    manifest = load_manifest()
    mcp_presets = load_mcp_presets()
    preset_lookup = {
        str(item.get("id")): item
        for item in mcp_presets.get("presets", [])
        if isinstance(item, dict) and item.get("id")
    }
    packs = []
    for pack in manifest.get("packs", []):
        if not isinstance(pack, dict):
            continue
        recommended_ids = [
            str(item).strip()
            for item in pack.get("recommended_mcp_presets", [])
            if str(item).strip()
        ]
        enriched_pack = dict(pack)
        enriched_pack["recommended_mcp_details"] = [
            preset_lookup[item]
            for item in recommended_ids
            if item in preset_lookup
        ]
        packs.append(enriched_pack)
    return {
        "success": True,
        "source": manifest.get("source"),
        "version": manifest.get("version"),
        "notes": manifest.get("notes", []),
        "packs": packs,
        "mcp_presets": mcp_presets.get("presets", []),
        "installed_skills": list_discovered_skills(),
        "clawhub_available": bool(shutil_which("clawhub")),
    }


@router.get("/api/skills/mcp/status")
def get_mcp_preset_status():
    mcp_presets = load_mcp_presets()
    statuses = []
    for preset in mcp_presets.get("presets", []):
        if not isinstance(preset, dict):
            continue
        server = str(preset.get("server") or "").strip()
        probe = probe_mcp_endpoint(server) if server else {"online": False, "reason": "missing_server"}
        protocol = (
            probe_mcp_protocol(server)
            if server and probe.get("online")
            else {"protocol_ready": False, "tool_count": 0, "protocol_reason": "not_reachable"}
        )
        statuses.append(
            {
                "id": str(preset.get("id") or ""),
                "server": server,
                "online": bool(probe.get("online")),
                "reason": str(probe.get("reason") or ""),
                "protocol_ready": bool(protocol.get("protocol_ready")),
                "tool_count": int(protocol.get("tool_count") or 0),
                "protocol_reason": str(protocol.get("protocol_reason") or ""),
            }
        )
    return {
        "success": True,
        "statuses": statuses,
    }


def shutil_which(command: str) -> str | None:
    from shutil import which

    return which(command)


@router.post("/api/skills/clawhub/install")
def install_clawhub_skills(payload: ClawHubInstallRequest):
    if not INSTALL_SCRIPT.is_file():
        raise HTTPException(status_code=404, detail="ClawHub installer script not found")

    packs = [item.strip() for item in (payload.packs or []) if isinstance(item, str) and item.strip()]
    skills = [item.strip() for item in (payload.skills or []) if isinstance(item, str) and item.strip()]

    command = [sys.executable, str(INSTALL_SCRIPT)]
    for pack in packs:
        command.extend(["--pack", pack])
    for skill in skills:
        command.extend(["--skill", skill])
    if payload.dry_run:
        command.append("--dry-run")

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    output = "\n".join(part for part in [stdout, stderr] if part).strip()

    response = {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "command": command,
        "dry_run": payload.dry_run,
        "output": output,
        "installed_skills": list_discovered_skills(),
    }

    if result.returncode != 0 and not payload.dry_run:
        raise HTTPException(status_code=400, detail=response)

    return response
