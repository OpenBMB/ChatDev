# AgentID Identity Verification

ChatDev agents collaborate as CEO, CTO, Programmer, Tester — but by default have no verifiable identity. [AgentID](https://getagentid.dev) adds cryptographic identity verification so agents can prove who they are before trusting each other with sensitive operations.

## Why Identity Matters

In a multi-agent pipeline, any agent could be compromised or impersonated. AgentID solves this by issuing ECDSA P-256 certificates per agent and providing a verification API that other agents can call at runtime.

**Use cases:**
- Verify the Programmer before accepting its code
- Gate the Code Reviewer on a minimum trust score
- Audit which verified agents participated in a build
- Discover agents by capability (e.g. "find me a deployment agent")

## Setup

### 1. Get an API Key

Sign up at [getagentid.dev](https://getagentid.dev) and create an API key.

### 2. Set Environment Variables

```bash
export AGENTID_API_KEY="aid_your_key_here"
# Optional: override the API endpoint
# export AGENTID_BASE_URL="https://your-instance.example.com/api/v1"
```

### 3. Install httpx

The AgentID tools require `httpx`:

```bash
pip install httpx
```

## Available Tools

All tools are in `functions/function_calling/agentid.py`:

| Tool | Auth Required | Description |
|------|:---:|-------------|
| `verify_agent_identity` | No | Verify an agent's cryptographic identity |
| `register_agent_identity` | Yes | Register a new agent and get a certificate |
| `discover_agents` | No | Search the registry by capability |
| `send_verified_message` | Yes | Send a verified message between agents |

## Usage in Workflows

### Add Tools to Agent Nodes

```yaml
- id: Programmer
  type: agent
  config:
    provider: openai
    name: gpt-4o
    role: "You are Programmer..."
    tooling:
      - type: function
        config:
          tools:
            - name: verify_agent_identity
            - name: register_agent_identity
```

### Identity Gate Pattern

Add an Identity Verifier node at the start of your pipeline that checks all agents before allowing work to proceed:

```yaml
- id: Identity Verifier
  type: agent
  config:
    provider: openai
    name: gpt-4o
    role: "Verify all agent identities before the pipeline starts..."
    tooling:
      - type: function
        config:
          tools:
            - name: verify_agent_identity
```

Then use edge conditions to gate downstream nodes:

```yaml
edges:
  - from: Identity Verifier
    to: Programmer
    condition:
      type: keyword
      config:
        any: ["VERIFIED"]
```

### Edge Conditions

Three identity-aware edge conditions are available in `functions/edge/conditions.py`:

- `identity_verified` — True when output contains `"verified": true`
- `identity_not_verified` — True when verification failed
- `trust_score_above_threshold` — True when trust score >= 0.7

## Example Workflow

See `yaml_instance/chatdev_with_identity.yaml` for a complete example that:

1. Verifies all agents before coding begins
2. Gates the Programmer on successful verification
3. Allows the Code Reviewer to re-verify the Programmer's identity
4. Routes to a final output only after reviewed by verified agents

## Architecture

```
User Task
    │
    ▼
┌──────────────────┐
│ Identity Verifier │ ← verify_agent_identity()
│   (gate node)     │
└────────┬─────────┘
         │ VERIFIED
         ▼
┌──────────────────┐
│   Programmer      │ ← writes code (verified identity)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Code Reviewer    │ ← can re-verify Programmer
└────────┬─────────┘
         │
         ▼
      Output
```

## Reference

- [AgentID Documentation](https://getagentid.dev/docs)
- [AgentID GitHub](https://github.com/haroldmalikfrimpong-ops/getagentid)
- [Issue #587](https://github.com/OpenBMB/ChatDev/issues/587)
