// v1.9.3 按预设点选实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9462;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v193', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await sleep(7000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.open = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  await new Promise(r=>setTimeout(r,700));
  return JSON.stringify({unit: window.MAP_PICK_UNIT, hasPick: typeof window.mapPickUnit});
})()`);

// 逐个预设 + 点同一个省，看右侧显示什么
out.pick = await evalJS(`(async()=>{
  const res = [];
  const pid = 13063;
  for(const p of ['prov','state','polit','region','terrain']){
    document.querySelector('.lt-preset[data-preset="' + p + '"]').click();
    await new Promise(r=>setTimeout(r,300));
    mapShowOps(pid, (MAP.idx[pid]||{}).state || 0);
    await new Promise(r=>setTimeout(r,300));
    const box = document.getElementById('selBox');
    res.push({preset: p, unit: window.MAP_PICK_UNIT,
      text: (box.textContent || '').replace(/\\s+/g,' ').trim().slice(0, 70)});
  }
  return JSON.stringify(res);
})()`);
await evalJS(`document.querySelector('.lt-preset[data-preset="polit"]').click()`);
await sleep(300);
await evalJS(`mapShowOps(13063, 0)`);
await sleep(500);
await shot('qa/shots/v193_pick_country.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
