// v0.63 验证：缩放下的环形菜单、AI 面板定位/关闭、雪绒显隐互切
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9349;
const URL = process.argv[2] || 'http://127.0.0.1:8903/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v063', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 150));
};
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 220) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
// 模拟用户开着"大字号"（zoom 1.06）
await evalJS(`applySize('large')`);
await sleep(600);

const out = {};
out.radial = await evalJS(`(()=>{
  const b = document.getElementById('aiBubble');
  b.style.left = '1180px'; b.style.top = '700px'; b.style.right = 'auto'; b.style.bottom = 'auto';
  openRadial();
  const z = uiZoom();
  const br = b.getBoundingClientRect();
  const cx = br.left + br.width/2, cy = br.top + br.height/2;
  const items = [...document.querySelectorAll('#aiRadial .rad-item')];
  const dists = items.map(el=>{
    const r = el.getBoundingClientRect();
    const dx = (r.left + r.width/2) - cx, dy = (r.top + r.height/2) - cy;
    return Math.round(Math.sqrt(dx*dx + dy*dy));
  });
  const names = items.map(x=>x.dataset.name);
  return JSON.stringify({zoom: z, count: items.length, dists, names,
    mascotItem: (document.querySelector('#aiRadial [data-act="mascot"]')||{}).dataset ? document.querySelector('#aiRadial [data-act="mascot"]').dataset.name : null});
})()`);
await sleep(500);
await shot('qa/shots/v0.63_radial_zoom.png');

out.aiPanel = await evalJS(`(async()=>{
  closeRadial();
  await openAI();
  await new Promise(r=>setTimeout(r,600));
  const el = document.getElementById('aiModal');
  const r = el.getBoundingClientRect();
  const z = uiZoom();
  return JSON.stringify({w: Math.round(r.width), h: Math.round(r.height),
    left: Math.round(r.left), top: Math.round(r.top),
    inside: r.left >= -1 && r.top >= -1 && r.right <= window.innerWidth + 1 && r.bottom <= window.innerHeight + 1,
    closeVisible: (()=>{ const b = document.getElementById('aiClose').getBoundingClientRect(); return b.top >= 0 && b.bottom <= window.innerHeight && b.right <= window.innerWidth; })()
  });
})()`);
await shot('qa/shots/v0.63_ai_panel.png');

out.aiDrag = await evalJS(`(()=>{
  const el = document.getElementById('aiModal');
  const head = el.querySelector('.diff-head');
  const r0 = el.getBoundingClientRect();
  const z = uiZoom();
  head.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true, clientX: r0.left + 40, clientY: r0.top + 10}));
  window.dispatchEvent(new PointerEvent('pointermove', {bubbles:true, clientX: r0.left + 40 - 300, clientY: r0.top + 10 - 200}));
  window.dispatchEvent(new PointerEvent('pointerup', {bubbles:true}));
  const r1 = el.getBoundingClientRect();
  return JSON.stringify({movedX: Math.round((r1.left - r0.left) / z), movedY: Math.round((r1.top - r0.top) / z),
    left: el.style.left, top: el.style.top});
})()`);

out.esc = await evalJS(`(()=>{
  const ev = new KeyboardEvent('keydown', {key:'Escape', bubbles:true});
  document.dispatchEvent(ev);
  return JSON.stringify({closed: !document.getElementById('aiModal').classList.contains('show')});
})()`);

out.mascotToggle = await evalJS(`(async()=>{
  showMascotFloat(true);
  openRadial();
  const first = document.querySelector('#aiRadial [data-act="mascot"]').dataset.name;
  document.querySelector('#aiRadial [data-act="mascot"]').click();
  await new Promise(r=>setTimeout(r,300));
  const hidden = document.getElementById('mascotFloat').style.display === 'none';
  openRadial();
  const second = document.querySelector('#aiRadial [data-act="mascot"]').dataset.name;
  document.querySelector('#aiRadial [data-act="mascot"]').click();
  await new Promise(r=>setTimeout(r,300));
  const shown = document.getElementById('mascotFloat').style.display !== 'none';
  closeRadial();
  return JSON.stringify({first, second, hidden, shown, stateSaved: localStorage.getItem('mascotFloatState')});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
