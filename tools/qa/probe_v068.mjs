// v0.68 变体增删 UI 实测
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const PORT = 9351;
const URL = process.argv[2] || 'http://127.0.0.1:8898/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_v068', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
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
out.open = await evalJS(`(async()=>{
  await openHistoryEditor('TST');
  await new Promise(r=>setTimeout(r,900));
  return JSON.stringify({shown: document.getElementById('historyModal').classList.contains('show'),
    hasAdd: !!document.getElementById('histVarAdd'),
    rows: document.querySelectorAll('#histVariants .hv-row').length,
    text: document.getElementById('histVariants').textContent.slice(0, 40)});
})()`);

out.add = await evalJS(`(async()=>{
  document.getElementById('histVarAdd').click();
  document.getElementById('hvName').value = 'UiJet';
  document.getElementById('hvType').value = 'fighter_equipment_0';
  document.getElementById('hvIcon').value = 'GFX_UiJet';
  document.getElementById('hvMods').value = 'fixed_main_weapon_slot = fighter_weapon_1\\nengine_slot = engine_1';
  await saveVariantForm();
  await new Promise(r=>setTimeout(r,1200));
  return JSON.stringify({rows: document.querySelectorAll('#histVariants .hv-row').length,
    names: [...document.querySelectorAll('#histVariants .hv-row .nm')].map(x=>x.textContent),
    status: document.getElementById('status').textContent});
})()`);
await shot('qa/shots/v0.68_variant_ui.png');

out.del = await evalJS(`(async()=>{
  window.confirm = ()=>true;
  const btn = document.querySelector('#histVariants [data-hvdel="UiJet"]');
  if(!btn) return JSON.stringify({error:'找不到删除按钮'});
  await deleteVariant('UiJet');
  await new Promise(r=>setTimeout(r,1200));
  return JSON.stringify({rows: document.querySelectorAll('#histVariants .hv-row').length,
    status: document.getElementById('status').textContent});
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
