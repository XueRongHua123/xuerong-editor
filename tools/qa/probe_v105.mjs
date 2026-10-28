// v1.0.5 十字交叉修复 UI 实测（副本 mod）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9400;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_cross', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 140));
};
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 240) };
  return r.result?.result?.value;
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.preview = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<120;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  mapRepair();
  for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,300));
    if(document.querySelectorAll('#mckList .mck-row').length >= 2) break; }
  const rows = [...document.querySelectorAll('#mckList .mck-row')].map(r=>({
    t: (r.querySelector('.mck-t')||{}).textContent,
    d: (r.querySelector('.mck-d')||{}).textContent,
    btn: !!(r.querySelector('[data-fix]'))
  }));
  return JSON.stringify({rows, stats: document.getElementById('mckStats').textContent});
})()`);
const shot = await send('Page.captureScreenshot', { format: 'png' });
fs.writeFileSync('qa/shots/v105_cross.png', Buffer.from(shot.result.data, 'base64'));
out.apply = await evalJS(`(async()=>{
  window.confirm = ()=>true;
  const btns = [...document.querySelectorAll('[data-fix]')];
  const b = btns.find(x=>x.dataset.fix.indexOf('十字') >= 0);
  if(!b) return JSON.stringify({error:'没有十字交叉按钮'});
  b.click();
  await new Promise(r=>setTimeout(r,9000));
  return JSON.stringify({stat: document.getElementById('status').textContent,
    btnText: b.textContent});
})()`);
out.after = await evalJS(`(async()=>{
  const r = await (await fetch('/api/map_repair_cross')).json();
  return JSON.stringify({found: r.found});
})()`);
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
