// v0.51 交互自检：无头 Chrome + CDP
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const PORT = 9333, URL = process.env.TEST_URL || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`,
  '--user-data-dir=C:\\Windows\\Temp\\cp_v051_profile',
  '--window-size=1600,1000', '--hide-scrollbars', '--no-first-run', '--disable-gpu',
  'about:blank'
], { stdio: 'ignore' });

let targets = [];
for (let i = 0; i < 60; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    if (targets.length) break;
  } catch {}
  await sleep(250);
}

const created = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(created.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let seq = 0;
const pending = new Map();
const problems = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') {
    const d = m.params.exceptionDetails || {};
    problems.push('EXCEPTION: ' + (d.exception?.description || d.text || ''));
  }
  if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
    problems.push('CONSOLE.ERROR: ' + (m.params.args || []).map(a => a.value ?? a.description ?? '').join(' '));
  }
};
function send(method, params = {}) {
  return new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
}
async function evalJS(expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text };
  return { value: r.result?.result?.value };
}
async function shot(file) {
  const r = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(file, Buffer.from(r.result.data, 'base64'));
}

await send('Runtime.enable');
await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(4000);

const out = {};
out.boot = await evalJS(`(()=>{
  const d = (typeof DATA === "undefined" ? null : DATA);
  return JSON.stringify({
    cmdBtn: !!document.getElementById('cmdBtn'),
    palette: !!document.getElementById('cmdPalette'),
    keysModal: !!document.getElementById('keysModal'),
    searchHits: !!document.getElementById('searchHits'),
    trees: d ? (d.trees||[]).length : -1,
    ideas: d ? (d.ideas||[]).length : -1,
    equips: d ? (d.equipment||[]).length : -1,
    techs: d ? (d.techs||[]).length : -1,
    events: d ? (d.events||[]).length : -1,
    welcome: getComputedStyle(document.getElementById('welcome')).display
  });
})()`);

out.palette = await evalJS(`(()=>{
  openCmd();
  const n1 = document.querySelectorAll('#cpList .cp-item').length;
  const inp = document.getElementById('cpInput');
  inp.value = '保存'; cpRender();
  const n2 = document.querySelectorAll('#cpList .cp-item').length;
  const l2 = document.querySelector('#cpList .cp-item .cp-label')?.textContent;
  inp.value = 'focus'; cpRender();
  const n3 = document.querySelectorAll('#cpList .cp-item').length;
  const cats = {}; document.querySelectorAll('#cpList .cp-group').forEach(g=>{cats[g.textContent]=(cats[g.textContent]||0);});
  inp.value=''; cpRender();
  const groups = {}; document.querySelectorAll('#cpList .cp-group').forEach(g=>{groups[g.textContent]=1;});
  const catsDefault = Object.keys(groups);
  inp.value = ''; cpRender();
  return JSON.stringify({open: n1, saveHit: n2, saveLabel: l2, focusHit: n3, count: document.getElementById('cpCount').textContent, catsDefault});
})()`);

await shot('_shot_palette.png');

out.jump = await evalJS(`(async()=>{
  const t = DATA.trees.find(t=>(t.focuses||[]).length>2) || DATA.trees[0];
  const f = t.focuses[0];
  jumpFocus(t.id, f.id);
  await new Promise(r=>setTimeout(r,300));
  return JSON.stringify({
    tree: t.id, focus: f.id, cur: curTree() && curTree().id, sel: selId,
    panel: document.getElementById('panel').classList.contains('show'),
    panelTitle: (document.querySelector('#panel>div')||{}).textContent
  });
})()`);

out.search = await evalJS(`(()=>{
  const s = document.getElementById('search');
  const f = (DATA.trees.find(t=>(t.focuses||[]).length)||{}).focuses[0];
  const q = String(f.id).slice(0, 4);
  s.value = q; renderSearchHits(q);
  const rows = document.querySelectorAll('#searchHits .sr-item').length;
  document.querySelector('#searchHits .sr-item')?.click();
  return JSON.stringify({q, rows, sel: selId, panel: document.getElementById('panel').classList.contains('show')});
})()`);

out.keys = await evalJS(`(()=>{
  openKeys();
  const n = document.querySelectorAll('#keysGrid .km-row').length;
  const shown = document.getElementById('keysModal').classList.contains('show');
  closeKeys();
  return JSON.stringify({rows: n, shown, closed: !document.getElementById('keysModal').classList.contains('show')});
})()`);

out.theme = await evalJS(`(()=>{
  const out = {};
  document.body.classList.add('theme-paper');
  const t = document.getElementById('panelTitle') || document.querySelector('#panel>div');
  out.panelTitleColor = t ? getComputedStyle(t).color : null;
  document.body.classList.remove('theme-paper');
  return JSON.stringify(out);
})()`);

out.problems = problems;
console.log(JSON.stringify(out, null, 2));

await send('Page.navigate', { url: URL });
await sleep(2500);
await evalJS(`document.getElementById('welcomeClose').click(); openCmd(); document.getElementById('cpInput').value='国策'; cpRender();`);
await sleep(300);
await shot('_shot_cmd.png');
await evalJS(`closeCmd(); openKeys();`);
await sleep(300);
await shot('_shot_keys.png');

ws.close();
chrome.kill();
process.exit(0);
