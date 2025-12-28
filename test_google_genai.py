#!/usr/bin/env python3
"""Test Google GenAI API connectivity."""

import os
import sys

# Try to load from .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get API keys - check GEMINI_API_KEYS (comma-separated) or individual keys
api_keys = []

# Check comma-separated format from .env.example
gemini_keys = os.getenv("GEMINI_API_KEYS", "")
if gemini_keys and gemini_keys != "your_api_key_1,your_api_key_2,your_api_key_3":
    for i, key in enumerate(gemini_keys.split(","), 1):
        key = key.strip()
        if key:
            api_keys.append((f"GEMINI_API_KEY_{i}", key))

# Also check individual key formats
for key_name in ["GOOGLE_API_KEY", "GEMINI_API_KEY"]:
    value = os.getenv(key_name)
    if value:
        api_keys.append((key_name, value))

# Allow passing key as command line argument
if len(sys.argv) > 1:
    api_keys.append(("CLI_ARG", sys.argv[1]))

if not api_keys:
    print("❌ No Google/Gemini API keys found")
    print("\nUsage options:")
    print("  1. Set GEMINI_API_KEYS env var (comma-separated)")
    print("  2. Create .env file with GEMINI_API_KEYS=key1,key2,key3")
    print("  3. Pass key as argument: python test_google_genai.py YOUR_API_KEY")
    exit(1)

print(f"Found {len(api_keys)} API key(s) to test\n")

try:
    import google.generativeai as genai
except ImportError:
    print("❌ google-generativeai not installed. Run: pip install google-generativeai")
    exit(1)

for key_name, api_key in api_keys:
    # Mask the key for display
    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print(f"Testing {key_name} ({masked_key})...")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content("Say 'API working' in 3 words or less")
        print(f"  ✅ SUCCESS: {response.text.strip()}\n")
    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg:
            print(f"  ❌ INVALID KEY: The API key is not valid\n")
        elif "PERMISSION_DENIED" in error_msg:
            print(f"  ❌ PERMISSION DENIED: Key may be blocked or restricted\n")
        elif "RESOURCE_EXHAUSTED" in error_msg:
            print(f"  ❌ QUOTA EXCEEDED: Rate limit or quota exhausted\n")
        elif "blocked" in error_msg.lower():
            print(f"  ❌ BLOCKED: {error_msg}\n")
        else:
            print(f"  ❌ ERROR: {error_msg}\n")
