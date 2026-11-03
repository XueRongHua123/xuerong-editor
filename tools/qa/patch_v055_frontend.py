# -*- coding: utf-8 -*-
"""v0.55 前端：国家中心 + 项目体检（注入 focus_editor_index.html）。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.55 国家中心与项目体检 ---------- */"

CSS = """  /* ---------- v0.55 国家中心与项目体检 ---------- */
  #countryModal,#lintModal{position:fixed;inset:0;z-index:96;background:rgba(10,12,13,.8);display:none;align-items:center;justify-content:center}
  #countryModal.show,#lintModal.show{display:flex}
  .cm-card{width:min(1200px,calc(100% - 60px));height:min(790px,calc(100% - 56px));background:var(--panel);
    border:1px solid var(--line);border-radius:var(--r-lg);display:flex;flex-direction:column;overflow:hidden;box-shadow:var(--shadow)}
  .cm-head{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--line);flex:0 0 auto}
  .cm-head b{color:var(--accent);font-size:14px;letter-spacing:.4px;flex:0 0 auto}
  .cm-head input{flex:1;max-width:320px;margin:0!important}
  .cm-body{display:flex;flex:1;min-height:0}
  .cm-list{width:300px;border-right:1px solid var(--line);overflow:auto;padding:6px;flex:0 0 auto}
  .cm-row{padding:7px 9px;border-radius:8px;cursor:pointer;border-left:2px solid transparent;display:flex;gap:8px;align-items:center}
  .cm-row:hover{background:var(--panel2)}
  .cm-row.on{background:var(--panel2);border-left-color:var(--accent)}
  .cm-dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;border:1px solid var(--line2);background:var(--panel2)}
  .cm-row b{font-size:12.5px;color:var(--text);font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .cm-row .cm-meta{font-size:10px;color:var(--muted);margin-left:auto;flex:0 0 auto}
  .cm-detail{flex:1;overflow:auto;padding:14px 16px 24px}
  .cm-title{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}
  .cm-title .cm-swatch{width:26px;height:26px;border-radius:8px;border:1px solid var(--line);flex:0 0 auto}
  .cm-title h3{margin:0;font-size:17px;color:var(--text);font-weight:600}
  .cm-title code{font-size:11px;color:var(--muted);background:var(--input);border:1px solid var(--line);border-radius:5px;padding:1px 6px}
  .cm-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));gap:8px;margin-bottom:6px}
  .cm-cell{border:1px solid var(--line);background:var(--panel2);border-radius:8px;padding:7px 10px}
  .cm-cell i{display:block;font-size:10px;color:var(--muted);letter-spacing:.6px;font-style:normal;margin-bottom:2px}
  .cm-cell b{font-size:12.5px;color:var(--text);font-weight:500;word-break:break-all}
  .cm-sec{margin:16px 0 8px;font-size:11px;letter-spacing:1.2px;color:var(--muted);text-transform:uppercase;
    border-bottom:1px solid var(--line);padding-bottom:5px;display:flex;justify-content:space-between;align-items:center}
  .cm-sec span{text-transform:none;letter-spacing:0;font-size:10.5px}
  .cm-items{display:flex;flex-wrap:wrap;gap:6px}
  .cm-chip{font-size:11px;padding:3px 9px;border:1px solid var(--line);border-radius:20px;background:var(--panel2);
    color:var(--text);cursor:pointer;white-space:nowrap}
  .cm-chip:hover{border-color:var(--accent);color:var(--accent)}
  .cm-line{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:6px;font-size:12px;color:var(--text);cursor:pointer}
  .cm-line:hover{background:var(--panel2)}
  .cm-line .cm-sub{font-size:10.5px;color:var(--muted)}
  .cm-line .cm-act{margin-left:auto;font-size:11px;color:var(--accent);border:1px solid color-mix(in srgb,var(--accent) 45%,transparent);
    border-radius:6px;padding:1px 8px}
  .cm-issue{padding:6px 9px;border-radius:6px;font-size:12px;margin:5px 0;border-left:3px solid var(--line);color:var(--text)}
  .cm-issue.error{border-left-color:#d16a6a;background:color-mix(in srgb,#d16a6a 12%,transparent)}
  .cm-issue.warn{border-left-color:var(--accent);background:color-mix(in srgb,var(--accent) 12%,transparent)}
  .cm-issue.info{border-left-color:var(--line2);background:var(--panel2)}
  .cm-empty{padding:20px 8px;color:var(--muted);font-size:12px;text-align:center}
  #lintStats{display:flex;gap:14px;align-items:center;padding:8px 16px;border-bottom:1px solid var(--line);font-size:12px;color:var(--muted);flex:0 0 auto}
  #lintStats b{font-size:13px}
  #lintList{flex:1;overflow:auto;padding:10px 16px 20px}
  .lint-group{margin:14px 0 6px;font-size:11px;letter-spacing:1px;color:var(--muted);text-transform:uppercase}
  .lint-item{display:flex;gap:10px;align-items:flex-start;padding:7px 10px;border-radius:7px;cursor:pointer;
    border-left:3px solid var(--line);background:var(--panel2);margin:5px 0;font-size:12px;color:var(--text)}
  .lint-item:hover{border-left-color:var(--accent)}
  .lint-item .lv{font-size:10px;letter-spacing:.6px;padding:1px 6px;border-radius:4px;flex:0 0 auto;
    border:1px solid var(--line);color:var(--muted)}
  .lint-item.error .lv{border-color:#d16a6a;color:#d16a6a}
  .lint-item.warn .lv{border-color:var(--accent);color:var(--accent)}
  .lint-item .txt{flex:1;min-width:0}
  .lint-item .txt small{display:block;color:var(--muted);font-size:10.5px;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .lint-item .go{font-size:10.5px;color:var(--accent);flex:0 0 auto}
"""

DOM = """    <div id="countryModal">
      <div class="cm-card">
        <div class="cm-head">
          <b>国家中心</b>
          <input id="countrySearch" placeholder="搜索 tag / 名称…" autocomplete="off">
          <span id="countryCount" style="font-size:11px;color:var(--muted)"></span>
          <button class="btn" id="countryClose" style="margin-left:auto">关闭</button>
        </div>
        <div class="cm-body">
          <div id="countryList" class="cm-list"></div>
          <div id="countryBody" class="cm-detail"></div>
        </div>
      </div>
    </div>
    <div id="lintModal">
      <div class="cm-card" style="width:min(1000px,calc(100% - 60px));height:min(760px,calc(100% - 56px))">
        <div class="cm-head">
          <b>项目体检</b>
          <select id="lintFilter" class="btn" style="padding:3px 6px">
            <option value="all">全部问题</option>
            <option value="error">只看错误</option>
            <option value="warn">错误 + 警告</option>
          </select>
          <button class="btn" id="lintRun">重新检查</button>
          <button class="btn" id="lintSyntax" title="旧的语法检查：花括号、replace_path、事件 namespace">语法检查</button>
          <button class="btn" id="lintClose" style="margin-left:auto">关闭</button>
        </div>
        <div id="lintStats"></div>
        <div id="lintList"></div>
      </div>
    </div>
"""

JS = """/* ---------- v0.55 国家中心与项目体检 ---------- */
let COUNTRY_DATA = null, countrySel = null;

function rgbOf(c){
  if(!c || c.length < 3) return '';
  const f = v => Math.round(Math.max(0, Math.min(1, v)) * 255);
  return 'rgb(' + f(c[0]) + ',' + f(c[1]) + ',' + f(c[2]) + ')';
}

async function openCountry(tag){
  document.getElementById('countryModal').classList.add('show');
  if(!COUNTRY_DATA){
    status('正在读取国家数据…');
    try {
      COUNTRY_DATA = await (await fetch('/api/countries')).json();
    } catch(e){ status('国家数据读取失败：' + e.message, true); return; }
  }
  renderCountryList('');
  const list = COUNTRY_DATA.list || [];
  const pick = tag || (list.find(x=>x.trees.length) || list[0] || {}).tag;
  if(pick) selectCountry(pick);
  status('国家中心：' + list.length + ' 个 tag');
}

function closeCountry(){ document.getElementById('countryModal').classList.remove('show'); }

function renderCountryList(q){
  q = (q || '').toLowerCase();
  const box = document.getElementById('countryList');
  const list = (COUNTRY_DATA && COUNTRY_DATA.list) || [];
  const hits = list.filter(x=>!q || x.tag.toLowerCase().includes(q) || (x.name||'').toLowerCase().includes(q));
  document.getElementById('countryCount').textContent = hits.length + ' / ' + list.length;
  if(!hits.length){ box.innerHTML = '<div class="cm-empty">没有匹配的国家</div>'; return; }
  box.innerHTML = hits.map(x=>
    '<div class="cm-row' + (x.tag === countrySel ? ' on' : '') + '" data-tag="' + escapeHtml(x.tag) + '">' +
      '<span class="cm-dot" style="background:' + (rgbOf(x.color) || 'var(--panel2)') + '"></span>' +
      '<b>' + escapeHtml(x.name || x.tag) + '</b>' +
      '<span class="cm-meta">' + escapeHtml(x.tag) + ' · 树' + x.trees.length + ' 州' + x.owned +
        (x.issues ? ' ⚠' + x.issues : '') + '</span>' +
    '</div>').join('');
  box.querySelectorAll('.cm-row').forEach(el=>{
    el.onclick = ()=>selectCountry(el.dataset.tag);
  });
}

async function selectCountry(tag){
  if(!tag) return;
  countrySel = tag;
  renderCountryList(document.getElementById('countrySearch').value);
  const body = document.getElementById('countryBody');
  body.innerHTML = '<div class="cm-empty">读取中…</div>';
  let d;
  try { d = await (await fetch('/api/country?tag=' + encodeURIComponent(tag))).json(); }
  catch(e){ body.innerHTML = '<div class="cm-empty">读取失败：' + escapeHtml(e.message) + '</div>'; return; }
  if(!d.ok){ body.innerHTML = '<div class="cm-empty">' + escapeHtml(d.msg || '没有这个国家') + '</div>'; return; }
  renderCountryBody(d);
}

function renderCountryBody(d){
  const body = document.getElementById('countryBody');
  const cell = (k, v) => '<div class="cm-cell"><i>' + k + '</i><b>' + escapeHtml(v == null || v === '' ? '——' : String(v)) + '</b></div>';
  let html = '<div class="cm-title">' +
    '<span class="cm-swatch" style="background:' + (rgbOf(d.color) || 'var(--panel2)') + '"></span>' +
    '<h3>' + escapeHtml(d.name) + '</h3>' +
    '<code>' + escapeHtml(d.tag) + '</code>' +
    (d.adj ? '<span class="cm-sub" style="font-size:11px;color:var(--muted)">' + escapeHtml(d.adj) + '</span>' : '') +
    '</div>';

  html += '<div class="cm-grid">' +
    cell('首都', d.capital) +
    cell('执政党', d.ruling_party) +
    cell('政治点', d.political_power) +
    cell('稳定度修正', d.stability) +
    cell('战争支持修正', d.war_support) +
    cell('图形文化组', d.graphical_culture) +
    cell('国策树', d.trees.length) +
    cell('所属州', d.states.length) +
    cell('仅核心州', d.cores_only.length) +
    cell('开局精神', d.ideas.length) +
    cell('开局科技', d.techs.length) +
    '</div>';

  html += '<div class="cm-sec">文件<span>' + escapeHtml(d.source) + '</span></div>';
  html += '<div class="cm-line" data-open="' + escapeHtml(d.history_file) + '">' +
    '<span class="cm-sub">history</span><span>' + escapeHtml(d.history_file || '（没有 history/countries 文件）') + '</span></div>';
  html += '<div class="cm-line"><span class="cm-sub">定义</span><span>' +
    escapeHtml((d.def_found ? '' : '缺文件 · ') + (d.def_file || '未登记')) + '</span></div>';

  html += '<div class="cm-sec">国策树<span>' + d.trees.length + ' 棵</span></div>';
  if(!d.trees.length) html += '<div class="cm-empty">这个国家没有挂任何国策树</div>';
  d.trees.forEach(t=>{
    html += '<div class="cm-line" data-tree="' + escapeHtml(t.id) + '">' +
      '<b style="font-size:12px">' + escapeHtml(t.id) + '</b>' +
      '<span class="cm-sub">' + (t.exists ? t.focuses + ' 焦点' : '树不存在') + (t.default ? ' · default ' + escapeHtml(t.default) : '') + '</span>' +
      '<span class="cm-act">打开</span></div>';
  });

  html += '<div class="cm-sec">开局精神<span>点一个打开编辑器</span></div>';
  if(!d.ideas.length) html += '<div class="cm-empty">没有通过 add_ideas 添加精神</div>';
  else html += '<div class="cm-items">' + d.ideas.map(i=>
    '<span class="cm-chip" data-idea="' + escapeHtml(i) + '">' + escapeHtml(i) + '</span>').join('') + '</div>';

  html += '<div class="cm-sec">开局科技<span>' + d.techs.length + ' 项，显示前 40</span></div>';
  if(!d.techs.length) html += '<div class="cm-empty">没有 set_technology</div>';
  else html += '<div class="cm-items">' + d.techs.slice(0, 40).map(t=>
    '<span class="cm-chip" data-tech="' + escapeHtml(t) + '">' + escapeHtml(t) + '</span>').join('') +
    (d.techs.length > 40 ? '<span class="cm-chip" style="cursor:default;color:var(--muted)">…另 ' + (d.techs.length - 40) + ' 项</span>' : '') + '</div>';

  html += '<div class="cm-sec">所属州<span>' + d.states.length + ' 个</span></div>';
  if(!d.states.length) html += '<div class="cm-empty">没有任何州把 owner 设成它</div>';
  else html += d.states.slice(0, 60).map(s=>
    '<div class="cm-line"><b style="font-size:12px">' + s.id + '</b>' +
    '<span>' + escapeHtml(s.loc || s.name) + '</span>' +
    '<span class="cm-sub">人力 ' + escapeHtml(s.manpower || '-') + ' · ' + escapeHtml(s.category || '') + (s.core ? ' · 核心' : '') + '</span></div>'
  ).join('') + (d.states.length > 60 ? '<div class="cm-empty">…另有 ' + (d.states.length - 60) + ' 个州</div>' : '');

  html += '<div class="cm-sec">问题<span>' + d.issues.length + ' 条</span></div>';
  if(!d.issues.length) html = html.replace('<div class="cm-sec">问题<span>0 条</span></div>', '<div class="cm-sec">问题<span>0 条</span></div><div class="cm-empty">没有发现结构性问题</div>');
  d.issues.forEach(it=>{
    html += '<div class="cm-issue ' + it.level + '">' + escapeHtml(it.text) + '</div>';
  });

  body.innerHTML = html;
  body.querySelectorAll('[data-tree]').forEach(el=>{
    el.onclick = ()=>{ closeCountry(); openTreeById(el.dataset.tree); };
  });
  body.querySelectorAll('[data-idea]').forEach(el=>{
    el.onclick = ()=>{ closeCountry(); openIdeaById(el.dataset.idea); };
  });
  body.querySelectorAll('[data-tech]').forEach(el=>{
    el.onclick = ()=>{ closeCountry(); openTechById(el.dataset.tech); };
  });
}

function openTreeById(tid){
  const i = (DATA.trees || []).findIndex(t=>t.id === tid);
  if(i < 0){ status('找不到国策树：' + tid, true); return; }
  current = i; resetView(); renderAll();
  status('已切换国策树：' + tid);
}

function openIdeaById(iid){
  const obj = (DATA.ideas || []).find(x=>x.id === iid);
  if(!obj){ status('找不到国家精神：' + iid, true); return; }
  openIdea();
  selectIdea(obj);
}

function openTechById(tid){
  const obj = (DATA.techs || []).find(x=>x.id === tid);
  if(!obj){ status('找不到科技：' + tid, true); return; }
  openTech();
  selectTech(obj);
}

/* ---------- 项目体检 ---------- */
let LINT_DATA = null;

async function openLint(){
  document.getElementById('lintModal').classList.add('show');
  await runLint();
}
function closeLint(){ document.getElementById('lintModal').classList.remove('show'); }

async function runLint(){
  const box = document.getElementById('lintList');
  document.getElementById('lintStats').textContent = '检查中…';
  box.innerHTML = '<div class="cm-empty">正在扫描树 / 国家 / 州 / 精神 / 事件 / 本地化…</div>';
  try { LINT_DATA = await (await fetch('/api/lint')).json(); }
  catch(e){ box.innerHTML = '<div class="cm-empty">检查失败：' + escapeHtml(e.message) + '</div>'; return; }
  renderLint();
}

const LINT_KIND_NAMES = {tree:'国策树', country:'国家', state:'州', idea:'国家精神', event:'事件', loc:'本地化'};

function renderLint(){
  if(!LINT_DATA) return;
  const filter = document.getElementById('lintFilter').value;
  const st = LINT_DATA.stats || {};
  const sc = LINT_DATA.scope || {};
  document.getElementById('lintStats').innerHTML =
    '<b style="color:#d16a6a">错误 ' + (st.error || 0) + '</b>' +
    '<b style="color:var(--accent)">警告 ' + (st.warn || 0) + '</b>' +
    '<span>提示 ' + (st.info || 0) + '</span>' +
    '<span style="margin-left:auto">树 ' + (sc.trees||0) + ' · 国家 ' + (sc.countries||0) + ' · 州 ' + (sc.states||0) +
    ' · 精神 ' + (sc.ideas||0) + ' · 事件 ' + (sc.events||0) + ' · 科技 ' + (sc.techs||0) + '</span>';
  let items = LINT_DATA.items || [];
  if(filter === 'error') items = items.filter(x=>x.level === 'error');
  else if(filter === 'warn') items = items.filter(x=>x.level !== 'info');
  const box = document.getElementById('lintList');
  if(!items.length){ box.innerHTML = '<div class="cm-empty">没有符合条件的问题</div>'; return; }
  const groups = {};
  items.forEach(it=>{
    const key = it.level + '/' + it.kind;
    (groups[key] = groups[key] || []).push(it);
  });
  const order = ['error/tree','error/country','error/state','error/idea','error/event',
                 'warn/tree','warn/country','warn/state','warn/idea','warn/event','warn/loc','info/state'];
  const keys = Object.keys(groups).sort((a,b)=>{
    const ia = order.indexOf(a), ib = order.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  let html = '';
  keys.forEach(k=>{
    const [lv, kind] = k.split('/');
    html += '<div class="lint-group">' + (LV_NAME[lv] || lv) + ' · ' + (LINT_KIND_NAMES[kind] || kind) +
            ' · ' + groups[k].length + '</div>';
    groups[k].forEach((it, idx)=>{
      html += '<div class="lint-item ' + lv + '" data-k="' + k + '" data-i="' + idx + '">' +
        '<span class="lv">' + (LV_NAME[lv] || lv) + '</span>' +
        '<span class="txt">' + escapeHtml(it.title) +
          (it.detail ? '<small>' + escapeHtml(it.detail) + '</small>' : '') + '</span>' +
        (it.goto && it.goto.type ? '<span class="go">跳转 ›</span>' : '') + '</div>';
    });
  });
  box.innerHTML = html;
  box.querySelectorAll('.lint-item').forEach(el=>{
    const k = el.dataset.k, i = Number(el.dataset.i);
    const it = groups[k][i];
    if(it && it.goto && it.goto.type) el.onclick = ()=>lintGoto(it.goto);
    else el.style.cursor = 'default';
  });
}

const LV_NAME = {error:'错误', warn:'警告', info:'提示'};

function lintGoto(g){
  if(!g) return;
  if(g.type === 'tree'){ closeLint(); openTreeById(g.id); return; }
  if(g.type === 'country'){ closeLint(); openCountry(g.id); return; }
  if(g.type === 'idea'){ closeLint(); openIdeaById(g.id); return; }
  if(g.type === 'tech'){ closeLint(); openTechById(g.id); return; }
  if(g.type === 'event'){ closeLint(); openEvents(); const s = document.getElementById('eventSearch');
    if(s){ s.value = g.id; renderEventList(g.id); } return; }
  if(g.type === 'loc'){ navigator.clipboard && navigator.clipboard.writeText(g.id); status('已复制本地化键：' + g.id); return; }
  if(g.type === 'state'){ status('州 ' + g.id + '：州编辑器还没做，可以先去国家中心看它属于谁'); return; }
}
"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    # CSS
    anchor_css = "  .btn{white-space:nowrap}\n"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, anchor_css + CSS, 1)

    # DOM：放在卸载弹窗之前
    anchor_dom = '    <div id="unloadModal">'
    assert h.count(anchor_dom) == 1
    h = h.replace(anchor_dom, DOM + anchor_dom, 1)

    # 侧栏入口
    anchor_side = '    <details>\n      <summary>装备</summary>'
    assert h.count(anchor_side) == 1
    side = '''    <details open>
      <summary>国家与州</summary>
      <div id="countryEntry" class="tabbtn">🌍 国家中心</div>
      <div id="lintEntry" class="tabbtn">🩺 项目体检</div>
    </details>
'''
    h = h.replace(anchor_side, side + anchor_side, 1)

    # JS：插在 initMascot 之前
    anchor_js = "function initMascot(){"
    assert h.count(anchor_js) == 1
    h = h.replace(anchor_js, JS + "\n" + anchor_js, 1)

    # 绑定
    bind = """document.getElementById('countryEntry').onclick = ()=>openCountry();
document.getElementById('lintEntry').onclick = openLint;
document.getElementById('countryClose').onclick = closeCountry;
document.getElementById('countrySearch').addEventListener('input', e=>renderCountryList(e.target.value.trim().toLowerCase()));
document.getElementById('countryModal').addEventListener('click', e=>{ if(e.target.id === 'countryModal') closeCountry(); });
document.getElementById('lintClose').onclick = closeLint;
document.getElementById('lintFilter').addEventListener('change', renderLint);
document.getElementById('lintRun').onclick = runLint;
document.getElementById('lintSyntax').onclick = ()=>openReport();
document.getElementById('lintModal').addEventListener('click', e=>{ if(e.target.id === 'lintModal') closeLint(); });
"""
    anchor_bind = "document.getElementById('cmdBtn').onclick = openCmd;"
    assert h.count(anchor_bind) == 1
    h = h.replace(anchor_bind, bind + anchor_bind, 1)

    # 工具栏「校验」改成体检（旧的语法检查在体检面板里）
    old_btn = "document.getElementById('reportBtn').onclick = openReport;"
    new_btn = "document.getElementById('reportBtn').onclick = ()=>openLint();"
    assert h.count(old_btn) == 1, 'reportBtn 绑定结构不符'
    h = h.replace(old_btn, new_btn, 1)
    h = h.replace('id="reportBtn">🧪 校验</button>', 'id="reportBtn">🩺 体检</button>')

    # 命令面板加两条
    old_cmd = "    {cat:'操作', label:'校验：本地化 / 前置 / 事件', run:()=>openReport()},"
    new_cmd = ("    {cat:'操作', label:'项目体检（跨系统引用检查）', hint:'', run:()=>openLint()},\n"
               "    {cat:'操作', label:'国家中心', run:()=>openCountry()},\n"
               "    {cat:'操作', label:'语法检查（花括号 / replace_path / namespace）', run:()=>openReport()},")
    assert h.count(old_cmd) == 1
    h = h.replace(old_cmd, new_cmd, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('前端注入完成：', P)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
