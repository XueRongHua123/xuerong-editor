// v1.17.0 州视图编辑实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9480;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_se', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(7500);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.open = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  document.querySelector('.lt-preset[data-preset="state"]').click();
  await new Promise(r=>setTimeout(r,800));
  mapShowOps(3838, 0);
  await new Promise(r=>setTimeout(r,1500));
  return JSON.stringify({unit: window.MAP_PICK_UNIT,
    curState: window.__curStateId,
    hasOwner: !!document.getElementById('stOwner'),
    hasAdd: !!document.getElementById('stProvAdd'),
    ownerVal: (document.getElementById('stOwner')||{}).value});
})()`);
out.owner = await evalJS(`(async()=>{
  const el = document.getElementById('stOwner');
  if(!el) return JSON.stringify({error:'面板没渲染'});
  const old = el.value;
  el.value = 'GER';
  document.getElementById('stOwnerSave').click();
  for(let i=0;i<25;i++){ await new Promise(r=>setTimeout(r,400));
    const t = document.getElementById('stOwnerMsg').textContent;
    if(t && t.indexOf('写入中') < 0) break; }
  return JSON.stringify({from: old, to: 'GER',
    msg: document.getElementById('stOwnerMsg').textContent.slice(0,80)});
})()`);
out.batch = await evalJS(`(async()=>{
  MAP.sel = [17300, 17301];
  mapRenderSelection();
  await new Promise(r=>setTimeout(r,300));
  document.getElementById('stProvAdd').click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,500));
    const t = document.getElementById('stProvMsg').textContent;
    if(t && t.indexOf('写入中') < 0) break; }
  return JSON.stringify({msg: document.getElementById('stProvMsg').textContent.slice(0,90)});
})()`);
await sleep(600);
await shot('qa/shots/v1170_state_edit.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
