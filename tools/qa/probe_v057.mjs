// v0.57 州面板实测（fixture mod：state 900）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9344;
const URL = process.argv[2] || 'http://127.0.0.1:8898/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v057', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
await sleep(300);

const out = {};
out.open = await evalJS(`(async()=>{
  await openStates(900);
  await new Promise(r=>setTimeout(r,900));
  return JSON.stringify({
    shown: document.getElementById('stateModal').classList.contains('show'),
    count: document.getElementById('stateCount').textContent,
    title: (document.querySelector('#stateBody .cm-title h3')||{}).textContent,
    owner: (document.getElementById('stOwner')||{}).value,
    man: (document.getElementById('stManpower')||{}).value,
    cat: (document.getElementById('stCategory')||{}).value,
    cores: (document.getElementById('stCores')||{}).value,
    bld: [...document.querySelectorAll('#stateBody [data-b]')].map(i=>i.dataset.b + '=' + i.value).filter(x=>!x.endsWith('='))
  });
})()`);

out.save = await evalJS(`(async()=>{
  window.confirm = ()=>true;
  document.getElementById('stOwner').value = 'TST';
  document.getElementById('stManpower').value = '123456';
  document.getElementById('stCategory').value = 'rural';
  const air = document.querySelector('#stateBody [data-b="air_base"]');
  if(air) air.value = '2';
  await saveState({id:900});
  await new Promise(r=>setTimeout(r,1200));
  return JSON.stringify({
    status: document.getElementById('status').textContent,
    diff: [...document.querySelectorAll('#stDiff .row')].map(r=>r.textContent.replace(/\\s+/g,' ')).join(' | ').slice(0,200),
    owner: document.getElementById('stOwner').value,
    man: document.getElementById('stManpower').value
  });
})()`);

await sleep(400);
const shot = await send('Page.captureScreenshot', { format: 'png' });
fs.mkdirSync('qa/shots', { recursive: true });
fs.writeFileSync('qa/shots/v0.57_state.png', Buffer.from(shot.result.data, 'base64'));

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
