// v0.58 面板实测：历史编辑器补全 + 省份编辑
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9345;
const URL = process.argv[2] || 'http://127.0.0.1:8898/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v058', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
await sleep(300);

const out = {};
out.history = await evalJS(`(async()=>{
  await openHistoryEditor('TST');
  await new Promise(r=>setTimeout(r,900));
  return JSON.stringify({
    shown: document.getElementById('historyModal').classList.contains('show'),
    techs: (document.getElementById('histTechs').value||'').split('\\n').filter(Boolean).length,
    oob: document.getElementById('histOob').value,
    popD: document.getElementById('histPopD').value,
    popF: document.getElementById('histPopF').value
  });
})()`);
await shot('qa/shots/v0.58_history_full.png');

out.historySave = await evalJS(`(async()=>{
  window.confirm = ()=>true;
  document.getElementById('histPopD').value = '60';
  document.getElementById('histOob').value = 'UI_OOB';
  await saveHistory();
  await new Promise(r=>setTimeout(r,1200));
  return JSON.stringify({
    status: document.getElementById('status').textContent,
    diff: [...document.querySelectorAll('#histDiff .row')].map(r=>r.textContent.replace(/\\s+/g,' ')).join(' | ').slice(0,240)
  });
})()`);

out.state = await evalJS(`(async()=>{
  closeHistoryEditor();
  await openStates(900);
  await new Promise(r=>setTimeout(r,900));
  const rows = document.querySelectorAll('#stateBody .st-table tbody tr').length;
  const firstNaval = document.querySelector('#stateBody [data-pb="111"][data-k="naval_base"]');
  const vp = document.querySelector('#stateBody [data-vp="111"]');
  return JSON.stringify({
    shown: document.getElementById('stateModal').classList.contains('show'),
    rows, naval111: firstNaval && firstNaval.value, vp111: vp && vp.value
  });
})()`);

out.stateSave = await evalJS(`(async()=>{
  window.confirm = ()=>true;
  const inp = document.querySelector('#stateBody [data-pb="111"][data-k="naval_base"]');
  if(inp) inp.value = '4';
  const vp = document.querySelector('#stateBody [data-vp="111"]');
  if(vp) vp.value = '6';
  await saveState({id:900});
  await new Promise(r=>setTimeout(r,1200));
  return JSON.stringify({
    status: document.getElementById('status').textContent,
    diff: [...document.querySelectorAll('#stDiff .row')].map(r=>r.textContent.replace(/\\s+/g,' ')).join(' | ').slice(0,240),
    naval111: (document.querySelector('#stateBody [data-pb="111"][data-k="naval_base"]')||{}).value,
    vp111: (document.querySelector('#stateBody [data-vp="111"]')||{}).value
  });
})()`);
await shot('qa/shots/v0.58_state_province.png');

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
