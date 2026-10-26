// 来源链面板截图
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9385;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_layers3', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map();
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 200) };
  return r.result?.result?.value;
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<150;i++){ await new Promise(r=>setTimeout(r,250));
    const t = document.getElementById('mapLayersList');
    if(t && t.textContent && t.textContent.indexOf('原版') >= 0) break; }
  const el = document.getElementById('mapLayersList');
  return JSON.stringify({html: (el.innerHTML || '').replace(/<[^>]+>/g,'|').slice(0,400), text: el.textContent.slice(0,300)});
})()`);
console.log(out);
await sleep(400);
const r = await send('Page.captureScreenshot', { format: 'png' });
fs.writeFileSync('qa/shots/v0.92_layers.png', Buffer.from(r.result.data, 'base64'));
ws.close(); chrome.kill(); process.exit(0);
