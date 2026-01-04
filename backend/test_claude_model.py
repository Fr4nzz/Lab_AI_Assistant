#!/usr/bin/env python3
"""
Test script to diagnose Claude model selection issues with the Agent SDK.

Tests different methods of setting the model to identify what works.
"""
import asyncio
import os
import sys
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Claude Model Selection Diagnostic Tests")
print("=" * 60)

# Test 1: Direct CLI call
print("\n[TEST 1] Direct CLI call with --model opus")
print("-" * 40)
try:
    result = subprocess.run(
        ["claude", "--model", "opus", "-p", "What model are you? Reply with ONLY your model name, nothing else."],
        capture_output=True,
        text=True,
        timeout=60
    )
    print(f"STDOUT: {result.stdout.strip()}")
    if result.stderr:
        print(f"STDERR: {result.stderr.strip()}")
    print(f"Return code: {result.returncode}")
except Exception as e:
    print(f"ERROR: {e}")

# Test 2: Check if SDK is available
print("\n[TEST 2] SDK availability check")
print("-" * 40)
try:
    from claude_agent_sdk import query, ClaudeAgentOptions, ClaudeSDKClient
    print("✓ claude_agent_sdk imported successfully")
    print(f"  - query: {query}")
    print(f"  - ClaudeAgentOptions: {ClaudeAgentOptions}")
    print(f"  - ClaudeSDKClient: {ClaudeSDKClient}")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 3: SDK with model parameter only
async def test_sdk_model_param():
    print("\n[TEST 3] SDK with model='opus' parameter only")
    print("-" * 40)

    options = ClaudeAgentOptions(
        model="opus",
        max_turns=1,
        allowed_tools=[],
    )
    print(f"Options: model={options.model}")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("What model are you? Reply with ONLY your model name, nothing else.")
            async for message in client.receive_response():
                msg_type = type(message).__name__
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            print(f"Response ({msg_type}): {block.text[:200]}")
                if hasattr(message, 'model'):
                    print(f"Message.model attribute: {message.model}")
    except Exception as e:
        print(f"ERROR: {e}")

# Test 4: SDK with env parameter
async def test_sdk_env_param():
    print("\n[TEST 4] SDK with env={'ANTHROPIC_MODEL': 'opus'}")
    print("-" * 40)

    options = ClaudeAgentOptions(
        max_turns=1,
        allowed_tools=[],
        env={"ANTHROPIC_MODEL": "opus"},
    )
    print(f"Options: env={{'ANTHROPIC_MODEL': 'opus'}}")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("What model are you? Reply with ONLY your model name, nothing else.")
            async for message in client.receive_response():
                msg_type = type(message).__name__
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            print(f"Response ({msg_type}): {block.text[:200]}")
                if hasattr(message, 'model'):
                    print(f"Message.model attribute: {message.model}")
    except Exception as e:
        print(f"ERROR: {e}")

