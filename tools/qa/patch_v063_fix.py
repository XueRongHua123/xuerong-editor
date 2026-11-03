# -*- coding: utf-8 -*-
"""v0.63：修环形菜单缩放偏移、AI 面板定位/关闭、雪绒显隐互切。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.63 缩放适配与面板定位 ---------- */"

CSS = """  /* ---------- v0.63 缩放适配与面板定位 ---------- */
  #aiBubble.open{transform:none}
  #aiBubble img{transition:transform .28s cubic-bezier(.2,.8,.2,1)}
  #aiBubble.open img{transform:rotate(45deg)}
  #aiModal{z-index:120!important}
  .ai-card{max-height:none!important}
  .ai-body{overflow:auto}
"""

JS = """/* ---------- v0.63 缩放适配与面板定位 ---------- */
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

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    anchor_css = "  /* ---------- v0.62 环形菜单与浮窗 ---------- */"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, CSS + anchor_css, 1)

    anchor_js = "\n/* ---------- v0.62 环形菜单与浮窗 ---------- */"
    assert h.count(anchor_js) == 1
    h = h.replace(anchor_js, "\n" + JS + "/* ---------- v0.62 环形菜单与浮窗 ---------- */", 1)

    # 1) openRadial：坐标按 zoom 归一，并按雪绒状态刷新最后一项
    old_open = """  const r = b.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  box.style.left = cx + 'px';
  box.style.top = cy + 'px';
  const items = [...box.querySelectorAll('.rad-item')];
  const R = 84, n = items.length;
  const vw = window.innerWidth, vh = window.innerHeight;"""
    new_open = """  syncRadialMascotItem();
  const z = uiZoom();
  const r = b.getBoundingClientRect();
  const cx = (r.left + r.width / 2) / z, cy = (r.top + r.height / 2) / z;
  box.style.left = cx + 'px';
  box.style.top = cy + 'px';
  const items = [...box.querySelectorAll('.rad-item')];
  const R = 84, n = items.length;
  const vw = window.innerWidth / z, vh = window.innerHeight / z;"""
    assert h.count(old_open) == 1, 'openRadial 结构不符'
    h = h.replace(old_open, new_open, 1)

    # 2) 菜单项换衣服 → 雪绒显隐互切
    old_act = """  if(act === 'skins'){ showMascotFloat(true); return openSkinPick(); }"""
    new_act = """  if(act === 'skins'){ showMascotFloat(true); return openSkinPick(); }
  if(act === 'mascot'){ toggleMascotFloat(); return; }"""
    assert h.count(old_act) == 1
    h = h.replace(old_act, new_act, 1)

    old_item = '<button class="rad-item" data-act="skins" data-name="换衣服">👗</button>'
    new_item = ('<button class="rad-item" data-act="skins" data-name="换衣服">👗</button>\n'
                '  <button class="rad-item" data-act="mascot" data-name="隐藏雪绒">👀</button>')
    assert h.count(old_item) == 1
    h = h.replace(old_item, new_item, 1)

    old_hide = '  <button class="rad-item" data-act="hide" data-name="隐藏雪绒">👀</button>\n'
    assert h.count(old_hide) == 1
    h = h.replace(old_hide, '', 1)

    # 3) openAI 末尾定位
    old_oai = """async function openAI(){
  document.getElementById('aiModal').classList.add('show');  document.getElementById('aiHint').textContent = '';"""
    new_oai = """async function openAI(){
  document.getElementById('aiModal').classList.add('show');
  if(typeof placeAiModal === 'function') placeAiModal();
  document.getElementById('aiHint').textContent = '';"""
    assert h.count(old_oai) == 1
    h = h.replace(old_oai, new_oai, 1)

    # 4) AI 拖动：改 window 级监听 + zoom 归一
    old_drag = """  head.addEventListener('pointerdown', e=>{
    if(e.target.closest('button')) return;
    const r = modal.getBoundingClientRect();
    modal.style.right = 'auto';
    modal.style.bottom = 'auto';
    modal.style.left = r.left + 'px';
    modal.style.top = r.top + 'px';
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
  });"""
    new_drag = """  head.addEventListener('pointerdown', e=>{
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
  });"""
    assert h.count(old_drag) == 1, 'AI 拖动结构不符'
    h = h.replace(old_drag, new_drag, 1)

    # 5) 双击头部复位：清空并重新定位
    old_dbl = """    modal.style.left = '';
    modal.style.top = '';
    modal.style.right = '20px';
    modal.style.bottom = '170px';
    try{ localStorage.removeItem('fe_ai_pos'); }catch(err){}"""
    new_dbl = """    try{ localStorage.removeItem('fe_ai_pos'); }catch(err){}
    modal.style.left = '';
    modal.style.top = '';
    modal.style.right = '';
    modal.style.bottom = '';
    placeAiModal();"""
    assert h.count(old_dbl) == 1
    h = h.replace(old_dbl, new_dbl, 1)

    # 6) 关闭按钮走 closeAI，Esc 也能关
    old_close = "document.getElementById('aiClose').onclick = ()=>{ document.getElementById('aiModal').classList.remove('show'); };"
    if h.count(old_close) == 1:
        h = h.replace(old_close, "document.getElementById('aiClose').onclick = closeAI;", 1)
    else:
        old_close2 = "document.getElementById('aiClose').onclick = ()=>{ document.getElementById('aiModal').classList.remove('show'); }"
        assert h.count(old_close2) == 1, 'aiClose 绑定结构不符'
        h = h.replace(old_close2, "document.getElementById('aiClose').onclick = closeAI", 1)

    old_esc = """  if(inField || e.ctrlKey || e.metaKey || e.altKey) return;"""
    new_esc = """  if(inField || e.ctrlKey || e.metaKey || e.altKey) return;
  if(k === 'escape'){
    const ai = document.getElementById('aiModal');
    if(ai && ai.classList.contains('show')){ closeAI(); return; }
  }"""
    assert h.count(old_esc) == 1
    h = h.replace(old_esc, new_esc, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.63 注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
