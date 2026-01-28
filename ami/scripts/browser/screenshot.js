#!/usr/bin/env node
/**
 * Browser Screenshot Tool
 *
 * Takes a full-page screenshot of a URL using headless Chromium via Playwright.
 *
 * Usage:
 *   node screenshot.js <url> <output.png> [--timeout <ms>] [--wait <ms>] [--width <px>] [--height <px>]
 *
 * Examples:
 *   node screenshot.js http://localhost:8001 /tmp/shot.png
 *   node screenshot.js http://localhost:8001 /tmp/shot.png --wait 10000 --width 1920 --height 1080
 */

const { chromium } = require('playwright');

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { url: null, output: null, timeout: 20000, wait: 5000, width: 1280, height: 720 };
  const positional = [];

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--timeout' && args[i + 1]) {
      opts.timeout = parseInt(args[++i], 10);
    } else if (args[i] === '--wait' && args[i + 1]) {
      opts.wait = parseInt(args[++i], 10);
    } else if (args[i] === '--width' && args[i + 1]) {
      opts.width = parseInt(args[++i], 10);
    } else if (args[i] === '--height' && args[i + 1]) {
      opts.height = parseInt(args[++i], 10);
    } else if (!args[i].startsWith('--')) {
      positional.push(args[i]);
    }
  }

  opts.url = positional[0];
  opts.output = positional[1];

  if (!opts.url || !opts.output) {
    console.error('Usage: node screenshot.js <url> <output.png> [--timeout <ms>] [--wait <ms>]');
    process.exit(1);
  }
  return opts;
}

(async () => {
  const opts = parseArgs();
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: opts.width, height: opts.height } });

  try {
    await page.goto(opts.url, { waitUntil: 'networkidle', timeout: opts.timeout });
  } catch (e) {
    console.error(`Navigation: ${e.message}`);
  }

  await page.waitForTimeout(opts.wait);
  await page.screenshot({ path: opts.output, fullPage: true });
  console.log(`Saved: ${opts.output}`);
  await browser.close();
})();
