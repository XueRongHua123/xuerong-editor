// v1.0.9 独立透明度 + 播放集 + Shift 多选
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9416;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v109', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 300) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(7000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.open = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  return JSON.stringify({ready: MAP.ready, w: MAP.w, h: MAP.h});
})()`);

// 独立透明度：把地形调到 30%，政治调到 100%，看两个图层的实际 opacity
out.opacity = await evalJS(`(async()=>{
  const set = (k, v)=>{
    const el = document.querySelector('.lt-op[data-op="'+k+'"]');
    if(el){ el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); }
  };
  document.getElementById('mapLTerrain').checked = true;
  document.getElementById('mapLPolit').checked = true;
  mapApplyLayers();
  set('terrain', 30);
  set('polit', 100);
  await new Promise(r=>setTimeout(r,300));
  return JSON.stringify({
    sliders: document.querySelectorAll('.lt-op').length,
    terrainOp: document.getElementById('mapTerrain').style.opacity,
    politOp: document.getElementById('mapPolit').style.opacity,
    edgesOp: document.getElementById('mapEdges').style.opacity
  });
})()`);
await sleep(500);
await shot('qa/shots/v109_layers.png');

// Shift 多选
out.multisel = await evalJS(`(async()=>{
  MAP.sel = [];
  const ids = Object.keys(MAP.idx || {}).filter(k=>MAP.idx[k].type==='land' && MAP.idx[k].px>100).slice(0,3).map(Number);
  mapToggleSel(ids[0]);
  mapToggleSel(ids[1]);
  mapToggleSel(ids[2]);
  await new Promise(r=>setTimeout(r,200));
  const a = {sel: MAP.sel.slice(), status: document.getElementById('msSel').textContent,
             info: document.getElementById('msInfo').textContent};
  mapToggleSel(ids[1]);   // 再点一次应移出
  await new Promise(r=>setTimeout(r,200));
  return JSON.stringify({after3: a, afterRemove: MAP.sel.slice(), status2: document.getElementById('msSel').textContent});
})()`);

// 播放集面板
out.playset = await evalJS(`(async()=>{
  document.getElementById('psOpen').click();
  await new Promise(r=>setTimeout(r,800));
  const rows = document.querySelectorAll('#psList .ps-row').length;
  const msg = document.getElementById('psMsg').textContent;
  const shown = document.getElementById('psModal').classList.contains('show');
  return JSON.stringify({shown, rows, msg});
})()`);
await sleep(400);
await shot('qa/shots/v109_playset.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
