// v1.6.0 缩放拖动 + 事件树独立入口 + 只看下游 + 双击编辑
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9448;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v160', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
const wheel = async (x, y, dy) => {
  await send('Input.dispatchMouseEvent', {type:'mouseWheel', x, y, deltaX:0, deltaY:dy});
  await sleep(250);
};
const drag = async (x1, y1, x2, y2) => {
  await send('Input.dispatchMouseEvent', {type:'mousePressed', x:x1, y:y1, button:'left', clickCount:1, buttons:1});
  await sleep(80);
  await send('Input.dispatchMouseEvent', {type:'mouseMoved', x:(x1+x2)/2, y:(y1+y2)/2, button:'left', buttons:1});
  await sleep(80);
  await send('Input.dispatchMouseEvent', {type:'mouseMoved', x:x2, y:y2, button:'left', buttons:1});
  await sleep(80);
  await send('Input.dispatchMouseEvent', {type:'mouseReleased', x:x2, y:y2, button:'left', clickCount:1, buttons:0});
  await sleep(250);
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(7000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};

// 国策预览：缩放 + 拖动
out.ft = await evalJS(`(async()=>{
  document.getElementById('ftOpen').click();
  for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,300));
    if(document.querySelectorAll('#ftSvg .ft-node').length) break; }
  const svg = document.getElementById('ftSvg');
  return JSON.stringify({vb0: svg.getAttribute('viewBox'), hasPan: !!svg._pan,
    nodes: document.querySelectorAll('#ftSvg .ft-node').length});
})()`);
const vb1 = await evalJS(`document.getElementById('ftSvg').getAttribute('viewBox')`);
const r1 = await evalJS(`(()=>{ const r = document.getElementById('ftBody').getBoundingClientRect(); return [Math.round(r.left+r.width/2), Math.round(r.top+r.height/2)]; })()`);
await wheel(r1[0], r1[1], -120);
const vb2 = await evalJS(`document.getElementById('ftSvg').getAttribute('viewBox')`);
await drag(r1[0], r1[1], r1[0] - 120, r1[1] - 80);
const vb3 = await evalJS(`document.getElementById('ftSvg').getAttribute('viewBox')`);
out.ftPan = JSON.stringify({ before: vb1, afterWheel: vb2, afterDrag: vb3,
  wheelChanged: vb1 !== vb2, dragChanged: vb2 !== vb3 });
await evalJS(`document.getElementById('ftClose').click()`);
await sleep(300);

// 事件树：独立入口 + 缩放 + 拖动 + 只看下游
out.ev = await evalJS(`(async()=>{
  const b = document.getElementById('evOpen');
  if(!b) return JSON.stringify({error:'没有独立入口'});
  b.click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,300));
    if(document.getElementById('evPick').options.length) break; }
  for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,300));
    if(document.querySelectorAll('#evSvg .ev-node').length) break; }
  const svg = document.getElementById('evSvg');
  return JSON.stringify({title: document.querySelector('#evHead b').textContent,
    nodes: document.querySelectorAll('#evSvg .ev-node').length,
    hasPan: !!svg._pan, vb: svg.getAttribute('viewBox'),
    hasFocusBtn: !!document.getElementById('evFocus')});
})()`);
const evb1 = await evalJS(`document.getElementById('evSvg').getAttribute('viewBox')`);
const r2 = await evalJS(`(()=>{ const r = document.getElementById('evBody').getBoundingClientRect(); return [Math.round(r.left+r.width/2), Math.round(r.top+r.height/2)]; })()`);
await wheel(r2[0], r2[1], -120);
const evb2 = await evalJS(`document.getElementById('evSvg').getAttribute('viewBox')`);
out.evPan = JSON.stringify({ before: evb1, afterWheel: evb2, wheelChanged: evb1 !== evb2 });

out.onlyDown = await evalJS(`(async()=>{
  const before = document.querySelectorAll('#evSvg .ev-node').length;
  const n = document.querySelectorAll('#evSvg .ev-node')[2];
  n.dispatchEvent(new MouseEvent('click', {bubbles:true}));
  await new Promise(r=>setTimeout(r,300));
  const fb = document.getElementById('evFocus');
  const enabled = !fb.disabled;
  fb.click();
  await new Promise(r=>setTimeout(r,700));
  const after = document.querySelectorAll('#evSvg .ev-node').length;
  const info = document.getElementById('evInfo').textContent;
  // 恢复
  document.getElementById('evAll').click();
  await new Promise(r=>setTimeout(r,700));
  const back = document.querySelectorAll('#evSvg .ev-node').length;
  return JSON.stringify({before, enabled, after, back, info: info.slice(0,50)});
})()`);
await sleep(400);
await shot('qa/shots/v160_event_tree.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
