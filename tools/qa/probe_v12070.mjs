// v1.20.7 接管完整性校验实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9492;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_wv', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await send('Page.navigate', { url: 'http://127.0.0.1:8893/' });
await sleep(8000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.ui = await evalJS(`(async()=>{
  document.getElementById('mapEntry') && document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  await new Promise(r=>setTimeout(r,500));
  return JSON.stringify({
    hasBtn: !!document.getElementById('wtBtn'),
    hasVerify: !!document.getElementById('wtVerify'),
    hasList: !!document.getElementById('wtList')
  });
})()`);
out.check = await evalJS(`(async()=>{
  const b = document.getElementById('wtVerify');
  if(!b) return JSON.stringify({error:'没有校验按钮'});
  b.click();
  for(let i=0;i<25;i++){ await new Promise(r=>setTimeout(r,400));
    const t = document.getElementById('wtMsg').textContent;
    if(t && t.indexOf('校验中') < 0 && t.length > 0) break; }
  const box = document.getElementById('wtList');
  return JSON.stringify({
    msg: (document.getElementById('wtMsg').textContent||'').slice(0,80),
    listLen: box ? box.innerHTML.length : 0,
    rows: box ? box.children.length : -1
  });
})()`);
out.targets = await evalJS(`(async()=>{
  const b = document.getElementById('wtBtn');
  if(!b) return JSON.stringify({error:'没有检查按钮'});
  b.click();
  for(let i=0;i<30;i++){ await new Promise(r=>setTimeout(r,400));
    const t = document.getElementById('wtMsg').textContent;
    if(t && t.indexOf('读取中') < 0 && t.length > 0) break; }
  const box = document.getElementById('wtList');
  return JSON.stringify({
    msg: (document.getElementById('wtMsg').textContent||'').slice(0,80),
    rows: box ? box.children.length : -1,
    adoptBtns: box ? box.querySelectorAll('.wt-adopt').length : -1
  });
})()`);
await sleep(400);
await shot('qa/shots/v12070_verify.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
