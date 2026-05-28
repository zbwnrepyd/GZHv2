#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

function usage() {
  console.log(`Usage:
  node canvas/screenshot.js --company <name> [--base-url http://127.0.0.1:5050] [--out output/cards/<name>] [--bg-image <path>]

Options:
  --company   Company name to export. Required.
  --base-url  Flask base URL. Default: http://127.0.0.1:5050
  --out       Output directory. Default: output/cards/<company>
  --bg-image  Path to local watermark image (PNG/JPEG). Injected as base64 data URL.
  --help      Show this help.
`);
}

function parseArgs(argv) {
  const args = {
    baseUrl: 'http://127.0.0.1:5050',
    company: '',
    out: '',
    bgImage: null,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const item = argv[i];
    if (item === '--help' || item === '-h') {
      args.help = true;
    } else if (item === '--company') {
      args.company = argv[++i] || '';
    } else if (item === '--base-url') {
      args.baseUrl = argv[++i] || args.baseUrl;
    } else if (item === '--out') {
      args.out = argv[++i] || '';
    } else if (item === '--bg-image' || item === '-b') {
      args.bgImage = argv[++i] || null;
    }
  }
  return args;
}

function safeName(value) {
  return String(value || 'company').replace(/[/\\?%*:|"<>]/g, '_');
}

function buildCardUrl(baseUrl, company, cardIndex, bgImagePath) {
  let url = `${baseUrl.replace(/\/$/, '')}/canvas/card/${encodeURIComponent(company)}/${cardIndex}`;
  if (bgImagePath) {
    const mime = bgImagePath.endsWith('.png') ? 'image/png' : 'image/jpeg';
    const b64 = fs.readFileSync(bgImagePath).toString('base64');
    const dataUrl = `data:${mime};base64,${b64}`;
    url += `?bg=${encodeURIComponent(dataUrl)}`;
  }
  return url;
}

async function waitForCard(page) {
  await page.waitForSelector('.knowledge-card', { timeout: 10000 });
  await page.evaluate(async () => {
    if (document.fonts && document.fonts.ready) {
      await document.fonts.ready;
    }
    const images = Array.from(document.images || []);
    await Promise.all(images.map((image) => {
      if (image.complete) return Promise.resolve();
      return new Promise((resolve) => {
        image.addEventListener('load', resolve, { once: true });
        image.addEventListener('error', resolve, { once: true });
      });
    }));
  });
}

async function run() {
  const args = parseArgs(process.argv);
  if (args.help) {
    usage();
    return;
  }
  if (!args.company) {
    usage();
    process.exitCode = 1;
    return;
  }

  let puppeteer;
  try {
    puppeteer = require('puppeteer');
  } catch (error) {
    console.error('Puppeteer is not installed. Run: npm install');
    process.exitCode = 1;
    return;
  }

  const company = args.company;
  const safeCompany = safeName(company);
  const outDir = path.resolve(args.out || path.join('output', 'cards', safeCompany));
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await puppeteer.launch({ headless: 'new' });
  try {
    const page = await browser.newPage();
    await page.setViewport({
      width: 900,
      height: 1200,
      deviceScaleFactor: 2,
    });

    for (let cardIndex = 1; cardIndex <= 8; cardIndex += 1) {
      const url = buildCardUrl(args.baseUrl, company, cardIndex, args.bgImage);
      await page.goto(url, { waitUntil: 'networkidle0' });
      await waitForCard(page);
      const filePath = path.join(outDir, `${safeCompany}_card_${String(cardIndex).padStart(2, '0')}.png`);
      await page.screenshot({ path: filePath, fullPage: false });
      console.log(`exported ${filePath}`);
    }
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
