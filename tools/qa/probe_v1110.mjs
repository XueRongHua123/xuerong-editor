// v1.11.0 铁路编辑 + 补给区实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9466;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_rail2', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  document.querySelector('.side-tab[data-tab="rail"]').click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,400));
    if(document.querySelectorAll('#railList .rail-row').length) break; }
  return JSON.stringify({tab: !!document.querySelector('.side-tab[data-tab="rail"]'),
    rows: document.querySelectorAll('#railList .rail-row').length,
    stat: document.getElementById('railStat').textContent.slice(0,60)});
})()`);
out.edit = await evalJS(`(async()=>{
  const row = document.querySelector('#railList .rail-row');
  if(!row) return JSON.stringify({error:'没有铁路行'});
  row.click();
  await new Promise(r=>setTimeout(r,300));
  const shown = document.getElementById('railEdit').style.display;
  const lv = document.getElementById('railLv').value;
  const provs = document.getElementById('railProvs').value;
  // 改等级并保存
  document.getElementById('railLv').value = '5';
  document.getElementById('railSave').click();
  await new Promise(r=>setTimeout(r,2500));
  return JSON.stringify({panelShown: shown, lv0: lv, provs0: provs.slice(0,30),
    msg: document.getElementById('railMsg').textContent.slice(0,60)});
})()`);
out.supply = await evalJS(`(async()=>{
  document.getElementById('supRefresh').click();
  for(let i=0;i<30;i++){ await new Promise(r=>setTimeout(r,400));
    if(document.getElementById('supList').textContent.trim()) break; }
  return JSON.stringify({stat: document.getElementById('supStat').textContent.slice(0,40),
    items: document.querySelectorAll('#supList > div').length,
    first: (document.querySelector('#supList > div')||{}).textContent});
})()`);
await sleep(500);
await shot('qa/shots/v1110_rail_edit.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
