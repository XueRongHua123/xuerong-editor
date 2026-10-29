// v1.15.0 装备编辑实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9476;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_eq', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  document.querySelector('.side-tab[data-tab="equip"]').click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,400));
    if(document.querySelectorAll('#eqList .eq-row').length) break; }
  return JSON.stringify({tab: !!document.querySelector('.side-tab[data-tab="equip"]'),
    rows: document.querySelectorAll('#eqList .eq-row').length,
    stat: document.getElementById('eqStat').textContent.slice(0,40)});
})()`);
out.detail = await evalJS(`(async()=>{
  const row = document.querySelector('#eqList .eq-row');
  if(!row) return JSON.stringify({error:'没有装备行'});
  row.click();
  for(let i=0;i<30;i++){ await new Promise(r=>setTimeout(r,400));
    if(document.getElementById('eqEdit').style.display === 'block') break; }
  await new Promise(r=>setTimeout(r,500));
  return JSON.stringify({shown: document.getElementById('eqEdit').style.display,
    cur: document.getElementById('eqCur').textContent.slice(0,60),
    props: document.querySelectorAll('#eqProps .eq-val').length,
    slots: document.getElementById('eqSlots').textContent.slice(0,50),
    refs: document.getElementById('eqRefs').textContent.slice(0,50)});
})()`);
out.edit = await evalJS(`(async()=>{
  const first = document.querySelector('#eqProps .eq-val');
  if(!first) return JSON.stringify({error:'没有属性输入框'});
  const k0 = first.dataset.k, v0 = first.value;
  first.value = '999';
  first.dispatchEvent(new Event('input'));
  document.getElementById('eqSave').click();
  for(let i=0;i<25;i++){ await new Promise(r=>setTimeout(r,400));
    const t = document.getElementById('eqMsg').textContent;
    if(t && t.indexOf('写入中') < 0) break; }
  return JSON.stringify({key: k0, from: v0, to: '999',
    msg: document.getElementById('eqMsg').textContent.slice(0,80)});
})()`);
await sleep(600);
await shot('qa/shots/v1150_equip.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
