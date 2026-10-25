// v0.61 AI 面板与悬浮球实测（不触发真实 API 调用）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9347;
const URL = process.argv[2] || 'http://127.0.0.1:8903/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v061', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 220) };
  return r.result?.result?.value;
};
const shot = async f => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.result.data, 'base64')); };
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
await sleep(300);

const out = {};
out.panel = await evalJS(`(async()=>{
  await openAI();
  await new Promise(r=>setTimeout(r,600));
  return JSON.stringify({
    shown: document.getElementById('aiModal').classList.contains('show'),
    tpls: document.querySelectorAll('#aiTemplates .cm-chip').length,
    hasTest: !!document.getElementById('aiTest'),
    hasClear: !!document.getElementById('aiClearHistory'),
    meta: !!document.getElementById('aiMeta'),
    hist: !!document.getElementById('aiHistory')
  });
})()`);

out.template = await evalJS(`(()=>{
  document.querySelector('#aiTemplates .cm-chip[data-tpl="check"]').click();
  return JSON.stringify({prompt: (document.getElementById('aiPrompt').value || '').slice(0, 30)});
})()`);

out.history = await evalJS(`(()=>{
  AI_HISTORY = [{q: '测试问题一', a: '答案一', t: '10:00'}, {q: '测试问题二', a: '答案二', t: '10:01'}];
  renderAIHistory();
  const n = document.querySelectorAll('#aiHistory .ai-h').length;
  document.querySelector('#aiHistory .ai-h').click();
  return JSON.stringify({rows: n, prompt: document.getElementById('aiPrompt').value, out: document.getElementById('aiOut').textContent});
})()`);
await shot('qa/shots/v0.61_ai_panel.png');

out.menu = await evalJS(`(()=>{
  document.getElementById('aiModal').classList.remove('show');
  openAiMenu(400, 300);
  const shown = document.getElementById('aiMenu').classList.contains('show');
  const items = [...document.querySelectorAll('#aiMenu [data-act]')].map(x=>x.textContent.trim());
  return JSON.stringify({shown, items});
})()`);
await shot('qa/shots/v0.61_bubble_menu.png');

out.menuAction = await evalJS(`(async()=>{
  aiMenuAction('cmd');
  await new Promise(r=>setTimeout(r,400));
  return JSON.stringify({menuClosed: !document.getElementById('aiMenu').classList.contains('show'),
    cmdOpen: document.getElementById('cmdPalette').classList.contains('show')});
})()`);

out.busy = await evalJS(`(()=>{
  closeCmd();
  startLoading('测试加载');
  const b1 = document.getElementById('aiBubble').classList.contains('busy');
  stopLoading('完成');
  const b2 = document.getElementById('aiBubble').classList.contains('busy');
  return JSON.stringify({duringLoad: b1, afterLoad: b2});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
