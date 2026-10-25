// v0.60 数据源面板与加载进度实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9346;
const URL = process.argv[2] || 'http://127.0.0.1:8903/';
const MOD = 'D:\\\\大肥鱼工作区\\\\HOI4 MUVLUVsub mod 制作\\\\work\\\\qa\\\\fixtures\\\\country_mod';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v060', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 200) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
await sleep(300);

const out = {};
out.before = await evalJS(`JSON.stringify({
  src: !!document.getElementById('srcBox'),
  badge: document.getElementById('srcBadge').textContent,
  state: document.getElementById('srcState').textContent,
  vanilla: document.getElementById('vanillaBtn').textContent,
  barHidden: !document.getElementById('loadBar').classList.contains('show'),
  oldBtnsInTree: document.querySelectorAll('details .tabbtn#addModBtn').length
})`);
await shot('qa/shots/v0.60_source_idle.png');

// 模拟加载中状态
await evalJS(`startLoading('正在加载 测试 mod…')`);
await sleep(600);
out.busy = await evalJS(`JSON.stringify({
  bar: document.getElementById('loadBar').classList.contains('show'),
  state: document.getElementById('srcState').textContent,
  spin: !!document.querySelector('#srcState .spin')
})`);
await shot('qa/shots/v0.60_source_busy.png');

// 真实加载 fixture mod
out.load = await evalJS(`(async()=>{
  updateLoading('读取国策树、科技、州与本地化…');
  const r = await fetch('/api/load_mod', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({path: '${MOD}'})});
  const j = await r.json();
  await loadData();
  stopLoading(j.msg || '已加载');
  await new Promise(x=>setTimeout(x,400));
  return JSON.stringify({ok: j.ok, msg: j.msg, badge: document.getElementById('srcBadge').textContent,
    state: document.getElementById('srcState').textContent, bar: document.getElementById('loadBar').classList.contains('show')});
})()`);

out.after = await evalJS(`JSON.stringify({
  badge: document.getElementById('srcBadge').textContent,
  vanilla: document.getElementById('vanillaBtn').textContent,
  state: document.getElementById('srcState').textContent
})`);
await shot('qa/shots/v0.60_source_loaded.png');

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
