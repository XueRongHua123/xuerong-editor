// v0.76 地图改省归属 UI 实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9361;
const URL = process.argv[2] || 'http://127.0.0.1:8898/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v076', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 160));
};
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 240) };
  return r.result?.result?.value;
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);

const out = {};
out.ops = await evalJS(`(()=>{
  mapShowOps(111, 900);
  const box = document.getElementById('mapProvOps');
  return JSON.stringify({shown: box.style.display !== 'none',
    target: document.getElementById('mapTargetState').value,
    detachEnabled: !document.getElementById('mapDetachProv').disabled,
    hasMove: !!document.getElementById('mapMoveProv')});
})()`);

out.detachDisabled = await evalJS(`(()=>{
  mapShowOps(555, 0);
  return JSON.stringify({detachDisabled: document.getElementById('mapDetachProv').disabled,
    target: document.getElementById('mapTargetState').value});
})()`);

out.move = await evalJS(`(async()=>{
  window.confirm = ()=>true;
  mapShowOps(111, 900);
  document.getElementById('mapTargetState').value = '901';
  await mapMoveProv(false);
  await new Promise(r=>setTimeout(r,1500));
  return JSON.stringify({status: document.getElementById('status').textContent,
    hud: document.getElementById('mapHudText').textContent,
    target: document.getElementById('mapTargetState').value});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
