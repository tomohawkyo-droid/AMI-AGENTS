#!/usr/bin/env node
/**
 * Browser DOM Query Tool
 *
 * Navigates to a URL and evaluates a JS expression against the page DOM.
 *
 * Usage:
 *   node dom-query.js <url> <expression> [--timeout <ms>] [--wait <ms>]
 *
 * Examples:
 *   node dom-query.js http://localhost:8001 "document.title"
 *   node dom-query.js http://localhost:8001 "document.querySelectorAll('.group').length"
 *   node dom-query.js http://localhost:8001 "[...document.querySelectorAll('aside span.font-bold')].slice(0,5).map(e=>e.textContent)"
 */

const { chromium } = require('playwright');

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { url: null, expr: null, timeout: 20000, wait: 5000 };
  const positional = [];

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--timeout' && args[i + 1]) {
      opts.timeout = parseInt(args[++i], 10);
    } else if (args[i] === '--wait' && args[i + 1]) {
      opts.wait = parseInt(args[++i], 10);
    } else if (!args[i].startsWith('--')) {
      positional.push(args[i]);
    }
  }

  opts.url = positional[0];
  opts.expr = positional[1];

  if (!opts.url || !opts.expr) {
    console.error('Usage: node dom-query.js <url> <expression> [--timeout <ms>] [--wait <ms>]');
    process.exit(1);
  }
  return opts;
}

(async () => {
  const opts = parseArgs();
  const browser = await chromium.launch();
  const page = await browser.newPage();

  try {
    await page.goto(opts.url, { waitUntil: 'networkidle', timeout: opts.timeout });
  } catch (e) {
    console.error(`Navigation: ${e.message}`);
  }

  await page.waitForTimeout(opts.wait);

  try {
    const result = await page.evaluate(opts.expr);
    console.log(JSON.stringify(result, null, 2));
  } catch (e) {
    console.error(`Eval error: ${e.message}`);
  }

  await browser.close();
})();
