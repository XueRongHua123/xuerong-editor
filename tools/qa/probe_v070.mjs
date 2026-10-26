// v0.70 命令面板最近使用实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9353;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v070', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
out.emptyBefore = await evalJS(`(()=>{
  localStorage.removeItem('fe_cmd_recent');
  openCmd();
  const groups = [...document.querySelectorAll('#cpList .cp-group')].map(x=>x.textContent);
  return JSON.stringify({groups: groups.slice(0, 3), hasRecent: groups.some(g=>g.indexOf('最近使用')===0)});
})()`);

// 执行两条命令，制造"最近使用"
out.run = await evalJS(`(async()=>{
  closeCmd();
  openCmd();
  const idx = cpItems.findIndex(it=>it.cat === '操作');
  const label = cpItems[idx] && cpItems[idx].label;
  cpRun(idx);
  await new Promise(r=>setTimeout(r,600));
  closeCmd();
  openCmd();
  const idx2 = cpItems.findIndex(it=>it.cat === '操作' && it.label !== label);
  if(idx2 >= 0) cpRun(idx2);
  await new Promise(r=>setTimeout(r,600));
  return JSON.stringify({first: label, stored: JSON.parse(localStorage.getItem('fe_cmd_recent')||'[]').slice(0,3)});
})()`);

out.after = await evalJS(`(()=>{
  closeCmd();
  openCmd();
  const groups = [...document.querySelectorAll('#cpList .cp-group')].map(x=>x.textContent);
  const firstGroup = groups[0] || '';
  const firstItems = [...document.querySelectorAll('#cpList .cp-item')].slice(0, 3)
    .map(el=>el.querySelector('.cp-label').textContent);
  return JSON.stringify({firstGroup, groups: groups.slice(0,3), firstItems});
})()`);
await shot('qa/shots/v0.70_cmd_recent.png');

out.searchStillWorks = await evalJS(`(()=>{
  document.getElementById('cpInput').value = '保存';
  cpRender();
  const groups = [...document.querySelectorAll('#cpList .cp-group')].map(x=>x.textContent);
  return JSON.stringify({hasRecent: groups.some(g=>g.indexOf('最近使用')===0), count: document.getElementById('cpCount').textContent});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
