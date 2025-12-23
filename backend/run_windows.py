"""Windows-specific runner for Lab Assistant."""
import asyncio
import sys

# MUST be set before any other imports on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    print("Starting Lab Assistant (Windows mode)...")
    print("Browser will open automatically. Please wait...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
