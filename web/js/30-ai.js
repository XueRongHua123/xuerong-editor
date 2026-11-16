// 30-ai：AI 助手（P4）
// 对话 / 模板 / 历史 / 流式中止 / 气泡菜单 / 径向菜单入口 / 弹窗拖动定位。

/* ---------- v0.63 缩放适配与面板定位 ---------- */
function uiZoom(){
  try{
    const z = parseFloat(getComputedStyle(document.body).zoom || '1');
    return (isFinite(z) && z > 0) ? z : 1;
  }catch(e){ return 1; }
}


function closeAI(){
  const m = document.getElementById('aiModal');
  if(m) m.classList.remove('show');
}


function clampNum(v, lo, hi){ return Math.max(lo, Math.min(hi, v)); }


function placeAiModal(){
  const el = document.getElementById('aiModal');
  if(!el) return;
  const z = uiZoom();
  const vw = window.innerWidth / z, vh = window.innerHeight / z;
  let saved = null;
  try{ saved = JSON.parse(localStorage.getItem('fe_ai_pos') || 'null'); }catch(e){}
  if(saved && typeof saved.x === 'number'){
    el.style.left = clampNum(saved.x, 8, Math.max(8, vw - 220)) + 'px';
    el.style.top = clampNum(saved.y, 8, Math.max(8, vh - 140)) + 'px';
    el.style.right = 'auto';
    el.style.bottom = 'auto';
  } else {
    el.style.left = 'auto';
    el.style.right = (18 / z) + 'px';
    el.style.top = 'auto';
    el.style.bottom = (110 / z) + 'px';
  }
  const maxH = Math.max(320, vh - 40);
  el.style.maxHeight = maxH + 'px';
  const card = el.querySelector('.ai-card');
  if(card) card.style.maxHeight = maxH + 'px';
}


function toggleMascotFloat(){
  const box = document.getElementById('mascotFloat');
  if(!box) return false;
  const on = (box.style.display !== 'none');
  showMascotFloat(!on);
  status(on ? '已隐藏雪绒，点环形菜单里的「显示雪绒」可以再叫出来' : '雪绒回来了');
  return !on;
}


function syncRadialMascotItem(){
  const item = document.querySelector('#aiRadial [data-act="mascot"]');
  if(!item) return;
  const box = document.getElementById('mascotFloat');
  const on = box && box.style.display !== 'none';
  item.dataset.name = on ? '隐藏雪绒' : '显示雪绒';
  item.textContent = on ? '👀' : '🐟';
}


/* ---------- v0.62 环形菜单与浮窗 ---------- */
function closeRadial(){
  const box = document.getElementById('aiRadial');
  if(box) box.classList.remove('show');
  const b = document.getElementById('aiBubble');
  if(b) b.classList.remove('open');
}


function openRadial(){
  const b = document.getElementById('aiBubble');
  const box = document.getElementById('aiRadial');
  if(!b || !box) return;
  syncRadialMascotItem();
  const z = uiZoom();
  const r = b.getBoundingClientRect();
  const cx = (r.left + r.width / 2) / z, cy = (r.top + r.height / 2) / z;
  box.style.left = cx + 'px';
  box.style.top = cy + 'px';
  const items = [...box.querySelectorAll('.rad-item')];
  const R = 84, n = items.length;
  const vw = window.innerWidth / z, vh = window.innerHeight / z;
  items.forEach((el, i)=>{
    const a = -Math.PI / 2 + i * 2 * Math.PI / n;
    let x = cx + Math.cos(a) * R, y = cy + Math.sin(a) * R;
    // 贴边时把按钮夹进视口，避免最外圈被裁掉
    x = Math.max(30, Math.min(vw - 30, x));
    y = Math.max(30, Math.min(vh - 30, y));
    el.style.setProperty('--tx', (x - cx).toFixed(1) + 'px');
    el.style.setProperty('--ty', (y - cy).toFixed(1) + 'px');
  });
  box.classList.add('show');
  b.classList.add('open');
}


function toggleRadial(){
  const box = document.getElementById('aiRadial');
  if(box && box.classList.contains('show')) closeRadial(); else openRadial();
}


