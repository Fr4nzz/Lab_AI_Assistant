# Cloudflare Named Tunnel Setup Guide

This guide walks you through setting up a **permanent Cloudflare Tunnel** with a stable URL that doesn't change on restart.

## Quick Tunnel vs Named Tunnel

| Feature | Quick Tunnel | Named Tunnel |
|---------|--------------|--------------|
| URL | Random `*.trycloudflare.com` | Your custom domain |
| Persistence | Changes every restart | Permanent |
| Setup | None | One-time setup |
| Cost | Free | Free |
| Best for | Testing, development | Production |

---

## Prerequisites

1. **Cloudflare Account** (free): https://dash.cloudflare.com/sign-up
2. **A domain** added to Cloudflare (free tier works)
   - You can buy a domain from Cloudflare (~$10/year for `.com`)
   - Or transfer an existing domain to use Cloudflare DNS

---

## Step 1: Install Cloudflared

### Option A: Using the Setup Script
```batch
.\cloudflare-tunnel-setup.bat
```
This will install cloudflared automatically if not found.

### Option B: Manual Installation
```powershell
winget install Cloudflare.cloudflared
```

Verify installation:
```powershell
cloudflared --version
```

---

## Step 2: Authenticate with Cloudflare

Run:
```powershell
cloudflared tunnel login
```

This will:
1. Open your browser
2. Ask you to log in to Cloudflare
3. Ask you to select a domain (zone) for the tunnel
4. Save a certificate to `%USERPROFILE%\.cloudflared\cert.pem`

---

## Step 3: Create the Tunnel

```powershell
cloudflared tunnel create lab-assistant
```

This creates:
- A tunnel with ID (UUID)
- Credentials file at `%USERPROFILE%\.cloudflared\<TUNNEL_ID>.json`

To see your tunnels:
```powershell
cloudflared tunnel list
```

---

## Step 4: Create DNS Record

Route a subdomain to your tunnel:

```powershell
cloudflared tunnel route dns lab-assistant lab.yourdomain.com
```

Replace `yourdomain.com` with your actual domain.

This creates a CNAME record in Cloudflare DNS pointing to your tunnel.

---

## Step 5: Create Configuration File

Create `%USERPROFILE%\.cloudflared\config.yml`:

```yaml
tunnel: lab-assistant
credentials-file: C:\Users\YourUsername\.cloudflared\<TUNNEL_ID>.json

ingress:
  - hostname: lab.yourdomain.com
    service: http://localhost:3000
  - service: http_status:404
```

**Important:** Replace:
- `YourUsername` with your Windows username
- `<TUNNEL_ID>` with your actual tunnel UUID
- `lab.yourdomain.com` with your chosen subdomain

---

## Step 6: Test the Tunnel

Start the tunnel manually:
```powershell
cloudflared tunnel run lab-assistant
```

Visit `https://lab.yourdomain.com` - it should connect to your local app!

---

## Step 7: Run with Lab Assistant

### Option A: Use the Run Script
```batch
.\cloudflare-tunnel-run.bat
```

### Option B: Install as Windows Service (Recommended)
Run as Administrator:
```batch
.\cloudflare-tunnel-service.bat
```

This makes the tunnel start automatically with Windows.

---

## Managing the Service

If installed as a Windows service:

```powershell
# Start the tunnel
net start cloudflared

# Stop the tunnel
net stop cloudflared

# Check status
sc query cloudflared

# Uninstall service
cloudflared service uninstall
```

---

## Troubleshooting

### Check tunnel status
```powershell
cloudflared tunnel info lab-assistant
```

### View logs
```powershell
cloudflared tunnel run lab-assistant --loglevel debug
```

### Common Issues

**"Tunnel credentials file not found"**
- Verify the path in `config.yml` matches your actual credentials file

**"No ingress rules match"**
- Make sure your config.yml has the correct hostname

**"DNS record not found"**
- Run: `cloudflared tunnel route dns lab-assistant your-subdomain.yourdomain.com`

**"Connection refused"**
- Make sure your local app is running on port 3000

---

## Multiple Services (Advanced)

You can route multiple services through one tunnel:

```yaml
tunnel: lab-assistant
credentials-file: C:\Users\YourUsername\.cloudflared\<TUNNEL_ID>.json

ingress:
  # Main app
  - hostname: lab.yourdomain.com
    service: http://localhost:3000

  # API (if separate)
  - hostname: api.yourdomain.com
    service: http://localhost:8000

  # Catch-all (required)
  - service: http_status:404
```

---

## Security Notes

1. **Keep credentials secret**: Never share your tunnel credentials file
2. **Use Access policies**: You can add Cloudflare Access to require authentication
3. **Monitor access**: Check Cloudflare dashboard for traffic logs

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `cloudflared tunnel login` | Authenticate with Cloudflare |
| `cloudflared tunnel create NAME` | Create a new tunnel |
| `cloudflared tunnel list` | List all tunnels |
| `cloudflared tunnel route dns NAME HOSTNAME` | Create DNS record |
| `cloudflared tunnel run NAME` | Start the tunnel |
| `cloudflared tunnel delete NAME` | Delete a tunnel |
| `cloudflared service install` | Install as Windows service |
| `cloudflared service uninstall` | Remove Windows service |

---

## Files Location

| File | Location |
|------|----------|
| Certificate | `%USERPROFILE%\.cloudflared\cert.pem` |
| Credentials | `%USERPROFILE%\.cloudflared\<TUNNEL_ID>.json` |
| Config | `%USERPROFILE%\.cloudflared\config.yml` |

---

## Need Help?

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Cloudflare Community](https://community.cloudflare.com/)
