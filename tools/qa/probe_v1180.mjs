// v1.18.0 州细化实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9484;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_sr3', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  await new Promise(r=>setTimeout(r,600));
  // 州 351 的某个省：从 centers 里找（用 idx 反查）
  let pid = 0;
  for(const k in MAP.idx){ if(MAP.idx[k] && Number(MAP.idx[k].state) === 351){ pid = Number(k); break; } }
  mapShowOps(pid, 351);
  await new Promise(r=>setTimeout(r,1400));
  return JSON.stringify({pid, curState: window.__curStateId,
    hasK: !!document.getElementById('stRefineK'),
    hasPreview: !!document.getElementById('stRefinePreview')});
})()`);
out.preview = await evalJS(`(async()=>{
  const k = document.getElementById('stRefineK');
  if(!k) return JSON.stringify({error:'没有细化控件'});
  k.value = '3';
  document.getElementById('stRefinePreview').click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,400));
    const t = document.getElementById('stRefineMsg').textContent;
    if(t && t.indexOf('计算中') < 0) break; }
  return JSON.stringify({msg: document.getElementById('stRefineMsg').textContent.slice(0,220)});
})()`);
await sleep(500);
await shot('qa/shots/v1180_state_refine.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
