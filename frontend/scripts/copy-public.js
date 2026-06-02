#!/usr/bin/env node
/**
 * After `expo export --platform web`, Expo writes the SSG bundle to /dist.
 * This script copies our static PWA assets (manifest, service worker, icons,
 * og-image) from /public into /dist so they're served from the site root.
 *
 * Run automatically as part of `yarn build:web`.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.resolve(__dirname, "..", "public");
const DEST = path.resolve(__dirname, "..", "dist");

if (!fs.existsSync(SRC)) {
  console.warn(`[copy-public] source dir not found: ${SRC} — skipping`);
  process.exit(0);
}
if (!fs.existsSync(DEST)) {
  console.error(`[copy-public] dist dir not found at ${DEST}. Run \`expo export --platform web\` first.`);
  process.exit(1);
}

function copyRecursive(src, dest) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
  } else {
    fs.copyFileSync(src, dest);
    console.log(`[copy-public] ${path.relative(process.cwd(), dest)}`);
  }
}

let count = 0;
for (const entry of fs.readdirSync(SRC)) {
  copyRecursive(path.join(SRC, entry), path.join(DEST, entry));
  count++;
}
console.log(`[copy-public] copied ${count} item(s) from /public → /dist`);
