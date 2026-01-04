#!/usr/bin/env python3
"""
Test Claude Code vision capabilities through Agent SDK.
Compares Opus vs Sonnet responses to the same image.
"""
import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

# Image path - update this to your test image
IMAGE_PATH = r"C:\Users\fzzch\Downloads\test_vision.png"

# Question to ask about the image
QUESTION = "que examenes estan marcados en la imagen"

async def test_vision(model_name: str):
    """Test vision with a specific model."""
    print(f"\n{'='*60}")
    print(f"Testing {model_name.upper()}")
    print(f"{'='*60}")

    # Verify image exists
    if not os.path.exists(IMAGE_PATH):
        print(f"ERROR: Image not found at {IMAGE_PATH}")
        return

    options = ClaudeAgentOptions(
        model=model_name,
        max_turns=1,
        # Allow Read tool so Claude can read the image
        allowed_tools=["Read"],
    )

    # Create prompt that tells Claude to read and analyze the image
    prompt = f"""Please read and analyze the image at this path: {IMAGE_PATH}

After viewing the image, answer this question: {QUESTION}

Use the Read tool to view the image first, then provide your analysis."""

    print(f"Prompt: {prompt[:100]}...")
    print("-" * 40)

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            full_response = ""
            model_used = None

            async for message in client.receive_response():
                # Capture model from response
                if hasattr(message, 'model') and message.model:
                    model_used = message.model

                # Capture text content
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            full_response += block.text

            print(f"Model used: {model_used}")
            print(f"\nResponse:\n{full_response}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

async def main():
    print("=" * 60)
    print("Claude Vision Test - Opus vs Sonnet")
    print("=" * 60)
    print(f"Image: {IMAGE_PATH}")
    print(f"Question: {QUESTION}")

    # Test with Opus
    await test_vision("opus")

    # Test with Sonnet
    await test_vision("sonnet")

    print("\n" + "=" * 60)
    print("Vision test complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
