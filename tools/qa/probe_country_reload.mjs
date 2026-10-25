// 复现回归：先开国家中心、再加载 mod，是否还能读到国家（不需要重启软件）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9341;
const URL = process.argv[2] || 'http://127.0.0.1:8897/';
const MOD = process.argv[3] || 'D:\\大肥鱼工作区\\HOI4 MUVLUVsub mod 制作\\muvluvCN_1.19';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_reload', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 120));
};
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async (e, timeout = 300000) => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 200) };
  return r.result?.result?.value;
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
await sleep(300);

const out = {};
// 1) 没加载任何 mod 时打开国家中心：应显示 0 并给出提示
out.before = await evalJS(`(async()=>{
  await openCountry();
  await new Promise(r=>setTimeout(r,500));
  return JSON.stringify({
    count: document.getElementById('countryCount').textContent,
    rows: document.querySelectorAll('#countryList .cm-row').length,
    hint: (document.querySelector('#countryBody .cm-empty')||{}).textContent || ''
  });
})()`);

// 2) 加载 mod（走真实接口），随后刷新前端数据
out.load = await evalJS(`(async()=>{
  const r = await fetch('/api/load_mod', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({path: ${JSON.stringify(MOD)}})});
  const j = await r.json();
  await loadData();
  return JSON.stringify({ok: j.ok, msg: j.msg});
})()`);

// 3) 不重启软件，再次打开国家中心
out.after = await evalJS(`(async()=>{
  await openCountry();
  await new Promise(r=>setTimeout(r,800));
  return JSON.stringify({
    count: document.getElementById('countryCount').textContent,
    rows: document.querySelectorAll('#countryList .cm-row').length,
    title: (document.querySelector('#countryBody .cm-title h3')||{}).textContent || ''
  });
})()`);

// 4) 卸载再重新加载，同样不重启
out.reload = await evalJS(`(async()=>{
  await fetch('/api/unload_mod', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: ${JSON.stringify(MOD)}})});
  await loadData();
  await openCountry();
  const off = document.getElementById('countryCount').textContent;
  const r = await fetch('/api/load_mod', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({path: ${JSON.stringify(MOD)}})});
  await r.json();
  await loadData();
  await openCountry();
  await new Promise(r=>setTimeout(r,800));
  return JSON.stringify({afterUnload: off, afterReload: document.getElementById('countryCount').textContent,
    rows: document.querySelectorAll('#countryList .cm-row').length});
})()`);

const shot = await send('Page.captureScreenshot', { format: 'png' });
fs.mkdirSync('qa/shots', { recursive: true });
fs.writeFileSync('qa/shots/v0.551_country_reload.png', Buffer.from(shot.result.data, 'base64'));

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
