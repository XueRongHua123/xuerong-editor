// v0.62 环形菜单 / AI 面板拖动 / 看板娘缩放换装 / 卸载排序
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9348;
const URL = process.argv[2] || 'http://127.0.0.1:8903/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v062', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await sleep(400);

const out = {};
out.radial = await evalJS(`(()=>{
  openRadial();
  const items = [...document.querySelectorAll('#aiRadial .rad-item')];
  return JSON.stringify({
    shown: document.getElementById('aiRadial').classList.contains('show'),
    count: items.length,
    names: items.map(x=>x.dataset.name),
    firstPos: items[0].style.getPropertyValue('--tx') + ',' + items[0].style.getPropertyValue('--ty'),
    bubbleOpen: document.getElementById('aiBubble').classList.contains('open')
  });
})()`);
await sleep(400);
await shot('qa/shots/v0.62_radial.png');

out.radialAction = await evalJS(`(async()=>{
  document.querySelector('#aiRadial .rad-item[data-act="cmd"]').click();
  await new Promise(r=>setTimeout(r,400));
  return JSON.stringify({closed: !document.getElementById('aiRadial').classList.contains('show'),
    cmd: document.getElementById('cmdPalette').classList.contains('show')});
})()`);

out.aiPanel = await evalJS(`(async()=>{
  closeCmd();
  await openAI();
  await new Promise(r=>setTimeout(r,500));
  const el = document.getElementById('aiModal');
  const r = el.getBoundingClientRect();
  return JSON.stringify({w: Math.round(r.width), h: Math.round(r.height),
    vw: window.innerWidth, vh: window.innerHeight,
    inside: r.right <= window.innerWidth && r.bottom <= window.innerHeight,
    head: !!el.querySelector('.ai-head-drag')});
})()`);

out.aiDrag = await evalJS(`(()=>{
  const el = document.getElementById('aiModal');
  el.style.left = '120px'; el.style.top = '90px';
  const r = el.getBoundingClientRect();
  return JSON.stringify({left: el.style.left, top: el.style.top, w: Math.round(r.width), h: Math.round(r.height)});
})()`);

out.mascot = await evalJS(`(()=>{
  applyMascotWidth(420);
  const box = document.getElementById('mascotFloat');
  const before = document.getElementById('mascotImg').getAttribute('src');
  mascotStepSkin(1);
  const after = document.getElementById('mascotImg').getAttribute('src');
  return JSON.stringify({width: box.style.width, saved: localStorage.getItem('mascotFloatW'),
    before, after, name: document.getElementById('mascotSkinName').textContent});
})()`);
await shot('qa/shots/v0.62_mascot.png');

out.unload = await evalJS(`(async()=>{
  DATA.roots = [{name:'最老mod', path:'C:/old', readonly:false},
                {name:'中间mod', path:'C:/mid', readonly:false},
                {name:'最近mod', path:'C:/new', readonly:false}];
  openUnloadModal();
  await new Promise(r=>setTimeout(r,300));
  return JSON.stringify({order: [...document.querySelectorAll('#unloadList .ul-main b')].map(x=>x.textContent),
    firstTag: (document.querySelector('#unloadList .ul-tag')||{}).textContent,
    rows: document.querySelectorAll('#unloadList .ul-row').length});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
