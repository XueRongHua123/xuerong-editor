// v0.67 脚本检查面板实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9350;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v067', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 150));
};
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 220) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);

const out = {};
out.open = await evalJS(`(async()=>{
  await openScriptCheck(true);
  await new Promise(r=>setTimeout(r,1800));
  return JSON.stringify({shown: document.getElementById('scriptModal').classList.contains('show'),
    meta: document.getElementById('scriptMeta').textContent,
    rows: document.querySelectorAll('#scriptBody .sc-row').length - 1});
})()`);
out.search = await evalJS(`(()=>{
  document.getElementById('scriptSearch').value = 'BETA';
  renderScriptList();
  return JSON.stringify({rows: document.querySelectorAll('#scriptBody .sc-row').length - 1});
})()`);
out.kind = await evalJS(`(()=>{
  document.getElementById('scriptSearch').value = '';
  document.getElementById('scriptKind').value = 'effect';
  renderScriptList();
  const kinds = [...new Set([...document.querySelectorAll('#scriptBody .sc-row:not(.head) .sc-kind')].map(x=>x.textContent))];
  return JSON.stringify({rows: document.querySelectorAll('#scriptBody .sc-row').length - 1, kinds});
})()`);
await shot('qa/shots/v0.67_script_panel.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
