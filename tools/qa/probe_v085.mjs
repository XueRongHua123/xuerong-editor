// v0.85 地形/大洲层 + 地图检查面板实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9366;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v085', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
out.layers = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<150;i++){ await new Promise(r=>setTimeout(r,200)); if(window.MAP && MAP.ready) break; }
  const t = document.getElementById('mapTerrain');
  const c = document.getElementById('mapContinent');
  return JSON.stringify({ready: !!MAP.ready, terrainLoaded: t && t.naturalWidth, continentLoaded: c && c.naturalWidth,
    hasOneBtn: !!document.getElementById('mapOne'), info: mapInfo(221)});
})()`);

out.terrainToggle = await evalJS(`(()=>{
  document.getElementById('mapLTerrain').checked = true;
  mapApplyLayers();
  return JSON.stringify({terrainOpacity: document.getElementById('mapTerrain').style.opacity,
    provOpacity: document.getElementById('mapProv').style.opacity,
    continentHidden: document.getElementById('mapContinent').style.display === 'none'});
})()`);
await sleep(600);
await shot('qa/shots/v0.85_terrain.png');

out.one = await evalJS(`(()=>{
  document.getElementById('mapOne').click();
  return JSON.stringify({k: Number(MAP.k.toFixed(2))});
})()`);

out.check = await evalJS(`(async()=>{
  document.getElementById('mapCheckBtn').click();
  for(let i=0;i<120;i++){ await new Promise(r=>setTimeout(r,300));
    if(document.querySelectorAll('#mckList .mck-row').length) break; }
  return JSON.stringify({shown: document.getElementById('mapCheckModal').classList.contains('show'),
    rows: document.querySelectorAll('#mckList .mck-row').length,
    stats: document.getElementById('mckStats').textContent,
    first: (document.querySelector('#mckList .mck-t') || {}).textContent});
})()`);
await shot('qa/shots/v0.85_check.png');

out.goto = await evalJS(`(async()=>{
  const b = document.querySelector('#mckList .mck-go');
  if(!b) return JSON.stringify({error:'没有定位按钮'});
  b.click();
  await new Promise(r=>setTimeout(r,800));
  return JSON.stringify({modalClosed: !document.getElementById('mapCheckModal').classList.contains('show'),
    hud: document.getElementById('msInfo').textContent, k: Number(MAP.k.toFixed(2))});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
