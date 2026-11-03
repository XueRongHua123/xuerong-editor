# -*- coding: utf-8 -*-
"""v0.62：悬浮球环形菜单、AI 面板可拖动、看板娘缩放与换装、卸载排序、弹窗收敛。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.62 环形菜单与浮窗 ---------- */"

CSS = """  /* ---------- v0.62 环形菜单与浮窗 ---------- */
  #aiModal{width:min(430px,calc(100vw - 28px))!important;right:auto;bottom:auto;left:auto;top:auto}
  #aiModal.show .ai-card{animation:aiPop .22s cubic-bezier(.2,.8,.2,1)}
  @keyframes aiPop{from{transform:translateY(8px) scale(.98);opacity:.4}to{transform:none;opacity:1}}
  .ai-card{max-height:calc(100vh - 120px);overflow:hidden}
  .ai-body{overflow:auto;max-height:calc(100vh - 220px)}
  .ai-head-drag{cursor:grab}
  .ai-head-drag:active{cursor:grabbing}
  #aiRadial{position:fixed;left:0;top:0;z-index:124;width:0;height:0;pointer-events:none}
  #aiRadial.show{pointer-events:auto}
  .rad-item{position:absolute;left:-22px;top:-22px;width:44px;height:44px;border-radius:50%;
    border:1px solid var(--line);background:var(--panel);color:var(--text);cursor:pointer;
    display:grid;place-items:center;font-size:16px;box-shadow:var(--shadow);
    transform:translate(0,0) scale(.35);opacity:0;
    transition:transform .28s cubic-bezier(.2,.8,.2,1),opacity .2s ease,border-color .16s}
  #aiRadial.show .rad-item{transform:translate(var(--tx),var(--ty)) scale(1);opacity:1}
  .rad-item:hover{border-color:var(--accent);color:var(--accent);transform:translate(var(--tx),var(--ty)) scale(1.12)}
  .rad-item::after{content:attr(data-name);position:absolute;left:50%;top:calc(100% + 4px);transform:translateX(-50%);
    white-space:nowrap;background:var(--panel);border:1px solid var(--line);border-radius:6px;
    padding:2px 7px;font-size:10.5px;color:var(--text);opacity:0;pointer-events:none;transition:opacity .15s}
  .rad-item:hover::after{opacity:1}
  #aiBubble.open{border-color:var(--accent);transform:rotate(45deg);box-shadow:0 0 0 6px color-mix(in srgb,var(--accent) 16%,transparent)}
  #aiBubble{transition:transform .28s cubic-bezier(.2,.8,.2,1),box-shadow .2s,border-color .2s}
  .mf-skins{display:flex;align-items:center;gap:6px;justify-content:center;padding:4px 8px 6px}
  .mf-nav{width:22px;height:22px;border-radius:50%;border:1px solid var(--line);background:var(--panel2);
    color:var(--text);cursor:pointer;font-size:13px;line-height:1;display:grid;place-items:center}
  .mf-nav:hover{border-color:var(--accent);color:var(--accent)}
  #mascotSkinName{font-size:10.5px;color:var(--muted);min-width:52px;text-align:center}
  #mascotResize{position:absolute;right:2px;bottom:2px;width:14px;height:14px;cursor:nwse-resize;
    border-right:2px solid var(--line2);border-bottom:2px solid var(--line2);border-bottom-right-radius:6px}
  #mascotResize:hover{border-color:var(--accent)}
  .cm-card{width:min(1040px,calc(100% - 48px))!important;height:min(740px,calc(100% - 48px))!important;
    border-radius:18px!important}
  #countryModal,#stateModal,#lintModal,#historyModal,#unloadModal,#keysModal{background:rgba(8,10,9,.62)!important;
    backdrop-filter:blur(3px)}
"""

RADIAL = """<div id="aiRadial">
  <button class="rad-item" data-act="ai" data-name="AI 助手">💬</button>
  <button class="rad-item" data-act="cmd" data-name="命令面板">⌘</button>
  <button class="rad-item" data-act="lint" data-name="项目体检">🩺</button>
  <button class="rad-item" data-act="country" data-name="国家中心">🌍</button>
  <button class="rad-item" data-act="state" data-name="州 / 地块">🗺</button>
  <button class="rad-item" data-act="skins" data-name="换衣服">👗</button>
  <button class="rad-item" data-act="hide" data-name="隐藏雪绒">👀</button>
</div>
"""

MF_DOM = """  <div class="mf-skins">
    <button class="mf-nav" id="mascotPrev" title="上一套">‹</button>
    <span id="mascotSkinName">经典</span>
    <button class="mf-nav" id="mascotNext" title="下一套">›</button>
  </div>
  <div id="mascotResize" title="拖动调整大小，双击复位"></div>
