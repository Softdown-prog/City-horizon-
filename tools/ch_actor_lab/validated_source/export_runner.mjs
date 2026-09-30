import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const outDir = process.argv[2] || 'out/ch_actor_validated_source';
await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

const errors = [];
page.on('console', msg => {
  if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
});
page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));

await page.goto('http://127.0.0.1:8765/tools/ch_actor_lab/validated_source/ch_actor_lab_original.html', {
  waitUntil: 'networkidle',
  timeout: 60000,
});

await page.waitForFunction(() => {
  const sheet = document.querySelector('#sheet');
  const status = document.querySelector('#status');
  return sheet && sheet.width === 384 && sheet.height === 256 &&
    status && status.textContent.includes('8 quadros × 4 direções');
}, null, { timeout: 30000 });

const runtime = await page.evaluate(() => ({
  sheet: {
    width: document.querySelector('#sheet').width,
    height: document.querySelector('#sheet').height,
  },
  status: document.querySelector('#status').textContent,
  resolution: document.querySelector('#resolution').value,
  frames: document.querySelector('#frames').value,
  leg: document.querySelector('#leg').value,
  arm: document.querySelector('#arm').value,
  bounce: document.querySelector('#bounce').value,
}));

if (runtime.sheet.width !== 384 || runtime.sheet.height !== 256) {
  throw new Error(`Unexpected sheet ${runtime.sheet.width}x${runtime.sheet.height}`);
}
if (runtime.resolution !== '48x64' || runtime.frames !== '8') {
  throw new Error(`Unexpected defaults ${runtime.resolution}, ${runtime.frames} frames`);
}
if (runtime.leg !== '0.32' || runtime.arm !== '0.18' || runtime.bounce !== '0.004') {
  throw new Error(`Validated walk defaults changed: ${JSON.stringify(runtime)}`);
}

const pngPromise = page.waitForEvent('download');
await page.click('#exportPng');
const png = await pngPromise;
await png.saveAs(path.join(outDir, 'ch_actor_48x64_8f.png'));

const jsonPromise = page.waitForEvent('download');
await page.click('#exportJson');
const manifest = await jsonPromise;
await manifest.saveAs(path.join(outDir, 'ch_actor_48x64_8f_manifest.json'));

await page.screenshot({
  path: path.join(outDir, 'ch_actor_lab_page.png'),
  fullPage: true,
});

const parsed = JSON.parse(await fs.readFile(path.join(outDir, 'ch_actor_48x64_8f_manifest.json'), 'utf8'));
if (parsed.metadata?.contractVersion !== 'CH_ACTOR_CONTRACT_V1') {
  throw new Error(`Unexpected contract ${parsed.metadata?.contractVersion}`);
}
if (parsed.camera?.yawDeg !== 45 || parsed.camera?.pitchDeg !== 30 || parsed.camera?.projection !== 'orthographic') {
  throw new Error(`Unexpected camera ${JSON.stringify(parsed.camera)}`);
}
if (parsed.dimensions?.groundAnchor?.x !== 24 || parsed.dimensions?.groundAnchor?.y !== 60) {
  throw new Error(`Unexpected ground anchor ${JSON.stringify(parsed.dimensions?.groundAnchor)}`);
}
if (parsed.animation?.frameCount !== 8 || parsed.animation?.kinematics?.legSwingRad !== 0.32 ||
    parsed.animation?.kinematics?.armSwingRad !== 0.18 || parsed.animation?.kinematics?.verticalBounce !== 0.004) {
  throw new Error(`Unexpected animation contract ${JSON.stringify(parsed.animation)}`);
}

await fs.writeFile(path.join(outDir, 'execution_report.json'), JSON.stringify({
  contract: 'CH_ACTOR_VALIDATED_SOURCE_EXECUTION_V1',
  source: 'tools/ch_actor_lab/validated_source/ch_actor_lab_original.html',
  generatedBy: 'GitHub Actions + Playwright Chromium',
  runtime,
  browserErrors: errors,
  result: errors.length ? 'PASS_WITH_BROWSER_CONSOLE_ERRORS' : 'PASS',
}, null, 2) + '\n');

if (errors.length) {
  throw new Error(`Browser reported errors:\n${errors.join('\n')}`);
}

console.log('CH Actor validated source export OK');
console.log(JSON.stringify(runtime, null, 2));
await browser.close();
