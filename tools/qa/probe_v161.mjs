// v1.6.1 视野改造实测：拖动/缩放/适应不再丢内容，缩放以鼠标为中心
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9450;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v161', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 180));
};
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 300) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
const wheel = async (x, y, dy) => { await send('Input.dispatchMouseEvent', {type:'mouseWheel', x, y, deltaX:0, deltaY:dy}); await sleep(300); };
const drag = async (x1, y1, x2, y2) => {
  await send('Input.dispatchMouseEvent', {type:'mousePressed', x:x1, y:y1, button:'left', clickCount:1, buttons:1});
  await sleep(60);
  await send('Input.dispatchMouseEvent', {type:'mouseMoved', x:(x1+x2)/2, y:(y1+y2)/2, button:'left', buttons:1});
  await sleep(60);
  await send('Input.dispatchMouseEvent', {type:'mouseMoved', x:x2, y:y2, button:'left', buttons:1});
  await sleep(60);
  await send('Input.dispatchMouseEvent', {type:'mouseReleased', x:x2, y:y2, button:'left', clickCount:1, buttons:0});
  await sleep(300);
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(7000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};

// 事件树
out.ev = await evalJS(`(async()=>{
  const b = document.getElementById('evOpen');
  const label = b.textContent;
  b.click();
  for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,300));
    if(document.querySelectorAll('#evSvg .ev-node').length) break; }
  await new Promise(r=>setTimeout(r,400));
  const svg = document.getElementById('evSvg');
  const body = document.getElementById('evBody');
  return JSON.stringify({label, vb: svg.getAttribute('viewBox'),
    dataW: svg.getAttribute('data-w'), dataH: svg.getAttribute('data-h'),
    bodyOverflow: getComputedStyle(body).overflow,
    nodes: document.querySelectorAll('#evSvg .ev-node').length});
})()`);

// 拖动后视野是否覆盖内容（不应出现空白）
const box = await evalJS(`(()=>{ const r = document.getElementById('evBody').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; })()`);
await drag(box[0] + box[2]/2, box[1] + box[3]/2, box[0] + box[2]/2 - 200, box[1] + box[3]/2 - 100);
out.afterDrag = await evalJS(`(()=>{ const s = document.getElementById('evSvg'); return s.getAttribute('viewBox'); })()`);
await shot('qa/shots/v161_ev_drag.png');

// 适应后必须能看到节点（检查节点是否落在视野内）
out.fit = await evalJS(`(async()=>{
  document.getElementById('evFit').click();
  await new Promise(r=>setTimeout(r,400));
  const s = document.getElementById('evSvg');
  const r = s.getBoundingClientRect();
  let visible = 0;
  document.querySelectorAll('#evSvg .ev-node').forEach(n=>{
    const nb = n.getBoundingClientRect();
    if(nb.width > 0 && nb.right > r.left && nb.left < r.right && nb.bottom > r.top && nb.top < r.bottom) visible++;
  });
  return JSON.stringify({vb: s.getAttribute('viewBox'), visible,
    total: document.querySelectorAll('#evSvg .ev-node').length});
})()`);
await shot('qa/shots/v161_ev_fit.png');

// 鼠标中心缩放：缩放前后鼠标下的内容点应基本不变
out.zoomAnchor = await evalJS(`(async()=>{
  const s = document.getElementById('evSvg');
  const r = s.getBoundingClientRect();
  const px = r.left + r.width * 0.25, py = r.top + r.height * 0.25;
  function imgAt(clientX, clientY){
    const v = s.getAttribute('viewBox').split(/[\\s,]+/).map(Number);
    const rr = s.getBoundingClientRect();
    return [v[0] + (clientX - rr.left) / rr.width * v[2],
            v[1] + (clientY - rr.top) / rr.height * v[3]];
  }
  const before = imgAt(px, py);
  // 直接改动 viewBox 模拟滚轮（走真实 wheel 会被 body 的 listener 处理）
  s.dispatchEvent(new WheelEvent('wheel', {deltaY:-120, clientX:px, clientY:py, bubbles:true}));
  await new Promise(r2=>setTimeout(r2,300));
  const after = imgAt(px, py);
  const dx = Math.abs(after[0]-before[0]), dy = Math.abs(after[1]-before[1]);
  return JSON.stringify({before: before.map(n=>Number(n.toFixed(1))),
    after: after.map(n=>Number(n.toFixed(1))),
    drift: [Number(dx.toFixed(1)), Number(dy.toFixed(1))],
    anchored: dx < 6 && dy < 6});
})()`);
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
