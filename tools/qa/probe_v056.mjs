// v0.56 国家历史编辑面板实测（对 fixture mod）
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9342;
const URL = process.argv[2] || 'http://127.0.0.1:8898/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v056', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 240) };
  return r.result?.result?.value;
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
await sleep(300);

const out = {};
out.open = await evalJS(`(async()=>{
  await openCountry('TST');
  await new Promise(r=>setTimeout(r,700));
  return JSON.stringify({
    title: (document.querySelector('#countryBody .cm-title h3')||{}).textContent,
    hasEditBtn: !!document.querySelector('#countryBody [data-hist]')
  });
})()`);

out.form = await evalJS(`(async()=>{
  document.querySelector('#countryBody [data-hist]').click();
  await new Promise(r=>setTimeout(r,900));
  return JSON.stringify({
    shown: document.getElementById('historyModal').classList.contains('show'),
    file: document.getElementById('histFile').textContent.slice(0,120),
    capital: document.getElementById('histCapital').value,
    party: document.getElementById('histParty').value,
    pp: document.getElementById('histPP').value,
    ideas: document.getElementById('histIdeas').value.replace(/\\n/g, ','),
    tree: document.getElementById('histTree').value,
    disabled: document.getElementById('histSave').disabled
  });
})()`);

out.save = await evalJS(`(async()=>{
  window.confirm = ()=>true;
  document.getElementById('histCapital').value = '201';
  document.getElementById('histPP').value = '130';
  await saveHistory();
  await new Promise(r=>setTimeout(r,900));
  return JSON.stringify({
    status: document.getElementById('status').textContent,
    diffRows: document.querySelectorAll('#histDiff .row').length,
    diffText: [...document.querySelectorAll('#histDiff .row')].map(r=>r.textContent.replace(/\\s+/g,' ')).join(' | ').slice(0,220),
    capital: document.getElementById('histCapital').value,
    pp: document.getElementById('histPP').value
  });
})()`);

out.after = await evalJS(`(async()=>{
  const d = await (await fetch('/api/country_history?tag=TST')).json();
  return JSON.stringify({capital: d.fields.capital, pp: d.fields.political_power, exists: d.exists});
})()`);

const shot = await send('Page.captureScreenshot', { format: 'png' });
fs.writeFileSync('qa/shots/v0.56_history.png', Buffer.from(shot.result.data, 'base64'));

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
