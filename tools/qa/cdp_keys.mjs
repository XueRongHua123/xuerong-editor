// v0.51 键盘/交互实测：Ctrl+K、搜索列表、Esc、纸页主题
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const PORT = 9334, URL = process.env.TEST_URL || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`,
  '--user-data-dir=C:\\Windows\\Temp\\cp_v051_profile2',
  '--window-size=1600,1000', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'
], { stdio: 'ignore' });

for (let i = 0; i < 60; i++) {
  try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {}
  await sleep(250);
}
const created = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(created.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let seq = 0; const pending = new Map(); const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') problems.push('EXC: ' + (m.params.exceptionDetails?.exception?.description || ''));
  if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') problems.push('ERR: ' + (m.params.args || []).map(a => a.value ?? '').join(' '));
};
const send = (method, params = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
async function evalJS(expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text };
  return r.result?.result?.value;
}
async function shot(file) { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(file, Buffer.from(r.result.data, 'base64')); }
async function key(k, code, mods = 0, text) {
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: k, code, windowsVirtualKeyCode: k.length === 1 ? k.toUpperCase().charCodeAt(0) : undefined, modifiers: mods });
  if (text) await send('Input.dispatchKeyEvent', { type: 'char', text, key: k, modifiers: mods });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, modifiers: mods });
}
const out = {};

await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);

out.state = await evalJS(`JSON.stringify({trees:(DATA.trees||[]).length, welcome:getComputedStyle(document.getElementById('welcome')).display, app:getComputedStyle(document.getElementById('app')).display, nodes:document.querySelectorAll('.node').length})`);

await evalJS(`document.getElementById('welcomeClose').click()`);
await sleep(300);

// Ctrl+K
await key('k', 'KeyK', 2);
await sleep(500);
out.ctrlK = await evalJS(`JSON.stringify({open: document.getElementById('cmdPalette').classList.contains('show'), focus: document.activeElement && document.activeElement.id, items: document.querySelectorAll('#cpList .cp-item').length})`);

// 输入“校验”
await send('Input.insertText', { text: '校验' });
await sleep(400);
out.query = await evalJS(`JSON.stringify({items: document.querySelectorAll('#cpList .cp-item').length, first: (document.querySelector('#cpList .cp-item .cp-label')||{}).textContent})`);

// 下箭头 + Enter 执行
await key('ArrowDown', 'ArrowDown', 0);
await sleep(200);
out.arrow = await evalJS(`JSON.stringify({on: (document.querySelector('#cpList .cp-item.on .cp-label')||{}).textContent})`);
await key('Escape', 'Escape', 0);
await sleep(300);
out.esc = await evalJS(`JSON.stringify({closed: !document.getElementById('cmdPalette').classList.contains('show')})`);

// 侧栏搜索真实输入
await evalJS(`(()=>{const s=document.getElementById('search'); s.focus(); s.value=''; })()`);
await send('Input.insertText', { text: 'AFR' });
await sleep(100);
await evalJS(`document.getElementById('search').dispatchEvent(new Event('input'))`);
await sleep(400);
out.sideSearch = await evalJS(`JSON.stringify({rows: document.querySelectorAll('#searchHits .sr-item').length, first: (document.querySelector('#searchHits .sr-item b')||{}).textContent})`);
await evalJS(`document.querySelector('#searchHits .sr-item') && document.querySelector('#searchHits .sr-item').click()`);
await sleep(600);
out.sideJump = await evalJS(`JSON.stringify({sel: selId, panel: document.getElementById('panel').classList.contains('show')})`);

// F 键、H 键
await evalJS(`document.getElementById('search').value=''; renderSearchHits(''); document.activeElement.blur();`);
await key('h', 'KeyH', 0);
await sleep(400);
out.hKey = await evalJS(`JSON.stringify({keys: document.getElementById('keysModal').classList.contains('show')})`);
await key('Escape', 'Escape', 0);
await sleep(300);
out.hEsc = await evalJS(`JSON.stringify({keysClosed: !document.getElementById('keysModal').classList.contains('show')})`);

// 纸页主题下命令面板
await evalJS(`applyTheme('paper'); openCmd(); document.getElementById('cpInput').value='装备'; cpRender();`);
await sleep(500);
await shot('_shot_cmd_paper.png');
out.paper = await evalJS(`(()=>{const c=document.querySelector('.cp-card');const it=document.querySelector('#cpList .cp-item.on');return JSON.stringify({card:getComputedStyle(c).backgroundColor, itemColor: it?getComputedStyle(it.querySelector('.cp-label')).color:null, body:document.body.className});})()`);
await evalJS(`closeCmd(); applyTheme('dark');`);

out.problems = problems;
console.log(JSON.stringify(out, null, 2));
ws.close(); chrome.kill(); process.exit(0);