function radialAction(act){
  closeRadial();
  if(act === 'ai') return openAI();
  if(act === 'cmd') return openCmd();
  if(act === 'lint') return openLint();
  if(act === 'country') return openCountry();
  if(act === 'state') return openStates();
  if(act === 'skins'){ showMascotFloat(true); return openSkinPick(); }
  if(act === 'mascot'){ toggleMascotFloat(); return; }
  if(act === 'hide'){ showMascotFloat(false); return status('已隐藏雪绒，可从左侧「❄ 雪绒」重新显示'); }
}


function aiFillTemplate(kind){
  const t = AI_TEMPLATES[kind];
  if(!t) return;
  const box = document.getElementById('aiPrompt');
  box.value = t;
  box.focus();
  status('已填入模板，按「发送」提交');
}


function aiUpdateMeta(txt){
  const el = document.getElementById('aiMeta');
  if(el) el.textContent = txt || '';
}


async function aiTest(){
  const btn = document.getElementById('aiTest');
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = '测试中…';
  const t0 = Date.now();
  try{
    const r = await fetch('/api/ai_test', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const j = await r.json();
    aiUpdateMeta((j.ok ? '✓ ' : '✗ ') + (j.msg || '') + ' · ' + (Date.now() - t0) + 'ms');
    status(j.ok ? 'AI 连接正常' : ('AI 连接失败：' + (j.msg || '')), !j.ok);
  }catch(e){
    aiUpdateMeta('✗ ' + e.message);
    status('测试失败：' + e.message, true);
  }
  btn.disabled = false;
  btn.textContent = old;
}


function aiPushHistory(prompt, answer){
  AI_HISTORY.unshift({q: prompt, a: answer, t: new Date().toLocaleTimeString().slice(0, 5)});
  AI_HISTORY = AI_HISTORY.slice(0, 12);
  renderAIHistory();
}


// v1.16.0 多轮上下文：把最近问答转成 messages（时间正序，AI_HISTORY 是新的在前）
function aiHistoryMessages(){
  const n = Number(document.getElementById('aiCtxTurns')?.value || 6);
  const list = AI_HISTORY.slice(0, Math.max(0, n)).slice().reverse();
  const msgs = [];
  list.forEach(function(h){
    if(h.q) msgs.push({role: 'user', content: String(h.q)});
    if(h.a) msgs.push({role: 'assistant', content: String(h.a)});
  });
  return msgs;
}


function aiClearCtx(){
  AI_HISTORY = [];
  renderAIHistory();
  aiUpdateMeta('上下文已清空');
  status('AI 上下文已清空');
}


function renderAIHistory(){
  const box = document.getElementById('aiHistory');
  if(!box) return;
  // 控制条始终显示：历史为空时也要能选轮数、能清空
  const ctrl = '<div class="k" style="margin:2px 0 2px;display:flex;align-items:center;gap:6px">'
    + '上下文 <select id="aiCtxTurns" style="height:20px;font-size:11px;background:var(--input);'
    + 'border:1px solid var(--line);color:var(--text);border-radius:4px">'
    + [0,2,4,6,8,12].map(function(n){
        return '<option value="' + n + '"' + (n === 6 ? ' selected' : '') + '>' + n + ' 轮</option>';
      }).join('')
    + '</select>'
    + '<button class="btn" id="aiClearCtx" style="height:20px;font-size:11px;padding:0 6px">清空</button>'
    + '</div>';
  if(!AI_HISTORY.length){
    box.innerHTML = ctrl + '<div class="k" style="color:var(--t3)">（暂无历史，多轮上下文未启用）</div>';
    const cb0 = document.getElementById('aiClearCtx');
    if(cb0){ cb0.onclick = aiClearCtx; }
    return;
  }
  box.innerHTML = ctrl
    + '<div class="k" style="margin:2px 0 2px">最近提问（点一下回填）</div>' +
    AI_HISTORY.map((h, i)=>'<div class="ai-h" data-i="' + i + '">' + h.t + ' · ' + escapeHtml(h.q.slice(0, 60)) + '</div>').join('');
  const cb = document.getElementById('aiClearCtx');
  if(cb && !cb.dataset.bound){
    cb.dataset.bound = '1';
    cb.onclick = aiClearCtx;
  }
  box.querySelectorAll('.ai-h').forEach(el=>{
    el.onclick = ()=>{
      const h = AI_HISTORY[Number(el.dataset.i)];
      if(!h) return;
      document.getElementById('aiPrompt').value = h.q;
      document.getElementById('aiOut').textContent = h.a;
      aiUpdateMeta('来自历史记录');
    };
  });
}


function aiClearHistory(){
  AI_HISTORY = [];
  renderAIHistory();
  document.getElementById('aiOut').textContent = '';
  aiUpdateMeta('');
  status('已清空最近对话');
}


function aiToggleKey(){
  const el = document.getElementById('aiKey');
  el.type = el.type === 'password' ? 'text' : 'password';
}


/* 悬浮球菜单 */
function openAiMenu(x, y){
  const menu = document.getElementById('aiMenu');
  menu.classList.add('show');
  const w = menu.offsetWidth || 176, h = menu.offsetHeight || 220;
  menu.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, x)) + 'px';
  menu.style.top = Math.max(8, Math.min(window.innerHeight - h - 8, y)) + 'px';
}

