// v1.2.1 选中省份高亮实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9428;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_sel', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready && MAP.idCanvas) break; }
  // 放大看高亮效果
  mapGoto(1900, 2400, 4);
  await new Promise(r=>setTimeout(r,600));
  return JSON.stringify({ready: MAP.ready, hasSelCanvas: !!document.getElementById('mapSelCanvas'), k: MAP.k});
})()`);
out.pick = await evalJS(`(async()=>{
  // 找一个视口内较大的陆地省
  // 直接取视口内像素最多的省（不做质心筛选，避免 centers 字段差异）
  const cv0 = document.getElementById('mapSelCanvas');
  const x0 = Math.max(0, Math.floor(-MAP.x / MAP.k));
  const y0 = Math.max(0, Math.floor(-MAP.y / MAP.k));
  const x1 = Math.min(MAP.w, Math.ceil((cv0.width - MAP.x) / MAP.k));
  const y1 = Math.min(MAP.h, Math.ceil((cv0.height - MAP.y) / MAP.k));
  const d0 = MAP.idCanvas.getContext('2d').getImageData(x0, y0, Math.max(1,x1-x0), Math.max(1,y1-y0)).data;
  const cnt = {};
  for(let i=0;i<d0.length;i+=4){
    const pid = (d0[i]<<16)|(d0[i+1]<<8)|d0[i+2];
    if(pid) cnt[pid] = (cnt[pid]||0)+1;
  }
  const target = Number(Object.entries(cnt).sort((a,b)=>b[1]-a[1])[0][0]);
  mapSelectProvince(target);
  await new Promise(r=>setTimeout(r,700));
  const cv = document.getElementById('mapSelCanvas');
  const ctx = cv.getContext('2d');
  const d = ctx.getImageData(0,0,cv.width,cv.height).data;
  let painted = 0;
  for(let i=3;i<d.length;i+=4) if(d[i] > 0) painted++;
  return JSON.stringify({pid: target, canvas: [cv.width, cv.height], paintedPixels: painted});
})()`);
await sleep(500);
await shot('qa/shots/v121_select_highlight.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
