// v1.3.0 省份细化 UI 实测（副本 mod）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9436;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_refine', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 300) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(7000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.open = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  return JSON.stringify({ready: MAP.ready});
})()`);
// 选大省 13063 并预览
out.preview = await evalJS(`(async()=>{
  mapSelectProvince(13063);
  await new Promise(r=>setTimeout(r,300));
  document.querySelector('.side-tab[data-tab="refine"]').click();
  await new Promise(r=>setTimeout(r,200));
  document.getElementById('rfK').value = '4';
  document.getElementById('rfPreview').click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,300));
    const t = document.getElementById('rfStat').textContent;
    if(t.indexOf('切成') >= 0 || t.indexOf('失败') >= 0) break; }
  return JSON.stringify({stat: document.getElementById('rfStat').textContent,
    applyDisabled: document.getElementById('rfApply').disabled});
})()`);

await sleep(400);
await shot('qa/shots/v130_refine_preview.png');
// 应用
out.apply = await evalJS(`(async()=>{
  window.confirm = ()=>true;
  document.getElementById('rfApply').click();
  for(let i=0;i<80;i++){ await new Promise(r=>setTimeout(r,400));
    const t = document.getElementById('rfStat').textContent;
    if(t.indexOf('已切') >= 0 || t.indexOf('失败') >= 0) break; }
  return JSON.stringify({stat: document.getElementById('rfStat').textContent});
})()`);
await sleep(3000);
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
