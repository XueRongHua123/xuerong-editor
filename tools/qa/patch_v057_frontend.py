# -*- coding: utf-8 -*-
"""v0.57 前端：州 / 地块面板。幂等注入。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.57 州 / 地块 ---------- */"

CSS = """  /* ---------- v0.57 州 / 地块 ---------- */
  #stateModal{position:fixed;inset:0;z-index:96;background:rgba(10,12,13,.8);display:none;align-items:center;justify-content:center}
  #stateModal.show{display:flex}
  .st-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px 10px;margin:8px 0 4px}
  .st-grid label{display:flex;flex-direction:column;gap:3px;font-size:11px;color:var(--muted)}
  .st-bld{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px 10px;margin:6px 0 4px}
  .st-bld label{display:flex;align-items:center;gap:6px;font-size:11.5px;color:var(--muted)}
  .st-bld input{width:64px}
  .st-prov{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0 8px}
  .st-prov span{font-size:10.5px;padding:2px 6px;border:1px solid var(--line);border-radius:5px;color:var(--muted);background:var(--panel2)}
  .st-vp{font-size:11.5px;color:var(--text);margin:2px 0}
"""

DOM = """    <div id="stateModal">
      <div class="cm-card">
        <div class="cm-head">
          <b>州 / 地块</b>
          <input id="stateSearch" placeholder="搜索 id / 名称 / owner…" autocomplete="off">
          <span id="stateCount" style="font-size:11px;color:var(--muted)"></span>
          <button class="btn" id="stateClose" style="margin-left:auto">关闭</button>
        </div>
        <div class="cm-body">
          <div id="stateList" class="cm-list"></div>
          <div id="stateBody" class="cm-detail"></div>
        </div>
      </div>
    </div>
"""

JS = """/* ---------- v0.57 州 / 地块 ---------- */
let STATE_DATA = null, stateSel = null;

async function openStates(id){
  document.getElementById('stateModal').classList.add('show');
  if(!STATE_DATA){
    status('正在读取州数据…');
    try { STATE_DATA = await (await fetch('/api/states')).json(); }
    catch(e){ status('州数据读取失败：' + e.message, true); return; }
  } else {
    try { STATE_DATA = await (await fetch('/api/states')).json(); } catch(e){}
  }
  renderStateList(document.getElementById('stateSearch').value || '');
  const list = (STATE_DATA && STATE_DATA.list) || [];
  if(!list.length){
    document.getElementById('stateBody').innerHTML = '<div class="cm-empty">还没有读取到任何州。<br>先加载一个 mod。</div>';
    document.getElementById('stateCount').textContent = '0';
    return;
  }
  const want = id || stateSel;
  const pick = (want && list.some(x=>String(x.id) === String(want))) ? Number(want) : list[0].id;
  await selectState(pick);
  status('州：' + list.length + ' 个');
}

function closeStates(){ document.getElementById('stateModal').classList.remove('show'); }

function renderStateList(q){
  q = (q || '').toLowerCase();
  const box = document.getElementById('stateList');
  const list = (STATE_DATA && STATE_DATA.list) || [];
  const hits = list.filter(x=>!q ||
    String(x.id).includes(q) || (x.name||'').toLowerCase().includes(q) || (x.owner||'').toLowerCase().includes(q));
  document.getElementById('stateCount').textContent = hits.length + ' / ' + list.length;
  const shown = hits.slice(0, 400);
  box.innerHTML = shown.map(x=>
    '<div class="cm-row' + (String(x.id) === String(stateSel) ? ' on' : '') + '" data-sid="' + x.id + '">' +
      '<b>' + x.id + ' ' + escapeHtml(x.name || x.raw_name || '') + '</b>' +
      '<span class="cm-meta">' + escapeHtml(x.owner || '—') + ' · 人' + (x.manpower || '0') + '</span>' +
    '</div>').join('') + (hits.length > shown.length ?
      '<div class="cm-empty">…另有 ' + (hits.length - shown.length) + ' 个，输入关键词缩小范围</div>' : '');
  box.querySelectorAll('[data-sid]').forEach(el=>{
    el.onclick = ()=>selectState(Number(el.dataset.sid));
  });
}

async function selectState(id){
  stateSel = id;
  renderStateList(document.getElementById('stateSearch').value || '');
  const body = document.getElementById('stateBody');
  body.innerHTML = '<div class="cm-empty">读取中…</div>';
  let d;
  try { d = await (await fetch('/api/state?id=' + encodeURIComponent(id))).json(); }
  catch(e){ body.innerHTML = '<div class="cm-empty">读取失败：' + escapeHtml(e.message) + '</div>'; return; }
  if(!d.ok){ body.innerHTML = '<div class="cm-empty">' + escapeHtml(d.msg || '没有这个州') + '</div>'; return; }
  renderStateBody(d);
}

