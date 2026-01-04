#!/usr/bin/env python3
"""
Test script to diagnose Claude model selection issues with the Agent SDK.

FINDINGS:
- The SDK correctly sets the model (Message.model attribute shows Opus)
- Claude doesn't accurately know its own model identity (known limitation)
- Direct CLI subprocess works correctly
- The model parameter in ClaudeAgentOptions works, but Claude self-reports incorrectly

Reference: https://github.com/anthropics/claude-code/issues/8992
"""
import asyncio
import os
import sys
import subprocess
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Claude Model Selection Diagnostic Tests")
print("=" * 60)

# Find Claude CLI
def find_claude_cli():
    """Find the Claude CLI executable."""
    claude_path = shutil.which("claude")
    if claude_path:
        return claude_path

    # Try common Windows paths
    if sys.platform == "win32":
        possible_paths = [
            os.path.expandvars(r"%APPDATA%\npm\claude.cmd"),
            os.path.expandvars(r"%LOCALAPPDATA%\npm\claude.cmd"),
            r"C:\Program Files\nodejs\claude.cmd",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
    return None

CLAUDE_CLI = find_claude_cli()
print(f"\nClaude CLI: {CLAUDE_CLI or 'NOT FOUND'}")

# Test 1: Check SDK availability
print("\n[TEST 1] SDK availability check")
print("-" * 40)
try:
    from claude_agent_sdk import query, ClaudeAgentOptions, ClaudeSDKClient
    print("✓ claude_agent_sdk imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 2: SDK with model='opus' - verify Message.model attribute
async def test_sdk_model_attribute():
    print("\n[TEST 2] SDK model='opus' - Check Message.model attribute")
    print("-" * 40)
    print("This tests if the SDK correctly sets the model in the response metadata.")

    options = ClaudeAgentOptions(
        model="opus",
        max_turns=1,
        allowed_tools=[],
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("Say 'hello' and nothing else.")
            async for message in client.receive_response():
                if hasattr(message, 'model'):
                    model = message.model
                    print(f"Message.model attribute: {model}")
                    if "opus" in model.lower():
                        print("✓ SDK correctly reports Opus model in metadata")
                    else:
                        print("✗ Model attribute does not contain 'opus'")
                    return model
    except Exception as e:
        print(f"ERROR: {e}")
        return None

# Test 3: Direct subprocess (confirmed working)
async def test_subprocess():
    print("\n[TEST 3] Direct subprocess with --model opus")
    print("-" * 40)
    print("This tests the CLI directly, which correctly reports Opus.")

    if not CLAUDE_CLI:
        print("Claude CLI not found - skipping")
        return None

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "--model", "opus", "-p", "What is your model name? Reply with just the model identifier."],
            capture_output=True,
            text=True,
            timeout=60,
            shell=True if sys.platform == "win32" else False
        )
        response = result.stdout.strip()
        print(f"CLI Response: {response}")
        if result.returncode == 0:
            print("✓ CLI subprocess works correctly")
        return response
    except Exception as e:
        print(f"ERROR: {e}")
        return None

# Test 4: SDK with cli_path option
async def test_sdk_with_cli_path():
    print("\n[TEST 4] SDK with explicit cli_path")
    print("-" * 40)

    if not CLAUDE_CLI:
        print("Claude CLI not found - skipping")
        return None

    options = ClaudeAgentOptions(
        model="opus",
        cli_path=CLAUDE_CLI,
        max_turns=1,
        allowed_tools=[],
    )
    print(f"Using cli_path: {CLAUDE_CLI}")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("Say 'test' and nothing else.")
            async for message in client.receive_response():
                if hasattr(message, 'model'):
                    model = message.model
                    print(f"Message.model attribute: {model}")
                    if "opus" in model.lower():
                        print("✓ With cli_path, SDK reports Opus")
                    return model
    except Exception as e:
        print(f"ERROR: {e}")
        return None

# Summary and recommendation
def print_summary(sdk_model, cli_response, cli_path_model):
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print("\nResults:")
    print(f"  SDK Message.model:     {sdk_model or 'N/A'}")
    print(f"  CLI subprocess:        {cli_response or 'N/A'}")
    print(f"  SDK with cli_path:     {cli_path_model or 'N/A'}")

    print("\nConclusion:")
    if sdk_model and "opus" in sdk_model.lower():
        print("  ✓ The SDK IS using Opus (based on Message.model attribute)")
        print("  ✓ Claude's self-identification is unreliable (known issue)")
        print("  ✓ Trust the Message.model attribute, not Claude's response")
    else:
        print("  ✗ Model selection may not be working correctly")

    print("\nReferences:")
    print("  - https://github.com/anthropics/claude-code/issues/8992")
    print("  - https://github.com/anthropics/claude-code/issues/6602")

# Run tests
async def main():
    sdk_model = await test_sdk_model_attribute()
    cli_response = await test_subprocess()
    cli_path_model = await test_sdk_with_cli_path()

    print_summary(sdk_model, cli_response, cli_path_model)

    print("\n" + "=" * 60)
    print("Tests complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