# Test 5: SDK with process-level env var
async def test_sdk_process_env():
    print("\n[TEST 5] SDK with os.environ['ANTHROPIC_MODEL'] = 'opus'")
    print("-" * 40)

    # Set at process level
    old_val = os.environ.get("ANTHROPIC_MODEL")
    os.environ["ANTHROPIC_MODEL"] = "opus"
    print(f"Set ANTHROPIC_MODEL=opus (was: {old_val})")

    options = ClaudeAgentOptions(
        max_turns=1,
        allowed_tools=[],
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("What model are you? Reply with ONLY your model name, nothing else.")
            async for message in client.receive_response():
                msg_type = type(message).__name__
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            print(f"Response ({msg_type}): {block.text[:200]}")
                if hasattr(message, 'model'):
                    print(f"Message.model attribute: {message.model}")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        # Restore
        if old_val:
            os.environ["ANTHROPIC_MODEL"] = old_val
        elif "ANTHROPIC_MODEL" in os.environ:
            del os.environ["ANTHROPIC_MODEL"]

# Test 6: SDK with both model param and env
async def test_sdk_both():
    print("\n[TEST 6] SDK with model='opus' AND env={'ANTHROPIC_MODEL': 'opus'}")
    print("-" * 40)

    options = ClaudeAgentOptions(
        model="opus",
        max_turns=1,
        allowed_tools=[],
        env={"ANTHROPIC_MODEL": "opus"},
    )
    print(f"Options: model={options.model}, env={{'ANTHROPIC_MODEL': 'opus'}}")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("What model are you? Reply with ONLY your model name, nothing else.")
            async for message in client.receive_response():
                msg_type = type(message).__name__
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            print(f"Response ({msg_type}): {block.text[:200]}")
                if hasattr(message, 'model'):
                    print(f"Message.model attribute: {message.model}")
    except Exception as e:
        print(f"ERROR: {e}")

# Test 7: SDK with full model ID
async def test_sdk_full_id():
    print("\n[TEST 7] SDK with model='claude-opus-4-5-20251101' (full ID)")
    print("-" * 40)

    options = ClaudeAgentOptions(
        model="claude-opus-4-5-20251101",
        max_turns=1,
        allowed_tools=[],
    )
    print(f"Options: model={options.model}")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("What model are you? Reply with ONLY your model name, nothing else.")
            async for message in client.receive_response():
                msg_type = type(message).__name__
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            print(f"Response ({msg_type}): {block.text[:200]}")
                if hasattr(message, 'model'):
                    print(f"Message.model attribute: {message.model}")
    except Exception as e:
        print(f"ERROR: {e}")

# Test 8: Check ClaudeAgentOptions attributes
def test_options_attrs():
    print("\n[TEST 8] ClaudeAgentOptions available attributes")
    print("-" * 40)

    options = ClaudeAgentOptions()
    attrs = [attr for attr in dir(options) if not attr.startswith('_')]
    print(f"Available attributes: {attrs}")

    # Check if model is actually set
    print(f"Default model value: {getattr(options, 'model', 'N/A')}")

    options2 = ClaudeAgentOptions(model="opus")
    print(f"After setting model='opus': {getattr(options2, 'model', 'N/A')}")

# Test 9: SDK with extra_args to pass --model flag directly
async def test_sdk_extra_args():
    print("\n[TEST 9] SDK with extra_args=['--model', 'opus']")
    print("-" * 40)

    options = ClaudeAgentOptions(
        max_turns=1,
        allowed_tools=[],
        extra_args=["--model", "opus"],
    )
    print(f"Options: extra_args=['--model', 'opus']")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("What model are you? Reply with ONLY your model name, nothing else.")
            async for message in client.receive_response():
                msg_type = type(message).__name__
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            print(f"Response ({msg_type}): {block.text[:200]}")
                if hasattr(message, 'model'):
                    print(f"Message.model attribute: {message.model}")
    except Exception as e:
        print(f"ERROR: {e}")

# Test 10: SDK with settings dict
async def test_sdk_settings():
    print("\n[TEST 10] SDK with settings={'model': 'opus'}")
    print("-" * 40)

    options = ClaudeAgentOptions(
        max_turns=1,
        allowed_tools=[],
        settings={"model": "opus"},
    )
    print(f"Options: settings={{'model': 'opus'}}")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("What model are you? Reply with ONLY your model name, nothing else.")
            async for message in client.receive_response():
                msg_type = type(message).__name__
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            print(f"Response ({msg_type}): {block.text[:200]}")
                if hasattr(message, 'model'):
                    print(f"Message.model attribute: {message.model}")
    except Exception as e:
        print(f"ERROR: {e}")

# Test 11: SDK with both model and extra_args
async def test_sdk_model_and_extra_args():
    print("\n[TEST 11] SDK with model='opus' AND extra_args=['--model', 'opus']")
    print("-" * 40)

    options = ClaudeAgentOptions(
        model="opus",
        max_turns=1,
        allowed_tools=[],
        extra_args=["--model", "opus"],
    )
    print(f"Options: model='opus', extra_args=['--model', 'opus']")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query("What model are you? Reply with ONLY your model name, nothing else.")
            async for message in client.receive_response():
                msg_type = type(message).__name__
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            print(f"Response ({msg_type}): {block.text[:200]}")
                if hasattr(message, 'model'):
                    print(f"Message.model attribute: {message.model}")
    except Exception as e:
        print(f"ERROR: {e}")

# Test 12: Direct subprocess with cli_path (Windows compatible)
async def test_subprocess_direct():
    print("\n[TEST 12] Direct subprocess with explicit cli_path")
    print("-" * 40)

    import shutil
    claude_path = shutil.which("claude")

    if not claude_path:
        # Try common Windows paths
        possible_paths = [
            os.path.expandvars(r"%APPDATA%\npm\claude.cmd"),
            os.path.expandvars(r"%LOCALAPPDATA%\npm\claude.cmd"),
            r"C:\Program Files\nodejs\claude.cmd",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                claude_path = path
                break

    if not claude_path:
        print("Claude CLI not found in PATH or common locations")
        return

    print(f"Found claude at: {claude_path}")

    try:
        result = subprocess.run(
            [claude_path, "--model", "opus", "-p", "What model are you? Reply with ONLY your model name."],
            capture_output=True,
            text=True,
            timeout=60,
            shell=True if sys.platform == "win32" else False
        )
        print(f"STDOUT: {result.stdout.strip()}")
        if result.stderr:
            print(f"STDERR: {result.stderr.strip()[:200]}")
        print(f"Return code: {result.returncode}")
    except Exception as e:
        print(f"ERROR: {e}")

# Test 13: Ask about capabilities instead of model name
async def test_capabilities():
    print("\n[TEST 13] Ask about Opus-specific capabilities with model='opus'")
    print("-" * 40)

    options = ClaudeAgentOptions(
        model="opus",
        max_turns=1,
        allowed_tools=[],
    )

    # Ask something that might reveal model behavior differences
    prompt = """I need to verify which model variant you are. Please answer these questions:
1. Are you Claude Opus 4.5 or Claude Sonnet 4?
2. What is your exact model identifier (the technical string like claude-xxx)?
3. What is your knowledge cutoff date?
Reply concisely."""

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                msg_type = type(message).__name__
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            print(f"Response: {block.text[:500]}")
                if hasattr(message, 'model'):
                    print(f"\nMessage.model attribute: {message.model}")
    except Exception as e:
        print(f"ERROR: {e}")

# Run all tests
async def main():
    test_options_attrs()
    await test_sdk_model_param()
    await test_sdk_env_param()
    await test_sdk_process_env()
    await test_sdk_both()
    await test_sdk_full_id()
    await test_sdk_extra_args()
    await test_sdk_settings()
    await test_sdk_model_and_extra_args()
    await test_subprocess_direct()
    await test_capabilities()

    print("\n" + "=" * 60)
    print("Tests complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