"""

JS = """/* ---------- v0.62 环形菜单与浮窗 ---------- */
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
  const r = b.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  box.style.left = cx + 'px';
  box.style.top = cy + 'px';
  const items = [...box.querySelectorAll('.rad-item')];
  const R = 84, n = items.length;
  items.forEach((el, i)=>{
    const a = -Math.PI / 2 + i * 2 * Math.PI / n;
    el.style.setProperty('--tx', (Math.cos(a) * R).toFixed(1) + 'px');
    el.style.setProperty('--ty', (Math.sin(a) * R).toFixed(1) + 'px');
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
  if(act === 'hide'){ showMascotFloat(false); return status('已隐藏雪绒，可从左侧「❄ 雪绒」重新显示'); }
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

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    # CSS
    anchor_css = "  /* ---------- v0.61 AI 面板与悬浮球 ---------- */"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, CSS + anchor_css, 1)

    # 环形菜单 DOM：放在 aiMenu 之后
    anchor_menu = '<div id="aiMenu">'
    assert h.count(anchor_menu) == 1
    h = h.replace(anchor_menu, RADIAL + anchor_menu, 1)

    # 看板娘：换装条 + 缩放手柄
    anchor_mf = '  <div id="mascotTip" class="mf-tip"></div>'
    assert h.count(anchor_mf) == 1
    h = h.replace(anchor_mf, MF_DOM + anchor_mf, 1)

    # JS
    anchor_js = "\n/* ---------- v0.61 AI 面板与悬浮球 ---------- */"
    assert h.count(anchor_js) == 1
    h = h.replace(anchor_js, JS + anchor_js, 1)

    # 球的单击 → 环形菜单（pointerup 的 else 分支）
    old_click = """    } else {
      const m = document.getElementById('aiModal');
      if(m.classList.contains('show')) m.classList.remove('show');
      else openAI();
    }"""
    new_click = """    } else {
      toggleRadial();
    }"""
    assert h.count(old_click) == 1, 'pointerup 分支结构不符'
    h = h.replace(old_click, new_click, 1)

    # 右键也开环形菜单
    old_ctx = """  bubble.addEventListener('contextmenu', e=>{
    e.preventDefault();
    openAiMenu(e.clientX - 8, e.clientY - 8);
  });"""
    new_ctx = """  bubble.addEventListener('contextmenu', e=>{
    e.preventDefault();
    closeAiMenu();
    toggleRadial();
  });"""
    assert h.count(old_ctx) == 1
    h = h.replace(old_ctx, new_ctx, 1)

    # 去掉双击（与单击冲突）
    old_dbl = """  bubble.addEventListener('dblclick', e=>{
    e.preventDefault();
    closeAiMenu();
    openCmd();
  });
"""
    assert h.count(old_dbl) == 1
    h = h.replace(old_dbl, "", 1)

    # 环形菜单点击与外部关闭、AI 头部拖动
    old_bind = "document.getElementById('aiMenu').addEventListener('click', e=>{"
    new_bind = """document.getElementById('aiRadial').addEventListener('click', e=>{
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
    const r = modal.getBoundingClientRect();
    drag = {sx: e.clientX, sy: e.clientY, ox: r.left, oy: r.top};
    head.setPointerCapture && head.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  head.addEventListener('pointermove', e=>{
    if(!drag) return;
    const w = modal.offsetWidth;
    const x = Math.max(8, Math.min(window.innerWidth - w - 8, drag.ox + e.clientX - drag.sx));
    const y = Math.max(8, Math.min(window.innerHeight - 80, drag.oy + e.clientY - drag.sy));
    modal.style.left = x + 'px';
    modal.style.top = y + 'px';
  });
  head.addEventListener('pointerup', ()=>{
    if(!drag) return;
    drag = null;
    try{ localStorage.setItem('fe_ai_pos', JSON.stringify({x: parseInt(modal.style.left) || 0, y: parseInt(modal.style.top) || 0})); }catch(e){}
  });
  head.addEventListener('dblclick', e=>{
    if(e.target.closest('button')) return;
    modal.style.left = '';
    modal.style.top = '';
    try{ localStorage.removeItem('fe_ai_pos'); }catch(err){}
  });
})();
document.getElementById('aiMenu').addEventListener('click', e=>{"""
    assert h.count(old_bind) == 1
    h = h.replace(old_bind, new_bind, 1)

    # 卸载面板：改用"最近加载优先"的渲染
    old_unload = """function openUnloadModal(){
  const box = document.getElementById('unloadList');
  const roots = (DATA && DATA.roots) || [];
  document.getElementById('unloadModal').classList.add('show');
  if(!roots.length){"""
    new_unload = """function openUnloadModal(){
  return openUnloadModalRecent();
}

function openUnloadModalOld(){
  const box = document.getElementById('unloadList');
  const roots = (DATA && DATA.roots) || [];
  document.getElementById('unloadModal').classList.add('show');
  if(!roots.length){"""
    assert h.count(old_unload) == 1
    h = h.replace(old_unload, new_unload, 1)

    # 初始化看板娘缩放（放在 initMascot 之后调用）
    old_init = "initMascot();\nloadData();"
    new_init = "initMascot();\ninitMascotFloatSize();\nloadData();"
    assert h.count(old_init) == 1
    h = h.replace(old_init, new_init, 1)

    # applySkin 后刷新看板娘面板上的名字
    old_apply = """  try { localStorage.setItem('mascotSkin', id); } catch(e){}
  document.getElementById('skinPick').classList.remove('show');"""
    new_apply = """  try { localStorage.setItem('mascotSkin', id); } catch(e){}
  if(typeof updateMascotSkinName === 'function') updateMascotSkinName();
  document.getElementById('skinPick').classList.remove('show');"""
    assert h.count(old_apply) == 1
    h = h.replace(old_apply, new_apply, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.62 注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
