// v0.98 前端涂色实测（副本 mod，不碰真实 mod）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import crypto from 'node:crypto';
const PORT = 9390;
const URL = 'http://127.0.0.1:8891/';
const BMP = 'D:\\大肥鱼工作区\\HOI4 MUVLUVsub mod 制作\\work\\tmp\\paintmod\\map\\provinces.bmp';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const md5 = p => crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex');
const before = md5(BMP);

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_paint', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);

const out = {};
// 打开地图并先构建图层（涂色需要 id 画布）
out.build = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP) break; }
  const r = await (await fetch('/api/map_build', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{"force":false}'})).json();
  await mapLoadMeta(MAP.root || '');
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(MAP.ready) break; }
  return JSON.stringify({built: !!r.ok, ready: MAP.ready, k: Number((MAP.k||0).toFixed(2))});
})()`);

// 切涂色模式
out.mode = await evalJS(`(()=>{
  mapSetMode('paint');
  return JSON.stringify({mode: MAP.mode,
    panelShown: document.getElementById('paintBox').style.display !== 'none',
    selHidden: document.getElementById('selBox').style.display === 'none'});
})()`);

// 填目标省 + 模拟拖动涂抹
out.paint = await evalJS(`(async()=>{
  document.getElementById('paintTarget').value = '221';
  document.getElementById('paintR').value = '6';
  document.getElementById('paintRVal').textContent = '6';
  const wrap = document.getElementById('mapStageWrap');
  const rect = wrap.getBoundingClientRect();
  const cx = rect.left + rect.width/2, cy = rect.top + rect.height/2;
  const mk = (type, x, y)=> new PointerEvent(type, {bubbles:true, cancelable:true, button:0, clientX:x, clientY:y, pointerId:1});
  wrap.dispatchEvent(mk('pointerdown', cx, cy));
  for(let i=1;i<=6;i++){
    wrap.dispatchEvent(mk('pointermove', cx + i*7, cy + i*3));
    await new Promise(r=>setTimeout(r,60));
  }
  window.dispatchEvent(mk('pointerup', cx + 42, cy + 18));
  await new Promise(r=>setTimeout(r,500));
  return JSON.stringify({stat: document.getElementById('paintStat').textContent,
    pid: document.getElementById('paintPid').textContent});
})()`);

// 应用
out.apply = await evalJS(`(async()=>{
  document.getElementById('paintApply').click();
  await new Promise(r=>setTimeout(r,1200));
  return JSON.stringify({stat: document.getElementById('paintStat').textContent,
    status: document.getElementById('status').textContent});
})()`);
await sleep(1500);
const after = md5(BMP);
out.file = JSON.stringify({changed: after !== before});

// 撤销
out.undo = await evalJS(`(async()=>{
  document.getElementById('paintUndo').click();
  await new Promise(r=>setTimeout(r,1500));
  return JSON.stringify({status: document.getElementById('status').textContent});
})()`);
await sleep(1500);
out.restored = JSON.stringify({md5Back: md5(BMP) === before});
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
