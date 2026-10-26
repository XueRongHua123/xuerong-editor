// v0.82 选择/拖拽防护实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9364;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v082', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);

const out = {};
out.css = await evalJS(`(()=>{
  const b = getComputedStyle(document.body).userSelect;
  const inp = getComputedStyle(document.getElementById('aiPrompt') || document.body).userSelect;
  const pre = getComputedStyle(document.getElementById('aiOut') || document.body).userSelect;
  return JSON.stringify({body: b, input: inp, pre: pre});
})()`);

out.dragGuard = await evalJS(`(()=>{
  const img = document.querySelector('#mapStack img') || document.querySelector('img');
  const ev = new DragEvent('dragstart', {bubbles:true, cancelable:true});
  img.dispatchEvent(ev);
  return JSON.stringify({imgDraggable: img.draggable, dragPrevented: ev.defaultPrevented});
})()`);

out.ctxGuard = await evalJS(`(()=>{
  const stage = document.getElementById('mapStageWrap');
  const ev = new MouseEvent('contextmenu', {bubbles:true, cancelable:true});
  stage.dispatchEvent(ev);
  const inp = document.getElementById('mapSearch');
  const ev2 = new MouseEvent('contextmenu', {bubbles:true, cancelable:true});
  inp.dispatchEvent(ev2);
  return JSON.stringify({stageBlocked: ev.defaultPrevented, inputAllowed: !ev2.defaultPrevented});
})()`);

out.selection = await evalJS(`(async()=>{
  const stage = document.getElementById('mapStageWrap');
  const r = stage.getBoundingClientRect();
  stage.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true, clientX:r.left+200, clientY:r.top+200}));
  for(let i=0;i<6;i++){
    stage.dispatchEvent(new PointerEvent('pointermove', {bubbles:true, clientX:r.left+200+i*30, clientY:r.top+200+i*20}));
    await new Promise(x=>setTimeout(x,20));
  }
  window.dispatchEvent(new PointerEvent('pointerup', {bubbles:true}));
  const sel = String(window.getSelection() || '');
  return JSON.stringify({selectionLength: sel.length, text: sel.slice(0, 40)});
})()`);

out.selectable = await evalJS(`(()=>{
  const out = document.getElementById('aiOut');
  if(!out) return JSON.stringify({skip: true});
  const ev = new Event('selectstart', {bubbles:true, cancelable:true});
  out.dispatchEvent(ev);
  return JSON.stringify({aiOutSelectStartAllowed: !ev.defaultPrevented});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
