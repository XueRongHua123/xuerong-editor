// v1.21.3 模板编辑界面实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9496;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_tu', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 260) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8897/' });
await sleep(8000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.elems = await evalJS(`(async()=>{
  document.getElementById('mapEntry') && document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  await new Promise(r=>setTimeout(r,600));
  return JSON.stringify({
    hasLoad: !!document.getElementById('tplLoad'),
    hasList: !!document.getElementById('tplList'),
    hasGrid: !!document.getElementById('tplGrid'),
    hasSup: !!document.getElementById('tplSup'),
    editorHidden: (()=>{const e=document.getElementById('tplEditor'); return e? getComputedStyle(e).display : '?'})()
  });
})()`);
out.load = await evalJS(`(async()=>{
  const b = document.getElementById('tplLoad');
  if(!b) return JSON.stringify({error:'没有载入按钮'});
  b.click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,400));
    const t = document.getElementById('tplMsg').textContent;
    if(t && t.indexOf('读取模板') < 0 && t.length > 3) break; }
  const box = document.getElementById('tplList');
  return JSON.stringify({
    msg: (document.getElementById('tplMsg').textContent||'').slice(0,60),
    rows: box ? box.children.length : -1
  });
})()`);
out.open = await evalJS(`(async()=>{
  const box = document.getElementById('tplList');
  if(!box || !box.children.length) return JSON.stringify({error:'列表空'});
  box.children[0].click();
  await new Promise(r=>setTimeout(r,500));
  const g = document.getElementById('tplGrid');
  const s = document.getElementById('tplSup');
  return JSON.stringify({
    editorShown: (()=>{const e=document.getElementById('tplEditor'); return e? getComputedStyle(e).display : '?'})(),
    gridCells: g ? g.children.length : -1,
    supCells: s ? s.children.length : -1,
    nameVal: (document.getElementById('tplName')||{}).value || ''
  });
})()`);
out.bats = await evalJS(`(async()=>{
  const r = await (await fetch('/api/battalions', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'})).json();
  return JSON.stringify({ok: r.ok, total: r.total, groups: (r.groups||[]).length});
})()`);
await sleep(400);
await shot('qa/shots/v12130_tpl.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
