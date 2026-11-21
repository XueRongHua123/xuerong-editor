// 50-mascot：雪绒挂件（P4）
// 皮肤 / 浮窗尺寸 / 拖动 / 提示气泡 / 初始化。

function openSkinPick(){
  const g = document.getElementById('skinGrid'); if(!g || !DATA) return;
  g.innerHTML = '';
  (DATA.mascots || []).forEach(m=>{
    const d = document.createElement('div');
    d.className = 'ip-item';
    d.innerHTML = '<img src="/' + m.thumb + '" alt=""><span>' + escapeHtml(m.name) + '</span>';
    d.onclick = ()=>applySkin(m.id);
    g.appendChild(d);
  });
  document.getElementById('skinPick').classList.add('show');
}

function applySkin(id){
  const m = ((DATA && DATA.mascots) || []).find(x=>x.id === id);
  if(!m) return;
  const img = document.getElementById('mascotImg');
  if(img) img.src = '/' + m.file;
  try { localStorage.setItem('mascotSkin', id); } catch(e){}
  if(typeof updateMascotSkinName === 'function') updateMascotSkinName();
  document.getElementById('skinPick').classList.remove('show');
}

function applySavedSkin(){
  try {
    const id = localStorage.getItem('mascotSkin');
    if(id && DATA && DATA.mascots){
      const m = DATA.mascots.find(x=>x.id === id);
      const img = document.getElementById('mascotImg');
      if(m && img) img.src = '/' + m.file;
    }
  } catch(e){}
}


function showMascotFloat(on){
  const box = document.getElementById('mascotFloat');
  if(!box) return;
  box.style.display = on ? 'block' : 'none';
  try{
    const raw = localStorage.getItem('mascotFloatState');
    const st = raw ? JSON.parse(raw) : {};
    st.hidden = !on;
    localStorage.setItem('mascotFloatState', JSON.stringify(st));
  }catch(e){}
}


/* 看板娘：快捷换装 + 自由缩放 */
function mascotSkins(){ return (DATA && DATA.mascots) || []; }


function mascotSkinId(){
  try{ return localStorage.getItem('mascotSkin') || 'card'; }catch(e){ return 'card'; }
}


function updateMascotSkinName(){
  const el = document.getElementById('mascotSkinName');
  if(!el) return;
  const m = mascotSkins().find(x=>x.id === mascotSkinId());
  el.textContent = m ? m.name : '经典';
}


function mascotStepSkin(step){
  const list = mascotSkins();
  if(!list.length) return;
  let i = list.findIndex(x=>x.id === mascotSkinId());
  if(i < 0) i = 0;
  i = (i + step + list.length) % list.length;
  applySkin(list[i].id);
  updateMascotSkinName();
  status('雪绒换装：' + list[i].name);
}


function applyMascotWidth(w){
  const box = document.getElementById('mascotFloat');
  if(!box) return;
  const width = Math.max(200, Math.min(560, Math.round(w)));
  box.style.width = width + 'px';
  try{ localStorage.setItem('mascotFloatW', String(width)); }catch(e){}
}


function initMascotFloatSize(){
  const box = document.getElementById('mascotFloat');
  const grip = document.getElementById('mascotResize');
  if(!box || !grip) return;
  try{
    const w = parseInt(localStorage.getItem('mascotFloatW') || '', 10);
    if(w) box.style.width = w + 'px';
  }catch(e){}
  let drag = null;
  grip.addEventListener('pointerdown', e=>{
    e.preventDefault(); e.stopPropagation();
    drag = {sx: e.clientX, w0: box.offsetWidth};
    grip.setPointerCapture && grip.setPointerCapture(e.pointerId);
  });
  grip.addEventListener('pointermove', e=>{
    if(!drag) return;
    applyMascotWidth(drag.w0 + (e.clientX - drag.sx));
  });
  grip.addEventListener('pointerup', ()=>{ drag = null; });
  grip.addEventListener('dblclick', e=>{
    e.preventDefault(); e.stopPropagation();
    applyMascotWidth(300);
    status('雪绒大小已复位');
  });
  const prev = document.getElementById('mascotPrev');
  const next = document.getElementById('mascotNext');
  if(prev) prev.onclick = ()=>mascotStepSkin(-1);
  if(next) next.onclick = ()=>mascotStepSkin(1);
  updateMascotSkinName();
}


