# 🚀 Web Deploy to Hostinger — Setup Guide

This repo auto-deploys the **PWA web version** to Hostinger every time you push to `main`
that touches `frontend/**`.

The Android Play Store build runs in parallel (`android-build.yml`) — both fire from the same push.

---

## 📋 One-time Setup — Add GitHub Secrets

Go to: **https://github.com/levkazaryan/Eilatush/settings/secrets/actions**

Click **"New repository secret"** and add these **4 secrets** one by one:

| Secret Name | Value | Notes |
|---|---|---|
| `HOSTINGER_FTP_HOST` | `92.112.189.182` | IP from hPanel → FTP Accounts |
| `HOSTINGER_FTP_USERNAME` | `u143568904.eilatush.app` | Your FTP username from hPanel |
| `HOSTINGER_FTP_PASSWORD` | `<the password you set in hPanel>` | Set via "Change FTP password" |
| `HOSTINGER_FTP_REMOTE_PATH` | `/public_html/` | Where files go on the server |

> ⚠️ **Important — never paste the password into code or chat.** Only into GitHub Secrets (they're encrypted at rest).

You should also already have these existing secrets (used by Android workflow):

- `EXPO_TOKEN` ✅
- `GOOGLE_SERVICE_ACCOUNT_KEY` ✅
- `EILATUSH_BACKEND_URL` ✅ (also reused by the web deploy for the build env)
- `EILATUSH_ADMIN_PASSWORD` ✅

---

## 🌐 Domain DNS Setup (GoDaddy → Hostinger)

You already started this on the Hostinger screen. After buying `eilatush.app` on GoDaddy:

1. **On GoDaddy**: My Products → eilatush.app → **DNS → Nameservers → Change**
2. Choose **"I'll use my own nameservers"**
3. Replace with Hostinger's:
   ```
   aurora.dns-parking.com
   nebula.dns-parking.com
   ```
4. Save. Propagation takes 5min – 2h (rarely up to 24h).

Then back on Hostinger:
- **Websites → eilatush.app → Security → SSL** → Install free Let's Encrypt SSL
- Wait ~5 min for SSL provisioning

---

## 🧪 Test the First Deploy

After secrets are added and DNS resolves to Hostinger:

**Option A — Manual run (recommended for first time):**
1. Go to: https://github.com/levkazaryan/Eilatush/actions
2. Click **"Web PWA Deploy (Hostinger FTP)"** (left sidebar)
3. Click **"Run workflow"** → branch `main` → **Run workflow**
4. Watch it run. Should take ~3-5 min.

**Option B — Just push a frontend change:**
```bash
git add . && git commit -m "trigger web deploy" && git push origin main
```

Both `android-build` AND `web-deploy` workflows will fire in parallel.

---

## 🔍 Verify

After the workflow goes green:

1. Visit **https://eilatush.app** — should load the PWA
2. On a mobile browser → tap "Add to Home Screen" → check it installs with the dolphin icon
3. View source → verify these are the production values:
   - `<link rel="canonical" href="https://eilatush.app/" />`
   - `<meta property="og:url" content="https://eilatush.app/" />`
   - Service Worker registered

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| FTP login fails | Re-check the **password** in hPanel — sometimes the IP changes when you migrate plans. Update `HOSTINGER_FTP_HOST` secret if needed. |
| Files deploy but site shows Hostinger placeholder | hPanel → File Manager → `public_html/` — delete `default.php`, `index.html` (Hostinger's placeholder). Or first deploy will overwrite them. |
| HTTPS not working | hPanel → SSL → Install Lifetime SSL → wait 5 min |
| PWA routes return 404 (e.g. `/jobs`) | Make sure `.htaccess` is uploaded (it is, automatically). Check **hPanel → File Manager → public_html/.htaccess** exists. |
| Old version shown after deploy | Service Worker cache. Hard refresh (Cmd+Shift+R) once. |

---

## 🔁 How It Works

```
git push main
    ↓
GitHub detects changes in frontend/**
    ↓
Two workflows run in parallel:
    ├─ android-build.yml → EAS Build → Auto-submit to Play Store (internal track)
    └─ web-deploy.yml    → yarn build:web → FTP upload to Hostinger
                                              ↓
                                       https://eilatush.app ✅
```