function closeAiMenu(){ document.getElementById('aiMenu').classList.remove('show'); }


function aiMenuAction(act){
  closeAiMenu();
  if(act === 'ai') return openAI();
  if(act === 'cmd') return openCmd();
  if(act === 'lint') return openLint();
  if(act === 'country') return openCountry();
  if(act === 'state') return openStates();
  if(act === 'hide'){
    const box = document.getElementById('mascotFloat');
    if(box) box.style.display = 'none';
    try{ localStorage.setItem('mascotFloatState', JSON.stringify({hidden: true})); }catch(e){}
    status('已隐藏雪绒，可从左侧「❄ 雪绒」重新显示');
  }
}


function aiBubbleBusy(on){
  const b = document.getElementById('aiBubble');
  if(b) b.classList.toggle('busy', !!on);
}


/* v0.61 面板绑定 */
document.getElementById('aiTest').onclick = aiTest;

document.getElementById('aiStop').onclick = stopAI;

document.getElementById('aiClearHistory').onclick = aiClearHistory;

document.querySelectorAll('#aiTemplates .cm-chip').forEach(el=>{
  el.onclick = ()=>aiFillTemplate(el.dataset.tpl);
});

document.getElementById('aiKey').addEventListener('dblclick', aiToggleKey);

document.getElementById('aiRadial').addEventListener('click', e=>{
  const btn = e.target.closest('.rad-item');
  if(btn) radialAction(btn.dataset.act);
});

document.addEventListener('pointerdown', e=>{
  if(!e.target.closest('#aiRadial') && !e.target.closest('#aiBubble')) closeRadial();
});

document.fonts && document.fonts.ready && document.fonts.ready.then(()=>{});

(function(){
  const modal = document.getElementById('aiModal');
  const head = modal && modal.querySelector('.diff-head');
  if(!head) return;
  head.classList.add('ai-head-drag');
  let drag = null;
  try{
    const p = JSON.parse(localStorage.getItem('fe_ai_pos') || 'null');
    if(p){ modal.style.left = p.x + 'px'; modal.style.top = p.y + 'px'; }
  }catch(e){}
  head.addEventListener('pointerdown', e=>{
    if(e.target.closest('button')) return;
    const z = uiZoom();
    const r = modal.getBoundingClientRect();
    modal.style.right = 'auto';
    modal.style.bottom = 'auto';
    modal.style.left = (r.left / z) + 'px';
    modal.style.top = (r.top / z) + 'px';
    modal.style.transform = 'none';
    drag = {sx: e.clientX, sy: e.clientY, ox: r.left / z, oy: r.top / z};
    e.preventDefault();
  });
  window.addEventListener('pointermove', e=>{
    if(!drag) return;
    const z = uiZoom();
    const vw = window.innerWidth / z, vh = window.innerHeight / z;
    const w = modal.offsetWidth, h = Math.min(modal.offsetHeight, vh - 16);
    const x = Math.max(8, Math.min(vw - w - 8, drag.ox + (e.clientX - drag.sx) / z));
    const y = Math.max(8, Math.min(vh - h - 8, drag.oy + (e.clientY - drag.sy) / z));
    modal.style.left = x + 'px';
    modal.style.top = y + 'px';
  });
  window.addEventListener('pointerup', ()=>{
    if(!drag) return;
    drag = null;
    try{ localStorage.setItem('fe_ai_pos', JSON.stringify({x: parseInt(modal.style.left) || 0, y: parseInt(modal.style.top) || 0})); }catch(e){}
  });
  head.addEventListener('dblclick', e=>{
    if(e.target.closest('button')) return;
    try{ localStorage.removeItem('fe_ai_pos'); }catch(err){}
    modal.style.left = '';
    modal.style.top = '';
    modal.style.right = '';
    modal.style.bottom = '';
    placeAiModal();
  });
})();

