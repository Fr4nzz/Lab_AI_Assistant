"""
Token capture utilities for extracting Orion API Bearer tokens.

This module provides functions to extract Bearer tokens from an active browser session.
It can be used standalone or integrated into the main application.
"""

import json
import re
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path


class TokenCapture:
    """Captures and stores Bearer tokens from browser requests."""

    def __init__(self):
        self.captured_tokens: Dict[str, dict] = {}
        self.api_requests: List[dict] = []

    def is_jwt(self, value: str) -> bool:
        """Check if a string looks like a JWT token."""
        if not value or not isinstance(value, str):
            return False
        parts = value.split(".")
        return len(parts) == 3 and len(value) > 30

    def capture_from_headers(self, headers: dict, url: str) -> Optional[str]:
        """Extract Bearer token from request headers."""
        auth_header = headers.get("authorization", headers.get("Authorization", ""))

        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            if self.is_jwt(token):
                self.captured_tokens["request_header"] = {
                    "token": token,
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                }
                return token
        return None

    async def extract_from_page(self, page) -> dict:
        """
        Extract potential tokens from a Playwright page.

        Args:
            page: Playwright page object

        Returns:
            Dict with found tokens from various sources
        """
        results = {
            "localStorage": {},
            "sessionStorage": {},
            "cookies": [],
            "tokens_found": [],
        }

        # Extract from localStorage and sessionStorage
        storage_script = """
        () => {
            const results = {
                localStorage: {},
                sessionStorage: {},
            };

            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                results.localStorage[key] = localStorage.getItem(key);
            }

            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                results.sessionStorage[key] = sessionStorage.getItem(key);
            }

            return results;
        }
        """

        try:
            storage = await page.evaluate(storage_script)
            results["localStorage"] = storage.get("localStorage", {})
            results["sessionStorage"] = storage.get("sessionStorage", {})

            # Look for JWT tokens in storage
            token_keywords = ["token", "jwt", "auth", "bearer", "access"]

            for storage_type in ["localStorage", "sessionStorage"]:
                for key, value in storage.get(storage_type, {}).items():
                    is_token_key = any(kw in key.lower() for kw in token_keywords)
                    is_jwt = self.is_jwt(value)

                    if is_token_key or is_jwt:
                        token_info = {
                            "source": f"{storage_type}.{key}",
                            "value": value,
                            "is_jwt": is_jwt,
                        }
                        results["tokens_found"].append(token_info)

                        if is_jwt:
                            self.captured_tokens[f"{storage_type}_{key}"] = {
                                "token": value,
                                "url": page.url,
                                "timestamp": datetime.now().isoformat(),
                            }

        except Exception as e:
            results["error"] = str(e)

        return results

    async def extract_from_context(self, context) -> dict:
        """
        Extract tokens from browser context (cookies).

        Args:
            context: Playwright browser context

        Returns:
            Dict with found cookies and tokens
        """
        results = {
            "cookies": [],
            "tokens_found": [],
        }

        try:
            cookies = await context.cookies()
            results["cookies"] = cookies

            token_keywords = ["token", "jwt", "auth", "bearer", "access", "session"]

            for cookie in cookies:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                domain = cookie.get("domain", "")

                # Only check orion-related cookies
                if "orion" not in domain.lower():
                    continue

                is_token_key = any(kw in name.lower() for kw in token_keywords)
                is_jwt = self.is_jwt(value)

                if is_token_key or is_jwt:
                    token_info = {
                        "source": f"cookie.{name}",
                        "domain": domain,
                        "value": value[:50] + "..." if len(value) > 50 else value,
                        "is_jwt": is_jwt,
                    }
                    results["tokens_found"].append(token_info)

                    if is_jwt:
                        self.captured_tokens[f"cookie_{name}"] = {
                            "token": value,
                            "url": domain,
                            "timestamp": datetime.now().isoformat(),
                        }

        except Exception as e:
            results["error"] = str(e)

        return results

    def get_best_token(self) -> Optional[str]:
        """Get the best available token (prefer request headers)."""
        priority_order = [
            "request_header",
            "cookie_token",
            "cookie_access_token",
            "localStorage_token",
            "localStorage_access_token",
            "sessionStorage_token",
            "sessionStorage_access_token",
        ]

        # Check priority order first
        for source in priority_order:
            if source in self.captured_tokens:
                return self.captured_tokens[source]["token"]

        # Return any token found
        if self.captured_tokens:
            return list(self.captured_tokens.values())[0]["token"]

        return None

    def get_all_tokens(self) -> Dict[str, dict]:
        """Get all captured tokens."""
        return self.captured_tokens.copy()

    def clear(self):
        """Clear all captured tokens."""
        self.captured_tokens.clear()
        self.api_requests.clear()


# Global instance for easy access
_token_capture = TokenCapture()


def get_token_capture() -> TokenCapture:
    """Get the global TokenCapture instance."""
    return _token_capture


async def extract_orion_token(browser_manager) -> Optional[str]:
    """
    Convenience function to extract Orion token from a BrowserManager instance.

    Args:
        browser_manager: BrowserManager instance with active session

    Returns:
        Bearer token string if found, None otherwise
    """
    capture = get_token_capture()

    if browser_manager.page:
        await capture.extract_from_page(browser_manager.page)

    if browser_manager.context:
        await capture.extract_from_context(browser_manager.context)

    return capture.get_best_token()
