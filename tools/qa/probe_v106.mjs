// v1.0.6 观感改进对比：地形纹理 / 边界细淡 / 放大插值
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9408;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_look', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
const shot = async (f) => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.open = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<150;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  return JSON.stringify({ready: MAP.ready});
})()`);

// 地形视图
out.terrain = await evalJS(`(async()=>{
  document.getElementById('mapLTerrain').checked = true;
  document.getElementById('mapLProv').checked = false;
  mapApplyLayers();
  mapGoto(2950, 700, 1.6);
  await new Promise(r=>setTimeout(r,700));
  return JSON.stringify({k: MAP.k, smooth: document.getElementById('mapStack').classList.contains('smooth')});
})()`);
await sleep(600);
await shot('qa/shots/v106_terrain.png');

// 政治视图放大（看插值 + 边界）
out.polit = await evalJS(`(async()=>{
  document.getElementById('mapLTerrain').checked = false;
  document.getElementById('mapLProv').checked = false;
  document.getElementById('mapLPolit').checked = true;
  mapApplyLayers();
  mapGoto(2900, 700, 3);
  await new Promise(r=>setTimeout(r,700));
  return JSON.stringify({k: MAP.k, smooth: document.getElementById('mapStack').classList.contains('smooth')});
})()`);
await sleep(600);
await shot('qa/shots/v106_polit_smooth.png');

// 1:1 时应回到像素锐利
out.one = await evalJS(`(async()=>{
  document.getElementById('mapOne').click();
  await new Promise(r=>setTimeout(r,600));
  return JSON.stringify({k: MAP.k, smooth: document.getElementById('mapStack').classList.contains('smooth')});
})()`);
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
