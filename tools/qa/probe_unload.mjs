// 卸载面板实测 + 截图：node qa/probe_unload.mjs [url]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9338;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_unload', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map();
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => (await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })).result?.result?.value;
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(7000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
await sleep(400);
await evalJS(`openUnloadModal()`);
await sleep(500);
const info = await evalJS(`JSON.stringify({
  shown: document.getElementById('unloadModal').classList.contains('show'),
  rows: [...document.querySelectorAll('#unloadList .ul-row')].map(r=>({name:r.querySelector('b').textContent, tag:r.querySelector('.ul-tag').textContent, path:r.querySelector('span').textContent})),
  roots: (DATA.roots||[]).length
})`);
console.log(info);
const shot = await send('Page.captureScreenshot', { format: 'png' });
fs.mkdirSync('qa/shots', { recursive: true });
fs.writeFileSync('qa/shots/v0.53_unload.png', Buffer.from(shot.result.data, 'base64'));
ws.close(); chrome.kill(); process.exit(0);
