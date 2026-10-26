// v0.80 战略区图层实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9362;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v080', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);

const out = {};
out.open = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<120;i++){ await new Promise(r=>setTimeout(r,200)); if(window.MAP && MAP.ready) break; }
  const img = document.getElementById('mapRegion');
  return JSON.stringify({ready: !!MAP.ready, hasLayer: !!img, loaded: img && img.naturalWidth,
    idxHasRegion: !!(MAP.idx && Object.keys(MAP.idx).some(k=>MAP.idx[k].region)),
    sample: MAP.idx && MAP.idx['221']});
})()`);

out.toggle = await evalJS(`(()=>{
  const cb = document.getElementById('mapLRegion');
  cb.checked = true;
  mapApplyLayers();
  const reg = document.getElementById('mapRegion');
  const pol = document.getElementById('mapPolit');
  return JSON.stringify({regionOpacity: reg.style.opacity, regionShown: reg.style.display !== 'none',
    politHidden: pol.style.display === 'none'});
})()`);
await sleep(700);
await shot('qa/shots/v0.80_region.png');

out.info = await evalJS(`(()=>{
  return JSON.stringify({text: mapInfo(221)});
})()`);

out.off = await evalJS(`(()=>{
  document.getElementById('mapLRegion').checked = false;
  mapApplyLayers();
  return JSON.stringify({regionHidden: document.getElementById('mapRegion').style.display === 'none'});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
