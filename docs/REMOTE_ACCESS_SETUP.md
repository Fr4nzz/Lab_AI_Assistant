# Remote Access & Authentication Setup

This guide explains how to set up Lab Assistant for remote access from any network, with Google OAuth authentication and admin controls.

## Overview

To access Lab Assistant from outside your local network, you need:
1. **Cloudflare Tunnel** - Exposes your local app to the internet (free)
2. **Google OAuth** - Handles user authentication (optional but recommended for security)
3. **Environment Configuration** - API keys and admin settings

## Prerequisites

- Lab Assistant running locally (see main README)
- A Google account (for OAuth setup)

---

## Step 1: Cloudflare Tunnel Setup

Cloudflare Tunnel creates a secure connection from your local machine to the internet without opening ports or configuring your router.

### Option A: Quick Tunnel (Easiest - Recommended for Testing)

**No account, no domain, completely free!**

1. Make sure Lab Assistant is running (`start-dev.bat`)

2. Run the quick tunnel script:
   ```batch
   .\cloudflare-quick-tunnel.bat
   ```

3. Look for the URL in the output:
   ```
   Your quick tunnel is ready!
   https://random-words-here.trycloudflare.com
   ```

4. Share this URL - anyone can access your app!

**Limitations of Quick Tunnels:**
- URL changes every time you restart the tunnel
- No SLA/uptime guarantee (meant for testing)
- 200 concurrent request limit
- Keep the terminal window open

> **Note**: Quick Tunnels work with our app's streaming chat because we use POST requests. See [Cloudflare Quick Tunnels docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/).

### Option B: Persistent Tunnel (Requires Domain)

For a **persistent URL** that never changes, you need a domain added to Cloudflare.

