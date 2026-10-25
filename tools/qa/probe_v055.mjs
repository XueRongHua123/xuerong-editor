// v0.55 国家中心 + 项目体检实测，并截图
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9340;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v055', '--window-size=1600,1000', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 160));
  if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') problems.push('ERR ' + (m.params.args || []).map(a => a.value ?? '').join(' ').slice(0, 160));
};
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 240) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(7000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
await sleep(400);

const out = {};
out.open = await evalJS(`(async()=>{
  await openCountry('AFR');
  await new Promise(r=>setTimeout(r,600));
  return JSON.stringify({
    shown: document.getElementById('countryModal').classList.contains('show'),
    rows: document.querySelectorAll('#countryList .cm-row').length,
    count: document.getElementById('countryCount').textContent,
    title: (document.querySelector('#countryBody .cm-title h3')||{}).textContent,
    cells: document.querySelectorAll('#countryBody .cm-cell').length,
    trees: [...document.querySelectorAll('#countryBody [data-tree]')].map(x=>x.dataset.tree),
    ideas: document.querySelectorAll('#countryBody [data-idea]').length,
    techs: document.querySelectorAll('#countryBody [data-tech]').length,
    issues: [...document.querySelectorAll('#countryBody .cm-issue')].map(x=>x.textContent.slice(0,30))
  });
})()`);
await sleep(300);
await shot('qa/shots/v0.55_country.png');

out.treeJump = await evalJS(`(async()=>{
  const el = document.querySelector('#countryBody [data-tree]');
  const tid = el.dataset.tree;
  el.click();
  await new Promise(r=>setTimeout(r,500));
  return JSON.stringify({clicked: tid, currentTree: curTree() && curTree().id,
    modalClosed: !document.getElementById('countryModal').classList.contains('show')});
})()`);

out.lint = await evalJS(`(async()=>{
  await openLint();
  await new Promise(r=>setTimeout(r,1500));
  return JSON.stringify({
    shown: document.getElementById('lintModal').classList.contains('show'),
    stats: document.getElementById('lintStats').textContent.replace(/\\s+/g,' ').slice(0,120),
    groups: [...document.querySelectorAll('#lintList .lint-group')].map(x=>x.textContent),
    items: document.querySelectorAll('#lintList .lint-item').length,
    first: (document.querySelector('#lintList .lint-item .txt')||{}).textContent?.slice(0,60)
  });
})()`);
await sleep(300);
await shot('qa/shots/v0.55_lint.png');

out.lintFilter = await evalJS(`(()=>{
  const f = document.getElementById('lintFilter');
  f.value = 'error'; renderLint();
  const n = document.querySelectorAll('#lintList .lint-item').length;
  f.value = 'all'; renderLint();
  return JSON.stringify({errorOnly: n, allAgain: document.querySelectorAll('#lintList .lint-item').length});
})()`);
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
