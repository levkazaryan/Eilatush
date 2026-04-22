#!/usr/bin/env node
/**
 * ensure-square-icons.js
 *
 * Runs on the EAS build server via the `eas-build-pre-install` hook.
 *
 * Problem: The Emergent deployment pipeline may inject a pre-downloaded app icon
 * that is NOT perfectly square (e.g. 512x513). Android build tools and
 * expo-doctor both REQUIRE square launcher icons. If an off-square icon is
 * uploaded, the AAB build fails.
 *
 * This script scans every PNG in assets/images/ that is referenced as an icon
 * and, if the dimensions are not square, pads it to the nearest larger square
 * using a solid background color that matches the app brand (#14B8B3). If the
 * image is already square, it is left untouched.
 *
 * The script uses `sharp` when available (preinstalled on EAS builders). If
 * sharp is not available, it falls back to `pngjs` + `zlib` (pure JS).
 */

const fs = require('fs');
const path = require('path');

const ASSETS_DIR = path.resolve(__dirname, '..', 'assets', 'images');
const BRAND_BG = { r: 20, g: 184, b: 179, alpha: 1 }; // #14B8B3 teal
const TARGET_FILES = [
  'icon.png',
  'adaptive-icon.png',
  'splash-icon.png',
  'favicon.png',
];

function readPngDimensions(filePath) {
  const buf = fs.readFileSync(filePath);
  if (buf.length < 24) return null;
  // PNG signature: 8 bytes, then IHDR chunk starts at offset 8
  // IHDR: 4-byte length, 4-byte type ("IHDR"), 4-byte width, 4-byte height
  if (buf[0] !== 0x89 || buf[1] !== 0x50 || buf[2] !== 0x4e || buf[3] !== 0x47) {
    return null; // Not a PNG
  }
  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);
  return { width, height };
}

async function squareWithSharp(filePath, size) {
  // Lazy require so the script doesn't fail when sharp isn't installed.
  const sharp = require('sharp');
  const tmpPath = filePath + '.tmp';
  await sharp(filePath)
    .resize(size, size, {
      fit: 'contain',
      background: BRAND_BG,
    })
    .png()
    .toFile(tmpPath);
  fs.renameSync(tmpPath, filePath);
  console.log(`  ✓ squared via sharp -> ${size}x${size}`);
}

async function squareWithJimp(filePath, size) {
  const { Jimp } = require('jimp');
  const img = await Jimp.read(filePath);
  img.contain({
    w: size,
    h: size,
    align: Jimp.HORIZONTAL_ALIGN_CENTER | Jimp.VERTICAL_ALIGN_MIDDLE,
  });
  // Fill background with brand teal
  const bgHex = (BRAND_BG.r << 24) | (BRAND_BG.g << 16) | (BRAND_BG.b << 8) | 0xff;
  const bg = new Jimp({ width: size, height: size, color: bgHex });
  bg.composite(img, 0, 0);
  await bg.write(filePath);
  console.log(`  ✓ squared via jimp -> ${size}x${size}`);
}

function squareWithCanvasFallback(filePath, size) {
  // Pure-JS fallback using pngjs. Reads the PNG, creates a square canvas
  // filled with the brand color, copies pixels centered.
  const { PNG } = require('pngjs');
  const input = PNG.sync.read(fs.readFileSync(filePath));
  const out = new PNG({ width: size, height: size });
  // Fill background
  for (let i = 0; i < size * size * 4; i += 4) {
    out.data[i] = BRAND_BG.r;
    out.data[i + 1] = BRAND_BG.g;
    out.data[i + 2] = BRAND_BG.b;
    out.data[i + 3] = 255;
  }
  // Compute centering offsets
  const offX = Math.floor((size - input.width) / 2);
  const offY = Math.floor((size - input.height) / 2);
  for (let y = 0; y < input.height; y++) {
    for (let x = 0; x < input.width; x++) {
      const srcIdx = (input.width * y + x) << 2;
      const dstX = x + offX;
      const dstY = y + offY;
      if (dstX < 0 || dstY < 0 || dstX >= size || dstY >= size) continue;
      const dstIdx = (size * dstY + dstX) << 2;
      const a = input.data[srcIdx + 3] / 255;
      out.data[dstIdx]     = Math.round(input.data[srcIdx]     * a + BRAND_BG.r * (1 - a));
      out.data[dstIdx + 1] = Math.round(input.data[srcIdx + 1] * a + BRAND_BG.g * (1 - a));
      out.data[dstIdx + 2] = Math.round(input.data[srcIdx + 2] * a + BRAND_BG.b * (1 - a));
      out.data[dstIdx + 3] = 255;
    }
  }
  fs.writeFileSync(filePath, PNG.sync.write(out));
  console.log(`  ✓ squared via pngjs -> ${size}x${size}`);
}

async function ensureSquare(filePath) {
  if (!fs.existsSync(filePath)) {
    console.log(`  (skip: ${path.basename(filePath)} not found)`);
    return;
  }
  const dim = readPngDimensions(filePath);
  if (!dim) {
    console.log(`  (skip: ${path.basename(filePath)} not a PNG)`);
    return;
  }
  const { width, height } = dim;
  if (width === height) {
    console.log(`  ✓ ${path.basename(filePath)} already square (${width}x${height})`);
    return;
  }
  const target = Math.max(width, height);
  console.log(`  ⚠ ${path.basename(filePath)} is ${width}x${height}, padding to ${target}x${target}...`);

  // Try strategies in order of quality/availability
  const strategies = [
    { name: 'sharp', fn: squareWithSharp },
    { name: 'jimp', fn: squareWithJimp },
    { name: 'pngjs', fn: squareWithCanvasFallback },
  ];
  let lastErr;
  for (const s of strategies) {
    try {
      await s.fn(filePath, target);
      return;
    } catch (err) {
      lastErr = err;
      // Try next strategy
    }
  }
  throw new Error(
    `Failed to square ${filePath}. Tried sharp, jimp, pngjs. Last error: ${lastErr && lastErr.message}`
  );
}

(async () => {
  console.log('[ensure-square-icons] Scanning', ASSETS_DIR);
  if (!fs.existsSync(ASSETS_DIR)) {
    console.log('[ensure-square-icons] Assets dir does not exist, skipping.');
    return;
  }
  for (const name of TARGET_FILES) {
    const fp = path.join(ASSETS_DIR, name);
    try {
      await ensureSquare(fp);
    } catch (err) {
      // Do not fail the whole build just because one icon could not be squared;
      // the build will surface a clearer error later if needed.
      console.error(`[ensure-square-icons] Error on ${name}: ${err.message}`);
    }
  }
  console.log('[ensure-square-icons] Done.');
})();
