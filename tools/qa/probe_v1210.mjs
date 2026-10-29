// v1.21.0 州编辑补全实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9490;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_sf', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  let pid = 0;
  for(const k in MAP.idx){ if(MAP.idx[k] && Number(MAP.idx[k].state) === 1){ pid = Number(k); break; } }
  mapShowOps(pid, 1);
  await new Promise(r=>setTimeout(r,1800));
  return JSON.stringify({pid, cur: window.__curStateId,
    hasCat: !!document.getElementById('mvCat'),
    hasMp: !!document.getElementById('mvManpower'),
    hasCores: !!document.getElementById('mvCores'),
    bldRows: document.querySelectorAll('#mvBuildings .st-bld').length,
    catVal: (document.getElementById('mvCat')||{}).value,
    mpVal: (document.getElementById('mvManpower')||{}).value,
    coresVal: (document.getElementById('mvCores')||{}).value});
})()`);
out.save = await evalJS(`(async()=>{
  const cat = document.getElementById('mvCat');
  if(!cat) return JSON.stringify({error:'没有控件'});
  cat.value = 'city';
  document.getElementById('mvManpower').value = '500000';
  document.getElementById('mvCatSave').click();
  for(let i=0;i<25;i++){ await new Promise(r=>setTimeout(r,400));
    const t = document.getElementById('mvCatMsg').textContent;
    if(t && t.indexOf('写入中') < 0) break; }
  return JSON.stringify({msg: document.getElementById('mvCatMsg').textContent.slice(0,70)});
})()`);
await sleep(500);
await shot('qa/shots/v1210_state_full.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
