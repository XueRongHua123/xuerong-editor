// 复现「点 UI 却选中了后面的地块」
import { spawn } from 'node:child_process';
const PORT = 9410;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_clickthrough', '--window-size=1500,950', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map();
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (m, p = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const evalJS = async e => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || '').slice(0, 300) };
  return r.result?.result?.value;
};
await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: 'http://127.0.0.1:8891/' });
await sleep(6000);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click()`);
await evalJS(`(async()=>{
  document.getElementById('mapEntry').click();
  for(let i=0;i<150;i++){ await new Promise(r=>setTimeout(r,300)); if(window.MAP && MAP.ready && MAP.idCanvas) break; }
  // 先选一个明确的省，作为"之前的状态"
  mapSelectProvince(221);
})()`);

const cases = await evalJS(`(()=>{
  const list = [
    ['#mapTools','图层面板'],
    ['#mapTools h4','图层标题'],
    ['#mapTools label','图层复选框行'],
    ['#mapSide','右侧属性面板'],
    ['#mapRail','左侧工具栏'],
    ['#mapRail .map-tool','工具栏按钮'],
    ['#mapStatus','状态栏'],
    ['#mapHead','顶部栏'],
    ['#mapSearch','搜索框'],
  ];
  return JSON.stringify(list.map(([sel,desc])=>{
    const el = document.querySelector(sel);
    if(!el) return {sel, desc, skip:true};
    const r = el.getBoundingClientRect();
    return {sel, desc, x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)};
  }));
})()`);
const list = JSON.parse(cases);
const results = [];
for (const c of list) {
  if (c.skip) { results.push({...c, skip:'元素不存在'}); continue; }
  // 每个用例前把选中重置成 221，便于判断是否被改
  await evalJS(`(()=>{ MAP.lastPid = 221; })()`);
  await send('Input.dispatchMouseEvent', {type:'mousePressed', x:c.x, y:c.y, button:'left', clickCount:1, buttons:1});
  await sleep(60);
  await send('Input.dispatchMouseEvent', {type:'mouseReleased', x:c.x, y:c.y, button:'left', clickCount:1, buttons:0});
  await sleep(200);
  const after = await evalJS(`MAP.lastPid`);
  results.push({desc:c.desc, sel:c.sel, xy:[c.x,c.y], before:221, after, changed: after !== 221});
}
console.log(JSON.stringify(results, null, 1));
ws.close(); chrome.kill(); process.exit(0);
