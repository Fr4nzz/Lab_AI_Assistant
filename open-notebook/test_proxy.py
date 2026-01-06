#!/usr/bin/env python3
"""
Test the Claude Code Proxy's OpenAI-compatible API endpoint.

This tests if Open Notebook can communicate with the Claude Code proxy.
"""
import requests
import json

PROXY_URL = "http://localhost:8080"

def test_health():
    """Test health endpoint."""
    print("=" * 50)
    print("TEST 1: Health Check")
    print("=" * 50)
    try:
        response = requests.get(f"{PROXY_URL}/health", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_models():
    """Test models listing endpoint."""
    print("\n" + "=" * 50)
    print("TEST 2: List Models (/v1/models)")
    print("=" * 50)
    try:
        response = requests.get(f"{PROXY_URL}/v1/models", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_chat_completion():
    """Test chat completion endpoint (non-streaming)."""
    print("\n" + "=" * 50)
    print("TEST 3: Chat Completion (/v1/chat/completions)")
    print("=" * 50)

    payload = {
        "model": "claude-sonnet",
        "messages": [
            {"role": "user", "content": "Say 'Hello from Claude Code!' and nothing else."}
        ],
        "stream": False
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer dummy-key"  # API key not actually used
    }

    try:
        print(f"Request: {json.dumps(payload, indent=2)}")
        print("\nWaiting for response (this may take 30-60 seconds)...")

        response = requests.post(
            f"{PROXY_URL}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=120
        )

        print(f"\nStatus: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Model: {data.get('model')}")
            print(f"Response ID: {data.get('id')}")

            if data.get('choices'):
                message = data['choices'][0].get('message', {})
                print(f"Assistant: {message.get('content')}")

            if data.get('usage'):
                usage = data['usage']
                print(f"Tokens: {usage.get('total_tokens')} (prompt: {usage.get('prompt_tokens')}, completion: {usage.get('completion_tokens')})")

            return True
        else:
            print(f"Error: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("ERROR: Request timed out (120s)")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_chat_streaming():
    """Test streaming chat completion."""
    print("\n" + "=" * 50)
    print("TEST 4: Streaming Chat Completion")
    print("=" * 50)

    payload = {
        "model": "claude-sonnet",
        "messages": [
            {"role": "user", "content": "Count from 1 to 5, one number per line."}
        ],
        "stream": True
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer dummy-key"
    }

    try:
        print("Streaming response:")
        print("-" * 30)

        response = requests.post(
            f"{PROXY_URL}/v1/chat/completions",
            json=payload,
            headers=headers,
            stream=True,
            timeout=120
        )

        full_content = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Remove 'data: ' prefix
                    if data_str == '[DONE]':
                        print("\n[DONE]")
                        break
                    try:
                        data = json.loads(data_str)
                        if data.get('choices'):
                            delta = data['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                print(content, end='', flush=True)
                                full_content += content
                    except json.JSONDecodeError:
                        pass

        print("-" * 30)
        print(f"Full content: {full_content}")
        return len(full_content) > 0

    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    print("=" * 50)
    print("Claude Code Proxy - OpenAI Compatibility Test")
    print("=" * 50)
    print(f"Testing: {PROXY_URL}")
    print()

    results = []

    # Test 1: Health
    results.append(("Health Check", test_health()))

    # Test 2: Models
    results.append(("List Models", test_models()))

    # Test 3: Chat (non-streaming)
    results.append(("Chat Completion", test_chat_completion()))

    # Test 4: Streaming
    results.append(("Streaming", test_chat_streaming()))

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed! The proxy is ready for Open Notebook.")
    else:
        print("Some tests failed. Check the errors above.")

    return all_passed

if __name__ == "__main__":
    main()
