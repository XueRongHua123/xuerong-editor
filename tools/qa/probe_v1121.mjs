// v1.12.1 地形批量 + 笔刷实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9470;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_b', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 200));
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
await sleep(7500);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.open = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  await new Promise(r=>setTimeout(r,600));
  return JSON.stringify({ready: MAP.ready,
    hasBatch: !!document.getElementById('msBatchApply'),
    hasType: !!document.getElementById('msTypeApply'),
    hasBrush: !!document.getElementById('msBrushToggle')});
})()`);
out.batch = await evalJS(`(async()=>{
  MAP.sel = [17300, 17301, 17302];
  mapRenderSelection();
  await new Promise(r=>setTimeout(r,300));
  document.getElementById('msTerrainSel').value = 'desert';
  document.getElementById('msBatchApply').click();
  for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,500));
    const t = document.getElementById('msBatchMsg').textContent;
    if(t && t.indexOf('写入中') < 0 && t.indexOf('转换中') < 0) break; }
  return JSON.stringify({info: document.getElementById('msBatchInfo').textContent,
    msg: document.getElementById('msBatchMsg').textContent.slice(0,90)});
})()`);
out.type = await evalJS(`(async()=>{
  const f = document.getElementById('msFromType'), t = document.getElementById('msToType');
  f.value = 'jungle'; t.value = 'plains';
  document.getElementById('msTypeApply').click();
  for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,500));
    const m = document.getElementById('msBatchMsg').textContent;
    if(m && m.indexOf('转换中') < 0) break; }
  return JSON.stringify({msg: document.getElementById('msBatchMsg').textContent.slice(0,90)});
})()`);
out.brush = await evalJS(`(async()=>{
  document.getElementById('msBrushToggle').click();
  await new Promise(r=>setTimeout(r,300));
  const active = window.mapBrushActive();
  const d1 = window.mapBrushDown(1500, 1500);
  const m1 = window.mapBrushMove(1510, 1510);
  window.mapBrushUp();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,400));
    const m = document.getElementById('msBatchMsg').textContent;
    if(m && m.indexOf('刷') >= 0) break; }
  return JSON.stringify({active, d1, m1,
    msg: document.getElementById('msBatchMsg').textContent.slice(0,80),
    btn: document.getElementById('msBrushToggle').textContent});
})()`);
await sleep(600);
await shot('qa/shots/v1121_batch.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
