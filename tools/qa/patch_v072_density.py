# -*- coding: utf-8 -*-
"""v0.72 节点密度 + 窄屏工具栏。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.72 节点密度与窄屏 ---------- */"

CSS = """  /* ---------- v0.72 节点密度与窄屏 ---------- */
  .toolbar .tb-narrow{display:none}
  @media (max-width: 1100px){
    .toolbar{flex-wrap:wrap;gap:4px}
    .toolbar .tb-wide{display:none}
    .toolbar .tb-narrow{display:inline-flex;align-items:center;gap:4px}
    .toolbar #tbMore{display:inline-flex}
  }
  #tbMore{display:none}
  #tbMoreMenu{position:fixed;z-index:130;display:none;background:var(--panel);border:1px solid var(--line);
    border-radius:10px;box-shadow:var(--shadow);padding:6px;min-width:180px;flex-direction:column;gap:2px}
  #tbMoreMenu.show{display:flex}
  #tbMoreMenu .tb-more-item{padding:7px 10px;border-radius:6px;font-size:12px;color:var(--text);cursor:pointer}
  #tbMoreMenu .tb-more-item:hover{background:var(--panel2);color:var(--accent)}
"""

DOM_HEAD = """      <select id="densitySel" class="btn" style="padding:3px 4px" title="节点密度">
        <option value="compact">紧凑</option>
        <option value="normal" selected>标准</option>
        <option value="comfy">舒适</option>
      </select>
"""

MENU = """<div id="tbMoreMenu"></div>
"""

JS = """/* ---------- v0.72 节点密度与窄屏 ---------- */
const NODE_SIZE = {compact: [118, 50, 96], normal: [136, 58, 110], comfy: [156, 66, 126]};

function applyDensity(mode){
  const v = NODE_SIZE[mode] || NODE_SIZE.normal;
  NODE_W = v[0];
  NODE_H = v[1];
  SCALE = v[2];
  try { localStorage.setItem('fe_density', mode); } catch(e){}
  const sel = document.getElementById('densitySel');
  if(sel) sel.value = mode;
  try { renderAll(); } catch(e){}
}

function initDensity(){
  let mode = 'normal';
  try { mode = localStorage.getItem('fe_density') || 'normal'; } catch(e){}
  if(!NODE_SIZE[mode]) mode = 'normal';
  applyDensity(mode);
}

function initNarrowMore(){
  const btn = document.getElementById('tbMore');
  const menu = document.getElementById('tbMoreMenu');
  if(!btn || !menu) return;
  const move = [
    ['💾 保存全部', 'btnSaveAll'],
    ['📤 导出覆盖包', 'btnExport'],
    ['🩺 体检', 'btnLint'],
    ['🕘 备份', 'btnBackup'],
    ['📖 内容库', 'btnLibrary'],
    ['❓ 教程', 'btnTutorial']
  ];
  menu.innerHTML = move.map(([label])=>
    '<div class="tb-more-item" data-label="' + label + '">' + label + '</div>').join('');
  btn.onclick = e=>{
    e.stopPropagation();
    const r = btn.getBoundingClientRect();
    menu.style.left = Math.max(8, Math.min(window.innerWidth - 200, r.left)) + 'px';
    menu.style.top = (r.bottom + 4) + 'px';
    menu.classList.add('show');
  };
  menu.querySelectorAll('.tb-more-item').forEach(item=>{
    item.onclick = ()=>{
      menu.classList.remove('show');
      const map = {
        '💾 保存全部': 'btnSaveAll', '📤 导出覆盖包': 'btnExport', '🩺 体检': 'btnLint',
        '🕘 备份': 'btnBackup', '📖 内容库': 'btnLibrary', '❓ 教程': 'btnTutorial'
      };
      const id = map[item.dataset.label];
      const target = id && document.getElementById(id);
      if(target && target.click) target.click();
    };
  });
  document.addEventListener('click', e=>{
    if(!e.target.closest('#tbMore') && !e.target.closest('#tbMoreMenu')) menu.classList.remove('show');
  });
}

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    # CSS
    anchor_css = "  /* ---------- v0.71 地图面板 ---------- */"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, CSS + anchor_css, 1)

    # 密度选择器
    anchor_sel = '      <select id="fsSel" class="btn" style="padding:3px 4px" title="界面大小">'
    assert h.count(anchor_sel) == 1
    h = h.replace(anchor_sel, DOM_HEAD + anchor_sel, 1)

    # 窄屏「更多」按钮 + 菜单
    anchor_more = '      <label class="btn"><input type="checkbox" id="showMutex"> 显示互斥</label>'
    assert h.count(anchor_more) == 1
    h = h.replace(anchor_more, anchor_more + '\n      <button class="btn tb-narrow" id="tbMore">⋯ 更多</button>', 1)

    anchor_body = '<div id="app">'
    assert h.count(anchor_body) == 1
    h = h.replace(anchor_body, MENU + anchor_body, 1)

    # NODE_W 常量改可变
    old_const = "const NODE_W = 136, NODE_H = 58, SCALE = 110;"
    new_const = "let NODE_W = 136, NODE_H = 58, SCALE = 110;"
    assert h.count(old_const) == 1
    h = h.replace(old_const, new_const, 1)

    # JS
    anchor_js = "\n/* ---------- v0.71 地图面板 ---------- */"
    assert h.count(anchor_js) == 1
    h = h.replace(anchor_js, JS + anchor_js, 1)

    # 绑定与初始化
    anchor_bind = "document.getElementById('mapEntry').onclick"
    assert h.count(anchor_bind) == 1
    idx = h.index(anchor_bind)
    bind = ("document.getElementById('densitySel').addEventListener('change', e=>applyDensity(e.target.value));\n"
            "initNarrowMore();\n")
    h = h[:idx] + bind + h[idx:]

    anchor_init = "initMascot();\ninitMascotFloatSize();"
    assert h.count(anchor_init) == 1
    h = h.replace(anchor_init, "initMascot();\ninitMascotFloatSize();\ninitDensity();", 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.72 注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