**Requirements:**
- A domain you own (can buy cheaply from [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/), Namecheap, etc.)
- Or a free subdomain from services like [FreeDNS](https://freedns.afraid.org/)

**Setup steps:**

1. Add your domain to Cloudflare (free account)
2. Run the setup script:
   ```batch
   .\cloudflare-tunnel-setup.bat
   ```
3. Follow the prompts to:
   - Login to Cloudflare
   - Create a tunnel
   - Configure the route

4. Run the tunnel:
   ```batch
   .\cloudflare-tunnel-run.bat
   ```

For detailed instructions, see [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/).

---

## Step 2: Google OAuth Setup (Optional but Recommended)

If you're exposing the app to the internet, you should enable authentication so only authorized users can access it.

### 2.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Name it something like "Lab Assistant"

### 2.2 Configure OAuth Consent Screen

1. Go to **APIs & Services** > **OAuth consent screen**
2. Select **External** user type
3. Fill in required fields:
   - App name: `Lab Assistant`
   - User support email: your email
   - Developer contact: your email
4. **Scopes**: Add `email`, `profile`, `openid`
5. **Test users**: Add your email (required while in "Testing" status)

### 2.3 Create OAuth Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. Application type: **Web application**
4. Name: `Lab Assistant Web`
5. **Authorized JavaScript origins**:
   ```
   http://localhost:3000
   https://your-tunnel-url.trycloudflare.com
   ```

6. **Authorized redirect URIs**:
   ```
   http://localhost:3000/auth/google
   https://your-tunnel-url.trycloudflare.com/auth/google
   ```

7. Click **Create** and copy the **Client ID** and **Client Secret**

> **Note for Quick Tunnels**: Since the URL changes, you'll need to update the redirect URIs each time. For production, use a persistent tunnel with a fixed domain.

### 2.4 Publish the App (Optional)

While in "Testing" status, only manually-added test users can log in. To allow any Google account:

1. Go to **OAuth consent screen**
2. Click **PUBLISH APP**

---

## Step 3: Environment Configuration

### 3.1 Create Environment File

```batch
cd frontend-nuxt
copy .env.example .env
```

### 3.2 Configure `.env` File

```bash
# Session security (REQUIRED - generate a random 32+ character string)
# Generate with: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
NUXT_SESSION_PASSWORD=your-super-secret-password-at-least-32-chars

# Google OAuth (required for authentication)
NUXT_OAUTH_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
NUXT_OAUTH_GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret

# User Access Control
# Comma-separated list of emails allowed to use the app
ALLOWED_EMAILS=user1@gmail.com,user2@gmail.com

# Admin emails - can manage users and trigger updates
ADMIN_EMAILS=your-admin-email@gmail.com

# Optional: OpenRouter API key for chat topic naming
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

### 3.3 Generate Session Password

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

---

## Step 4: Where to Get All API Keys

| Key | Where to Get | Cost |
|-----|--------------|------|
| **Google OAuth** | [Google Cloud Console](https://console.cloud.google.com/) | Free |
| **Gemini API Keys** | [Google AI Studio](https://aistudio.google.com/apikey) | Free (20/day/key) |
| **OpenRouter API** | [OpenRouter](https://openrouter.ai/keys) | Pay-per-use |
| **Cloudflare** | [Cloudflare Dashboard](https://dash.cloudflare.com/) | Free account |

---

## Quick Start Summary

### For Testing (5 minutes)

1. Start app: `.\start-dev.bat`
2. Start tunnel: `.\cloudflare-quick-tunnel.bat`
3. Share the `trycloudflare.com` URL
4. ✅ Done! (No auth, anyone with URL can access)

### For Production (30 minutes)

1. Configure `.env` with Google OAuth credentials
2. Add your email to `ADMIN_EMAILS`
3. Add allowed users to `ALLOWED_EMAILS`
4. Start app: `.\start-dev.bat`
5. Start tunnel: `.\cloudflare-quick-tunnel.bat` or use persistent tunnel
6. ✅ Done! (Only authorized Google accounts can access)

---

## Troubleshooting

### "Email not authorized" error
- Add the email to `ALLOWED_EMAILS` in `.env`
- Admins are always allowed automatically
- Restart frontend after changing `.env`

### OAuth redirect error
- Verify redirect URI matches exactly (including `https://`)
- For Quick Tunnels, update the URI when URL changes

### Tunnel URL not working
- Make sure `start-dev.bat` is running first (app on localhost:3000)
- Keep the tunnel terminal window open
- Check for firewall blocking cloudflared

### Streaming not working through tunnel
- Our app uses POST for streaming, which works with Quick Tunnels
- If issues persist, try a named tunnel instead

---

## Security Notes

1. **Keep `.env` secret** - Never commit to git
2. **Use OAuth for public access** - Don't expose without auth
3. **Limit allowed emails** - Only add users who need access
4. **Quick Tunnels are temporary** - URL changes provide some obscurity
5. **Admin powers** - Admins can add/remove users and update the app

---

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `cloudflare-quick-tunnel.bat` | Start free temporary tunnel (no setup needed) |
| `cloudflare-quick-tunnel-notify.bat` | Start tunnel + send URL via WhatsApp |
| `cloudflare-tunnel-setup.bat` | Configure persistent tunnel (needs domain) |
| `cloudflare-tunnel-run.bat` | Run configured persistent tunnel |
| `cloudflare-tunnel-service.bat` | Install tunnel as Windows service |

---

## WhatsApp URL Notification (Optional)

Want to automatically receive the tunnel URL on WhatsApp when it starts?

### Prerequisites

1. **WhatsApp Web logged in** - Go to [web.whatsapp.com](https://web.whatsapp.com) and scan the QR code
2. **Keep the browser open** - The script will use this session

### Usage

```batch
# Start the app first
.\start-dev.bat

# Start tunnel with WhatsApp notification
.\cloudflare-quick-tunnel-notify.bat +51987654321
```

Replace `+51987654321` with your phone number (with country code).

### What happens:

1. Starts the Quick Tunnel
2. Waits for the URL to appear
3. Opens WhatsApp Web and sends you the URL
4. Message: "🔗 Lab Assistant URL: https://xxx.trycloudflare.com"

### First time setup:

The script will auto-install `pywhatkit` if not present:
```
pip install pywhatkit
```

### Notes:

- The script opens a browser tab to send the message, then closes it
- Make sure WhatsApp Web is logged in before running
- Phone number must include country code (e.g., `+1` for US, `+51` for Peru)

---

## When Does the URL Change?

Quick Tunnel URLs persist as long as the `cloudflared` process is running:

| Event | URL Changes? |
|-------|--------------|
| Backend/Frontend restart (update button) | **No** ✅ |
| PC sleep/wake | **No** ✅ |
| PC restart | **Yes** ❌ |
| Close tunnel terminal window | **Yes** ❌ |
| Network reconnect | **Maybe** |

**Tip**: Keep the tunnel terminal window open. The URL can last for days/weeks!

---

## Sources

- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/)
- [Cloudflare Tunnel Setup](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [TryCloudflare](https://try.cloudflare.com/)
- [Quick Tunnel SSE Limitations](https://github.com/cloudflare/cloudflared/issues/1449) - Note: POST requests work fine
