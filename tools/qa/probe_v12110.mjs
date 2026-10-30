// v1.21.1 部队图层与面板实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9494;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_ut', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await send('Page.navigate', { url: 'http://127.0.0.1:8895/' });
await sleep(8000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.elems = await evalJS(`(async()=>{
  document.getElementById('mapEntry') && document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  await new Promise(r=>setTimeout(r,800));
  return JSON.stringify({
    hasImg: !!document.getElementById('mapUnits'),
    hasCb: !!document.getElementById('mapLUnits'),
    imgSrc: (document.getElementById('mapUnits')||{}).src || '',
    imgVisible: (()=>{const e=document.getElementById('mapUnits'); return e? getComputedStyle(e).display : 'none'})()
  });
})()`);
out.toggle = await evalJS(`(async()=>{
  const cb = document.getElementById('mapLUnits');
  if(!cb) return JSON.stringify({error:'没有勾选框'});
  cb.checked = true;
  cb.dispatchEvent(new Event('change'));
  await new Promise(r=>setTimeout(r,300));
  const e = document.getElementById('mapUnits');
  return JSON.stringify({showAfterCheck: e ? getComputedStyle(e).display : 'none'});
})()`);
out.unitsApi = await evalJS(`(async()=>{
  const r = await (await fetch('/api/units', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'})).json();
  return JSON.stringify({ok: r.ok, tpl: r.templates_total, div: r.divisions_total,
    provs: Object.keys(r.by_prov||{}).length});
})()`);
await sleep(400);
await shot('qa/shots/v12110_units.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
