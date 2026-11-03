# -*- coding: utf-8 -*-
"""v0.56 前端：国家历史编辑面板。幂等注入。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.56 国家历史编辑 ---------- */"

CSS = """  /* ---------- v0.56 国家历史编辑 ---------- */
  #historyModal{position:fixed;inset:0;z-index:97;background:rgba(10,12,13,.8);display:none;align-items:center;justify-content:center}
  #historyModal.show{display:flex}
  .hist-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px 10px;margin:6px 0 4px}
  .hist-grid label{display:flex;flex-direction:column;gap:3px;font-size:11px;color:var(--muted)}
  .hist-diff{margin-top:10px;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  .hist-diff .row{display:flex;gap:8px;padding:6px 10px;font-size:12px;border-bottom:1px solid var(--line);color:var(--text)}
  .hist-diff .row:last-child{border-bottom:0}
  .hist-diff .row i{font-style:normal;color:var(--muted);min-width:88px}
  .hist-diff .row .old{color:var(--muted);text-decoration:line-through}
  .hist-diff .row .new{color:var(--accent)}
  .hist-warn{color:var(--warn);font-size:11.5px;margin-top:6px;line-height:1.5}
"""

DOM = """    <div id="historyModal">
      <div class="diff-card" style="width:min(780px,calc(100% - 70px))">
        <div class="diff-head"><b>编辑国家历史 <span id="histTag" style="color:var(--accent)"></span></b>
          <button class="btn" id="histClose">关闭</button></div>
        <div class="diff-body" style="font-family:inherit;white-space:normal;font-size:12.5px">
          <div id="histFile" class="k" style="margin-top:0"></div>
          <div class="hist-grid">
            <label>首都（州 id）<input type="number" id="histCapital" placeholder="留空不改"></label>
            <label>执政党<select id="histParty">
              <option value="">（不改）</option>
              <option value="democratic">democratic</option>
              <option value="fascism">fascism</option>
              <option value="communism">communism</option>
              <option value="neutrality">neutrality</option>
            </select></label>
            <label>政治点<input type="number" id="histPP" placeholder="留空不改"></label>
            <label>稳定度修正<input type="number" step="0.01" id="histStab" placeholder="如 0.05"></label>
            <label>战争支持修正<input type="number" step="0.01" id="histWS" placeholder="如 0.1"></label>
            <label>国策树<select id="histTree"></select></label>
          </div>
          <div class="k">开局精神（每行一个 idea id；清空 = 不写这一项）</div>
          <textarea id="histIdeas" style="height:88px" placeholder="mvlv_unf&#10;tsf_production"></textarea>
          <div id="histWarn" class="hist-warn"></div>
          <div style="display:flex;gap:8px;margin-top:10px;align-items:center">
            <button class="btn primary" id="histSave">写入文件</button>
            <button class="btn" id="histReload">重新读取</button>
            <span class="k" style="margin:0">只改上面填写的字段，注释、条件块和其它键原样保留</span>
          </div>
          <div id="histDiff"></div>
        </div>
      </div>
    </div>
"""

JS = """/* ---------- v0.56 国家历史编辑 ---------- */
let histTag = null;

async function openHistoryEditor(tag){
  histTag = tag;
  document.getElementById('histTag').textContent = tag;
  document.getElementById('historyModal').classList.add('show');
  await loadHistoryIntoForm();
}

async function loadHistoryIntoForm(){
  const tag = histTag;
  const fileEl = document.getElementById('histFile');
  const diffEl = document.getElementById('histDiff');
  diffEl.innerHTML = '';
  document.getElementById('histWarn').textContent = '';
  fileEl.textContent = '读取中…';
  let d;
  try { d = await (await fetch('/api/country_history?tag=' + encodeURIComponent(tag))).json(); }
  catch(e){ fileEl.textContent = '读取失败：' + e.message; return; }
  if(!d.ok){ fileEl.textContent = d.msg || '读取失败'; return; }
  fileEl.textContent = (d.exists ? '' : '（还没有 history 文件，保存时会新建）') +
    (d.file || '') + (d.writable ? '' : ' · 只读来源，不能保存');
  const f = d.fields || {};
  document.getElementById('histCapital').value = f.capital || '';
  document.getElementById('histParty').value = f.ruling_party || '';
  document.getElementById('histPP').value = f.political_power || '';
  document.getElementById('histStab').value = f.stability || '';
  document.getElementById('histWS').value = f.war_support || '';
  document.getElementById('histIdeas').value = (f.ideas || []).join('\\n');
  const sel = document.getElementById('histTree');
  sel.innerHTML = '<option value="">（不挂/不改）</option>' +
    ((DATA && DATA.trees) || []).map(t=>
      '<option value="' + escapeHtml(t.id) + '">' + escapeHtml(t.id) + '（' + (t.focuses || []).length + ' 焦点）</option>'
    ).join('');
  sel.value = f.focus_tree || '';
  document.getElementById('histSave').disabled = !d.writable;
}

async function saveHistory(){
  if(!histTag) return;
  const ideasRaw = document.getElementById('histIdeas').value;
  const fields = {
    capital: document.getElementById('histCapital').value.trim(),
    ruling_party: document.getElementById('histParty').value,
    political_power: document.getElementById('histPP').value.trim(),
    stability: document.getElementById('histStab').value.trim(),
    war_support: document.getElementById('histWS').value.trim(),
    focus_tree: document.getElementById('histTree').value,
    ideas: ideasRaw.split(/\\r?\\n/).map(s=>s.trim()).filter(Boolean)
  };
  if(!fields.capital && !fields.ruling_party && !fields.political_power && !fields.stability &&
     !fields.war_support && !fields.focus_tree && !fields.ideas.length){
    status('没有填写任何字段', true); return;
  }
  if(!confirm('把修改写入 ' + histTag + ' 的历史文件？\\n会先自动备份（.bak 与历史记录），只改你填写的字段。')) return;
  let r;
  try {
    r = await (await fetch('/api/country_save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: histTag, fields})})).json();
  } catch(e){ status('保存失败：' + e.message, true); return; }
  status(r.msg || '', !r.ok);
  if(!r.ok) return;
  const diffEl = document.getElementById('histDiff');
  const rows = (r.diff || []).map(x=>
    '<div class="row"><i>' + escapeHtml(x.label) + '</i><span class="old">' +
    escapeHtml(x.old || '（空）') + '</span><span>→</span><span class="new">' +
    escapeHtml(x.new || '（空）') + '</span></div>').join('');
  diffEl.innerHTML = rows ? '<div class="hist-diff">' + rows + '</div>' : '';
  document.getElementById('histWarn').textContent = (r.warnings || []).join('；');
  await loadData();
  await loadHistoryIntoForm();
  if(document.getElementById('countryModal').classList.contains('show')) await selectCountry(histTag);
}

function closeHistoryEditor(){ document.getElementById('historyModal').classList.remove('show'); }

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    anchor_css = "  #status{background:color-mix(in srgb,var(--panel) 94%,transparent)!important;color:var(--text)!important;"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, CSS + anchor_css, 1)

    anchor_dom = '    <div id="countryModal">'
    assert h.count(anchor_dom) == 1
    h = h.replace(anchor_dom, DOM + anchor_dom, 1)

    anchor_js = "/* ---------- 项目体检 ---------- */"
    assert h.count(anchor_js) == 1
    h = h.replace(anchor_js, JS + anchor_js, 1)

    # 详情里加按钮
    old_btn = """    cell('开局科技', d.techs.length) +
    '</div>';"""
    new_btn = """    cell('开局科技', d.techs.length) +
    '</div>' +
    '<div style="margin:-2px 0 12px"><button class="btn primary" data-hist="1">✏️ 编辑历史</button> ' +
    '<span class="k" style="margin:0">改首都 / 执政党 / 政治点 / 开局精神 / 国策树</span></div>';"""
    assert h.count(old_btn) == 1, '详情结构不符'
    h = h.replace(old_btn, new_btn, 1)

    old_bind = "  body.querySelectorAll('[data-tree]').forEach(el=>{"
    new_bind = """  body.querySelectorAll('[data-hist]').forEach(el=>{
    el.onclick = ()=>openHistoryEditor(d.tag);
  });
  body.querySelectorAll('[data-tree]').forEach(el=>{"""
    assert h.count(old_bind) == 1
    h = h.replace(old_bind, new_bind, 1)

    # 绑定面板按钮
    anchor_b = "document.getElementById('countryClose').onclick = closeCountry;"
    bind = """document.getElementById('histClose').onclick = closeHistoryEditor;
document.getElementById('histReload').onclick = loadHistoryIntoForm;
document.getElementById('histSave').onclick = saveHistory;
document.getElementById('historyModal').addEventListener('click', e=>{ if(e.target.id === 'historyModal') closeHistoryEditor(); });
""" + anchor_b
    assert h.count(anchor_b) == 1
    h = h.replace(anchor_b, bind, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('前端注入完成：', P)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
