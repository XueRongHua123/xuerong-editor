// v0.99 合并面板实测（副本 mod）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import crypto from 'node:crypto';
const PORT = 9392;
const BMP = 'D:\\大肥鱼工作区\\HOI4 MUVLUVsub mod 制作\\work\\tmp\\paintmod\\map\\provinces.bmp';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const md5 = p => crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex');
const before = md5(BMP);
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_merge', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 240) };
  return r.result?.result?.value;
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.open = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP) break; }
  await (await fetch('/api/map_build', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{"force":false}'})).json();
  await mapLoadMeta(MAP.root || '');
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(MAP.ready) break; }
  mapSetMode('paint');
  return JSON.stringify({ready: MAP.ready, panelShown: document.getElementById('paintBox').style.display !== 'none'});
})()`);
out.neighbors = await evalJS(`(async()=>{
  document.getElementById('mgSrcPid').value = '221';
  document.getElementById('mgNeighbors').click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,200));
    if(document.querySelectorAll('#mgNbList [data-pid]').length) break; }
  return JSON.stringify({count: document.querySelectorAll('#mgNbList [data-pid]').length,
    first: (document.querySelector('#mgNbList [data-pid]') || {}).textContent,
    stat: document.getElementById('mgStat').textContent});
})()`);
out.preview = await evalJS(`(async()=>{
  document.getElementById('mgDstPid').value = '2824';
  document.getElementById('mgPreview').click();
  await new Promise(r=>setTimeout(r,6000));
  return JSON.stringify({stat: document.getElementById('mgStat').textContent});
})()`);
out.apply = await evalJS(`(async()=>{
  window.confirm = ()=>true;
  document.getElementById('mgApply').click();
  await new Promise(r=>setTimeout(r,20000));
  return JSON.stringify({stat: document.getElementById('mgStat').textContent});
})()`);
await sleep(2000);
out.file = JSON.stringify({ changed: md5(BMP) !== before });
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
