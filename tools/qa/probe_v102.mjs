// v1.0.2 省份排行实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9395;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_rank', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
out.open = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<120;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  return JSON.stringify({ready: MAP.ready});
})()`);
out.rank = await evalJS(`(async()=>{
  mapShowRank();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,250));
    if(document.querySelectorAll('#mckList .mck-row').length) break; }
  return JSON.stringify({title: document.getElementById('mckTitle').textContent,
    hint: document.getElementById('mckHint').textContent,
    rows: document.querySelectorAll('#mckList .mck-row').length,
    stats: document.getElementById('mckStats').textContent,
    first: (document.querySelector('#mckList .mck-t') || {}).textContent});
})()`);
const r = await send('Page.captureScreenshot', { format: 'png' });
fs.writeFileSync('qa/shots/v102_rank.png', Buffer.from(r.result.data, 'base64'));
out.goto = await evalJS(`(async()=>{
  const b = document.querySelector('#mckList .mck-go');
  b.click(); await new Promise(r=>setTimeout(r,900));
  return JSON.stringify({closed: !document.getElementById('mapCheckModal').classList.contains('show'),
    info: document.getElementById('msInfo').textContent});
})()`);
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