function renderStateBody(d){
  const body = document.getElementById('stateBody');
  const cell = (k, v) => '<div class="cm-cell"><i>' + k + '</i><b>' +
    escapeHtml(v == null || v === '' ? '——' : String(v)) + '</b></div>';
  const ownerOpts = ['<option value="">（不改）</option>'].concat(
    d.owners.map(t=>'<option value="' + t + '">' + t + (LOC_NAME(t) ? ' · ' + escapeHtml(LOC_NAME(t)) : '') + '</option>')).join('');

  let html = '<div class="cm-title"><h3>' + d.id + ' ' + escapeHtml(d.name || d.raw_name || '') + '</h3>' +
    '<code>' + escapeHtml(d.file || '') + '</code>' +
    (d.writable ? '' : '<span class="cm-sub" style="font-size:11px;color:var(--warn)">只读来源</span>') + '</div>';

  html += '<div class="cm-grid">' +
    cell('所属国家', (d.owner || '') + (d.owner_name ? ' · ' + d.owner_name : '')) +
    cell('核心数', d.cores.length) +
    cell('人力', d.manpower) +
    cell('州类别', d.category) +
    cell('省份数', d.province_count) +
    cell('胜利点', d.victory_points.length) +
    cell('建筑合计', Object.values(d.buildings).reduce((a, b)=>a + b, 0)) +
    cell('历史日期', d.history_date) +
    '</div>';

  html += '<div class="cm-sec">编辑<span>只改填写的字段，注释与省份子块原样保留</span></div>' +
    '<div class="st-grid">' +
      '<label>owner<select id="stOwner">' + ownerOpts + '</select></label>' +
      '<label>人力<input type="number" id="stManpower" value="' + escapeHtml(d.manpower || '') + '"></label>' +
      '<label>州类别<select id="stCategory"><option value="">（不改）</option>' +
        d.categories.map(c=>'<option value="' + c + '">' + c + '</option>').join('') + '</select></label>' +
      '<label>核心（逗号或换行分隔）<textarea id="stCores" style="height:56px">' +
        escapeHtml(d.cores.join(', ')) + '</textarea></label>' +
    '</div>' +
    '<div class="k">建筑（留空或 0 = 改成 0；不填的项目保持不变）</div>' +
    '<div class="st-bld">' + d.building_keys.map(k=>
      '<label>' + k + '<input type="number" min="0" data-b="' + k + '" value="' +
      (d.buildings[k] != null ? d.buildings[k] : '') + '" placeholder="—"></label>').join('') + '</div>' +
    '<div style="display:flex;gap:8px;margin:8px 0 6px"><button class="btn primary" id="stSave">写入州文件</button>' +
      '<button class="btn" id="stReload">重新读取</button></div>' +
    '<div id="stDiff" class="hist-diff" style="display:none"></div>';

  if(d.provinces.length){
    html += '<div class="cm-sec">省份<span>' + d.province_count + ' 个</span></div>' +
      '<div class="st-prov">' + d.provinces.map(p=>'<span>' + p + '</span>').join('') +
      (d.province_count > d.provinces.length ? '<span>…</span>' : '') + '</div>';
  }
  if(d.victory_points.length){
    html += '<div class="cm-sec">胜利点<span>' + d.victory_points.length + ' 处</span></div>' +
      d.victory_points.map(vp=>'<div class="st-vp">省份 ' + vp[0] + ' → ' + vp[1] + ' 点</div>').join('');
  }
  const pbs = Object.entries(d.province_buildings || {});
  if(pbs.length){
    html += '<div class="cm-sec">省份建筑<span>只读</span></div>' +
      pbs.map(([pid, b])=>'<div class="st-vp">省 ' + escapeHtml(pid) + '：' +
        Object.entries(b).map(([k, v])=>k + ' ' + v).join('，') + '</div>').join('');
  }

  body.innerHTML = html;
  document.getElementById('stOwner').value = d.owner || '';
  document.getElementById('stCategory').value = d.category || '';
  document.getElementById('stSave').onclick = ()=>saveState(d);
  document.getElementById('stReload').onclick = ()=>selectState(d.id);
}

function LOC_NAME(tag){
  const c = ((COUNTRY_DATA && COUNTRY_DATA.list) || []).find(x=>x.tag === tag);
  return c ? c.name : '';
}

