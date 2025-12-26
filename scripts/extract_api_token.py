#!/usr/bin/env python3
"""
Script to extract Orion API Bearer token from an authenticated browser session.

This script uses the existing browser session (from browser_data/) to:
1. Intercept network requests and look for Authorization headers
2. Check localStorage and sessionStorage for JWT tokens
3. Trigger API calls by navigating/interacting with the page

Usage:
    python scripts/extract_api_token.py

The token will be saved to .env.local for your reference (NOT committed to git).
"""

import asyncio
import json
import os
import re
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, Request, Response

# Paths
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_DIR = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_DIR / "backend"
BROWSER_DATA_DIR = BACKEND_DIR / "browser_data"
OUTPUT_FILE = PROJECT_DIR / ".env.local"

# Orion URL patterns
ORION_API_PATTERNS = [
    r"/api/v1/",
    r"/api/",
    r"orion-labs\.com",
]

class TokenExtractor:
    """Extracts Bearer tokens from Orion web session."""

    def __init__(self):
        self.found_tokens = {}
        self.captured_requests = []
        self.playwright = None
        self.context = None
        self.page = None

    async def start_browser(self):
        """Start browser with existing session data."""
        print(f"\n{'='*60}")
        print("🔐 Orion API Token Extractor")
        print(f"{'='*60}\n")

        print(f"📁 Using browser data from: {BROWSER_DATA_DIR}")

        if not BROWSER_DATA_DIR.exists():
            print("❌ ERROR: browser_data directory not found!")
            print("   You need to login to Orion first using the main application.")
            return False

        self.playwright = await async_playwright().start()

        # Browser args
        browser_args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
        ]

        # Try to detect available browser
        browser_channel = os.getenv("BROWSER_CHANNEL", "msedge")
        channel = None if browser_channel == "chromium" else browser_channel

        try:
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_DATA_DIR),
                headless=False,  # Need to see the browser for login if needed
                channel=channel,
                viewport={"width": 1280, "height": 900},
                args=browser_args,
                ignore_default_args=["--enable-automation"],
            )
            print(f"✅ Browser started with channel: {browser_channel}")
        except Exception as e:
            print(f"⚠️ Failed with {browser_channel}, trying chromium: {e}")
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_DATA_DIR),
                headless=False,
                viewport={"width": 1280, "height": 900},
                args=browser_args,
                ignore_default_args=["--enable-automation"],
            )
            print("✅ Browser started with chromium")

        # Setup page
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # Setup request interception
        self.page.on("request", self._on_request)
        self.page.on("response", self._on_response)

        return True

    async def _on_request(self, request: Request):
        """Intercept requests and look for Authorization headers."""
        headers = request.headers
        url = request.url

        # Check for Authorization header
        auth_header = headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            self._save_token("request_header", token, url)

        # Log API requests for debugging
        for pattern in ORION_API_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                self.captured_requests.append({
                    "url": url,
                    "method": request.method,
                    "has_auth": bool(auth_header),
                })
                break

    async def _on_response(self, response: Response):
        """Check responses for token data."""
        url = response.url

        # Only check API responses
        if "/api/" not in url:
            return

        try:
            # Check if response contains token
            if response.headers.get("content-type", "").startswith("application/json"):
                body = await response.text()
                data = json.loads(body)

                # Look for token fields in response
                for key in ["token", "access_token", "accessToken", "jwt", "bearer_token"]:
                    if key in data:
                        self._save_token(f"response_{key}", data[key], url)

        except Exception:
            pass  # Ignore non-JSON responses

    def _save_token(self, source: str, token: str, url: str):
        """Save a found token."""
        # Validate it looks like a JWT (3 parts separated by dots)
        if self._is_jwt(token):
            token_preview = f"{token[:20]}...{token[-10:]}" if len(token) > 35 else token
            print(f"\n🔑 TOKEN FOUND!")
            print(f"   Source: {source}")
            print(f"   URL: {url}")
            print(f"   Preview: {token_preview}")
            print(f"   Length: {len(token)} chars")

            self.found_tokens[source] = {
                "token": token,
                "url": url,
                "timestamp": datetime.now().isoformat(),
            }

    def _is_jwt(self, token: str) -> bool:
        """Check if a string looks like a JWT."""
        if not token or not isinstance(token, str):
            return False
        parts = token.split(".")
        return len(parts) == 3 and len(token) > 30

    async def check_storage(self):
        """Check localStorage and sessionStorage for tokens."""
        print("\n📦 Checking browser storage...")

        # Make sure we're on the Orion domain first
        current_url = self.page.url
        if "orion" not in current_url.lower() and "about:blank" in current_url.lower():
            print("   ⚠️ Not on Orion site yet, skipping storage check...")
            print("   (Storage will be checked after navigation)")
            return

        storage_script = """
        () => {
            const results = {
                localStorage: {},
                sessionStorage: {},
            };

            try {
                // Check localStorage
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    const value = localStorage.getItem(key);
                    if (key && value) {
                        results.localStorage[key] = value;
                    }
                }
            } catch (e) {
                results.localStorageError = e.message;
            }

            try {
                // Check sessionStorage
                for (let i = 0; i < sessionStorage.length; i++) {
                    const key = sessionStorage.key(i);
                    const value = sessionStorage.getItem(key);
                    if (key && value) {
                        results.sessionStorage[key] = value;
                    }
                }
            } catch (e) {
                results.sessionStorageError = e.message;
            }

            return results;
        }
        """

        try:
            storage = await self.page.evaluate(storage_script)
        except Exception as e:
            print(f"   ⚠️ Could not access storage: {e}")
            return

        # Check for storage access errors
        if storage.get("localStorageError"):
            print(f"   ⚠️ localStorage error: {storage['localStorageError']}")
        if storage.get("sessionStorageError"):
            print(f"   ⚠️ sessionStorage error: {storage['sessionStorageError']}")

        # Keywords that might indicate token storage
        token_keywords = ["token", "jwt", "auth", "bearer", "access", "session", "credential"]

        for storage_type, items in storage.items():
            # Skip error entries
            if storage_type.endswith("Error") or not isinstance(items, dict):
                continue

            print(f"\n   {storage_type}:")
            for key, value in items.items():
                # Check if key suggests it's a token
                is_token_key = any(kw in key.lower() for kw in token_keywords)

                # Check if value looks like a JWT
                is_jwt_value = self._is_jwt(value)

                if is_token_key or is_jwt_value:
                    preview = f"{value[:30]}..." if len(value) > 35 else value
                    print(f"      🔹 {key}: {preview}")

                    if is_jwt_value:
                        self._save_token(f"{storage_type}_{key}", value, "storage")
                else:
                    # Just show key name for non-token values
                    if len(items) <= 10:  # Only show if not too many items
                        print(f"      • {key}: (not a token)")

    async def check_cookies(self):
        """Check cookies for token-like values."""
        print("\n🍪 Checking cookies...")

        cookies = await self.context.cookies()

        token_keywords = ["token", "jwt", "auth", "bearer", "access", "session"]

        for cookie in cookies:
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            domain = cookie.get("domain", "")

            # Only check orion-related cookies
            if "orion" not in domain.lower():
                continue

            is_token_key = any(kw in name.lower() for kw in token_keywords)
            is_jwt_value = self._is_jwt(value)

            preview = f"{value[:30]}..." if len(value) > 35 else value

            if is_token_key or is_jwt_value:
                print(f"   🔹 {name} ({domain}): {preview}")

                if is_jwt_value:
                    self._save_token(f"cookie_{name}", value, domain)
            else:
                print(f"   • {name} ({domain})")

    async def trigger_api_calls(self):
        """Navigate to pages that trigger API calls."""
        print("\n🌐 Triggering API calls by navigating...")

        base_url = "https://laboratoriofranz.orion-labs.com"

        # Pages that likely trigger API calls
        pages_to_visit = [
            "/ordenes",
            "/ordenes?page=1",
        ]

        for path in pages_to_visit:
            url = f"{base_url}{path}"
            print(f"\n   📄 Navigating to: {path}")

            try:
                await self.page.goto(url, timeout=30000)
                await self.page.wait_for_load_state("networkidle", timeout=15000)

                # Check if we're on login page
                current_url = self.page.url
                if "/login" in current_url:
                    print("\n   ⚠️ NOT LOGGED IN - Redirected to login page")
                    print("   Please login manually in the browser window...")
                    print("   Waiting 60 seconds for you to login...")

                    # Wait for manual login
                    for i in range(60):
                        await asyncio.sleep(1)
                        if "/login" not in self.page.url:
                            print(f"\n   ✅ Login detected! Continuing...")
                            await asyncio.sleep(2)  # Wait for page to load
                            break
                        if i % 10 == 0:
                            print(f"   ... {60-i} seconds remaining")

                    # Check again
                    if "/login" in self.page.url:
                        print("\n   ❌ Timeout waiting for login. Please try again.")
                        return False

                # Small delay between navigations
                await asyncio.sleep(1)

            except Exception as e:
                print(f"   ⚠️ Error navigating to {path}: {e}")

        return True

    async def attempt_api_login(self):
        """Try to find and use a login endpoint to get a token."""
        print("\n🔐 Attempting to find API login endpoint...")

        # Common API login endpoints to try
        login_endpoints = [
            "/api/v1/auth/login",
            "/api/v1/login",
            "/api/auth/login",
            "/api/login",
        ]

        base_url = "https://laboratoriofranz.orion-labs.com"

        for endpoint in login_endpoints:
            url = f"{base_url}{endpoint}"
            print(f"   Checking: {endpoint}")

            try:
                # Make a request to see if endpoint exists
                response = await self.page.request.head(url)
                status = response.status

                if status != 404:
                    print(f"   ✅ Endpoint exists! Status: {status}")
                    print(f"   You may be able to POST credentials to: {url}")

            except Exception as e:
                pass

    def save_results(self):
        """Save found tokens to file."""
        if not self.found_tokens:
            print("\n❌ No Bearer tokens found.")
            print("\n📝 Debug info - Captured API requests:")
            for req in self.captured_requests[:10]:
                auth_status = "🔓" if req["has_auth"] else "🔒"
                print(f"   {auth_status} {req['method']} {req['url'][:80]}")
            return

        print(f"\n{'='*60}")
        print("📝 RESULTS")
        print(f"{'='*60}")

        # Get the best token (prefer request headers over storage)
        best_token = None
        for source in ["request_header", "cookie_token", "localStorage_token", "sessionStorage_token"]:
            if source in self.found_tokens:
                best_token = self.found_tokens[source]
                break

        if not best_token:
            best_token = list(self.found_tokens.values())[0]

        token = best_token["token"]

        print(f"\n✅ Best token found:")
        print(f"   Source: {list(self.found_tokens.keys())[0]}")
        print(f"   Token (first 50 chars): {token[:50]}...")
        print(f"   Full length: {len(token)} characters")

        # Save to .env.local
        env_content = f"""# Orion API Token - Generated {datetime.now().isoformat()}
# WARNING: Keep this secret! Do not commit to git.
# Use this token in the Authorization header: Bearer <token>

ORION_API_TOKEN={token}

# All found tokens:
"""
        for source, data in self.found_tokens.items():
            env_content += f"# {source}: {data['token'][:50]}...\n"

        with open(OUTPUT_FILE, "w") as f:
            f.write(env_content)

        print(f"\n💾 Token saved to: {OUTPUT_FILE}")
        print("   ⚠️ Keep this file secret! It's in .gitignore")

        # Print usage example
        print(f"\n{'='*60}")
        print("📖 USAGE EXAMPLE")
        print(f"{'='*60}")
        print("""
# Python example:
import requests

token = "YOUR_TOKEN_HERE"
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

response = requests.get(
    "https://laboratoriofranz.orion-labs.com/api/v1/ordenes",
    headers=headers
)
print(response.json())

# Or with curl:
curl -H "Authorization: Bearer YOUR_TOKEN" \\
     -H "Accept: application/json" \\
     https://laboratoriofranz.orion-labs.com/api/v1/ordenes
""")

    async def stop(self):
        """Close browser."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()


async def main():
    extractor = TokenExtractor()

    try:
        # Start browser
        if not await extractor.start_browser():
            return

        # First navigate to Orion to trigger API calls (this also gets us on the right domain)
        await extractor.trigger_api_calls()

        # Wait a bit for any delayed API calls
        print("\n⏳ Waiting for additional API calls...")
        await asyncio.sleep(3)

        # Now check storage (after we're on the Orion domain)
        await extractor.check_storage()

        # Check cookies
        await extractor.check_cookies()

        # Try to find API login endpoint
        await extractor.attempt_api_login()

        # Save results
        extractor.save_results()

        # Keep browser open for manual inspection
        if not extractor.found_tokens:
            print("\n💡 TIP: The browser is still open.")
            print("   Try interacting with the page and watch Network tab in DevTools.")
            print("   Press Ctrl+C when done.")

            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n\n👋 Closing...")

    finally:
        await extractor.stop()


if __name__ == "__main__":
    asyncio.run(main())