/* 卸载列表：最近加载的排最前 */
function openUnloadModalRecent(){
  const roots = (DATA && DATA.roots) || [];
  const box = document.getElementById('unloadList');
  document.getElementById('unloadModal').classList.add('show');
  if(!roots.length){
    box.innerHTML = '<div class="ul-empty">还没有加载任何内容。</div>';
    return;
  }
  const ordered = roots.map((r, i)=>({r, i})).reverse();
  box.innerHTML = ordered.map((o, idx)=>
    '<div class="ul-row' + (idx === 0 ? ' recent' : '') + '">' +
      '<div class="ul-main"><b>' + escapeHtml(o.r.name || o.r.path) + '</b><span>' +
        escapeHtml(o.r.path || '') + '</span></div>' +
      '<span class="ul-tag' + (o.r.readonly ? ' ro' : '') + '">' +
        (o.r.readonly ? '原版 · 只读' : (idx === 0 ? '最近加载' : '可编辑')) + '</span>' +
      '<button class="btn" data-i="' + o.i + '">卸载</button>' +
    '</div>').join('');
  box.querySelectorAll('button[data-i]').forEach(b=>{
    b.onclick = ()=>unloadRoot(roots[Number(b.dataset.i)]);
  });
}


function initMascot(){
  const box = document.getElementById('mascotFloat'); if(!box) return;
  const tipEl = document.getElementById('mascotTip');
  const m = I18N.mascot || {};
  const tips = (m.tips && (m.tips[LANG] || m.tips.zh)) || [];
  let i = Math.floor(Math.random() * Math.max(1, tips.length));
  const show = ()=>{ if(tips.length) tipEl.textContent = tips[i % tips.length]; };
  show();
  const bubble = document.getElementById('mascotBubble');
  const greeting = (m.greeting && (m.greeting[LANG] || m.greeting.zh)) || '';
  let bubTimer = null;
  const showBubble = (text, ms)=>{
    if(!text || !bubble) return;
    bubble.textContent = text;
    bubble.classList.add('show');
    clearTimeout(bubTimer);
    bubTimer = setTimeout(()=>bubble.classList.remove('show'), ms || 3500);
  };
  try {
    if(greeting && !sessionStorage.getItem('mascotGreeted')){
      sessionStorage.setItem('mascotGreeted', '1');
      setTimeout(()=>showBubble(greeting, 6000), 700);
    }
  } catch(e){}
  const KEY = 'mascotFloatState';
  const load = ()=>{ try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e){ return {}; } };
  const save = ()=>{ try { localStorage.setItem(KEY, JSON.stringify({left: parseInt(box.style.left) || null, top: parseInt(box.style.top) || null, large: box.classList.contains('large'), hidden: box.style.display === 'none'})); } catch(e){} };
  const st = load();
  if(st.large) box.classList.add('large');
  if(st.left !== null && st.left !== undefined){
    box.style.left = st.left + 'px';
    box.style.right = 'auto';
    box.style.bottom = 'auto';
    box.style.top = (st.top || 14) + 'px';
  }
  if(st.hidden) box.style.display = 'none';
  let drag = null, moved = false;
  box.addEventListener('mousedown', e=>{
    if(e.target.closest('button')) return;
    drag = {sx: e.clientX, sy: e.clientY, ox: box.offsetLeft, oy: box.offsetTop};
    moved = false; box.style.cursor = 'grabbing'; e.preventDefault();
  });
  window.addEventListener('mousemove', e=>{
    if(!drag) return;
    const dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
    if(Math.abs(dx) + Math.abs(dy) > 3) moved = true;
    box.style.transform = 'rotate(' + Math.max(-6, Math.min(6, dx * 0.12)) + 'deg)';
    const x = Math.max(0, Math.min(window.innerWidth - box.offsetWidth, drag.ox + dx));
    const y = Math.max(0, Math.min(window.innerHeight - box.offsetHeight, drag.oy + dy));
    box.style.left = x + 'px'; box.style.right = 'auto'; box.style.top = y + 'px'; box.style.bottom = 'auto';
  });
  window.addEventListener('mouseup', ()=>{
    if(!drag) return;
    box.style.cursor = 'move'; drag = null;
    box.style.transition = 'transform .25s';
    box.style.transform = '';
    setTimeout(()=>{ box.style.transition = ''; }, 260);
    if(moved) save();
  });
  box.addEventListener('click', e=>{
    if(e.target.closest('button')) return;
    if(moved){ moved = false; return; }
    i++; show();
    if(tips.length) showBubble(tips[i % tips.length], 4000);
  });
  box.addEventListener('dblclick', ()=>{ box.classList.toggle('large'); save(); });
  document.getElementById('mascotClose').onclick = ()=>{ box.style.display = 'none'; save(); };
  document.getElementById('mascotSize').onclick = ()=>{ box.classList.toggle('large'); save(); };
  const autoTimer = setInterval(()=>{
    if(document.hidden || box.style.display === 'none' || drag) return;
    tipEl.classList.add('fade');
    setTimeout(()=>{ i++; show(); tipEl.classList.remove('fade'); }, 350);
  }, 25000);
  const entry = document.getElementById('mascotEntry');
  if(entry) entry.onclick = ()=>{ openSkinPick(); };
}
