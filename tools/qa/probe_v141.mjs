// v1.4.1 预览 ↔ 编辑器打通实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9442;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_ft2', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  document.getElementById('ftOpen').click();
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,300));
    if(document.getElementById('ftPick').options.length) break; }
  for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,300));
    if(document.querySelectorAll('#ftSvg .ft-node').length) break; }
  const eb = document.getElementById('ftEdit');
  return JSON.stringify({nodes: document.querySelectorAll('#ftSvg .ft-node').length,
    editDisabled: eb ? eb.disabled : 'no-btn'});
})()`);
out.pickThenEdit = await evalJS(`(async()=>{
  const n = document.querySelectorAll('#ftSvg .ft-node')[3];
  const fid = n.dataset.id;
  n.dispatchEvent(new MouseEvent('click', {bubbles:true}));
  await new Promise(r=>setTimeout(r,300));
  const eb = document.getElementById('ftEdit');
  const enabled = !eb.disabled;
  eb.click();
  await new Promise(r=>setTimeout(r,1200));
  const editorNode = document.querySelector('#viewport .node[data-id="' + fid + '"]');
  return JSON.stringify({fid, btnEnabled: enabled,
    modalClosed: !document.getElementById('ftModal').classList.contains('show'),
    editorHasNode: !!editorNode,
    status: document.getElementById('status').textContent.slice(0,50)});
})()`);
await sleep(800);
await shot('qa/shots/v141_jump_to_editor.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
