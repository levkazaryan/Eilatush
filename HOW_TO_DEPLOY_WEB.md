# Eilatush Web (PWA) — Deployment Guide

## 📦 What is this?

The static web bundle of the Eilatush mobile app — a Progressive Web App (PWA)
that runs in any browser, can be installed to a phone's home screen, and works
offline. It shares the **exact same backend and database** as the Android app.

After running `yarn build:web` the entire site lives in `/app/frontend/dist`.
You can upload that folder to any static host.

---

## 🛡️ Will this break the Android app?

**No.** The web build is completely isolated from the Android pipeline:

| File / change                        | Used by                          |
|--------------------------------------|----------------------------------|
| `app/+html.tsx`                      | Web export only (Expo convention)|
| `public/*` (manifest, SW, icons, OG) | Web export only — copied to /dist|
| `components/PWAInstallBanner.tsx`    | Renders `null` on native (Platform.OS check) |
| `scripts/copy-public.js`             | Web build script only             |
| `yarn build:web` script              | Web only — never runs in EAS Build |

The EAS Android pipeline still produces the **exact same AAB** — none of the
above files are bundled into native. ✅

---

## 🌐 Deploying to Cloudflare Pages (RECOMMENDED)

Best for free, global, fast, automatic HTTPS and custom domains.

### Step 1 — Push the `dist/` folder to a Git repo
```bash
# Option A — separate repo for the web build
cd /app/frontend/dist
git init && git add -A && git commit -m "web: initial PWA build"
gh repo create eilatush-web --public --source=. --push

# Option B — use the main monorepo, point Cloudflare to /frontend/dist
```

### Step 2 — Connect Cloudflare Pages
1. Go to https://dash.cloudflare.com/ → **Workers & Pages → Create application → Pages → Connect to Git**
2. Pick your repo
3. **Build command**: `yarn build:web` (or leave empty if uploading prebuilt `/dist`)
4. **Build output directory**: `frontend/dist` (or just `dist` if you uploaded option A)
5. Click Deploy. Site live in ~30s.

### Step 3 — Connect your custom domain
1. **Custom domains** tab → Add `eilatush.co.il`
2. Cloudflare gives you a CNAME → add it in your DNS provider's panel
3. HTTPS auto-issued. Done.

✅ The `_redirects` and `_headers` files in /dist are read **automatically** by Cloudflare Pages. No further config needed.

---

## 🌐 Deploying to Netlify

Identical to Cloudflare Pages — they share the `_redirects` + `_headers` format.

1. **Netlify dashboard** → New site from Git → pick repo
2. **Build command**: `cd frontend && yarn install && yarn build:web`
3. **Publish directory**: `frontend/dist`
4. Deploy

`_redirects` and `_headers` are picked up automatically.

---

## 🌐 Deploying to plain cPanel / shared hosting (Apache)

If your existing hosting is shared cPanel (most Israeli hosts) and uses Apache:

### Step 1 — Upload `/app/frontend/dist/*` to `public_html/`
Use FTP, File Manager, or rsync. **Important**: also upload `.htaccess` and `_redirects` even though they look like hidden files.

### Step 2 — Verify mod_rewrite is enabled
Most hosts have it on by default. If not, ask your hosting support to enable
`mod_rewrite` and `mod_headers`.

The provided `.htaccess` file handles:
- HTTPS redirect
- Clean URL rewrites (`/businesses` → `/businesses.html`)
- Dynamic routes (`/business/:id` → `/business/[id].html`)
- SPA fallback for unknown paths
- Service worker no-cache
- Long cache for hashed assets

### Step 3 — Point your domain to the public_html directory
Standard DNS A-record / nameserver config in your domain registrar's panel.

---

## 🌐 Deploying to Nginx (VPS / Hetzner / DigitalOcean)

