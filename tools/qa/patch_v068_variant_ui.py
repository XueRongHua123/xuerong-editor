# -*- coding: utf-8 -*-
"""v0.68 前端：历史编辑器里的变体新增 / 删除。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.68 变体写入 ---------- */"

CSS = """  /* ---------- v0.68 变体写入 ---------- */
  .hv-bar{display:flex;gap:6px;align-items:center;margin:2px 0 6px;flex-wrap:wrap}
  .hv-row{display:flex;gap:6px;align-items:center;padding:4px 0;border-bottom:1px solid var(--line)}
  .hv-row .nm{flex:1;color:var(--text);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .hv-row .ty{color:var(--muted);font-size:10.5px;min-width:120px}
  .hv-row .md{color:var(--muted);font-size:10.5px;min-width:52px;text-align:right}
  #histVarForm{display:none;gap:6px;flex-direction:column;padding:8px;border:1px solid var(--line);
    border-radius:8px;margin:4px 0 8px;background:var(--panel2)}
  #histVarForm.show{display:flex}
  #histVarForm input,#histVarForm textarea{height:28px}
  #histVarForm textarea{height:74px}
  .hv-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
"""

JS = """/* ---------- v0.68 变体写入 ---------- */
function renderHistVariants(list){
  const box = document.getElementById('histVariants');
  if(!box) return;
  const rows = (list || []).map(v=>
    '<div class="hv-row"><span class="nm">' + escapeHtml(v.name) + '</span>' +
    '<span class="ty">' + escapeHtml(v.type || '?') + '</span>' +
    '<span class="md">' + (v.modules || 0) + ' 模块</span>' +
    '<button class="btn" data-hvdel="' + escapeHtml(v.name) + '" style="padding:2px 8px">删除</button></div>'
  ).join('');
  box.innerHTML =
    '<div class="hv-bar"><button class="btn" id="histVarAdd">＋ 新增变体</button>' +
      '<span class="k">写文件后可用「🕘 备份」回滚</span></div>' +
    '<div id="histVarForm">' +
      '<div class="hv-grid"><input id="hvName" placeholder="变体名称，如 TestJet">' +
      '<input id="hvType" placeholder="底盘 type，如 fighter_equipment_0"></div>' +
      '<input id="hvIcon" placeholder="图标 GFX 名（可留空）">' +
      '<textarea id="hvMods" placeholder="每行一个模块：槽位 = 模块&#10;fixed_main_weapon_slot = fighter_weapon_1"></textarea>' +
      '<div class="hv-bar"><button class="btn primary" id="hvSave">写入</button>' +
        '<button class="btn" id="hvCancel">取消</button><span class="k" id="hvHint"></span></div>' +
    '</div>' +
    '<div class="hist-diff" style="margin:2px 0 8px">' + (rows || '<div class="k">这个国家还没有开局变体</div>') + '</div>';

  const form = document.getElementById('histVarForm');
  document.getElementById('histVarAdd').onclick = ()=>{
    form.classList.toggle('show');
    if(form.classList.contains('show')) document.getElementById('hvName').focus();
  };
  document.getElementById('hvCancel').onclick = ()=>form.classList.remove('show');
  document.getElementById('hvSave').onclick = ()=>saveVariantForm();
  box.querySelectorAll('[data-hvdel]').forEach(b=>{
    b.onclick = ()=>deleteVariant(b.dataset.hvdel);
  });
}

function parseModuleLines(raw){
  const out = {};
  (raw || '').split(/\\r?\\n/).forEach(line=>{
    const s = line.trim();
    if(!s) return;
    const m = s.split(/\\s*=\\s*/);
    if(m.length === 2 && m[0] && m[1]) out[m[0].trim()] = m[1].trim();
  });
  return out;
}

async function saveVariantForm(){
  const hint = document.getElementById('hvHint');
  const name = document.getElementById('hvName').value.trim();
  const type = document.getElementById('hvType').value.trim();
  const icon = document.getElementById('hvIcon').value.trim();
  const modules = parseModuleLines(document.getElementById('hvMods').value);
  if(!name || !type || !Object.keys(modules).length){
    hint.textContent = '名称、底盘、至少一个模块都要填';
    return;
  }
  hint.textContent = '写入中…';
  try{
    const r = await (await fetch('/api/country_variant', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: histTag, action: 'add', name, type, icon, modules})})).json();
    if(!r.ok){ hint.textContent = r.msg || '失败'; return; }
    renderHistVariants(r.variants || []);
    status(r.msg || '已新增变体');
  }catch(e){ hint.textContent = '失败：' + e.message; }
}

async function deleteVariant(name){
  if(!confirm('删除变体 ' + name + '？\\n会直接改文件，可用「🕘 备份」回滚。')) return;
  try{
    const r = await (await fetch('/api/country_variant', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: histTag, action: 'del', name})})).json();
    if(!r.ok){ status(r.msg || '删除失败', true); return; }
    renderHistVariants(r.variants || []);
    status(r.msg || '已删除变体');
  }catch(e){ status('删除失败：' + e.message, true); }
}

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    anchor_css = "  /* ---------- v0.67 脚本检查面板 ---------- */"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, CSS + anchor_css, 1)

    # 替换旧渲染函数
    start = h.index("function renderHistVariants(list){")
    end = h.index(chr(10) + "}" + chr(10), start) + 3
    old_fn = h[start:end]
    assert "hist-diff" in old_fn, old_fn[:200]
    h = h[:start] + JS + h[end:]

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.68 前端注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
