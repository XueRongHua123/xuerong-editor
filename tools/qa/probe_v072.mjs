// v0.72 节点密度 + 窄屏工具栏实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9357;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v072', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 240) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
const setViewport = async (w, h) => { await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: false }); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);

const out = {};
out.density = await evalJS(`(()=>{
  const before = [NODE_W, NODE_H, SCALE];
  document.getElementById('densitySel').value = 'compact';
  applyDensity('compact');
  const compact = [NODE_W, NODE_H, SCALE];
  applyDensity('comfy');
  const comfy = [NODE_W, NODE_H, SCALE];
  applyDensity('normal');
  const normal = [NODE_W, NODE_H, SCALE];
  return JSON.stringify({before, compact, comfy, normal,
    saved: localStorage.getItem('fe_density')});
})()`);
await shot('qa/shots/v0.72_density.png');

await setViewport(1024, 800);
await sleep(700);
out.narrow = await evalJS(`(()=>{
  const more = document.getElementById('tbMore');
  const wideHidden = [...document.querySelectorAll('.toolbar .tb-wide')].map(e=>getComputedStyle(e).display).slice(0,3);
  return JSON.stringify({moreVisible: getComputedStyle(more).display !== 'none',
    toolbarWrap: getComputedStyle(document.querySelector('.toolbar')).flexWrap,
    wideSamples: [...document.querySelectorAll('.tb-wide')].map(e=>getComputedStyle(e).display).slice(0,3),
    menuItems: document.querySelectorAll('#tbMoreMenu .tb-more-item').length});
})()`);
await evalJS(`document.getElementById('tbMore').click()`);
await sleep(300);
await shot('qa/shots/v0.72_narrow.png');

out.wide = await evalJS(`(async()=>{
  document.getElementById('tbMoreMenu').classList.remove('show');
  return JSON.stringify({ok: true});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