```nginx
server {
    listen 443 ssl http2;
    server_name eilatush.co.il www.eilatush.co.il;
    root /var/www/eilatush;
    index index.html;

    # Service worker never cached
    location = /service-worker.js {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Service-Worker-Allowed "/";
        try_files $uri =404;
    }

    # Manifest — short cache
    location = /manifest.webmanifest {
        add_header Cache-Control "public, max-age=3600";
        try_files $uri =404;
    }

    # Hashed Expo bundles — immutable
    location /_expo/static/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
        try_files $uri =404;
    }

    # Long-cache for icons and OG image
    location ~* \.(png|jpg|jpeg|webp|svg|ico)$ {
        add_header Cache-Control "public, max-age=2592000";
        try_files $uri =404;
    }

    # Dynamic routes — serve the [id].html template
    location ~ ^/business/[^/]+/?$ { try_files /business/[id].html =404; }
    location ~ ^/article/[^/]+/?$  { try_files /article/[id].html  =404; }
    location ~ ^/job/[^/]+/?$      { try_files /job/[id].html      =404; }

    # Clean URLs — try .html extension first, then SPA fallback
    location / {
        try_files $uri $uri/ $uri.html /index.html;
    }
}
```

---

## ⚠️ Backend CORS check

Your backend at `https://eilat-connect.emergent.host` **already** allows all
origins (`CORSMiddleware allow_origins=["*"]` in server.py).

This means the web frontend on any domain (eilatush.co.il, eilatush.app, etc.)
can call `/api/*` endpoints without modification.

If you ever want to **tighten** CORS to your specific domains for security,
edit `backend/server.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://eilatush.co.il",
        "https://www.eilatush.co.il",
        "capacitor://localhost",  # for Android WebView if needed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

But for now, the default `*` works fine.

---

## 🧪 Testing the PWA before deploy

### Lighthouse audit
1. Open Chrome → DevTools → Lighthouse tab
2. Run audit on `https://eilatush.co.il`
3. Target scores: **Performance > 80, PWA = 100, SEO = 100**

### Install test on Android
1. Visit the URL in Chrome
2. After 30s of interaction the install banner should slide up
3. Tap "התקנה" → native dialog appears → install
4. App icon should appear on home screen
5. Opening it should look exactly like the Play Store version

### Install test on iOS
1. Open URL in Safari (NOT Chrome — Chrome iOS doesn't support PWAs)
2. Tap Share button → "Add to Home Screen"
3. Icon appears → opens in fullscreen

### Share preview test
Open https://opengraph.dev and paste `https://eilatush.co.il` — should show the
1200×630 dolphin image with title and tagline.

---

## 🚦 Standard deploy flow (after first setup)

```bash
# 1) Build
cd /app/frontend
yarn build:web

# 2) Upload /dist contents to your host
# (Cloudflare Pages / Netlify do this automatically on git push)
# (cPanel: FTP or File Manager upload)

# 3) Hard-refresh your browser to bust the service worker cache
```

Service worker auto-updates on the next visit (it cache-busts the SW file via
the `Cache-Control: no-cache` rule, so users get the new version within seconds).

---

## 🔗 What to share publicly

**Single URL** that works everywhere:
```
https://eilatush.co.il
```

- Android users → can install as PWA OR get the Play Store version (link to Play Store from the site if you want)
- iOS users → can install as PWA (no App Store dependency)
- Desktop users → can use it in any browser

Post this to WhatsApp groups, Facebook, Instagram — the OG preview will look
beautiful (blue gradient + dolphin + Hebrew tagline).

---

## 💡 Recommended hosting

| Host                    | Cost      | Best for             |
|-------------------------|-----------|----------------------|
| **Cloudflare Pages**    | Free      | RECOMMENDED — global CDN, free custom domains, free HTTPS, auto-deploy from Git |
| Netlify                 | Free tier | Identical to CF Pages, slightly simpler UI |
| Vercel                  | Free tier | Excellent but Vercel optimizes for Next.js — overkill for static |
| cPanel / shared hosting | Whatever you pay | If you already own one; uses `.htaccess` |
| Nginx VPS               | $5+/mo    | If you want full control |

My recommendation: **Cloudflare Pages**. Free, fast, native PWA support, custom
domain in 2 minutes.
