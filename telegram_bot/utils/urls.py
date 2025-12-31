"""URL generation utilities for chat links."""

import os
import socket
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_cloudflare_url() -> str | None:
    """Get Cloudflare tunnel URL from environment or file."""
    # Check environment variable first
    url = os.environ.get("CLOUDFLARE_TUNNEL_URL")
    if url:
        logger.debug(f"Using Cloudflare URL from env: {url}")
        return url.rstrip("/")

    # Check tunnel URL file (written by cloudflare-quick-tunnel.bat)
    tunnel_file = Path(__file__).parent.parent.parent / "data" / "tunnel_url.txt"
    logger.debug(f"Checking tunnel URL file: {tunnel_file}")

    if tunnel_file.exists():
        try:
            # Read with UTF-8 and handle BOM
            content = tunnel_file.read_text(encoding="utf-8-sig").strip()
            # Also strip any null bytes or weird characters
            url = content.replace('\x00', '').strip()
            logger.debug(f"Tunnel file content: '{url}'")
            if url and (url.startswith("http://") or url.startswith("https://")):
                logger.info(f"Using Cloudflare URL from file: {url}")
                return url.rstrip("/")
            else:
                logger.warning(f"Tunnel file exists but content is invalid: '{url}'")
        except Exception as e:
            logger.warning(f"Failed to read tunnel URL file: {e}")
    else:
        logger.debug(f"Tunnel URL file not found: {tunnel_file}")

    return None


def get_local_ip() -> str | None:
    """Get local IP address, preferring Ethernet over Wi-Fi."""
    # Try PowerShell method (Windows)
    try:
        ps_command = """
        $ips = Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object {
                $_.AddressState -eq 'Preferred' -and
                $_.IPAddress -notlike '127.*' -and
                $_.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN|Ethernet' -and
                $_.InterfaceAlias -notmatch 'VMware|VirtualBox|vEthernet|Hyper-V|WSL'
            }
        $ethernet = $ips | Where-Object { $_.InterfaceAlias -match 'Ethernet' } | Select-Object -First 1
        if ($ethernet) {
            Write-Host $ethernet.IPAddress
        } else {
            $wifi = $ips | Where-Object { $_.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN' } | Select-Object -First 1
            if ($wifi) {
                Write-Host $wifi.IPAddress
            }
        }
        """
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=5
        )
        ip = result.stdout.strip()
        if ip and not ip.startswith("127."):
            return ip
    except Exception as e:
        logger.debug(f"PowerShell IP detection failed: {e}")

    # Fallback: socket method (cross-platform)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127."):
            return ip
    except Exception as e:
        logger.debug(f"Socket IP detection failed: {e}")

    return None


def get_base_url() -> str:
    """Get the best available base URL for the web UI.

    Priority:
    1. Cloudflare Tunnel URL (if running)
    2. Local network IP (Ethernet preferred over Wi-Fi)
    3. Localhost (fallback)
    """
    # 1. Check for Cloudflare tunnel URL
    cloudflare_url = get_cloudflare_url()
    if cloudflare_url:
        logger.info(f"Using Cloudflare URL: {cloudflare_url}")
        return cloudflare_url

    # 2. Try local network IP
    local_ip = get_local_ip()
    if local_ip:
        url = f"http://{local_ip}:3000"
        logger.info(f"Using local IP: {url}")
        return url

    # 3. Fallback to localhost
    logger.info("Using localhost fallback")
    return "http://localhost:3000"


def build_chat_url(chat_id: str) -> str:
    """Build full URL to a specific chat."""
    base_url = get_base_url()
    return f"{base_url}/chat/{chat_id}"
