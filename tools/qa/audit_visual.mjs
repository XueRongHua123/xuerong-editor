// v0.52 视觉巡检：对比度 / 横向溢出 / 越界，覆盖双主题 × 各弹窗 × 两档视口
// 用法：node qa/audit_visual.mjs [url]
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const PORT = 9335;
const URL = process.argv[2] || 'http://127.0.0.1:8891/';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const OUT_DIR = 'qa/reports';
fs.mkdirSync(OUT_DIR, { recursive: true });

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`,
  '--user-data-dir=C:\\Windows\\Temp\\cp_v052_audit',
  '--window-size=1600,1000', '--hide-scrollbars', '--no-first-run', '--disable-gpu', 'about:blank'
], { stdio: 'ignore' });

for (let i = 0; i < 60; i++) {
  try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (l.length) break; } catch {}
  await sleep(250);
}
const page = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let seq = 0; const pending = new Map(); const consoleErrors = [];
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown') consoleErrors.push('EXC: ' + (m.params.exceptionDetails?.exception?.description || '').slice(0, 200));
  if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') consoleErrors.push('ERR: ' + (m.params.args || []).map(a => a.value ?? '').join(' ').slice(0, 200));
};
const send = (method, params = {}) => new Promise(res => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
async function evalJS(expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: (r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text || '').slice(0, 300) };
  return r.result?.result?.value;
}
async function shot(file) { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(file, Buffer.from(r.result.data, 'base64')); }

// 注入到页面的巡检函数
const INJECT = `window.__audit = function(){
  const out = {lowContrast: [], overflow: [], offscreen: []};
  function lum(c){
    const m = String(c).match(/rgba?\\(([^)]+)\\)/); if(!m) return null;
    const p = m[1].split(',').map(x=>parseFloat(x));
    const r=p[0]/255,g=p[1]/255,b=p[2]/255,a=(p.length>3?p[3]:1);
    const f=v=> v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4);
    return {L:0.2126*f(r)+0.7152*f(g)+0.0722*f(b), a};
  }
  function bgOf(el){
    let n = el;
    while(n && n!==document.documentElement){
      const st = getComputedStyle(n);
      const b = lum(st.backgroundColor);
      if(b && b.a > 0.55) return st.backgroundColor;
      n = n.parentElement;
    }
    return getComputedStyle(document.body).backgroundColor;
  }
  function ratio(fg,bg){
    const a=lum(fg), b=lum(bg); if(!a||!b) return null;
    const l1=Math.max(a.L,b.L), l2=Math.min(a.L,b.L);
    return (l1+0.05)/(l2+0.05);
  }
  const seen = new Set();
  document.querySelectorAll('body *').forEach(el=>{
    if(el.closest && el.closest('#svg') && el.tagName !== 'text') return;
    const r = el.getBoundingClientRect();
    if(r.width < 6 || r.height < 6) return;
    const st = getComputedStyle(el);
    if(st.visibility==='hidden' || st.display==='none' || parseFloat(st.opacity) < 0.25) return;
    // 折叠 details / 隐藏弹窗里的元素不渲染，computed color 会停在 transition 起始值（假阳性）
    if(el.getClientRects().length === 0) return;
    if(el.closest('[style*="display:none"]')) return;
    let txt = '';
    for(const n of el.childNodes) if(n.nodeType===3) txt += n.textContent;
    txt = txt.replace(/\\s+/g,' ').trim();
    if(txt.length >= 2){
      const c = ratio(st.color, bgOf(el));
      if(c !== null && c < 4.5){
        const key = (el.id||'') + '|' + (el.className||'').toString().slice(0,24) + '|' + txt.slice(0,16) + '|' + Math.round(c*10);
        if(!seen.has(key)){
          seen.add(key);
          out.lowContrast.push({id: el.id||'', cls: (el.className||'').toString().slice(0,40), text: txt.slice(0,30), fg: st.color, bg: bgOf(el), ratio: Math.round(c*100)/100, size: st.fontSize, w: Math.round(r.width)});
        }
      }
    }
    if(el.scrollWidth > el.clientWidth + 2 && r.width > 40){
      const ox = st.overflowX;
      if(ox !== 'auto' && ox !== 'scroll' && ox !== 'hidden'){
        out.overflow.push({id: el.id||'', cls:(el.className||'').toString().slice(0,40), sw: el.scrollWidth, cw: el.clientWidth, text: txt.slice(0,24)});
      }
    }
    if(r.right > window.innerWidth + 2 && r.width > 60 && el.id){
      out.offscreen.push({id: el.id, cls:(el.className||'').toString().slice(0,40), right: Math.round(r.right), vw: window.innerWidth});
    }
  });
  return JSON.stringify(out);
};`;

const CLOSE_ALL = `(function(){
  try{
    document.querySelectorAll('.diff-card,.cp-card,.km-grid').forEach(x=>{});
    ['diffModal','keysModal','ideaModal','equipModal','techModal','eventModal','contentModal','backupModal','reportModal','usagesModal','locModal','logModal','designerModal','aiModal'].forEach(id=>{
      const e=document.getElementById(id); if(!e) return;
      e.classList.remove('show');
      e.style.display='none';
    });
    ['treeSet','skinPick','iconPick','folderPick','newMod','cmdPalette','focusPreview','unloadModal','countryModal','lintModal'].forEach(id=>{
      const e=document.getElementById(id); if(!e) return;
      e.classList.remove('show');
      e.style.display='none';
    });
    const p=document.getElementById('panel'); if(p) p.classList.remove('show');
  }catch(e){}
})()`;

const STATES = [
  { name: 'welcome', open: `document.getElementById('welcome').style.display='flex';` },
  { name: 'main', open: `document.getElementById('welcome').style.display='none';` },
  { name: 'panel', open: `document.getElementById('welcome').style.display='none'; (function(){const t=curTree(); if(t&&t.focuses[0]){ selId=t.focuses[0].id; renderTree(); showPanel(); }})();`, wait: 900 },
  { name: 'cmdPalette', open: `openCmd();`, wait: 400 },
  { name: 'keysModal', open: `openCmd(); closeCmd(); openKeys();`, wait: 300 },
  { name: 'ideaModal', open: `openIdea();`, wait: 1200 },
  { name: 'equipModal', open: `openEquip();`, wait: 1200 },
  { name: 'designerModal', open: `openEquip(); openDesigner();`, wait: 1600 },
  { name: 'techModal', open: `openTech();`, wait: 1200 },
  { name: 'techTree', open: `openTech(); switchTechTab('tree');`, wait: 1600 },
  { name: 'eventModal', open: `openEvents();`, wait: 1000 },
  { name: 'contentModal', open: `openContent();`, wait: 1000 },
  { name: 'backupModal', open: `openBackups();`, wait: 1200 },
  { name: 'reportModal', open: `openReport();`, wait: 1500 },
  { name: 'locModal', open: `openLocCheck();`, wait: 1500 },
  { name: 'logModal', open: `openLog();`, wait: 1000 },
  { name: 'usagesModal', open: `(function(){const i=(DATA.ideas||[])[0]; if(i) openUsages(i.id);})();`, wait: 1200 },
  { name: 'treeSet', open: `openTreeSet();`, wait: 500 },
  { name: 'skinPick', open: `openSkinPick();`, wait: 500 },
  { name: 'iconPick', open: `openIconPicker();`, wait: 1500 },
  { name: 'aiModal', open: `openAI();`, wait: 700 },
  { name: 'focusPreview', open: `(function(){const t=curTree(); if(t&&t.focuses[0]) openFocusPreview(t.focuses[0]);})();`, wait: 900 },
  { name: 'newMod', open: `openNewMod();`, wait: 400 },
  { name: 'unloadModal', open: `openUnloadModal();`, wait: 500 },
  { name: 'countryModal', open: `openCountry('AFR');`, wait: 2600 },
  { name: 'lintModal', open: `openLint();`, wait: 3200 }
];

const KILL_TRANSITION = `(function(){
  if(document.getElementById('__noTrans')) return;
  const st = document.createElement('style');
  st.id = '__noTrans';
  st.textContent = '*,*::before,*::after{transition:none!important;animation:none!important}';
  document.head.appendChild(st);
})()`;

await send('Runtime.enable');
await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(6000);
await evalJS(INJECT);
await evalJS(KILL_TRANSITION);
await evalJS(`document.getElementById('welcomeClose') && document.getElementById('welcomeClose').click();`);
await sleep(400);

const report = { url: URL, when: new Date().toISOString(), viewports: [], errors: consoleErrors };

for (const vp of [{ w: 1600, h: 1000, tag: 'wide' }, { w: 1180, h: 820, tag: 'narrow' }]) {
  await send('Emulation.setDeviceMetricsOverride', { width: vp.w, height: vp.h, deviceScaleFactor: 1, mobile: false });
  await sleep(600);
  const vpReport = { viewport: vp, themes: {} };
  for (const theme of ['dark', 'paper']) {
    await evalJS(`applyTheme('${theme}');`);
    await sleep(250);
    const stateResults = {};
    for (const st of STATES) {
      await evalJS(CLOSE_ALL);
      await sleep(120);
      const r = await evalJS(st.open + '; "ok"');
      if (typeof r === 'object' && r.error) { stateResults[st.name] = { openError: r.error }; continue; }
      await sleep(st.wait || 400);
      const raw = await evalJS(`window.__audit()`);
      let data = {};
      try { data = JSON.parse(raw); } catch { stateResults[st.name] = { auditError: String(raw).slice(0, 200) }; continue; }
      stateResults[st.name] = {
        lowContrast: data.lowContrast.slice(0, 24),
        lowContrastCount: data.lowContrast.length,
        overflow: data.overflow.slice(0, 12),
        overflowCount: data.overflow.length,
        offscreen: data.offscreen.slice(0, 12)
      };
      if (['welcome', 'main', 'ideaModal', 'equipModal', 'techTree', 'designerModal'].includes(st.name)) {
        await shot(`${OUT_DIR}/v0.52_${vp.tag}_${theme}_${st.name}.png`);
      }
    }
    vpReport.themes[theme] = stateResults;
  }
  report.viewports.push(vpReport);
  await send('Emulation.clearDeviceMetricsOverride');
}

report.errors = consoleErrors;
fs.writeFileSync(`${OUT_DIR}/v0.52_audit.json`, JSON.stringify(report, null, 1));

// 控制台摘要
for (const vp of report.viewports) {
  for (const theme of ['dark', 'paper']) {
    const res = vp.themes[theme];
    let lc = 0, ov = 0, off = 0;
    for (const k of Object.keys(res)) {
      lc += res[k].lowContrastCount || 0;
      ov += res[k].overflowCount || 0;
      off += (res[k].offscreen || []).length;
    }
    console.log(`[${vp.viewport.tag}/${theme}] lowContrast=${lc} overflow=${ov} offscreen=${off}`);
  }
}
console.log('states:', STATES.length, 'errors:', consoleErrors.length);
ws.close(); chrome.kill(); process.exit(0);
