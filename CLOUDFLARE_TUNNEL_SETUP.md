# Cloudflare Tunnel Setup Guide

Access your Lab Assistant AI from anywhere on the internet using Cloudflare Tunnel.
This provides a secure, permanent URL without opening ports on your router.

## Prerequisites

1. **Free Cloudflare Account**
   - Sign up at https://dash.cloudflare.com/sign-up
   - No credit card required

2. **Windows 10/11**
   - The setup scripts are designed for Windows

## Quick Start

### Step 1: Run Setup

Double-click `cloudflare-tunnel-setup.bat` or run from command prompt:

```batch
cloudflare-tunnel-setup.bat
```

The setup will:
1. Install `cloudflared` if not present (via winget)
2. Open a browser to log into your Cloudflare account
3. Create a tunnel named `lab-assistant`
4. Generate the configuration file

### Step 2: Start the Tunnel

**Option A: With start-dev.bat (Recommended)**

```batch
start-dev.bat
```

When prompted, press `Y` to start the tunnel with the application.

Or use the `--tunnel` flag to start automatically:

```batch
start-dev.bat --tunnel
```

**Option B: Standalone**

```batch
cloudflare-tunnel-run.bat
```

### Step 3: Access Your App

Your permanent URL will be:
```
https://<tunnel-id>.cfargotunnel.com
```

The tunnel ID is shown during setup and in the startup summary.

## Command Reference

| Script | Description |
|--------|-------------|
| `cloudflare-tunnel-setup.bat` | First-time setup (run once) |
| `cloudflare-tunnel-run.bat` | Start tunnel manually |
| `cloudflare-tunnel-service.bat` | Install as Windows service (auto-start) |
| `start-dev.bat` | Start app with optional tunnel |
| `start-dev.bat --tunnel` | Start app + tunnel automatically |
| `start-dev.bat --no-tunnel` | Start app without tunnel prompt |

## Installing as Windows Service

To have the tunnel start automatically with Windows:

1. Run as Administrator:
   ```batch
   cloudflare-tunnel-service.bat
   ```

2. Manage the service:
   ```batch
   net start cloudflared   # Start
   net stop cloudflared    # Stop
   cloudflared service uninstall  # Remove
   ```

## Custom Domain (Optional)

If you have a domain on Cloudflare, you can add a custom hostname:

1. Go to https://dash.cloudflare.com
2. Select your domain > DNS
3. Add a CNAME record:
   - Name: `lab` (or whatever subdomain you want)
   - Target: `<tunnel-id>.cfargotunnel.com`
   - Proxy: Enabled (orange cloud)

4. Update `%USERPROFILE%\.cloudflared\config.yml`:
   ```yaml
   tunnel: lab-assistant
   credentials-file: ...

   ingress:
     - hostname: lab.yourdomain.com
       service: http://localhost:3000
     - service: http_status:404
   ```

5. Restart the tunnel

## Troubleshooting

### "cloudflared not found"

Install manually from:
https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/

Or via winget:
```batch
winget install Cloudflare.cloudflared
```

### "Login failed"

1. Make sure you're logged into Cloudflare in your browser
2. Check that pop-ups aren't blocked
3. Try running the setup script again

### "Tunnel not connecting"

1. Check your internet connection
2. Verify the tunnel exists:
   ```batch
   cloudflared tunnel list
   ```
3. Check the config file at `%USERPROFILE%\.cloudflared\config.yml`

### "Connection refused" on remote access

1. Make sure the frontend is running on port 3000
2. Check that the tunnel is running (green window)
3. Verify the URL is correct

## Security Notes

1. **Authentication**: Enable NextAuth.js for secure access (configured in `.env.local`)
2. **Email Whitelist**: Add `ALLOWED_EMAILS` in `.env.local` to restrict access
3. **Tunnel Access**: Only you can create tunnels on your Cloudflare account
4. **Data**: All traffic is encrypted via Cloudflare

## Files Created

| File | Location | Purpose |
|------|----------|---------|
| `cert.pem` | `%USERPROFILE%\.cloudflared\` | Cloudflare authentication |
| `config.yml` | `%USERPROFILE%\.cloudflared\` | Tunnel configuration |
| `<tunnel-id>.json` | `%USERPROFILE%\.cloudflared\` | Tunnel credentials |

## Uninstalling

1. Remove service (if installed):
   ```batch
   cloudflared service uninstall
   ```

2. Delete tunnel:
   ```batch
   cloudflared tunnel delete lab-assistant
   ```

3. Remove cloudflared:
   ```batch
   winget uninstall Cloudflare.cloudflared
   ```

4. Delete config files:
   ```batch
   rmdir /s /q "%USERPROFILE%\.cloudflared"
   ```
