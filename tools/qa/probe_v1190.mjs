// v1.19.0 孤儿 tag 诊断 + 严格政治图实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9488;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_or', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
out.orphan = await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  document.getElementById('orphanBtn').click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,400));
    const t = document.getElementById('orphanStat').textContent;
    if(t && t.indexOf('检查中') < 0) break; }
  return JSON.stringify({stat: document.getElementById('orphanStat').textContent.slice(0,120),
    rows: document.querySelectorAll('#orphanList > div').length});
})()`);
out.strict = await evalJS(`(async()=>{
  document.querySelector('.lt-preset[data-preset="polit"]').click();
  await new Promise(r=>setTimeout(r,1500));
  const polit = document.getElementById('mapPolit');
  const normalSrc = polit.getAttribute('src');
  // 采样欧洲
  const sample = function(){
    const c = document.createElement('canvas');
    c.width = polit.naturalWidth; c.height = polit.naturalHeight;
    c.getContext('2d').drawImage(polit, 0, 0);
    const d = c.getContext('2d').getImageData(2900, 620, 1, 1).data;
    return [d[0], d[1], d[2]];
  };
  const before = sample();
  const st = document.getElementById('mapLStrict');
  st.checked = true;
  st.dispatchEvent(new Event('change'));
  for(let i=0;i<30;i++){ await new Promise(r=>setTimeout(r,300));
    if(polit.complete && polit.getAttribute('src') !== normalSrc) break; }
  await new Promise(r=>setTimeout(r,600));
  const after = sample();
  return JSON.stringify({srcNormal: (normalSrc||'').slice(-24),
    srcStrict: (polit.getAttribute('src')||'').slice(-26),
    europeBefore: before, europeAfter: after});
})()`);
await sleep(600);
await shot('qa/shots/v1190_strict.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
