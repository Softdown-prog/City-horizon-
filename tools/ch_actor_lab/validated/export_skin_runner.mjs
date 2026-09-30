import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const outDir = process.argv[2] || 'out/ch_actor_clown_validated';
await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on('console', msg => { if (msg.type() === 'error') errors.push(`console: ${msg.text()}`); });
page.on('pageerror', err => errors.push(`pageerror: ${err.message}`));

await page.goto('http://127.0.0.1:8765/tools/ch_actor_lab/validated/clown_01.html', {
  waitUntil: 'networkidle',
  timeout: 60000,
});

await page.waitForFunction(() => {
  const sheet = document.querySelector('#sheet');
  const status = document.querySelector('#status');
  const contract = document.querySelector('#contract');
  return sheet && sheet.width === 384 && sheet.height === 256 &&
    status && status.textContent.includes('32 frames') &&
    contract && contract.textContent.includes('CH_ACTOR_VALIDATED_V1');
}, null, { timeout: 30000 });

const runtime = await page.evaluate(() => ({
  sheet: { width: document.querySelector('#sheet').width, height: document.querySelector('#sheet').height },
  status: document.querySelector('#status').textContent,
  contract: document.querySelector('#contract').textContent,
}));

if (runtime.sheet.width !== 384 || runtime.sheet.height !== 256) {
  throw new Error(`Unexpected clown sheet ${runtime.sheet.width}x${runtime.sheet.height}`);
}
if (!runtime.contract.includes('CH_ACTOR_VALIDATED_V1') || !runtime.contract.includes('CH_ACTOR_SKIN_V1')) {
  throw new Error(`Unexpected contracts: ${runtime.contract}`);
}

const pngPromise = page.waitForEvent('download');
await page.click('#exportPng');
const png = await pngPromise;
await png.saveAs(path.join(outDir, 'clown_01_ch_actor_validated_4dir_8f.png'));

const jsonPromise = page.waitForEvent('download');
await page.click('#exportJson');
const manifest = await jsonPromise;
await manifest.saveAs(path.join(outDir, 'clown_01_ch_actor_validated.json'));

await page.screenshot({ path: path.join(outDir, 'clown_01_page.png'), fullPage: true });

const parsed = JSON.parse(await fs.readFile(path.join(outDir, 'clown_01_ch_actor_validated.json'), 'utf8'));
if (parsed.contract !== 'CH_ACTOR_SKIN_EXPORT_V1') throw new Error(`Unexpected export contract ${parsed.contract}`);
if (parsed.actorContract !== 'CH_ACTOR_VALIDATED_V1') throw new Error(`Unexpected actor contract ${parsed.actorContract}`);
if (parsed.frame?.size?.[0] !== 48 || parsed.frame?.size?.[1] !== 64) throw new Error('Unexpected frame size');
if (parsed.frame?.groundAnchor?.[0] !== 24 || parsed.frame?.groundAnchor?.[1] !== 60) throw new Error('Unexpected anchor');
if (!parsed.motion?.locked || parsed.motion?.legSwingRad !== 0.32 || parsed.motion?.armSwingRad !== 0.18 || parsed.motion?.verticalBounce !== 0.004 || parsed.motion?.frames !== 8) {
  throw new Error(`Validated motion changed: ${JSON.stringify(parsed.motion)}`);
}
if (parsed.head?.parent !== 'torso' || parsed.head?.independentYaw !== false) throw new Error(`Head lock changed: ${JSON.stringify(parsed.head)}`);
if (errors.length) throw new Error(`Browser errors:\n${errors.join('\n')}`);

await fs.writeFile(path.join(outDir, 'execution_report.json'), JSON.stringify({
  contract: 'CH_ACTOR_SKIN_EXECUTION_V1',
  source: 'tools/ch_actor_lab/validated/clown_01.html',
  actorAuthority: 'CH_ACTOR_VALIDATED_V1',
  skin: 'clown_01',
  runtime,
  result: 'PASS',
}, null, 2) + '\n');

console.log('CH Actor clown skin export OK');
console.log(JSON.stringify(runtime, null, 2));
await browser.close();
