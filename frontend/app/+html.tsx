// @ts-nocheck
import { ScrollViewStyleReset } from "expo-router/html";
import type { PropsWithChildren } from "react";

/**
 * Root HTML wrapper served for ALL web routes.
 *
 * Includes the full PWA + Open Graph + Twitter Card meta-tag set so:
 *   • Chrome / Edge / Samsung Internet show the "Install" prompt
 *   • iOS Safari treats it as a "Web App" when added to home screen
 *   • WhatsApp / Facebook / X show a rich share preview
 *   • Google indexes the site properly for search
 */
export default function Root({ children }: PropsWithChildren) {
  return (
    <html lang="he" dir="rtl" style={{ height: "100%" }}>
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, shrink-to-fit=no, viewport-fit=cover"
        />

        {/* ── Core SEO ─────────────────────────────────────────────────── */}
        <title>אילתוש — כל מה שקורה באילת, במקום אחד 🐬</title>
        <meta
          name="description"
          content="אילתוש מרכזת במקום אחד את כל מה שקורה באילת: אירועים, עסקים, חדשות, משרות ועוזרת AI חכמה בעברית. כל המידע ממקורות רשמיים."
        />
        <meta
          name="keywords"
          content="אילתוש, אילת, אירועים באילת, עסקים באילת, חדשות אילת, משרות אילת, מה לעשות באילת, אפליקציה אילת"
        />
        <meta name="author" content="Lev Kazaryan" />
        <link rel="canonical" href="https://eilatush.emergent.host/" />

        {/* ── PWA manifest ─────────────────────────────────────────────── */}
        <link rel="manifest" href="/manifest.webmanifest" />
        <meta name="theme-color" content="#0172E5" />
        <meta name="application-name" content="אילתוש" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="אילתוש" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="format-detection" content="telephone=yes" />

        {/* ── Favicons & touch icons ───────────────────────────────────── */}
        <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />
        <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        <link rel="apple-touch-icon" sizes="152x152" href="/icon-152.png" />
        <link rel="apple-touch-icon" sizes="180x180" href="/icon-180.png" />
        <link rel="shortcut icon" href="/favicon-32.png" />

        {/* ── Open Graph (WhatsApp / Facebook / LinkedIn share) ────────── */}
        <meta property="og:type" content="website" />
        <meta property="og:site_name" content="אילתוש" />
        <meta property="og:title" content="אילתוש — כל מה שקורה באילת, במקום אחד 🐬" />
        <meta
          property="og:description"
          content="אירועים, עסקים, חדשות, משרות ועוזרת AI חכמה בעברית — הכל באפליקציה אחת."
        />
        <meta property="og:image" content="https://eilatush.emergent.host/og-image.jpg" />
        <meta property="og:image:width" content="1200" />
        <meta property="og:image:height" content="630" />
        <meta property="og:image:alt" content="אילתוש — הדולפין המקומי של אילת" />
        <meta property="og:locale" content="he_IL" />
        <meta property="og:url" content="https://eilatush.emergent.host/" />

        {/* ── Twitter / X Cards ─────────────────────────────────────────── */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="אילתוש — כל מה שקורה באילת 🐬" />
        <meta
          name="twitter:description"
          content="אירועים, עסקים, חדשות, משרות ועוזרת AI חכמה. הכל באפליקציה אחת."
        />
        <meta name="twitter:image" content="https://eilatush.emergent.host/og-image.jpg" />

        {/*
          Disable body scrolling on web so RN ScrollView components work correctly.
        */}
        <ScrollViewStyleReset />
        <style
          dangerouslySetInnerHTML={{
            __html: `
              /* Fix for RN-Web root container */
              body > div:first-child {
                position: fixed !important; top: 0; left: 0; right: 0; bottom: 0;
              }
              [role="tablist"] [role="tab"] * { overflow: visible !important; }
              [role="heading"], [role="heading"] * { overflow: visible !important; }

              /* Reset the install prompt animation */
              @keyframes eilatushSlideUp {
                from { transform: translateY(120%); opacity: 0; }
                to   { transform: translateY(0);    opacity: 1; }
              }

              /* On wide screens, center the app inside a phone-frame */
              @media (min-width: 768px) {
                html { background: linear-gradient(135deg, #0172E5 0%, #14B8B3 100%); }
                body > div:first-child {
                  max-width: 480px !important;
                  margin: 0 auto !important;
                  box-shadow: 0 10px 60px rgba(0,0,0,0.30);
                  border-radius: 24px;
                  overflow: hidden;
                  top: 16px !important;
                  bottom: 16px !important;
                }
              }
            `,
          }}
        />
      </head>
      <body
        style={{
          margin: 0,
          height: "100%",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          backgroundColor: "#F7F8FA",
        }}
      >
        {/* Service Worker registration — quietly registers SW for offline + install prompts */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                  navigator.serviceWorker.register('/service-worker.js', { scope: '/' })
                    .then(function(reg) {
                      // console.log('[Eilatush] SW registered:', reg.scope);
                    })
                    .catch(function(err) {
                      console.warn('[Eilatush] SW registration failed:', err);
                    });
                });
              }

              // Capture the install prompt for our custom UI to trigger later
              window.addEventListener('beforeinstallprompt', function(e) {
                e.preventDefault();
                window.__eilatushDeferredPrompt = e;
                window.dispatchEvent(new CustomEvent('eilatush:installable'));
              });

              window.addEventListener('appinstalled', function() {
                window.__eilatushDeferredPrompt = null;
                try { localStorage.setItem('eilatush_pwa_installed', '1'); } catch (_) {}
              });
            `,
          }}
        />
        {children}
      </body>
    </html>
  );
}
