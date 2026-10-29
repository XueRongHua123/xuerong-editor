// v1.13.0 战略区实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9472;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_sr', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  document.querySelector('.side-tab[data-tab="rail"]').click();
  await new Promise(r=>setTimeout(r,1500));
  document.getElementById('srRefresh').click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,400));
    if(document.querySelectorAll('#srList .sr-row').length) break; }
  return JSON.stringify({rows: document.querySelectorAll('#srList .sr-row').length,
    stat: document.getElementById('srStat').textContent.slice(0,40),
    hasCreate: !!document.getElementById('srCreate')});
})()`);
out.create = await evalJS(`(async()=>{
  MAP.sel = [17300, 17301];
  mapRenderSelection();
  await new Promise(r=>setTimeout(r,300));
  document.getElementById('srNewName').value = 'UI测试区';
  document.getElementById('srCreate').click();
  for(let i=0;i<50;i++){ await new Promise(r=>setTimeout(r,400));
    const t = document.getElementById('srMsg').textContent;
    if(t && t.indexOf('创建中') < 0) break; }
  return JSON.stringify({msg: document.getElementById('srMsg').textContent.slice(0,80),
    rows: document.querySelectorAll('#srList .sr-row').length});
})()`);
out.pick = await evalJS(`(async()=>{
  const rows = document.querySelectorAll('#srList .sr-row');
  const last = rows[rows.length-1];
  last.click();
  await new Promise(r=>setTimeout(r,400));
  return JSON.stringify({shown: document.getElementById('srEdit').style.display,
    cur: document.getElementById('srCur').textContent});
})()`);
await sleep(500);
await shot('qa/shots/v1130_sr.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
