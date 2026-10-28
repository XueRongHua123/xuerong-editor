// v1.9.2 图层预设实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9460;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v192', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 180));
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
  await new Promise(r=>setTimeout(r,800));
  return JSON.stringify({presets: document.querySelectorAll('.lt-preset').length,
    active: (document.querySelector('.lt-preset.on')||{}).textContent || '(无)'});
})()`);
// 逐个预设切换，记录每个图层状态
out.switch = await evalJS(`(async()=>{
  const res = [];
  for(const p of ['terrain','state','prov','polit','region','raw']){
    document.querySelector('.lt-preset[data-preset="' + p + '"]').click();
    await new Promise(r=>setTimeout(r,400));
    const vis = {};
    ['mapLProv','mapLPolit','mapLTerrain','mapLState','mapLRegion','mapLBase'].forEach(id=>{
      vis[id] = document.getElementById(id).checked;
    });
    const shown = Object.entries(vis).filter(([k,v])=>v).map(([k])=>k.replace('mapL','').toLowerCase());
    res.push({preset: p, on: shown,
      activeBtn: (document.querySelector('.lt-preset.on')||{}).textContent});
  }
  return JSON.stringify(res);
})()`);
// 停在州视图截图
await evalJS(`document.querySelector('.lt-preset[data-preset="state"]').click()`);
await sleep(700);
await shot('qa/shots/v192_preset_state.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
