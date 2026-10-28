// v1.0.7 交互第二批：快捷键 / 悬停增强 / 状态栏 / 点穿
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9412;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_hk', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 300) };
  return r.result?.result?.value;
};
const key = async (k) => {
  await send('Input.dispatchKeyEvent', {type:'keyDown', key:k, text: k.length===1 ? k : undefined, windowsVirtualKeyCode: k.toUpperCase().charCodeAt(0)});
  await send('Input.dispatchKeyEvent', {type:'keyUp', key:k});
  await sleep(200);
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.open = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<150;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready && MAP.idCanvas) break; }
  return JSON.stringify({ready: MAP.ready});
})()`);

// 快捷键切模式
out.modes = [];
for (const [k, expect] of [['v','view'],['p','paint'],['s','state'],['v','view']]) {
  await key(k);
  const m = await evalJS(`MAP.mode`);
  out.modes.push({key:k, mode:m, ok: m === expect});
}

// 悬停信息
out.info = await evalJS(`mapInfo(221)`);

// 状态栏
out.status = await evalJS(`(()=>{
  mapGoto(2900, 700, 2.5);
  return JSON.stringify({pct: document.getElementById('msPct').textContent,
    sel: document.getElementById('msSel').textContent});
})()`);
await sleep(300);
const shot = await send('Page.captureScreenshot', { format: 'png' });
fs.writeFileSync('qa/shots/v107_hotkeys.png', Buffer.from(shot.result.data, 'base64'));

// Alt+滚轮调笔刷
out.brush = await evalJS(`(async()=>{
  mapSetMode('paint');
  document.getElementById('paintR').value = '4';
  const wrap = document.getElementById('mapStageWrap');
  const r = wrap.getBoundingClientRect();
  wrap.dispatchEvent(new WheelEvent('wheel', {deltaY:-100, altKey:true, clientX:r.left+300, clientY:r.top+300, bubbles:true, cancelable:true}));
  await new Promise(x=>setTimeout(x,200));
  return JSON.stringify({r: document.getElementById('paintR').value,
    label: document.getElementById('paintRVal').textContent});
})()`);
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
