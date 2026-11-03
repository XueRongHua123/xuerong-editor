# -*- coding: utf-8 -*-
"""v0.67 前端：脚本检查面板（定义清单 + 引用计数）。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.67 脚本检查面板 ---------- */"

CSS = """  /* ---------- v0.67 脚本检查面板 ---------- */
  #scriptModal{position:fixed;inset:0;z-index:96;display:none;place-items:center;
    background:rgba(8,10,9,.62);backdrop-filter:blur(3px)}
  #scriptModal.show{display:grid}
  #scriptToolbar{display:flex;gap:8px;align-items:center;padding:0 18px 8px;flex-wrap:wrap}
  #scriptToolbar input{flex:1;min-width:180px;height:30px}
  #scriptToolbar select{height:30px}
  #scriptBody{overflow:auto;padding:0 18px 16px;font-size:12px}
  .sc-row{display:grid;grid-template-columns:1fr 68px 150px 56px;gap:8px;align-items:center;
    padding:5px 8px;border-bottom:1px solid var(--line)}
  .sc-row:hover{background:var(--panel2)}
  .sc-row.head{color:var(--muted);font-size:11px;border-bottom:1px solid var(--line2);position:sticky;top:0;
    background:var(--panel);z-index:2}
  .sc-name{color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sc-kind{font-size:10.5px;color:var(--muted)}
  .sc-file{color:var(--muted);font-size:10.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sc-refs{text-align:right;font-variant-numeric:tabular-nums}
  .sc-row.unused .sc-refs{color:var(--warn);font-weight:600}
  .sc-row.empty .sc-refs{color:var(--muted)}
"""

DOM = """    <div id="scriptModal">
      <div class="cm-card" style="width:min(1000px,calc(100% - 60px));height:min(760px,calc(100% - 56px));display:flex;flex-direction:column">
        <div class="cm-head">
          <b>脚本检查 · scripted trigger / effect</b>
          <span class="k" id="scriptMeta" style="margin-right:auto"></span>
          <button class="btn" id="scriptReload">重新扫描</button>
          <button class="btn" id="scriptClose">关闭</button>
        </div>
        <div id="scriptToolbar">
          <input id="scriptSearch" placeholder="搜索名称（支持中文）…">
          <select id="scriptKind" class="btn">
            <option value="">全部类型</option>
            <option value="trigger">trigger</option>
            <option value="effect">effect</option>
          </select>
          <select id="scriptSort" class="btn">
            <option value="refs">引用少 → 多</option>
            <option value="name">名称 A→Z</option>
            <option value="file">按文件</option>
          </select>
        </div>
        <div id="scriptBody"></div>
      </div>
    </div>
"""

JS = """/* ---------- v0.67 脚本检查面板 ---------- */
let SCRIPT_DATA = null;

async function openScriptCheck(force){
  document.getElementById('scriptModal').classList.add('show');
  if(SCRIPT_DATA && !force){ renderScriptList(); return; }
  const body = document.getElementById('scriptBody');
  body.innerHTML = '<div class="cm-empty">扫描中…（大 mod 首次约 1 秒到几秒）</div>';
  document.getElementById('scriptMeta').textContent = '';
  try{
    const d = await (await fetch('/api/scripted')).json();
    SCRIPT_DATA = d;
    document.getElementById('scriptMeta').textContent =
      (d.total || 0) + ' 个定义 · ' + (d.unused || 0) + ' 个只出现一次（疑似未使用）';
    renderScriptList();
  }catch(e){
    body.innerHTML = '<div class="cm-empty">扫描失败：' + escapeHtml(e.message) + '</div>';
  }
}

function renderScriptList(){
  const body = document.getElementById('scriptBody');
  if(!SCRIPT_DATA){ return; }
  const q = (document.getElementById('scriptSearch').value || '').trim().toLowerCase();
  const kind = document.getElementById('scriptKind').value;
  const sort = document.getElementById('scriptSort').value;
  let items = (SCRIPT_DATA.items || []).slice();
  if(kind) items = items.filter(x=>x.kind === kind);
  if(q) items = items.filter(x=>x.name.toLowerCase().includes(q) || (x.file||'').toLowerCase().includes(q));
  if(sort === 'name') items.sort((a,b)=>a.name.localeCompare(b.name));
  else if(sort === 'file') items.sort((a,b)=>(a.file||'').localeCompare(b.file||'') || a.name.localeCompare(b.name));
  else items.sort((a,b)=>a.refs - b.refs || a.name.localeCompare(b.name));
  const head = '<div class="sc-row head"><span>名称</span><span>类型</span><span>文件</span><span class="sc-refs">引用</span></div>';
  const rows = items.slice(0, 800).map(it=>
    '<div class="sc-row' + (it.refs <= 1 ? ' unused' : '') + (it.empty ? ' empty' : '') + '">' +
      '<span class="sc-name" title="' + escapeHtml(it.name) + '">' + escapeHtml(it.name) +
        (it.empty ? ' <span class="k">（空块）</span>' : '') + '</span>' +
      '<span class="sc-kind">' + escapeHtml(it.kind) + '</span>' +
      '<span class="sc-file" title="' + escapeHtml(it.file || '') + '">' + escapeHtml(it.file || '') + '</span>' +
      '<span class="sc-refs">' + (it.refs || 0) + '</span>' +
    '</div>').join('');
  body.innerHTML = head + (rows || '<div class="cm-empty">没有匹配项</div>') +
    (items.length > 800 ? '<div class="k" style="padding:8px">只显示前 800 条，用搜索缩小范围</div>' : '');
}

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    anchor_css = "  /* ---------- v0.63 缩放适配与面板定位 ---------- */"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, CSS + anchor_css, 1)

    anchor_dom = '''    <div id="unloadModal">'''
    assert h.count(anchor_dom) == 1
    h = h.replace(anchor_dom, DOM + anchor_dom, 1)

    # 侧栏入口
    anchor_entry = '''      <div id="lintEntry" class="tabbtn">🩺 项目体检</div>'''
    assert h.count(anchor_entry) == 1
    h = h.replace(anchor_entry, anchor_entry + '\n      <div id="scriptEntry" class="tabbtn">🔍 脚本检查</div>', 1)

    anchor_js = "/* ---------- v0.63 缩放适配与面板定位 ---------- */"
    pos = h.rindex(anchor_js)
    h = h[:pos] + JS + h[pos:]

    anchor_bind = "document.getElementById('lintEntry').onclick"
    idx = h.index(anchor_bind)
    line_end = h.index("\n", idx) + 1
    bind = ("document.getElementById('scriptEntry').onclick = ()=>openScriptCheck(true);\n"
            "document.getElementById('scriptClose').onclick = ()=>{ document.getElementById('scriptModal').classList.remove('show'); };\n"
            "document.getElementById('scriptReload').onclick = ()=>openScriptCheck(true);\n"
            "document.getElementById('scriptSearch').addEventListener('input', renderScriptList);\n"
            "document.getElementById('scriptKind').addEventListener('change', renderScriptList);\n"
            "document.getElementById('scriptSort').addEventListener('change', renderScriptList);\n")
    h = h[:line_end] + bind + h[line_end:]

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.67 前端注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
