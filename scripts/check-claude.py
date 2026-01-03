#!/usr/bin/env python3
"""
Check Claude Code installation and authentication status.
Used by Lab_Assistant.bat on startup to show Claude status.

Exit codes:
  0 - Claude Code is ready (installed + authenticated)
  1 - Claude Code not installed
  2 - Claude Code not authenticated
  3 - Other error
"""
import subprocess
import sys
import os
import json


def check_claude_status():
    """Check Claude Code status and print result."""
    result = {
        "installed": False,
        "authenticated": False,
        "version": None,
        "error": None
    }

    # Check if Claude CLI is installed
    try:
        version_result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if version_result.returncode == 0:
            result["installed"] = True
            result["version"] = version_result.stdout.strip()
        else:
            result["error"] = "Claude Code CLI not found"
            return result, 1
    except FileNotFoundError:
        result["error"] = "Claude Code CLI not installed"
        return result, 1
    except subprocess.TimeoutExpired:
        result["error"] = "Claude Code CLI timed out"
        return result, 3
    except Exception as e:
        result["error"] = str(e)
        return result, 3

    # Check authentication by running a simple query
    # Remove API key to force subscription auth
    env = os.environ.copy()
    if "ANTHROPIC_API_KEY" in env:
        del env["ANTHROPIC_API_KEY"]

    try:
        auth_result = subprocess.run(
            ["claude", "-p", "Say OK", "--max-turns", "1"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        if auth_result.returncode == 0:
            result["authenticated"] = True
        else:
            # Check if it's an auth error
            stderr = auth_result.stderr.lower()
            if "login" in stderr or "auth" in stderr or "token" in stderr:
                result["error"] = "Not authenticated. Run: claude login"
            else:
                result["error"] = f"Auth check failed: {auth_result.stderr[:100]}"
            return result, 2
    except subprocess.TimeoutExpired:
        result["error"] = "Authentication check timed out"
        return result, 2
    except Exception as e:
        result["error"] = str(e)
        return result, 3

    return result, 0


def main():
    """Main entry point."""
    # Check for --json flag
    json_output = "--json" in sys.argv

    result, exit_code = check_claude_status()

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        # Human-readable output
        if result["installed"]:
            print(f"  [OK] Claude Code {result['version']}")
            if result["authenticated"]:
                print("  [OK] Authenticated (Max subscription)")
            else:
                print(f"  [!] {result['error'] or 'Not authenticated'}")
        else:
            print(f"  [X] {result['error'] or 'Not installed'}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
