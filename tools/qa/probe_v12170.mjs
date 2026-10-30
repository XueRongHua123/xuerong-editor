// v1.21.7 国家精神界面实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9504;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_ci', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await send('Page.navigate', { url: 'http://127.0.0.1:8905/' });
await sleep(8000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
out.elems = await evalJS(`(async()=>{
  document.getElementById('mapEntry') && document.getElementById('mapEntry').click();
  for(let i=0;i<200;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready) break; }
  await new Promise(r=>setTimeout(r,600));
  for(const t of document.querySelectorAll('.side-tab')){ if(t.textContent.trim()==='编辑'){ t.click(); break; } }
  await new Promise(r=>setTimeout(r,800));
  return JSON.stringify({
    hasTag: !!document.getElementById('cideaTag'),
    hasLoad: !!document.getElementById('cideaLoad'),
    hasOn: !!document.getElementById('cideaOn'),
    hasQ: !!document.getElementById('cideaQ'),
    hasHits: !!document.getElementById('cideaHits'),
    hasTech: !!document.getElementById('ctechTag'),
    hasTpl: !!document.getElementById('tplPanel')
  });
})()`);
out.load = await evalJS(`(async()=>{
  const t = document.getElementById('cideaTag');
  const b = document.getElementById('cideaLoad');
  if(!t || !b) return JSON.stringify({error:'没有控件'});
  t.value = 'AFR';
  b.click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,400));
    const m = document.getElementById('cideaMsg').textContent;
    if(m && m.indexOf('读取中') < 0 && m.length > 3) break; }
  const on = document.getElementById('cideaOn');
  const hits = document.getElementById('cideaHits');
  return JSON.stringify({
    msg: (document.getElementById('cideaMsg').textContent||'').slice(0,60),
    onRows: on ? on.children.length : -1,
    hitRows: hits ? hits.children.length : -1
  });
})()`);
out.search = await evalJS(`(async()=>{
  const q = document.getElementById('cideaQ');
  if(!q) return JSON.stringify({error:'没有搜索框'});
  q.value = 'mvlv';
  q.dispatchEvent(new Event('input'));
  await new Promise(r=>setTimeout(r,600));
  const hits = document.getElementById('cideaHits');
  return JSON.stringify({
    rows: hits ? hits.children.length : -1,
    first: hits && hits.children[0] ? hits.children[0].textContent.trim().slice(0,40) : ''
  });
})()`);
await sleep(400);
await shot('qa/shots/v12170_cidea.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
