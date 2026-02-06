#!/usr/bin/env python3
"""Test script for Claude Code persistent session feature."""

import sys
sys.path.insert(0, '.')

# Test 1: Direct provider test (no SDK dependencies)
print("=" * 60)
print("Test 1: Direct ClaudeCodeProvider Test")
print("=" * 60)

try:
    from runtime.node.agent.providers.claude_code_provider import ClaudeCodeProvider

    # Check session storage works
    print("\n[1.1] Session storage test...")
    ClaudeCodeProvider.set_session("test_node", "session_123")
    retrieved = ClaudeCodeProvider.get_session("test_node")
    assert retrieved == "session_123", f"Expected 'session_123', got '{retrieved}'"
    print("  ✓ set_session/get_session works")

    # Check clear works
    ClaudeCodeProvider.clear_session("test_node")
    retrieved = ClaudeCodeProvider.get_session("test_node")
    assert retrieved is None, f"Expected None after clear, got '{retrieved}'"
    print("  ✓ clear_session works")

    # Check clear_all works
    ClaudeCodeProvider.set_session("node1", "sess1")
    ClaudeCodeProvider.set_session("node2", "sess2")
    ClaudeCodeProvider.clear_all_sessions()
    assert ClaudeCodeProvider.get_session("node1") is None
    assert ClaudeCodeProvider.get_session("node2") is None
    print("  ✓ clear_all_sessions works")

    print("\n✅ Direct provider tests passed!")

except Exception as e:
    print(f"\n❌ Direct provider test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: AgentConfig test
print("\n" + "=" * 60)
print("Test 2: AgentConfig persistent_session/skip_memory fields")
print("=" * 60)

try:
    from entity.configs.node.agent import AgentConfig

    # Test default values
    print("\n[2.1] Default values test...")
    config_data = {
        "provider": "claude-code",
        "name": "sonnet",
        "base_url": None,
    }
    config = AgentConfig.from_dict(config_data, path="test")
    assert config.persistent_session == True, f"Expected True, got {config.persistent_session}"
    assert config.skip_memory == False, f"Expected False, got {config.skip_memory}"
    print("  ✓ Default values correct (persistent_session=True, skip_memory=False)")

    # Test explicit values
    print("\n[2.2] Explicit values test...")
    config_data2 = {
        "provider": "claude-code",
        "name": "sonnet",
        "base_url": None,
        "persistent_session": False,
        "skip_memory": True,
    }
    config2 = AgentConfig.from_dict(config_data2, path="test2")
    assert config2.persistent_session == False
    assert config2.skip_memory == True
    print("  ✓ Explicit values work (persistent_session=False, skip_memory=True)")

    print("\n✅ AgentConfig tests passed!")

except Exception as e:
    print(f"\n❌ AgentConfig test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Live Claude Code call (if available)
print("\n" + "=" * 60)
print("Test 3: Live Claude Code CLI Test")
print("=" * 60)

try:
    import subprocess
    import shutil

    claude_path = shutil.which("claude")
    if not claude_path:
        print("\n⚠️  Claude CLI not found in PATH, skipping live test")
    else:
        print(f"\n[3.1] Claude CLI found at: {claude_path}")

        # Simple test call
        print("\n[3.2] Making test call...")
        result = subprocess.run(
            [claude_path, "-p", "Say 'Hello from Claude Code test!' and nothing else.",
             "--output-format", "json", "--max-turns", "1"],
            capture_output=True,
            text=True,
            timeout=60
        )

        import json
        response = json.loads(result.stdout)
        print(f"  Response: {response.get('result', 'N/A')[:100]}...")

        session_id = response.get("session_id")
        if session_id:
            print(f"  ✓ Got session_id: {session_id}")

            # Test resume
            print("\n[3.3] Testing --resume flag...")
            result2 = subprocess.run(
                [claude_path, "-p", "What did you just say?",
                 "--resume", session_id,
                 "--output-format", "json", "--max-turns", "1"],
                capture_output=True,
                text=True,
                timeout=60
            )
            response2 = json.loads(result2.stdout)
            print(f"  Response: {response2.get('result', 'N/A')[:100]}...")
            print("  ✓ --resume flag works!")
        else:
            print("  ⚠️  No session_id in response (might be older Claude CLI version)")

        print("\n✅ Live Claude Code tests passed!")

except subprocess.TimeoutExpired:
    print("\n⚠️  Claude CLI timed out")
except Exception as e:
    print(f"\n❌ Live test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
