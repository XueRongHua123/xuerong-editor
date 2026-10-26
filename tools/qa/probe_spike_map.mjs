// 地图叠图性能实测（file:// 打开 spike_maplayer.html）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
const PORT = 9355;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const file = 'file:///' + path.resolve('qa/shots/spike_map/spike_maplayer.html').replace(/\\/g, '/');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_spike', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu=false', 'about:blank'], { stdio: 'ignore' });
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
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 200) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: file });
await sleep(4000);
const out = {};
out.load = await evalJS(`(async()=>{
  for(let i=0;i<50 && !window.__perf.ready;i++) await new Promise(r=>setTimeout(r,100));
  return JSON.stringify({ready: window.__perf.ready, loadMs: window.__perf.loadMs, sizes: window.__perf.sizes,
    viewport: innerWidth + 'x' + innerHeight});
})()`);
out.fps = await evalJS(`window.__perf.frames(1500).then(r=>JSON.stringify(r))`);
await shot('qa/shots/spike_map/perf_shot.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
