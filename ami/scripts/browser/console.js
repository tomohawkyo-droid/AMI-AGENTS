#!/usr/bin/env node
/**
 * Browser Console Logger
 *
 * Captures console output, network errors, and page errors from a URL
 * using headless Chromium via Playwright.
 *
 * Usage:
 *   node console.js <url> [--timeout <ms>] [--wait <ms>] [--no-network]
 *
 * Examples:
 *   node console.js http://localhost:8001
 *   node console.js http://localhost:8001 --timeout 30000 --wait 10000
 *   node console.js http://localhost:8001 --no-network
 */

const { chromium } = require('playwright');

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { url: null, timeout: 20000, wait: 5000, network: true };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--timeout' && args[i + 1]) {
      opts.timeout = parseInt(args[++i], 10);
    } else if (args[i] === '--wait' && args[i + 1]) {
      opts.wait = parseInt(args[++i], 10);
    } else if (args[i] === '--no-network') {
      opts.network = false;
    } else if (!args[i].startsWith('--')) {
      opts.url = args[i];
    }
  }

  if (!opts.url) {
    console.error('Usage: node console.js <url> [--timeout <ms>] [--wait <ms>] [--no-network]');
    process.exit(1);
  }
  return opts;
}

(async () => {
  const opts = parseArgs();
  const browser = await chromium.launch();
  const page = await browser.newPage();

  page.on('console', msg => {
    const type = msg.type().toUpperCase().padEnd(7);
    console.log(`[${type}] ${msg.text()}`);
  });

  page.on('pageerror', err => {
    console.log(`[PGERROR] ${err.message}`);
  });

  if (opts.network) {
    page.on('requestfailed', req => {
      const failure = req.failure();
      console.log(`[NETFAIL] ${req.method()} ${req.url()}: ${failure ? failure.errorText : 'unknown'}`);
    });

    page.on('response', res => {
      if (res.status() >= 400) {
        console.log(`[HTTP${res.status()}] ${res.request().method()} ${res.url()}`);
      }
    });
  }

  try {
    await page.goto(opts.url, { waitUntil: 'networkidle', timeout: opts.timeout });
    console.log(`[NAVIGATE] Loaded ${opts.url}`);
  } catch (e) {
    console.log(`[NAVIGATE] ${e.message}`);
  }

  await page.waitForTimeout(opts.wait);
  await browser.close();
})();
