// v1.7.0 事件就地编辑 + 自动本地化实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9452;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v170', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  document.getElementById('evOpen').click();
  for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,300));
    if(document.querySelectorAll('#evSvg .ev-node').length) break; }
  return JSON.stringify({pane: !!document.getElementById('evEditPane'),
    nodes: document.querySelectorAll('#evSvg .ev-node').length});
})()`);
// 点第一个本 mod 的节点 → 加载到编辑栏
out.load = await evalJS(`(async()=>{
  const ns = document.querySelectorAll('#evSvg .ev-node');
  let target = null;
  for(const n of ns){
    if(!n.classList.contains('ext')){ target = n; break; }
  }
  if(!target) return JSON.stringify({error:'没有本 mod 节点'});
  target.dispatchEvent(new MouseEvent('click', {bubbles:true}));
  for(let i=0;i<30;i++){ await new Promise(r=>setTimeout(r,300));
    if(document.getElementById('evEdTitle').value) break; }
  return JSON.stringify({id: target.dataset.id,
    title: document.getElementById('evEdTitle').value,
    desc: document.getElementById('evEdDesc').value,
    titleText: document.getElementById('evEdTitleText').textContent.slice(0,40),
    optCount: document.querySelectorAll('#evEdOpts .o-row').length,
    saveEnabled: !document.getElementById('evEdSave').disabled});
})()`);
await sleep(400);
await shot('qa/shots/v170_event_edit.png');
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
