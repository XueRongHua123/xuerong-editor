// v0.71 地图面板实测：打开、缩放、点查省、搜索定位、联动州
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9356;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v071', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  for(let i=0;i<80;i++){
    await new Promise(r=>setTimeout(r,200));
    if(window.MAP && MAP.ready) break;
  }
  return JSON.stringify({shown: document.getElementById('mapModal').classList.contains('show'),
    ready: !!(window.MAP && MAP.ready), w: MAP && MAP.w, h: MAP && MAP.h,
    k: MAP && Number(MAP.k.toFixed(3)), meta: document.getElementById('mapMeta').textContent,
    hasIdx: !!(MAP && MAP.idx && Object.keys(MAP.idx).length),
    hasCenters: !!(MAP && MAP.centers && Object.keys(MAP.centers).length)});
})()`);
await shot('qa/shots/v0.71_map.png');

out.hover = await evalJS(`(async()=>{
  const wrap = document.getElementById('mapStageWrap');
  const r = wrap.getBoundingClientRect();
  const ev = new PointerEvent('pointermove', {bubbles:true, clientX: r.left + r.width/2, clientY: r.top + r.height/2});
  wrap.dispatchEvent(ev);
  await new Promise(x=>setTimeout(x,300));
  return JSON.stringify({hud: document.getElementById('mapHud').textContent});
})()`);

out.search = await evalJS(`(()=>{
  document.getElementById('mapSearch').value = '50';
  mapSearchGo();
  return JSON.stringify({hud: document.getElementById('mapHud').textContent, k: Number(MAP.k.toFixed(2))});
})()`);

out.layers = await evalJS(`(()=>{
  document.getElementById('mapLState').checked = true;
  document.getElementById('mapOpacity').value = '70';
  mapApplyLayers();
  const st = document.getElementById('mapState');
  return JSON.stringify({stateShown: st.style.display !== 'none', stateOpacity: st.style.opacity,
    provOpacity: document.getElementById('mapProv').style.opacity});
})()`);
await shot('qa/shots/v0.71_map_state_layer.png');

out.provAt = await evalJS(`(()=>{
  if(!MAP.idCanvas) return JSON.stringify({error:'idCanvas 未就绪（prov_id.png 还在加载）'});
  const c = MAP.centers && Object.keys(MAP.centers)[0];
  if(!c) return JSON.stringify({error:'没有中心点'});
  const cen = MAP.centers[c];
  const pid = mapProvAt(cen[0], cen[1]);
  return JSON.stringify({sample: c, expect: Number(c), got: pid, match: Number(c) === pid, info: mapInfo(pid)});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
