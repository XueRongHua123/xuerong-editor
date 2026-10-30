// v1.21.5 科技树预览实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9500;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_tt', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await send('Page.navigate', { url: 'http://127.0.0.1:8901/' });
await sleep(8000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.elems = await evalJS(`(async()=>{
  document.getElementById('mapEntry') && document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  await new Promise(r=>setTimeout(r,600));
  for(const t of document.querySelectorAll('.side-tab')){ if(t.textContent.trim()==='编辑'){ t.click(); break; } }
  await new Promise(r=>setTimeout(r,1200));
  const sel = document.getElementById('ttFolder');
  return JSON.stringify({
    hasSel: !!sel,
    hasSvg: !!document.getElementById('techTreeSvg'),
    optCount: sel ? sel.options.length : -1
  });
})()`);
out.draw = await evalJS(`(async()=>{
  const sel = document.getElementById('ttFolder');
  if(!sel) return JSON.stringify({error:'没有下拉'});
  const want = 'infantry_folder';
  for(const o of sel.options){ if(o.value === want){ sel.value = want; break; } }
  document.getElementById('ttDraw').click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,400));
    const m = document.getElementById('ttMsg').textContent;
    if(m && m.indexOf('读取中') < 0 && m.length > 3) break; }
  const svg = document.getElementById('techTreeSvg');
  return JSON.stringify({
    msg: (document.getElementById('ttMsg').textContent||'').slice(0,70),
    nodes: svg ? svg.querySelectorAll('.tt-node').length : -1,
    lines: svg ? svg.querySelectorAll('line').length : -1,
    w: svg ? svg.getAttribute('data-w') : ''
  });
})()`);
await sleep(400);
await shot('qa/shots/v12150_techtree.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
