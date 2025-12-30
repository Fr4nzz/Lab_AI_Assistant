# Remote Access & Authentication Setup

This guide explains how to set up Lab Assistant for remote access from any network, with Google OAuth authentication and admin controls.

## Overview

To access Lab Assistant from outside your local network, you need:
1. **Cloudflare Tunnel** - Exposes your local app to the internet (free)
2. **Google OAuth** - Handles user authentication
3. **Environment Configuration** - API keys and admin settings

## Prerequisites

- Lab Assistant running locally (see main README)
- A Google account (for OAuth setup)
- A Cloudflare account (free tier works)

---

## Step 1: Cloudflare Tunnel Setup

Cloudflare Tunnel creates a secure connection from your local machine to the internet without opening ports or configuring your router.

### 1.1 Install Cloudflared

**Option A: Using the setup script (Windows)**
```batch
cloudflare-tunnel-setup.bat
```
This will install cloudflared via winget if not present.

**Option B: Manual installation**
- Download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
- Or via winget: `winget install Cloudflare.cloudflared`

### 1.2 Login to Cloudflare

```batch
cloudflared tunnel login
```
A browser window opens. Log in to your Cloudflare account and authorize the connection.

### 1.3 Create a Tunnel

Run the setup script or manually:

```batch
:: Run the interactive setup
cloudflare-tunnel-setup.bat
```

Or manually:
```batch
cloudflared tunnel create lab-assistant
```

### 1.4 Get Your Tunnel URL

After setup, you'll get a permanent URL like:
```
https://xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.cfargotunnel.com
```

This URL points to your local `http://localhost:3000`.

### 1.5 Running the Tunnel

**Option A: Manual (for testing)**
```batch
cloudflare-tunnel-run.bat
```

**Option B: Windows Service (runs at startup)**
```batch
cloudflare-tunnel-service.bat
```

### 1.6 Custom Domain (Optional)

To use a custom domain like `lab.yourdomain.com`:

1. Add your domain to Cloudflare (free)
2. Edit `%USERPROFILE%\.cloudflared\config.yml`:
   ```yaml
   tunnel: lab-assistant
   credentials-file: C:\Users\YourUser\.cloudflared\xxxxx.json

   ingress:
     - hostname: lab.yourdomain.com
       service: http://localhost:3000
     - service: http_status:404
   ```
3. Create a CNAME record in Cloudflare DNS:
   - Name: `lab`
   - Target: `your-tunnel-id.cfargotunnel.com`
   - Proxied: Yes

---

## Step 2: Google OAuth Setup

Google OAuth allows users to log in with their Google account. Only emails you whitelist can access the app.

### 2.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Name it something like "Lab Assistant"

### 2.2 Configure OAuth Consent Screen

1. Go to **APIs & Services** > **OAuth consent screen**
2. Select **External** user type (unless you have Google Workspace)
3. Fill in the required fields:
   - App name: `Lab Assistant`
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue**
5. **Scopes**: Add `email`, `profile`, `openid`
6. **Test users**: Add your email (required for "Testing" status)
7. Click **Save and Continue**

### 2.3 Create OAuth Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. Application type: **Web application**
4. Name: `Lab Assistant Web`
5. **Authorized JavaScript origins**:
   ```
   http://localhost:3000
   https://your-tunnel-id.cfargotunnel.com
   ```
   (Add your custom domain if using one)

6. **Authorized redirect URIs**:
   ```
   http://localhost:3000/auth/google
   https://your-tunnel-id.cfargotunnel.com/auth/google
   ```

7. Click **Create**
8. **Copy the Client ID and Client Secret** - you'll need these!

### 2.4 Publish the App (Optional but Recommended)

While in "Testing" status, only test users you manually add can log in. To allow any Google account:

1. Go to **OAuth consent screen**
2. Click **PUBLISH APP**
3. Confirm the verification notice

> Note: For internal use, "Testing" status is fine - just add all your users to the test users list.

---

## Step 3: Environment Configuration

### 3.1 Create Frontend Environment File

```batch
cd frontend-nuxt
copy .env.example .env
```

### 3.2 Edit `.env` File

