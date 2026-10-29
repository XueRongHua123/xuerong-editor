// v1.16.0 AI 多轮上下文实测（不调真实模型，只验消息拼装）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9478;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_ai', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(7000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
const out = {};
// 造 3 轮历史，检查转出来的 messages
out.msgs = await evalJS(`(()=>{
  AI_HISTORY = [
    {q: 'Q3', a: 'A3', t: '10:03'},
    {q: 'Q2', a: 'A2', t: '10:02'},
    {q: 'Q1', a: 'A1', t: '10:01'}
  ];
  const m = aiHistoryMessages();
  return JSON.stringify({count: m.length, roles: m.map(x=>x.role), contents: m.map(x=>x.content)});
})()`);
// 切 2 轮
out.turns2 = await evalJS(`(()=>{
  renderAIHistory();                       // 先渲染才有控件
  const sel = document.getElementById('aiCtxTurns');
  if(!sel) return JSON.stringify({error:'没有轮数选择'});
  const res = [];
  [12, 6, 2, 0].forEach(function(n){
    sel.value = String(n);
    const m = aiHistoryMessages();
    res.push({turns: n, msgs: m.length});
  });
  return JSON.stringify(res);
})()`);
// 清空
out.clear = await evalJS(`(()=>{
  renderAIHistory();
  const b = document.getElementById('aiClearCtx');
  if(!b) return JSON.stringify({error:'没有清空按钮'});
  b.click();
  const m = aiHistoryMessages();
  return JSON.stringify({after: m.length, histLen: AI_HISTORY.length});
})()`);
out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
