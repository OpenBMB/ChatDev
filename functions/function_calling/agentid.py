"""AgentID identity verification tools for ChatDev agents.

Provides cryptographic identity verification using the AgentID protocol
(https://getagentid.dev). Enables ChatDev agents to verify each other's
identities before delegating tasks or sharing sensitive data.

Environment variables:
    AGENTID_API_KEY  -- Bearer token for authenticated endpoints (register, connect).
    AGENTID_BASE_URL -- Override the default https://getagentid.dev/api/v1 endpoint.
"""

import json
import os
from typing import Optional

import httpx

_BASE_URL = os.getenv("AGENTID_BASE_URL", "https://getagentid.dev/api/v1").rstrip("/")
_TIMEOUT = 15


def _auth_headers() -> dict:
    key = os.getenv("AGENTID_API_KEY", "")
    if not key:
        raise ValueError(
            "AGENTID_API_KEY environment variable is required. "
            "Get one at https://getagentid.dev"
        )
    return {"Authorization": f"Bearer {key}"}


def verify_agent_identity(agent_id: str) -> str:
    """Verify an AI agent's cryptographic identity via AgentID.

    Use this before trusting another agent with sensitive operations
    like code execution, deployment, or data access. Returns the
    agent's verification status, trust score, certificate validity,
    and capabilities.

    This is a public endpoint -- no API key is required.

    Args:
        agent_id: The AgentID identifier to verify (e.g. "agent_abc123").

    Returns:
        A JSON string with verification results including
        ``verified``, ``trust_score``, ``certificate``, and ``capabilities``.
    """
    try:
        resp = httpx.post(
            f"{_BASE_URL}/agents/verify",
            json={"agent_id": agent_id},
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        data = resp.json()
        if resp.status_code >= 400:
            return json.dumps({"error": data.get("error", f"HTTP {resp.status_code}")})
        return json.dumps(data, indent=2, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def register_agent_identity(
    name: str,
    description: str = "",
    capabilities: str = "",
) -> str:
    """Register a new agent with AgentID and obtain a cryptographic certificate.

    The certificate contains an ECDSA P-256 key pair and a unique
    ``agent_id`` that other agents can use to verify this agent.

    Requires the AGENTID_API_KEY environment variable.

    Args:
        name: Human-readable name for the agent (e.g. "Programmer", "Code Reviewer").
        description: Short description of the agent's purpose.
        capabilities: Comma-separated capability tags (e.g. "coding,review,testing").

    Returns:
        A JSON string with ``agent_id``, ``certificate``, and key material.
    """
    try:
        caps = [c.strip() for c in capabilities.split(",") if c.strip()] if capabilities else []
        resp = httpx.post(
            f"{_BASE_URL}/agents/register",
            json={
                "name": name,
                "description": description,
                "capabilities": caps,
                "platform": "chatdev",
            },
            headers=_auth_headers(),
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        data = resp.json()
        if resp.status_code >= 400:
            return json.dumps({"error": data.get("error", f"HTTP {resp.status_code}")})
        return json.dumps(data, indent=2, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def discover_agents(
    capability: str = "",
    owner: str = "",
    limit: int = 20,
) -> str:
    """Search the AgentID registry for verified agents by capability.

    Useful for finding agents that can handle a specific task
    (e.g. "coding", "review", "testing", "deployment").

    This is a public endpoint -- no API key is required.

    Args:
        capability: Filter by capability keyword.
        owner: Filter by owner or organisation name.
        limit: Maximum number of results (1-100).

    Returns:
        A JSON string with a list of matching agents and their trust scores.
    """
    try:
        params: dict = {"limit": min(int(limit), 100)}
        if capability:
            params["capability"] = capability
        if owner:
            params["owner"] = owner
        resp = httpx.get(
            f"{_BASE_URL}/agents/discover",
            params=params,
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        data = resp.json()
        if resp.status_code >= 400:
            return json.dumps({"error": data.get("error", f"HTTP {resp.status_code}")})
        return json.dumps(data, indent=2, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def send_verified_message(
    from_agent: str,
    to_agent: str,
    payload: str,
    message_type: str = "request",
) -> str:
    """Send a cryptographically verified message between two agents.

    Both agents' identities are verified before delivery. Returns a
    trust check indicating whether both parties are verified and a
    recommendation for data exchange safety.

    Requires the AGENTID_API_KEY environment variable.

    Args:
        from_agent: The agent_id of the sending agent.
        to_agent: The agent_id of the receiving agent.
        payload: JSON string with the message payload.
        message_type: Message type: "request", "response", or "notification".

    Returns:
        A JSON string with delivery status and trust check results.
    """
    try:
        payload_dict = json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        return json.dumps({"error": "payload must be a valid JSON string"})

    try:
        resp = httpx.post(
            f"{_BASE_URL}/agents/connect",
            json={
                "from_agent": from_agent,
                "to_agent": to_agent,
                "message_type": message_type,
                "payload": payload_dict,
            },
            headers=_auth_headers(),
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        data = resp.json()
        if resp.status_code >= 400:
            return json.dumps({"error": data.get("error", f"HTTP {resp.status_code}")})
        return json.dumps(data, indent=2, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
