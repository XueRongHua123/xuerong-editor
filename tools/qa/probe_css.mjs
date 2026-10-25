// 用 CDP CSS 域查某节点真实匹配样式：node qa/probe_css.mjs "#techEntry"
import { spawn } from 'node:child_process';
const PORT = 9337;
const SEL = process.argv[2] || '#techEntry';
const URL = process.argv[3] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--user-data-dir=C:\\Windows\\Temp\\cp_probecss', '--window-size=1600,1000', '--no-first-run', '--disable-gpu', 'about:blank'], { stdio: 'ignore' });
for (let i = 0; i < 60; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {} await sleep(200); }
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map();
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
await send('DOM.enable'); await send('CSS.enable'); await send('Runtime.enable'); await send('Page.enable');
await send('Page.navigate', { url: URL }); await sleep(5500);
await send('Runtime.evaluate', { expression: `applyTheme('dark')` });
await sleep(900);
const { result: { root } } = await send('DOM.getDocument', { depth: -1 });
const q = await send('DOM.querySelector', { nodeId: root.nodeId, selector: SEL });
const ms = await send('CSS.getMatchedStylesForNode', { nodeId: q.result.nodeId });
const out = { selector: SEL, matched: [] };
for (const m of ms.result.matchedCSSRules || []) {
  const props = (m.rule.style.cssProperties || []).filter(p => /^(color|background-color|opacity)$/.test(p.name) && p.value);
  if (props.length) out.matched.push({ sel: m.rule.selectorList.text.slice(0, 60), origin: m.rule.origin, props: props.map(p => `${p.name}:${p.value}${p.important ? '!' : ''}`) });
}
const comp = await send('CSS.getComputedStyleForNode', { nodeId: q.result.nodeId });
out.computed = (comp.result.computedStyle || []).filter(p => ['color', 'background-color', '--muted'].includes(p.name)).map(p => `${p.name}=${p.value}`);
const r = await send('Runtime.evaluate', { expression: `(()=>{applyTheme('dark'); const e=document.querySelector('${SEL}'); return JSON.stringify({cls:document.body.className,color:getComputedStyle(e).color,muted:getComputedStyle(e).getPropertyValue('--muted')});})()`, returnByValue: true });
out.runtime = r.result.result.value;
console.log(JSON.stringify(out, null, 1));
ws.close(); chrome.kill(); process.exit(0);
