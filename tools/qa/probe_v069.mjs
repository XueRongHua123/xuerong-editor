// v0.69 AI 流式 UI 实测（配合 run_v069_ui.py up 起的 mock + 编辑器）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9352;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v069', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 150));
};
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 220) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);

const out = {};
out.stream = await evalJS(`(async()=>{
  await openAI();
  await new Promise(r=>setTimeout(r,500));
  document.getElementById('aiPrompt').value = '测试流式';
  const t0 = Date.now();
  const p = sendAI();
  const snapshots = [];
  for(let i = 0; i < 12; i++){
    await new Promise(r=>setTimeout(r,120));
    const txt = document.getElementById('aiOut').textContent;
    if(snapshots.length === 0 || snapshots[snapshots.length-1] !== txt) snapshots.push(txt);
  }
  await p;
  await new Promise(r=>setTimeout(r,300));
  return JSON.stringify({
    snapshots,
    final: document.getElementById('aiOut').textContent,
    meta: document.getElementById('aiMeta').textContent,
    stopHidden: document.getElementById('aiStop').style.display === 'none',
    elapsed: Date.now() - t0
  });
})()`);
await shot('qa/shots/v0.69_stream.png');

out.abort = await evalJS(`(async()=>{
  document.getElementById('aiPrompt').value = '第二次';
  const p = sendAI();
  await new Promise(r=>setTimeout(r,150));
  stopAI();
  await p;
  return JSON.stringify({meta: document.getElementById('aiMeta').textContent,
    text: document.getElementById('aiOut').textContent.slice(0, 30),
    stopHidden: document.getElementById('aiStop').style.display === 'none'});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