document.getElementById('aiMenu').addEventListener('click', e=>{
  const row = e.target.closest('[data-act]');
  if(row) aiMenuAction(row.dataset.act);
});

document.addEventListener('click', e=>{
  if(!e.target.closest('#aiMenu') && !e.target.closest('#aiBubble')) closeAiMenu();
});

window.addEventListener('resize', closeAiMenu);

async function openAI(){
  document.getElementById('aiModal').classList.add('show');
  if(typeof placeAiModal === 'function') placeAiModal();
  document.getElementById('aiHint').textContent = '';
  try {
    const r = await fetch('/api/ai_config');
    const j = await r.json();
    const c = j.config || {};
    document.getElementById('aiProvider').value = c.provider || 'openai';
    document.getElementById('aiBase').value = c.base_url || '';
    document.getElementById('aiModel').value = c.model || '';
    document.getElementById('aiSystem').value = c.system || '';
    document.getElementById('aiHint').textContent = j.has_key ? '已保存 Key（留空则沿用）' : '尚未保存 API Key';
  } catch(e){}
}

async function openAIWithContext(text, promptText){
  await openAI();
  document.getElementById('aiContext').value = text || '';
  document.getElementById('aiPrompt').value = promptText || '请根据要求修改这段脚本，并只输出脚本内容：';
}

async function saveAIConfig(){
  const r = await fetch('/api/ai_config', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      provider: document.getElementById('aiProvider').value,
      base_url: document.getElementById('aiBase').value.trim(),
      model: document.getElementById('aiModel').value.trim(),
      api_key: document.getElementById('aiKey').value.trim(),
      system: document.getElementById('aiSystem').value.trim()
    })});
  const j = await r.json();
  status(j.msg || '', !j.ok);
}


async function sendAI(){
  const out = document.getElementById('aiOut');
  const prompt = document.getElementById('aiPrompt').value.trim();
  if(!prompt){ status('先输入问题'); return; }
  out.textContent = '';
  aiUpdateMeta('请求中…');
  const t0 = Date.now();
  aiAbort = new AbortController();
  const stopBtn = document.getElementById('aiStop');
  if(stopBtn) stopBtn.style.display = '';
  let acc = '', finished = false;
  try{
    const r = await fetch('/api/ai_chat', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({prompt,
                            context: document.getElementById('aiContext').value,
                            stream: true,
                            history: aiHistoryMessages()}),
      signal: aiAbort.signal});
    if(!r.ok || !r.body){ throw new Error('HTTP ' + r.status); }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while(true){
      const step = await reader.read();
      if(step.done) break;
      buf += dec.decode(step.value, {stream: true});
      let idx;
      while((idx = buf.indexOf('\n\n')) >= 0){
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = chunk.split('\n').find(l=>l.indexOf('data:') === 0);
        if(!line) continue;
        let obj;
        try{ obj = JSON.parse(line.slice(5).trim()); }catch(e){ continue; }
        if(obj.d){
          acc += obj.d;
          out.textContent = acc;
          out.scrollTop = out.scrollHeight;
        }
        if(obj.end){
          finished = true;
          if(!obj.ok){
            out.textContent = acc || ('失败：' + (obj.msg || '未知错误'));
            aiUpdateMeta('✗ ' + (obj.msg || ''));
          } else {
            aiUpdateMeta('✓ ' + (Date.now() - t0) + 'ms · 流式');
            if(acc) aiPushHistory(prompt, acc);
          }
        }
      }
    }
    if(!finished && acc){ aiUpdateMeta('✓ ' + (Date.now() - t0) + 'ms · 流式'); aiPushHistory(prompt, acc); }
  }catch(e){
    if(e.name === 'AbortError'){
      aiUpdateMeta('已停止');
      if(acc) aiPushHistory(prompt, acc);
    } else {
      out.textContent = '失败：' + e.message;
      aiUpdateMeta('✗ 网络错误');
    }
  }
  if(stopBtn) stopBtn.style.display = 'none';
  aiAbort = null;
}


function stopAI(){
  if(aiAbort){ aiAbort.abort(); }
}
