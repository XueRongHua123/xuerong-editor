// v1.18.2 政治图层 + 空态面板实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9486;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_fix', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  document.querySelector('.lt-preset[data-preset="polit"]').click();
  await new Promise(r=>setTimeout(r,1200));
  return JSON.stringify({ready: MAP.ready, preset: (document.querySelector('.lt-preset.on')||{}).textContent});
})()`);
// 采样政治图上的几个点：海洋 vs 陆地
out.pixels = await evalJS(`(async()=>{
  const img = document.getElementById('mapPolit');
  const c = document.createElement('canvas');
  c.width = img.naturalWidth; c.height = img.naturalHeight;
  c.getContext('2d').drawImage(img, 0, 0);
  const ctx = c.getContext('2d');
  const pick = function(x, y){
    const d = ctx.getImageData(x, y, 1, 1).data;
    return [d[0], d[1], d[2]];
  };
  // 大西洋中部（海洋）、欧洲内陆（陆地）
  return JSON.stringify({
    ocean: pick(1800, 700),
    inland: pick(2900, 620),
    size: [img.naturalWidth, img.naturalHeight]
  });
})()`);
// 点海洋省看空态
out.empty = await evalJS(`(async()=>{
  // 找一个 sea 省
  let pid = 0;
  for(const k in MAP.idx){
    const r = MAP.idx[k];
    if(r && String(r.type||'').toLowerCase() === 'sea'){ pid = Number(k); break; }
  }
  mapShowOps(pid, 0);
  await new Promise(r=>setTimeout(r,900));
  const box = document.getElementById('selBox');
  const side = document.getElementById('mapSide');
  return JSON.stringify({pid,
    text: (box?box.textContent:'').slice(0,60),
    cardW: (box && box.querySelector('.mp-empty-card') ? Math.round(box.querySelector('.mp-empty-card').getBoundingClientRect().width) : 0),
    sideW: side ? Math.round(side.getBoundingClientRect().width) : 0});
})()`);
await sleep(600);
await shot('qa/shots/v1182_polit_fixed.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
