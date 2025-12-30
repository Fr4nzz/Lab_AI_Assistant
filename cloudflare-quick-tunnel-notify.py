#!/usr/bin/env python3
"""
Quick Tunnel with WhatsApp Notification

Starts a Cloudflare Quick Tunnel and sends the URL via WhatsApp.
Requires: pip install pywhatkit

Usage:
    python cloudflare-quick-tunnel-notify.py +1234567890
    python cloudflare-quick-tunnel-notify.py +1234567890 --group "GroupName"

Prerequisites:
    1. WhatsApp Web must be logged in on your default browser
    2. cloudflared must be installed
"""

import subprocess
import sys
import re
import time
import os
import argparse

# Check if pywhatkit is installed
try:
    import pywhatkit as kit
except ImportError:
    print("Installing pywhatkit...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywhatkit"])
    import pywhatkit as kit


def find_cloudflared():
    """Find cloudflared executable."""
    # Check PATH
    try:
        result = subprocess.run(["where", "cloudflared"], capture_output=True, text=True)
        if result.returncode == 0:
            return "cloudflared"
    except:
        pass

    # Check common locations
    locations = [
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"),
        os.path.expandvars(r"%ProgramFiles%\cloudflared\cloudflared.exe"),
    ]
    for loc in locations:
        if os.path.exists(loc):
            return loc

    return None


def send_whatsapp(phone: str, message: str, is_group: bool = False):
    """Send WhatsApp message using pywhatkit."""
    try:
        if is_group:
            # For groups, use group ID (get from WhatsApp Web URL)
            kit.sendwhatmsg_to_group_instantly(phone, message, wait_time=15, tab_close=True)
        else:
            # For individual contacts
            kit.sendwhatmsg_instantly(phone, message, wait_time=15, tab_close=True)
        print(f"✓ WhatsApp message sent!")
        return True
    except Exception as e:
        print(f"✗ Failed to send WhatsApp: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Start Quick Tunnel and notify via WhatsApp")
    parser.add_argument("phone", nargs="?", default=None, help="Phone number with country code (e.g., +1234567890) or group ID")
    parser.add_argument("--group", "-g", action="store_true", help="Send to WhatsApp group instead of individual")
    parser.add_argument("--port", "-p", type=int, default=3000, help="Local port to tunnel (default: 3000)")
    parser.add_argument("--no-notify", action="store_true", help="Don't send WhatsApp notification")
    args = parser.parse_args()

    # Get phone from argument or environment variable
    phone = args.phone or os.environ.get("WHATSAPP_NOTIFY_PHONE")
    if not phone and not args.no_notify:
        print("Error: No phone number provided.")
        print("Either:")
        print("  1. Set WHATSAPP_NOTIFY_PHONE in .env")
        print("  2. Pass phone as argument: python cloudflare-quick-tunnel-notify.py +1234567890")
        print("  3. Use --no-notify to skip WhatsApp notification")
        sys.exit(1)

    # Find cloudflared
    cloudflared = find_cloudflared()
    if not cloudflared:
        print("Error: cloudflared not found. Run cloudflare-quick-tunnel.bat first to install.")
        sys.exit(1)

    print("=" * 50)
    print("   Cloudflare Quick Tunnel with WhatsApp Notify")
    print("=" * 50)
    print()
    print(f"Starting tunnel to http://localhost:{args.port}...")
    print("Looking for tunnel URL...")
    print()

    # Start cloudflared and capture output
    process = subprocess.Popen(
        [cloudflared, "tunnel", "--url", f"http://localhost:{args.port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    tunnel_url = None
    url_pattern = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')

    try:
        # Read output line by line
        for line in process.stdout:
            print(line, end='')  # Show cloudflared output

            # Look for the URL
            if not tunnel_url:
                match = url_pattern.search(line)
                if match:
                    tunnel_url = match.group(0)
                    print()
                    print("=" * 50)
                    print(f"🎉 TUNNEL URL: {tunnel_url}")
                    print("=" * 50)
                    print()

                    # Send WhatsApp notification
                    if not args.no_notify and phone:
                        message = f"🔗 Lab Assistant URL:\n{tunnel_url}\n\n(Quick Tunnel - URL may change on restart)"
                        print(f"Sending to WhatsApp: {phone}")
                        send_whatsapp(phone, message, args.group)

                    print()
                    print("Tunnel is running. Press Ctrl+C to stop.")
                    print()

        # Wait for process to finish
        process.wait()

    except KeyboardInterrupt:
        print("\nStopping tunnel...")
        process.terminate()
        process.wait()
        print("Tunnel stopped.")


if __name__ == "__main__":
    main()
