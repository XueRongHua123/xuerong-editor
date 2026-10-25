// 缩放验收：滚轮是否以鼠标为锚点、缩放后坐标换算是否正确
import { spawn } from 'node:child_process';
const PORT = 9339;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_zoom', '--window-size=1600,1000', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map();
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: r.result.exceptionDetails.exception?.description };
  return r.result?.result?.value;
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(7000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
await sleep(500);

const out = {};

// 选一个屏幕内可见的节点，取其中心
const pick = await evalJS(`(()=>{
  const nodes=[...document.querySelectorAll('#viewport .node')];
  const vis=nodes.filter(n=>{const r=n.getBoundingClientRect(); return r.width>0 && r.left>100 && r.top>120 && r.right<1550 && r.bottom<960;});
  const n=vis[Math.floor(vis.length/2)];
  if(!n) return null;
  const r=n.getBoundingClientRect();
  return JSON.stringify({id:n.dataset.id, x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), k:view.k});
})()`);
out.pick = pick;
const p = JSON.parse(pick);

const centerOf = async id => evalJS(`(()=>{const n=document.querySelector('#viewport .node[data-id="${id}"]'); if(!n) return null; const r=n.getBoundingClientRect(); return JSON.stringify({x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), k:view.k});})()`);

const before = JSON.parse(await centerOf(p.id));
// 在节点中心滚 3 格放大
for (let i = 0; i < 3; i++) {
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: p.x, y: p.y, deltaX: 0, deltaY: -120, modifiers: 0 });
  await sleep(120);
}
await sleep(300);
const after = JSON.parse(await centerOf(p.id));
out.mouseZoom = {
  before, after,
  drift: { x: Math.round(after.x - before.x), y: Math.round(after.y - before.y) },
  zoomed: Math.round((after.k / before.k - 1) * 100) + '%'
};

// 缩小回去
for (let i = 0; i < 3; i++) {
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: p.x, y: p.y, deltaX: 0, deltaY: 120, modifiers: 0 });
  await sleep(120);
}
await sleep(300);
const back = JSON.parse(await centerOf(p.id));
out.mouseZoomOut = { drift: { x: Math.round(back.x - before.x), y: Math.round(back.y - before.y) }, k: back.k };

// 屏幕锚点模式：滚轮后应保持画布中心处的场景点不动
out.screenMode = await evalJS(`(()=>{
  zoomAnchor='screen';
  const rect = svg.getBoundingClientRect();
  const cx = rect.left + rect.width/2, cy = rect.top + rect.height/2;
  const p0 = screenToSvg({clientX: cx, clientY: cy});
  const k0 = view.k;
  applyZoomFactor(1.5);
  const p1 = screenToSvg({clientX: cx, clientY: cy});
  const res = {k0, k1: view.k, driftX: +(p1.x-p0.x).toFixed(2), driftY: +(p1.y-p0.y).toFixed(2), text: document.getElementById('zoomAnchorBtn').textContent};
  zoomAnchor='mouse';
  return JSON.stringify(res);
})()`);

// 缩放后坐标换算：屏幕移动 110px 在 k=0.5 时应等于 220 场景单位
out.coordMath = await evalJS(`(()=>{
  view={x:0,y:0,k:0.5}; applyView();
  const a = screenToSvg({clientX: 400, clientY: 300});
  const b = screenToSvg({clientX: 510, clientY: 300});
  view={x:0,y:0,k:2}; applyView();
  const c = screenToSvg({clientX: 400, clientY: 300});
  const d = screenToSvg({clientX: 510, clientY: 300});
  return JSON.stringify({k05_dx: +(b.x-a.x).toFixed(1), k2_dx: +(d.x-c.x).toFixed(1), expect_k05: 220, expect_k2: 55});
})()`);

out.label = await evalJS(`document.getElementById('zoomLevel').textContent`);
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