Open `frontend-nuxt/.env` and configure:

```bash
# Session security (generate a random 32+ character string)
# You can use: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
NUXT_SESSION_PASSWORD=your-super-secret-password-at-least-32-chars

# Google OAuth (from Step 2.3)
NUXT_OAUTH_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
NUXT_OAUTH_GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret

# User Access Control
# Comma-separated list of emails allowed to use the app
# Leave empty to allow all authenticated users (not recommended)
ALLOWED_EMAILS=user1@gmail.com,user2@gmail.com

# Admin emails - can manage allowed users and update the app
ADMIN_EMAILS=your-admin-email@gmail.com

# Optional: OpenRouter API key for chat topic naming
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

### 3.3 Generate Session Password

Run this command to generate a secure session password:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

Or use any password generator to create a 32+ character random string.

---

## Step 4: Where to Get All API Keys

| Key | Where to Get | Cost |
|-----|--------------|------|
| **Google OAuth Client ID/Secret** | [Google Cloud Console](https://console.cloud.google.com/) > APIs & Services > Credentials | Free |
| **Cloudflare Account** | [Cloudflare Dashboard](https://dash.cloudflare.com/) | Free |
| **Gemini API Keys** | [Google AI Studio](https://aistudio.google.com/apikey) | Free tier: 20 req/day/key |
| **OpenRouter API Key** | [OpenRouter](https://openrouter.ai/keys) | Pay-per-use (very cheap) |

---

## Step 5: Final Checklist

- [ ] Cloudflare Tunnel is running (`cloudflare-tunnel-run.bat`)
- [ ] Google OAuth credentials are configured in `.env`
- [ ] `NUXT_SESSION_PASSWORD` is set (32+ characters)
- [ ] `ADMIN_EMAILS` includes your email
- [ ] `ALLOWED_EMAILS` includes all authorized users
- [ ] Redirect URIs in Google Console include your tunnel URL

---

## Testing the Setup

1. Start the app: `start-dev.bat`
2. Start the tunnel: `cloudflare-tunnel-run.bat`
3. Open your tunnel URL in a browser
4. Click "Login with Google"
5. Authenticate with an allowed email
6. You should be redirected to the chat interface

---

## Troubleshooting

### "Email not authorized" error
- Add the email to `ALLOWED_EMAILS` in `.env`
- Or add to `ADMIN_EMAILS` (admins are always allowed)
- Restart the frontend after changing `.env`

### OAuth redirect error
- Verify the redirect URI in Google Console matches exactly:
  `https://your-tunnel-url/auth/google`
- Check for trailing slashes - they must match

### "Access blocked: App not verified"
- You're using "Testing" status - add the user to test users in Google Console
- Or publish the app (Step 2.4)

### Tunnel not connecting
- Check if cloudflared is running: `cloudflared tunnel list`
- Verify config file: `%USERPROFILE%\.cloudflared\config.yml`
- Try restarting: `cloudflare-tunnel-run.bat`

### Session issues after restart
- Make sure `NUXT_SESSION_PASSWORD` hasn't changed
- Clear browser cookies and log in again

---

## Security Notes

1. **Keep your `.env` file secret** - Never commit it to git
2. **Use strong session password** - At least 32 random characters
3. **Limit allowed emails** - Only add users who need access
4. **Admin emails have special powers** - They can add/remove users and trigger updates
5. **Cloudflare Tunnel is secure** - Traffic is encrypted end-to-end

---

## Quick Reference: Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NUXT_SESSION_PASSWORD` | Yes | Session encryption key (32+ chars) |
| `NUXT_OAUTH_GOOGLE_CLIENT_ID` | Yes* | Google OAuth client ID |
| `NUXT_OAUTH_GOOGLE_CLIENT_SECRET` | Yes* | Google OAuth client secret |
| `ALLOWED_EMAILS` | Recommended | Comma-separated allowed emails |
| `ADMIN_EMAILS` | Recommended | Comma-separated admin emails |
| `OPENROUTER_API_KEY` | No | For auto-generating chat titles |
| `BACKEND_URL` | No | Default: `http://localhost:8000` |

*Required for remote access with authentication