async function saveState(d){
  const coresRaw = document.getElementById('stCores').value;
  const cores = coresRaw.split(/[,，\\s]+/).map(s=>s.trim()).filter(Boolean);
  const buildings = {};
  document.querySelectorAll('#stateBody [data-b]').forEach(inp=>{
    const v = inp.value.trim();
    if(v !== '') buildings[inp.dataset.b] = Number(v);
  });
  const fields = {
    owner: document.getElementById('stOwner').value,
    cores: cores,
    manpower: document.getElementById('stManpower').value.trim(),
    category: document.getElementById('stCategory').value,
    buildings: buildings
  };
  if(!confirm('写入州 ' + d.id + ' 的文件？\\n会先自动备份，只改你填写的字段。')) return;
  let r;
  try {
    r = await (await fetch('/api/state_save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: d.id, fields})})).json();
  } catch(e){ status('保存失败：' + e.message, true); return; }
  status(r.msg || '', !r.ok);
  if(!r.ok) return;
  const box = document.getElementById('stDiff');
  const rows = (r.diff || []).map(x=>'<div class="row"><i>' + escapeHtml(x.label) + '</i>' +
    '<span class="old">' + escapeHtml(x.old || '（空）') + '</span><span>→</span>' +
    '<span class="new">' + escapeHtml(x.new || '（空）') + '</span></div>').join('');
  await loadData();
  STATE_DATA = null;
  await openStates(d.id);
  const box2 = document.getElementById('stDiff');
  if(box2){ box2.style.display = rows ? '' : 'none'; box2.innerHTML = rows; }
}

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    anchor_css = "  /* ---------- v0.56 国家历史编辑 ---------- */"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, CSS + anchor_css, 1)

    anchor_dom = '    <div id="historyModal">'
    assert h.count(anchor_dom) == 1
    h = h.replace(anchor_dom, DOM + anchor_dom, 1)

    anchor_js = "\n/* ---------- v0.56 国家历史编辑 ---------- */"
    assert h.count(anchor_js) == 1
    h = h.replace(anchor_js, JS + anchor_js, 1)

    # 侧栏入口
    old_side = '      <div id="lintEntry" class="tabbtn">🩺 项目体检</div>'
    new_side = old_side + '\n      <div id="stateEntry" class="tabbtn">🗺 州 / 地块</div>'
    assert h.count(old_side) == 1
    h = h.replace(old_side, new_side, 1)

    # 绑定
    anchor_b = "document.getElementById('countryEntry').onclick = ()=>openCountry();"
    bind = ("document.getElementById('stateEntry').onclick = ()=>openStates();\n"
            "document.getElementById('stateClose').onclick = closeStates;\n"
            "document.getElementById('stateSearch').addEventListener('input', e=>renderStateList(e.target.value.trim().toLowerCase()));\n"
            "document.getElementById('stateModal').addEventListener('click', e=>{ if(e.target.id === 'stateModal') closeStates(); });\n")
    assert h.count(anchor_b) == 1
    h = h.replace(anchor_b, bind + anchor_b, 1)

    # 体检 state 跳转
    old_goto = """  if(g.type === 'state'){ status('州 ' + g.id + '：州编辑器还没做，可以先去国家中心看它属于谁'); return; }"""
    new_goto = """  if(g.type === 'state'){ closeLint(); openStates(g.id); return; }"""
    assert h.count(old_goto) == 1
    h = h.replace(old_goto, new_goto, 1)

    # 国家中心里的州列表可点
    old_state_row = """  else html += d.states.slice(0, 60).map(s=>
    '<div class="cm-line"><b style="font-size:12px">' + s.id + '</b>' +"""
    new_state_row = """  else html += d.states.slice(0, 60).map(s=>
    '<div class="cm-line" data-state="' + s.id + '"><b style="font-size:12px">' + s.id + '</b>' +"""
    assert h.count(old_state_row) == 1
    h = h.replace(old_state_row, new_state_row, 1)

    old_bind2 = """  body.querySelectorAll('[data-hist]').forEach(el=>{"""
    new_bind2 = """  body.querySelectorAll('[data-state]').forEach(el=>{
    el.onclick = ()=>{ closeCountry(); openStates(el.dataset.state); };
  });
  body.querySelectorAll('[data-hist]').forEach(el=>{"""
    assert h.count(old_bind2) == 1
    h = h.replace(old_bind2, new_bind2, 1)

    # 命令面板加一条
    old_cmd = "    {cat:'操作', label:'国家中心', run:()=>openCountry()},"
    new_cmd = old_cmd + "\n    {cat:'操作', label:'州 / 地块', run:()=>openStates()},"
    assert h.count(old_cmd) == 1
    h = h.replace(old_cmd, new_cmd, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('前端 v0.57 注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
