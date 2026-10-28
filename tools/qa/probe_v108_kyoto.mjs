// 验证「muv 京都燃烧」playset 的地图读取与显示
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9414;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_kyoto', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  return JSON.stringify({ready: MAP.ready, w: MAP.w, h: MAP.h, k: Number((MAP.k||0).toFixed(3)),
    layers: (MAP.layers||[]).length});
})()`);
out.info = await evalJS(`(()=>{
  // 找一个陆地省的悬停文本
  const ids = Object.keys(MAP.idx || {});
  for(const pid of ids){
    const rec = MAP.idx[pid];
    if(rec.type === 'land' && rec.px > 50) return mapInfo(Number(pid));
  }
  return '没找到陆地省';
})()`);
await sleep(500);
await shot('qa/shots/v108_kyoto_map.png');
// 地形视图
out.terrain = await evalJS(`(async()=>{
  document.getElementById('mapLTerrain').checked = true;
  document.getElementById('mapLProv').checked = false;
  mapApplyLayers();
  await new Promise(r=>setTimeout(r,500));
  return JSON.stringify({k: MAP.k});
})()`);
await sleep(600);
await shot('qa/shots/v108_kyoto_terrain.png');
// 省份排行（新地图的大省）
out.rank = await evalJS(`(async()=>{
  const r = await (await fetch('/api/map_analysis?limit=5')).json();
  return JSON.stringify({count: r.count, median: r.median, big: r.big_count,
    top: (r.top||[]).slice(0,3).map(x=>[x.pid, x.px, x.state])});
})()`);
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
