// 10-focus：国策树画布（P4）
// renderTree / showPanel / saveNode / 连线 / 拖动 / 多选批量 / 缩放 / 国家精神列表。
// 和 20-panels 双向调用：renderTree 里点节点开面板，面板改完字段回调保存再重画。
// 全部是顶层 function 声明——HTML 里 379 个内联 onclick 按名字调，名字一个都不能改。

function nodeById(t,id){ return t.focuses.find(f=>f.id===id); }

function curTree(){ return DATA.trees[current]; }

function rootOf(t){
  // 树的真实所在层（后端按 _layer_dirs 的 base 记；创意工坊/原版层会自动被接管到最顶层可写 mod）
  if(t && t.root) return t.root;
  return (DATA.roots.find(r=>t.source===r.name)||DATA.roots[0]||{}).path;
}


function renderTree(){
  const t = curTree();
  if(!t){ vp.innerHTML = ''; return; }
  const ids = new Set(t.focuses.map(f=>f.id));
  let html = `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#5d7f99"/></marker></defs>`;
  t.analysis.edges.forEach(([a,b])=>{
    const A=nodeById(t,a), B=nodeById(t,b); if(!A||!B) return;
    const x1=(A.ax??A.x??0)*SCALE+NODE_W/2, y1=(A.ay??A.y??0)*SCALE+NODE_H;
    const x2=(B.ax??B.x??0)*SCALE+NODE_W/2, y2=(B.ay??B.y??0)*SCALE;
    const cyc = t.analysis.cycles.some(c=>c.includes(a)&&c.includes(b));
    html += `<path class="edge ${cyc?'cycle':''}" d="M${x1},${y1} L${x2},${y2}" marker-end="url(#arrow)"/>`;
  });
  if(showMutex()){
    t.focuses.forEach(f=>{ (f.mutex||[]).forEach(m=>{
      if(!ids.has(m)||f.id>m) return;
      const A=nodeById(t,f.id), B=nodeById(t,m); if(!A||!B) return;
      const x1=(A.ax??A.x??0)*SCALE+NODE_W/2, y1=(A.ay??A.y??0)*SCALE+NODE_H/2;
      const x2=(B.ax??B.x??0)*SCALE+NODE_W/2, y2=(B.ay??B.y??0)*SCALE+NODE_H/2;
      html += `<line class="edge mutex" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
    });});
  }
  t.focuses.forEach(f=>{
    const x=(f.ax??f.x??0)*SCALE, y=(f.ay??f.y??0)*SCALE;
    const cyc = t.analysis.cycles.some(c=>c.includes(f.id));
    const cls='node'+(cyc?' cycle':'')+(selId===f.id?' sel':'')+(multiSel.has(f.id)?' multi':'')+(dirty.has(f.id)?' dirty':'');
    const iconUrl = f.icon ? ('/api/icon?gfx=' + encodeURIComponent(f.icon)) : (f.iconPng || '');
    const withIcon = iconUrl ? `<image href="${iconUrl}" x="4" y="6" width="24" height="24" preserveAspectRatio="xMidYMid meet"/>` : '';
    const tx = iconUrl ? 32 : 6;
    html += `<g class="${cls}" data-id="${escapeHtml(f.id)}" transform="translate(${x},${y})">
      <rect width="${NODE_W}" height="${NODE_H}" rx="8"></rect>
      ${withIcon}
      <text x="${tx}" y="15">${escapeHtml(f.id).slice(0,16)}</text>
      <text x="${tx}" y="30">${escapeHtml(f.name||f.id).slice(0,10)}</text>
      <text x="${tx}" y="46" class="nmeta">${f.cost?('cost '+f.cost):''}</text>
      ${f.cost ? `<text x="${NODE_W-9}" y="15" text-anchor="end" class="ncost">◆${escapeHtml(String(f.cost)).slice(0,4)}</text>` : ''}
    </g>`;
  });
  vp.innerHTML = html;
  applyView();
  vp.querySelectorAll('.node').forEach(n=>{
    n.addEventListener('mousedown', ev=>startNodeDrag(ev, n));
    n.addEventListener('click', ev=>{
      ev.stopPropagation();
      const id = n.dataset.id;
      if(ev.ctrlKey || ev.metaKey){
        if(multiSel.has(id)) multiSel.delete(id); else multiSel.add(id);
        renderTree();
        updateBatchBar();
        return;
      }
      onNodeClick(id);
    });
  });
}


function screenToSvg(ev){
  // 必须用 #viewport 的 CTM：svg 自身的 CTM 不含 translate/scale，
  // 用它算出来的坐标在缩放后是偏的（滚轮缩放漂移、拖动距离随缩放失真）
  const ctm = vp.getScreenCTM() || svg.getScreenCTM();
  const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
  return pt.matrixTransform(ctm.inverse());
}

function onNodeClick(id){
  if(linkMode){
    if(!linkSrc){ linkSrc = id; status(`已选起点：${id}，点击目标节点`); return; }
    if(linkSrc === id){ status('不能连自己'); return; }
    if(linkMode === 'prereq') addPrereq(linkSrc, id); else addMutex(linkSrc, id);
    linkSrc = null; return;
  }
  selId = id; renderTree(); showPanel();
  if(typeof nodePicked !== 'undefined') nodePicked = true;
  if(typeof renderStepBar === 'function') renderStepBar();
}

async function addPrereq(src, dst){
  const t = curTree(); const f = nodeById(t, dst); if(!f) return;
  const pre = (f.prereq||[]).map(g=>[...g]);
  if(pre.some(g=>g.includes(src))){ status('已存在这条前置'); return; }
  pre.push([src]);
  await postSave(f, {prereq: pre});
  status('已添加前置：' + src + ' → ' + dst);
}

async function addMutex(a, b){
  const t = curTree();
  for(const [x,y] of [[a,b],[b,a]]){
    const f = nodeById(t, x); if(!f) continue;
    const mx = [...(f.mutex||[])];
    if(!mx.includes(y)) mx.push(y);
    await postSave(f, {mutex: mx});
  }
  status('已添加互斥：' + a + ' ↔ ' + b);
}

function startNodeDrag(ev, node){
  if(!editMode || linkMode) return;
  ev.stopPropagation(); ev.preventDefault();
  const t = curTree(); const id = node.dataset.id; const f = nodeById(t, id); if(!f) return;
  const p = screenToSvg(ev);
  drag = { id, node, f, start: p, origX: (f.ax??f.x??0), origY: (f.ay??f.y??0), moved:false };
  window.addEventListener('mousemove', onNodeDrag);
  window.addEventListener('mouseup', endNodeDrag, {once:true});
}

function onNodeDrag(ev){
  if(!drag) return;
  const p = screenToSvg(ev);
  const dx = (p.x - drag.start.x)/SCALE, dy = (p.y - drag.start.y)/SCALE;
  drag.moved = drag.moved || Math.abs(dx)>0.05 || Math.abs(dy)>0.05;
  drag.last = {x: drag.origX + dx, y: drag.origY + dy};
  drag.node.setAttribute('transform', `translate(${drag.last.x*SCALE},${drag.last.y*SCALE})`);
}

function endNodeDrag(){
  window.removeEventListener('mousemove', onNodeDrag);
  if(!drag) return;
  const t = curTree(); const f = drag.f;
  let movedId = null;
  if(drag.moved && drag.last){
    let rx = Math.round(drag.last.x*2)/2, ry = Math.round(drag.last.y*2)/2;
    if(f.rel){ const p = nodeById(t, f.rel); if(p){ rx = Math.round((drag.last.x-(p.ax??p.x??0))*2)/2; ry = Math.round((drag.last.y-(p.ay??p.y??0))*2)/2; } }
    dirty.set(f.id, {x:rx, y:ry});
    f.ax = drag.last.x; f.ay = drag.last.y;
    movedId = f.id;
    status(`已移动 ${f.id}：x=${rx}, y=${ry}（未保存）`);
  }
  drag = null; renderTree();
  // 拖动后属性面板里的 X/Y 还是旧值，得重画一次，否则看不到新坐标
  if(movedId && selId === movedId && panel.classList.contains('show')) showPanel();
}


function fillFxQuick(f){
  const fx = f.fx || {};
  const set = (id, v)=>{
    const el = document.getElementById(id);
    if(!el) return;
    el.value = (v === undefined || v === null || v === '') ? '' : v;
  };
  set('fxPP', fx.pp);
  set('fxStab', fx.stab !== undefined ? Math.round(fx.stab * 10000) / 100 : '');
  set('fxWS', fx.ws !== undefined ? Math.round(fx.ws * 10000) / 100 : '');
  set('fxMP', fx.mp !== undefined ? Math.round(fx.mp / 10) / 100 : '');
  set('fxCP', fx.cp);
  set('fxArmy', fx.army);
  set('fxAir', fx.air);
  set('fxNavy', fx.navy);
}

function saveFxQuick(f){
  const keys = ['add_political_power','add_stability','add_war_support','add_manpower',
                'add_command_power','add_army_experience','add_air_experience','add_navy_experience'];
  let raw = (document.getElementById('edEffect') || {}).value || '';
  let lines = raw.split(/\r?\n/).filter(ln=>!keys.some(k=>new RegExp('^\\s*'+k+'\\s*=').test(ln)));
  const num = id=>{ const v=parseFloat((document.getElementById(id)||{}).value); return isNaN(v)?0:v; };
  const fmt = v=>String(Number(v.toFixed(4)));
  if(num('fxPP')) lines.push('add_political_power = ' + fmt(num('fxPP')));
  if(num('fxStab')) lines.push('add_stability = ' + fmt(num('fxStab')/100));
  if(num('fxWS')) lines.push('add_war_support = ' + fmt(num('fxWS')/100));
  if(num('fxMP')) lines.push('add_manpower = ' + fmt(num('fxMP')*1000));
  if(num('fxCP')) lines.push('add_command_power = ' + fmt(num('fxCP')));
  if(num('fxArmy')) lines.push('add_army_experience = ' + fmt(num('fxArmy')));
  if(num('fxAir')) lines.push('add_air_experience = ' + fmt(num('fxAir')));
  if(num('fxNavy')) lines.push('add_navy_experience = ' + fmt(num('fxNavy')));
  const text = lines.join('\n').trim();
  postSave(f, {effect: text}).then(ok=>{ if(ok){ selId = f.id; status('快捷效果已保存'); showPanel(); } });
}

async function showPanel(){
  const t = curTree(); const f = nodeById(t, selId);
  if(!f){ panel.classList.remove('show'); return; }
  let fdet = {};
  try {
    fdet = await (await fetch('/api/focus?tree=' + encodeURIComponent(t.id) + '&id=' + encodeURIComponent(f.id))).json();
  } catch(e){}
  const d = dirty.get(f.id) || {};
  const xv = d.x ?? f.x, yv = d.y ?? f.y;
  const pre = d.prereq !== undefined ? d.prereq : (f.prereq||[]);
  const preText = pre.map(g=>g.join(' + ')).join('  |  ');
  const mutex = d.mutex !== undefined ? d.mutex : (f.mutex||[]);
  panel.innerHTML = `
    <div style="font-size:14px;color:#ffd479;margin-bottom:6px">${escapeHtml(f.name||f.id)}</div>
    <div class="k">ID：<span class="v">${escapeHtml(f.id)}</span></div>
    <div class="k">文件：<span class="v">${escapeHtml(f.file)}</span></div>
    <div class="src-hint" id="pnSrc"></div>
    <div class="k">原始坐标（相对定位时为偏移）</div>
    <div>X <input type="number" step="0.5" id="edX" value="${xv??''}"> Y <input type="number" step="0.5" id="edY" value="${yv??''}"></div>
    <div class="k">前置：每组 OR，组内 + 表示 AND</div>
    <textarea id="edPre">${escapeHtml(preText)}</textarea>
    <div class="k">互斥（逗号分隔）</div>
    <input type="text" id="edMutex" value="${escapeHtml(mutex.join(', '))}">
    <div class="k">快捷效果（填数字，0/空 = 不添加）</div>
    <div class="fxgrid">
      <label>政治点 <input type="number" step="1" id="fxPP" value=""></label>
      <label>稳定度(%) <input type="number" step="0.1" id="fxStab" value=""></label>
      <label>战争支持(%) <input type="number" step="0.1" id="fxWS" value=""></label>
      <label>人力(千) <input type="number" step="1" id="fxMP" value=""></label>
      <label>指挥点 <input type="number" step="1" id="fxCP" value=""></label>
      <label>陆军经验 <input type="number" step="1" id="fxArmy" value=""></label>
      <label>空军经验 <input type="number" step="1" id="fxAir" value=""></label>
      <label>海军经验 <input type="number" step="1" id="fxNavy" value=""></label>
    </div>
    <div style="display:flex;gap:6px;margin:4px 0 8px">
      <button class="btn" id="btnFxQuick">保存快捷效果</button>
      <button class="btn" id="btnFxClear">清空常见效果</button>
    </div>
    <datalist id="ideaIds"></datalist>
    <div class="k">快速添加内容（直接写入完成效果）</div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
      <button class="btn" id="quickIdea">＋ 国家精神</button>
      <button class="btn" id="quickEquip">＋ 装备</button>
      <button class="btn" id="quickTech">＋ 科技</button>
      <button class="btn" id="quickEvent">＋ 事件</button>
    </div>
    <details><summary class="k">高级：直接编辑效果原文</summary>
    <textarea id="edEffect" style="height:120px">${escapeHtml(fdet.effect||'')}</textarea>
    </details>
    <div class="k">选择效果 select_effect（可留空）</div>
    <textarea id="edSelect" style="height:70px">${escapeHtml(fdet.select_effect||'')}</textarea>
    <div class="k">花费 / 图标</div>
    <div style="display:flex;gap:6px"><input type="number" step="1" id="edCost" value="${escapeHtml(f.cost||'')}" style="width:80px"><input type="text" id="edIcon" value="${escapeHtml(f.icon||'')}"></div>
    <div style="margin-bottom:8px"><button class="btn" id="btnIconPick">🖼 选择图标</button></div>
    <div class="k">中文名称 / 描述</div>
    <input type="text" id="edNameZ" value="${escapeHtml((d.loc && d.loc.simp_chinese && d.loc.simp_chinese[f.id] !== undefined) ? d.loc.simp_chinese[f.id] : (f.name||''))}">
    <textarea id="edDescZ">${escapeHtml((d.loc && d.loc.simp_chinese && d.loc.simp_chinese[f.id+'_desc'] !== undefined) ? d.loc.simp_chinese[f.id+'_desc'] : (fdet.desc||''))}</textarea>
    <div class="k">English name / description</div>
    <input type="text" id="edNameE" value="${escapeHtml((d.loc && d.loc.english && d.loc.english[f.id] !== undefined) ? d.loc.english[f.id] : '')}">
    <textarea id="edDescE">${escapeHtml((d.loc && d.loc.english && d.loc.english[f.id+'_desc'] !== undefined) ? d.loc.english[f.id+'_desc'] : '')}</textarea>
    <div class="k">日本語 名前 / 説明</div>
    <input type="text" id="edNameJ" value="${escapeHtml((d.loc && d.loc.japanese && d.loc.japanese[f.id] !== undefined) ? d.loc.japanese[f.id] : '')}">
    <textarea id="edDescJ">${escapeHtml((d.loc && d.loc.japanese && d.loc.japanese[f.id+'_desc'] !== undefined) ? d.loc.japanese[f.id+'_desc'] : '')}</textarea>
    <div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap">
      <button class="btn" id="btnCopy">⧉ 复制分支</button>
      <button class="btn" id="btnLoc">保存名称/描述</button>
      <button class="btn" id="btnReset">还原</button>
      <button class="btn warn" id="btnDel">删除节点</button>
    </div>`;
  panel.classList.add('show');
  translateDom(panel);
  // v1.24.2：这条节点从哪层来、保存会写到哪——打开时就问，不等保存时才知道
  fillSrcHint('pnSrc', rootOf(t), f.file, t.source);
  // 面板里的改动是实时进 dirty 的，保存统一走顶部「保存 (N)」；按钮已移除
  const _btnSave = document.getElementById('btnSave');
  if(_btnSave) _btnSave.onclick = ()=>saveNode(f);
  document.getElementById('btnCopy').onclick = ()=>copyBranch(f);
  document.getElementById('quickIdea').onclick = ()=>openContent('idea');
  document.getElementById('quickEquip').onclick = ()=>openContent('equip');
  document.getElementById('quickTech').onclick = ()=>openContent('tech');
  document.getElementById('quickEvent').onclick = ()=>openContent('event');
  document.getElementById('btnLoc').onclick = ()=>saveLoc(f);
  document.getElementById('btnReset').onclick = ()=>{ dirty.delete(f.id); loadData(); };
  document.getElementById('btnDel').onclick = ()=>delNode(f);
  fillFxQuick(f);
  document.getElementById('btnIconPick').onclick = openIconPicker;
  document.getElementById('btnFxQuick').onclick = ()=>saveFxQuick(f);
  document.getElementById('btnFxClear').onclick = ()=>{ ['fxPP','fxStab','fxWS','fxMP','fxCP','fxArmy','fxAir','fxNavy'].forEach(id=>{ const el=document.getElementById(id); if(el) el.value=''; }); };
  bindPanelDirty(f);
  translateDom(panel);
}


/* 面板输入实时进 dirty：顶部「保存全部」也能直接落盘，不必先点「保存此节点」 */
function bindPanelDirty(f){
  const map = [['edX','x'],['edY','y'],['edCost','cost'],['edIcon','icon'],
               ['edEffect','effect'],['edSelect','select_effect'],
               ['edPre','prereq'],['edMutex','mutex']];
  map.forEach(function(pair){
    const el = document.getElementById(pair[0]);
    if(!el) return;
    const key = pair[1];
    const read = function(){
      if(key === 'prereq') return parsePre(el.value);
      if(key === 'mutex') return el.value.split(',').map(function(s){ return s.trim(); }).filter(Boolean);
      if(key === 'x' || key === 'y'){ const v = parseFloat(el.value); return isNaN(v) ? 0 : v; }
      return el.value;
    };
    const onChange = function(){
      const was = dirty.has(f.id);
      const cur = dirty.get(f.id) || {};
      cur[key] = read();
      dirty.set(f.id, cur);
      if(!was) renderTree();   // 只有第一次变脏才重画画布，避免每次按键重建 DOM
      renderStats();
    };
    el.addEventListener('input', onChange);
    el.addEventListener('change', onChange);
  });
  const locMap = [
    ['edNameZ', 'simp_chinese', f.id],
    ['edDescZ', 'simp_chinese', f.id + '_desc'],
    ['edNameE', 'english', f.id],
    ['edDescE', 'english', f.id + '_desc'],
    ['edNameJ', 'japanese', f.id],
    ['edDescJ', 'japanese', f.id + '_desc']
  ];
  locMap.forEach(function(item){
    const el = document.getElementById(item[0]);
    if(!el) return;
    const lang = item[1], locKey = item[2];
    const onLocChange = function(){
      const was = dirty.has(f.id);
      const cur = dirty.get(f.id) || {};
      cur.loc = cur.loc || {};
      cur.loc[lang] = cur.loc[lang] || {};
      cur.loc[lang][locKey] = el.value;
      dirty.set(f.id, cur);
      if(!was) renderTree();
      renderStats();
    };
    el.addEventListener('input', onLocChange);
    el.addEventListener('change', onLocChange);
  });
}

function parsePre(text){
  text=(text||'').trim(); if(!text) return [];
  return text.split('|').map(s=>s.split('+').map(x=>x.trim()).filter(Boolean)).filter(g=>g.length);
}

function updateBatchBar(){
  const bar = document.getElementById('batchBar'); if(!bar) return;
  if(!multiSel.size){ bar.style.display='none'; bar.innerHTML=''; return; }
  bar.style.display = 'flex';
  bar.innerHTML = '<span>已选 ' + multiSel.size + ' 个节点</span>' +
    '<button class="btn" id="bcCost">改花费</button>' +
    '<button class="btn" id="bcIcon">改图标</button>' +
    '<button class="btn" id="bcArrange">自动排版</button>' +
    '<button class="btn" id="bcClear">取消选择</button>';
  document.getElementById('bcCost').onclick = batchSetCost;
  document.getElementById('bcIcon').onclick = ()=>{ batchIconMode = true; openIconPicker(); };
  document.getElementById('bcArrange').onclick = autoArrange;
  document.getElementById('bcClear').onclick = ()=>{ multiSel.clear(); renderTree(); updateBatchBar(); };
}

async function batchSetCost(){
  const v = prompt('新的花费（单位：周，留空取消）：');
  if(v === null || v === '') return;
  const t = curTree(); let ok = 0;
  for(const id of [...multiSel]){
    const f = nodeById(t, id); if(!f) continue;
    const r = await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootOf(t), file: f.file, id: f.id, fields:{cost: parseFloat(v)}})});
    const j = await r.json(); if(j.ok) ok++;
  }
  status('已修改 ' + ok + ' 个节点的花费');
  multiSel.clear(); await loadData(); updateBatchBar();
}

async function applyBatchIcon(gfx){
  const t = curTree(); let ok = 0;
  for(const id of [...multiSel]){
    const f = nodeById(t, id); if(!f) continue;
    const r = await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootOf(t), file: f.file, id: f.id, fields:{icon: gfx}})});
    const j = await r.json(); if(j.ok) ok++;
  }
  status('已修改 ' + ok + ' 个节点的图标');
  multiSel.clear(); await loadData(); updateBatchBar();
}

async function autoArrange(){
  const t = curTree(); if(!t) return;
  const ids = multiSel.size ? [...multiSel] : t.focuses.map(f=>f.id);
  const set = new Set(ids);
  const by = {}; t.focuses.forEach(f=>by[f.id] = f);
  const lvl = {};
  function lv(id, seen){
    if(lvl[id] !== undefined) return lvl[id];
    if(seen.has(id)) return 0;
    const f = by[id]; if(!f) return 0;
    let m = -1;
    (f.prereq || []).forEach(g=>g.forEach(p=>{ if(set.has(p)) m = Math.max(m, lv(p, new Set([...seen, id]))); }));
    lvl[id] = m + 1;
    return lvl[id];
  }
  const groups = {};
  ids.forEach(id=>{ const l = lv(id, new Set()); (groups[l] = groups[l] || []).push(id); });
  let ok = 0;
  for(const l of Object.keys(groups)){
    const arr = groups[l].sort();
    for(let idx=0; idx<arr.length; idx++){
      const f = by[arr[idx]]; if(!f) continue;
      const r = await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({root: rootOf(t), file: f.file, id: f.id, fields:{x: idx - (arr.length - 1) / 2, y: Number(l)}})});
      const j = await r.json(); if(j.ok) ok++;
    }
  }
  status('已自动排版并保存 ' + ok + ' 个节点');
  multiSel.clear(); await loadData(); updateBatchBar();
}

async function copyBranch(f){
  const t = curTree();
  if(!t || t.id === 'shared_focuses'){ status('共享焦点库暂不支持复制分支'); return; }
  const children = {};
  t.focuses.forEach(x=>{
    (x.prereq || []).forEach(g=>g.forEach(p=>{ (children[p] = children[p] || []).push(x.id); }));
  });
  const ids = [], stack = [f.id], seen = new Set();
  while(stack.length){
    const id = stack.pop();
    if(seen.has(id)) continue;
    seen.add(id); ids.push(id);
    (children[id] || []).forEach(c=>stack.push(c));
  }
  const prefix = prompt('将复制 ' + ids.length + ' 个节点，新 ID 前缀：', f.id + '_copy');
  if(!prefix) return;
  const map = {};
  ids.forEach(id=>{ map[id] = prefix + '_' + id; });
  for(const id of ids){
    const n = nodeById(t, id); if(!n) continue;
    const nid = map[id];
    let j = await (await fetch('/api/add_focus', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootOf(t), file: n.file, tree: t.id, id: nid,
        x: (n.x ?? 0) + 2, y: (n.y ?? 0), cost: n.cost || 1,
        icon: n.icon || 'GFX_goal_generic_national_unity'})})).json();
    if(!j.ok){ status('复制失败：' + j.msg, true); return; }
    let det = {};
    try {
      det = await (await fetch('/api/focus?tree=' + encodeURIComponent(t.id) + '&id=' + encodeURIComponent(id))).json();
    } catch(e){}
    const fields = {
      prereq: (n.prereq || []).map(g=>g.map(p=>map[p] || p)),
      mutex: (n.mutex || []).map(m=>map[m] || m),
      effect: det.effect || n.effect || '',
      select_effect: det.select_effect || n.select_effect || ''
    };
    j = await (await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootOf(t), file: n.file, id: nid, fields})})).json();
    if(!j.ok){ status('复制失败：' + j.msg, true); return; }
  }
  status('已复制 ' + ids.length + ' 个节点');
  await loadData();
}

async function saveNode(f){
  const fields = {
    x: parseFloat(document.getElementById('edX').value),
    y: parseFloat(document.getElementById('edY').value),
    cost: document.getElementById('edCost').value,
    icon: document.getElementById('edIcon').value.trim(),
    effect: document.getElementById('edEffect').value,
    select_effect: document.getElementById('edSelect').value,
    prereq: parsePre(document.getElementById('edPre').value),
    mutex: document.getElementById('edMutex').value.split(',').map(s=>s.trim()).filter(Boolean)
  };
  const cmp = ['x','y','cost','icon','effect','select_effect','prereq','mutex'];
  const show = v=>{
    if(Array.isArray(v)) return JSON.stringify(v);
    const s = v === undefined || v === null ? '' : String(v);
    return s.length > 500 ? s.slice(0, 500) + ' ...' : s;
  };
  const changes = [];
  cmp.forEach(k=>{
    const oldV = f[k] === undefined ? (k === 'select_effect' ? '' : '') : f[k];
    const newV = fields[k];
    if(JSON.stringify(oldV) !== JSON.stringify(newV)) changes.push([k, oldV, newV]);
  });
  if(!changes.length){ status('没有改动'); return; }
  pendingSave = {f, fields};
  document.getElementById('diffBody').innerHTML = changes.map(([k, o, n])=>
    '<div class="del">- ' + k + ': ' + escapeHtml(show(o)) + '</div>' +
    '<div class="add">+ ' + k + ': ' + escapeHtml(show(n)) + '</div>').join('');
  document.getElementById('diffModal').classList.add('show');
}

async function postSave(f, fields){
  const t = curTree();
  const r = await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: rootOf(t), file: f.file, id: f.id, fields})});
  const j = await r.json();
  if(j.ok){ dirty.delete(f.id); await loadData(); }
  else { showError(j); status('保存失败：' + j.msg, true); }
  return j.ok;
}

async function saveAll(){
  if(!dirty.size){ status('没有未保存的改动'); return; }
  const t = curTree(); let ok=0, bad=0, firstFail=null, adoptedTo='';
  const locEntries = {simp_chinese:{}, english:{}, japanese:{}};
  let hasLoc = false, locOnlyNodes = 0;
  for(const [id,d] of [...dirty.entries()]){
    const f = nodeById(t,id); if(!f) continue;
    let nodeHasLoc = false;
    if(d.loc){
      ['simp_chinese','english','japanese'].forEach(lang=>{
        const m = d.loc[lang];
        if(!m) return;
        Object.keys(m).forEach(k=>{
          const v = (m[k] || '').trim();
          if(v !== ''){ locEntries[lang][k] = v; hasLoc = true; nodeHasLoc = true; }
        });
      });
    }
    const fields = {};
    ['x','y','cost','icon','effect','select_effect','prereq','mutex'].forEach(function(k){
      if(d[k] !== undefined) fields[k] = d[k];
    });
    if(!Object.keys(fields).length){
      if(nodeHasLoc) locOnlyNodes++;
      continue;
    }
    const r = await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootOf(t), file:f.file, id:f.id, fields})});
    const j = await r.json();
    if(j.ok){ ok++; if(j.adopted_to) adoptedTo = j.adopted_to; }
    else { bad++; if(!firstFail) firstFail = j; }
  }
  if(hasLoc){
    const lr = await fetch('/api/loc_save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootOf(t), entries: locEntries})});
    const lj = await lr.json();
    if(lj.ok){
      ok += locOnlyNodes;
      if(lj.adopted_to) adoptedTo = lj.adopted_to;
    }else{
      bad++; if(!firstFail) firstFail = lj;
    }
  }
  if(firstFail) showError(firstFail);
  // v1.24.1：后端若因为「写到了只读层」自动接管，把复制到的目标一起说出来
  const _adopt = (typeof adoptedTo === 'string' && adoptedTo) ? ('（文件已复制到 ' + adoptedTo + '，原层未改动）') : '';
  status(bad ? ('已保存 ' + ok + ' 个，' + bad + ' 个失败')
             : ('已保存 ' + ok + ' 个节点' + _adopt), !!bad);
  if(!bad) savedOnce = true;
  await loadData();
}

async function delNode(f){
  if(!confirm('确定删除焦点 ' + f.id + ' ？（会写回文件，可在 .bak 恢复）')) return;
  const t = curTree();
  const r = await fetch('/api/delete_focus', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: rootOf(t), file: f.file, id: f.id})});
  const j = await r.json();
  if(!j.ok) showError(j);
  status(j.ok ? ('已删除 ' + f.id) : ('删除失败：' + j.msg), !j.ok);
  if(j.ok) await loadData();
}

async function addNode(){
  const id = prompt('新焦点 ID（例如 UNI_new_focus）：');
  if(!id) return;
  const t = curTree();
  const x = parseFloat(prompt('X 坐标（整数）：', '0'));
  const y = parseFloat(prompt('Y 坐标（整数）：', '0'));
  const r = await fetch('/api/add_focus', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: rootOf(t), file: t.file, tree: t.id, id, x, y, cost: 5})});
  const j = await r.json();
  if(!j.ok) showError(j);
  status(j.ok ? ('已新建 ' + id) : ('新建失败：' + j.msg), !j.ok);
  if(j.ok) await loadData();
}

async function saveLoc(f){
  await withBusy('正在保存名称/描述并刷新…', async ()=>{
    const entries = {simp_chinese:{}, english:{}, japanese:{}};
    const nz = document.getElementById('edNameZ').value.trim();
    const dz = document.getElementById('edDescZ').value.trim();
    const ne = document.getElementById('edNameE').value.trim();
    const de = document.getElementById('edDescE').value.trim();
    const nj = document.getElementById('edNameJ').value.trim();
    const dj = document.getElementById('edDescJ').value.trim();
    if(nz) entries.simp_chinese[f.id] = nz;
    if(dz) entries.simp_chinese[f.id+'_desc'] = dz;
    if(ne) entries.english[f.id] = ne;
    if(de) entries.english[f.id+'_desc'] = de;
    if(nj) entries.japanese[f.id] = nj;
    if(dj) entries.japanese[f.id+'_desc'] = dj;
    const t = curTree();
    const r = await fetch('/api/loc_save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootOf(t), entries})});
    const j = await r.json();
    status(j.ok ? '名称/描述已保存' : ('保存失败：' + j.msg), !j.ok);
    if(j.ok) await loadData();
  });
}

async function addTree(){
  const id = prompt('新国策树 ID（例如 my_new_tree）：');
  if(!id) return;
  const root = _writableRoot();
  if(!root){ status('先加载或新建一个可写的模组', true); return; }
  const r = await fetch('/api/add_tree', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root, id})});
  const j = await r.json();
  status(j.ok ? ('已新建树 ' + id) : ('新建失败：' + j.msg), !j.ok);
  if(j.ok) await loadData();
}

async function delTree(){
  const t = curTree();
  if(!confirm('确定删除整棵树 ' + t.id + ' ？会写回文件（.bak 可恢复）')) return;
  const r = await fetch('/api/delete_tree', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: rootOf(t), file: t.file, id: t.id})});
  const j = await r.json();
  status(j.ok ? ('已删除树 ' + t.id) : ('删除失败：' + j.msg), !j.ok);
  if(j.ok) await loadData();
}

function renderStats(){
  const t = curTree();
  if(!t){
    document.getElementById('stats').innerHTML = '<div class="muted">尚未加载 mod</div>';
    return;
  }
  const a = t.analysis;
  document.getElementById('stats').innerHTML =
    `<div>焦点数：<span class="v">${t.focuses.length}</span></div>` +
    `<div>前置边：<span class="v">${a.edges.length}</span></div>` +
    `<div>循环依赖：<span class="${a.cycles.length?'warn':'ok'}">${a.cycles.length}</span></div>` +
    `<div>坐标重叠：<span class="${a.overlaps.length?'warn':'ok'}">${a.overlaps.length}</span></div>` +
    `<div>悬空前置：<span class="${a.missing.length?'warn':'ok'}">${a.missing.length}</span></div>` +
    `<div>未保存改动：<span class="${dirty.size?'warn':'ok'}">${dirty.size}</span></div>` +
    (linkMode ? `<div class="warn">连线模式：${linkMode==='prereq'?'前置':'互斥'}（点两个节点）</div>` : '');
  updateSaveBtn();
  if(typeof renderStepBar === 'function') renderStepBar();
}


/* v1.24.0 统一保存：按钮上直接显示有几处没存，0 时变灰 */
function updateSaveBtn(){
  const b = document.getElementById('saveAll');
  if(!b) return;
  const n = (typeof dirty !== 'undefined' && dirty) ? dirty.size : 0;
  b.textContent = n ? ('💾 保存 (' + n + ')') : '💾 保存';
  b.disabled = !n;
  b.style.opacity = n ? '' : '.5';
  b.style.cursor = n ? '' : 'default';
  b.title = n ? ('保存 ' + n + ' 处改动（Ctrl+S）') : '没有未保存的改动';
}


/* v1.24.0 有未保存改动时，关页面/刷新先拦一下（浏览器不给自定义文案，只弹通用确认） */
window.addEventListener('resize', function(){
  if(typeof renderStepBar === 'function') renderStepBar();
});


window.addEventListener('beforeunload', function(ev){
  if(typeof dirty !== 'undefined' && dirty && dirty.size){
    ev.preventDefault();
    ev.returnValue = '';
    return '';
  }
});

function fitView(){
  const t = curTree(); if(!t || !t.focuses.length){ view={x:0,y:0,k:1}; applyView(); return; }
  let minX=1e9,minY=1e9,maxX=-1e9,maxY=-1e9;
  t.focuses.forEach(f=>{ const x=(f.ax??f.x??0)*SCALE, y=(f.ay??f.y??0)*SCALE;
    minX=Math.min(minX,x); minY=Math.min(minY,y); maxX=Math.max(maxX,x+NODE_W); maxY=Math.max(maxY,y+NODE_H); });
  const rect = svg.getBoundingClientRect(); const pad=70;
  const w = Math.max(maxX-minX,1), h = Math.max(maxY-minY,1);
  const k = Math.min((rect.width-pad*2)/w, (rect.height-pad*2)/h, 1.6);
  view.k = Math.max(0.2, k);
  view.x = (rect.width - w*view.k)/2 - minX*view.k;
  view.y = (rect.height - h*view.k)/2 - minY*view.k;
  applyView();
  updateZoomLabel();
}

function renderAll(){
  // 只有第一次加载或切换了树才自动适应屏幕；保存后刷新数据时保持当前视图不变
  const _t0 = curTree();
  const _tid = _t0 ? _t0.id : '';
  const _needFit = (_tid !== _lastFitTree) || !_viewReady;
  treeOptions(); renderTree(); renderStats();
  if(_needFit){ fitView(); _lastFitTree = _tid; _viewReady = true; }
  fillIdeaDatalist(); updateBatchBar();
  const t = curTree();
  const shared = t && t.id === 'shared_focuses';
  document.getElementById('sharedAddBtn').style.display = shared ? '' : 'none';
  document.getElementById('sharedDelBtn').style.display = shared ? '' : 'none';
  translateDom();
}

function fillIdeaDatalist(){
  const dl = document.getElementById('ideaIds'); if(!dl || !DATA) return;
  dl.innerHTML = (DATA.ideas||[]).slice(0,4000).map(i=>'<option value="'+String(i.id).replace(/"/g,'')+'"></option>').join('');
}

function rootByName(n){
  const hitRoot = ((DATA && DATA.roots) || []).find(r=>r.name===n);
  if(hitRoot && hitRoot.path) return hitRoot.path;
  const hitLayer = ((DATA && DATA.layers) || []).find(l=>l.name===n);
  if(hitLayer && hitLayer.path) return hitLayer.path;
  return _writableRoot();
}

let _ideaScope = 'all';
let _ideaTab = 'basic';
let _ideaRawDirty = false;

const _IDEA_MOD_ZH = {
  political_power_gain: '每日政治点数',
  political_power_factor: '政治点数修正',
  stability_factor: '稳定度',
  stability_weekly: '每周稳定度',
  war_support_factor: '战争支持度',
  war_support_weekly: '每周战争支持度',
  consumer_goods_factor: '消费品工厂系数',
  industrial_capacity_factory: '军工产出',
  industrial_capacity_dockyard: '船坞产出',
  production_speed_buildings_factor: '建造速度',
  research_speed_factor: '科研速度',
  army_attack_factor: '陆军攻击',
  army_defence_factor: '陆军防御',
  army_org_factor: '组织度',
  conscription_factor: '适役人口修正',
  training_time_factor: '训练时间',
};

function setIdeaScope(scope){
  _ideaScope = scope === 'mod' ? 'mod' : 'all';
  const bAll = document.getElementById('ideaScopeAll');
  const bMod = document.getElementById('ideaScopeMod');
  if(bAll) bAll.classList.toggle('on', _ideaScope === 'all');
  if(bMod) bMod.classList.toggle('on', _ideaScope === 'mod');
  const q = (document.getElementById('ideaSearch')?.value || '').trim().toLowerCase();
  renderIdeaList(q);
}

function switchIdeaTab(tab){
  _ideaTab = (tab === 'cond' || tab === 'raw') ? tab : 'basic';
  const tabs = { basic: 'ideaTabBasic', cond: 'ideaTabCond', raw: 'ideaTabRaw' };
  const panes = { basic: 'ideaPaneBasic', cond: 'ideaPaneCond', raw: 'ideaPaneRaw' };
  Object.keys(tabs).forEach(k=>{
    const b = document.getElementById(tabs[k]);
    if(b) b.classList.toggle('on', k === _ideaTab);
    const p = document.getElementById(panes[k]);
    if(p) p.style.display = (k === _ideaTab) ? 'flex' : 'none';
  });
}

function _removeIdeaModFromRaw(k){
  const rawEl = document.getElementById('ideaRaw');
  if(!rawEl || !k) return;
  const raw = rawEl.value || '';
  const m = /(?:^|\n)([ \t]*)modifier\s*=\s*\{/.exec(raw) || /\bmodifier\s*=\s*\{/.exec(raw);
  if(!m) return;
  const openIdx = raw.indexOf('{', m.index);
  if(openIdx < 0) return;
  let depth = 0, endIdx = -1;
  for(let i = openIdx; i < raw.length; i++){
    if(raw[i] === '{') depth++;
    else if(raw[i] === '}'){
      depth--;
      if(depth === 0){ endIdx = i; break; }
    }
  }
  if(endIdx < 0) return;
  const esc = k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const inner = raw.slice(openIdx + 1, endIdx);
  const lineRe = new RegExp('^\\s*' + esc + '\\s*=\\s*[^\\s#{}]+(?:\\s*#.*)?$');
  let nextInner;
  if(inner.includes('\n')){
    nextInner = inner.split('\n').filter(ln => !lineRe.test(ln)).join('\n');
  } else {
    nextInner = inner.replace(new RegExp('\\b' + esc + '\\s*=\\s*[^\\s#{}]+'), '').replace(/\s{2,}/g, ' ');
  }
  if(!nextInner.trim()){
    const blockStart = m[0].startsWith('\n') ? m.index + 1 : m.index;
    let after = endIdx + 1;
    if(raw[after] === '\r') after++;
    if(raw[after] === '\n') after++;
    rawEl.value = raw.slice(0, blockStart) + raw.slice(after);
  } else {
    rawEl.value = raw.slice(0, openIdx + 1) + nextInner + raw.slice(endIdx);
  }
}

function _appendIdeaProp(pg, k, v){
  if(!pg.querySelector('input[data-prop]')) pg.innerHTML = '';
  const card = document.createElement('div');
  card.className = 'idea-prop-card';
  const head = document.createElement('div');
  head.className = 'idea-prop-head';
  const titles = document.createElement('div');
  titles.className = 'idea-prop-titles';
  const keyEl = document.createElement('span');
  keyEl.className = 'idea-prop-key';
  keyEl.textContent = k;
  titles.appendChild(keyEl);
  const zh = _IDEA_MOD_ZH[k];
  if(zh){
    const subEl = document.createElement('span');
    subEl.className = 'idea-prop-zh';
    subEl.textContent = zh;
    titles.appendChild(subEl);
  }
  const delBtn = document.createElement('button');
  delBtn.type = 'button';
  delBtn.className = 'idea-prop-del';
  delBtn.title = '移除此修正项';
  delBtn.textContent = '×';
  delBtn.onclick = ()=>{
    card.remove();
    _removeIdeaModFromRaw(k);
    if(!pg.querySelector('input[data-prop]')){
      pg.innerHTML = '<div class="idea-empty">暂无修正项，可点上方预设标签或下方添加</div>';
    }
  };
  head.appendChild(titles);
  head.appendChild(delBtn);
  const inp = document.createElement('input');
  inp.type = 'text';
  inp.value = v;
  inp.dataset.prop = k;
  card.appendChild(head);
  card.appendChild(inp);
  pg.appendChild(card);
  return inp;
}

function renderIdeaList(q){
  const box = document.getElementById('ideaList'); if(!box || !DATA) return;
  q = (q||'').trim().toLowerCase();
  const allIdeas = DATA.ideas || [];
  const modNames = new Set((DATA.roots || []).filter(r=>r && !r.readonly && r.name).map(r=>r.name));
  const scoped = _ideaScope === 'mod'
    ? allIdeas.filter(i=>modNames.has(i.source))
    : allIdeas;
  const items = scoped.filter(i=>!q || i.id.toLowerCase().includes(q) || (i.name||'').toLowerCase().includes(q));
  const statEl = document.getElementById('ideaScopeStat');
  if(statEl){
    const modCount = allIdeas.filter(i=>modNames.has(i.source)).length;
    statEl.textContent = _ideaScope === 'mod'
      ? ('显示 ' + items.length + ' / 当前 mod ' + modCount)
      : ('显示 ' + items.length + ' / 共 ' + allIdeas.length);
  }
  box.innerHTML = '';
  items.slice(0,600).forEach(i=>{
    const d = listRow(i.id, i.name, i.source, i.file);
    d.dataset.ideaId = i.id;
    if(ideaSel && ideaSel.id === i.id) d.classList.add('on');
    d.onclick = ()=>selectIdea(i);
    box.appendChild(d);
  });
  if(!items.length){
    const emp = document.createElement('div');
    emp.className = 'idea-empty';
    emp.textContent = _ideaScope === 'mod'
      ? '当前 mod 下暂无匹配精神，可点「全部」查看原版'
      : '（没有匹配的国家精神）';
    box.appendChild(emp);
  }
}

async function fetchRaw(kind, id){
  try {
    const r = await fetch('/api/raw?kind=' + kind + '&id=' + encodeURIComponent(id));
    const j = await r.json();
    return j.raw || '';
  } catch(e){ return ''; }
}

async function selectIdea(i){
  if(!i) return;
  ideaSel = i;
  _ideaRawDirty = false;
  document.querySelectorAll('#ideaList .lr').forEach(el=>{
    el.classList.toggle('on', el.dataset.ideaId === i.id);
  });
  document.getElementById('ideaTitle').textContent = i.id + '   (' + i.file + ')';
  fillSrcHint('ideaSrc', rootByName(i.source) || _lastRoot(), i.file, i.source);
  document.getElementById('ideaNameZ').value = i.name||'';
  document.getElementById('ideaDescZ').value = i.desc||'';
  document.getElementById('ideaPic').value = i.picture||'';
  document.getElementById('ideaNameJa').value = '';
  document.getElementById('ideaDescJa').value = '';
  document.getElementById('ideaNameEn').value = '';
  document.getElementById('ideaDescEn').value = '';
  const pg = document.getElementById('ideaProps');
  pg.innerHTML = '';
  const props = i.props || {};
  const keys = Object.keys(props);
  if(!keys.length){
    pg.innerHTML = '<div class="idea-empty">暂无修正项，可点上方预设标签或下方添加</div>';
  } else {
    keys.forEach(k=>_appendIdeaProp(pg, k, props[k]));
  }
  const detail = await fetchRawDetail('idea', i.id);
  if(ideaSel !== i) return;
  const raw = detail.raw || '';
  const loc = detail.loc || {};
  document.getElementById('ideaNameZ').value = (loc && loc.name) || i.name || '';
  document.getElementById('ideaDescZ').value = (loc && loc.desc) || i.desc || '';
  if(loc && loc.name_ja) document.getElementById('ideaNameJa').value = loc.name_ja;
  if(loc && loc.desc_ja) document.getElementById('ideaDescJa').value = loc.desc_ja;
  if(loc && loc.name_en) document.getElementById('ideaNameEn').value = loc.name_en;
  if(loc && loc.desc_en) document.getElementById('ideaDescEn').value = loc.desc_en;
  document.getElementById('ideaRaw').value = raw;
  document.getElementById('ideaAllowed').value = extractBlock(raw, 'allowed');
  document.getElementById('ideaTrigger').value = extractBlock(raw, 'trigger');
}

function addIdeaMod(presetKey, presetVal){
  const keyEl = document.getElementById('ideaModKey');
  const valEl = document.getElementById('ideaModVal');
  const pg = document.getElementById('ideaProps');
  if(!keyEl || !valEl || !pg) return;
  const isPreset = typeof presetKey === 'string';
  const k = (isPreset ? presetKey : (keyEl.value || '')).trim();
  const v = (isPreset && presetVal !== undefined ? String(presetVal) : (valEl.value || '')).trim();
  if(!k){ status('请输入或选择 modifier 键名', true); keyEl.focus(); return; }
  const existing = [...pg.querySelectorAll('input[data-prop]')].find(i=>i.dataset.prop === k);
  if(existing){
    if(v !== '') existing.value = v;
    existing.focus();
    if(!isPreset){ keyEl.value = ''; valEl.value = ''; }
    return;
  }
  const inp = _appendIdeaProp(pg, k, v);
  if(!isPreset){
    keyEl.value = '';
    valEl.value = '';
    if(v === '') inp.focus();
    else keyEl.focus();
  } else {
    inp.focus();
  }
}

async function saveIdea(){
  if(!ideaSel){ status('先选择一个国家精神'); return; }
  const curId = ideaSel.id;
  const btns = ['ideaSave', 'ideaSaveTop'].map(id=>document.getElementById(id)).filter(Boolean);
  btns.forEach(b=>{ b.disabled = true; });
  status('正在保存国家精神…');
  try{
    let payload;
    if(_ideaTab === 'raw' && _ideaRawDirty){
      payload = {
        root: rootByName(ideaSel.source),
        file: ideaSel.file,
        id: ideaSel.id,
        raw: document.getElementById('ideaRaw').value,
        name: document.getElementById('ideaNameZ').value,
        desc: document.getElementById('ideaDescZ').value,
        name_ja: document.getElementById('ideaNameJa').value,
        desc_ja: document.getElementById('ideaDescJa').value,
        name_en: document.getElementById('ideaNameEn').value,
        desc_en: document.getElementById('ideaDescEn').value,
        props: {}
      };
    } else {
      const pendingKey = (document.getElementById('ideaModKey')?.value || '').trim();
      const pendingVal = (document.getElementById('ideaModVal')?.value || '').trim();
      if(pendingKey && pendingVal) addIdeaMod();
      const props = {};
      document.querySelectorAll('#ideaProps input[data-prop]').forEach(i=>{
        const v = (i.value || '').trim();
        if(v !== '') props[i.dataset.prop] = v;
      });
      const alw = (document.getElementById('ideaAllowed').value || '').trim();
      const trg = (document.getElementById('ideaTrigger').value || '').trim();
      if(alw) props.allowed_raw = alw;
      if(trg) props.trigger_raw = trg;
      payload = {
        root: rootByName(ideaSel.source),
        file: ideaSel.file,
        id: ideaSel.id,
        raw: document.getElementById('ideaRaw').value,
        props,
        picture: document.getElementById('ideaPic').value.trim(),
        name: document.getElementById('ideaNameZ').value,
        desc: document.getElementById('ideaDescZ').value,
        name_ja: document.getElementById('ideaNameJa').value,
        desc_ja: document.getElementById('ideaDescJa').value,
        name_en: document.getElementById('ideaNameEn').value,
        desc_en: document.getElementById('ideaDescEn').value
      };
    }
    const r = await fetch('/api/idea_save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)});
    const j = await r.json();
    status(j.ok ? '国家精神已保存' : ('保存失败：' + j.msg), !j.ok);
    if(j.ok){
      _ideaRawDirty = false;
      const q = document.getElementById('ideaSearch')?.value || '';
      if(j.item){
        _upsertDataItem('ideas', j.item);
        renderIdeaList(q);
        await selectIdea(j.item);
      } else {
        await loadData();
        renderIdeaList(q);
        const hit = (DATA.ideas||[]).find(i=>i.id===curId);
        if(hit) await selectIdea(hit);
      }
    }
  } finally {
    btns.forEach(b=>{ b.disabled = false; });
  }
}

async function addIdea(){
  const id = prompt('新国家精神 ID（字母、数字、下划线）：');
  if(!id) return;
  const root = _writableRoot();
  if(!root){ status('先加载或新建一个可写的模组', true); return; }
  const btn = document.getElementById('ideaAdd');
  if(btn) btn.disabled = true;
  status('正在新建国家精神…');
  try{
    const r = await fetch('/api/add_idea', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root, id})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
    if(j.ok){
      const sInp = document.getElementById('ideaSearch');
      if(sInp) sInp.value = '';
      let hit = null;
      if(j.item){
        hit = _upsertDataItem('ideas', j.item);
      } else {
        await loadData();
        hit = (DATA.ideas||[]).find(i=>i.id===id);
      }
      if(hit){
        const modNames = new Set((DATA.roots || []).filter(rt=>rt && !rt.readonly && rt.name).map(rt=>rt.name));
        if(_ideaScope === 'mod' && !modNames.has(hit.source)){
          _ideaScope = 'all';
          const bAll = document.getElementById('ideaScopeAll');
          const bMod = document.getElementById('ideaScopeMod');
          if(bAll) bAll.classList.add('on');
          if(bMod) bMod.classList.remove('on');
        }
        renderIdeaList('');
        switchIdeaTab('basic');
        await selectIdea(hit);
        const nmEl = document.getElementById('ideaNameZ');
        if(nmEl) nmEl.focus();
      } else {
        renderIdeaList('');
      }
    }
  } finally {
    if(btn) btn.disabled = false;
  }
}

async function deleteIdeaSel(){
  if(!ideaSel){ status('先选择一个国家精神'); return; }
  if(!confirm('确定删除国家精神 ' + ideaSel.id + ' ？（可用 .bak 恢复）')) return;
  await withBusy('正在删除国家精神并刷新…', async ()=>{
    const r = await fetch('/api/delete_idea', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootByName(ideaSel.source), file: ideaSel.file, id: ideaSel.id})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
    if(j.ok){
      await loadData();
      ideaSel = null;
      document.getElementById('ideaRaw').value = '';
      document.getElementById('ideaTitle').textContent = '';
      renderIdeaList(document.getElementById('ideaSearch')?.value || '');
    }
  });
}

function addFxLine(line){
  const el = document.getElementById('edEffect'); if(!el) return;
  const cur = el.value.trim();
  el.value = (cur ? cur + '\n' : '') + line;
}

svg.addEventListener('mousedown', ev=>{
  if(ev.target.closest('.node')) return;
  pan = {x: ev.clientX, y: ev.clientY, vx: view.x, vy: view.y};
});

window.addEventListener('mousemove', ev=>{
  if(pan){ view.x = pan.vx + (ev.clientX - pan.x); view.y = pan.vy + (ev.clientY - pan.y); applyView(); }
});

window.addEventListener('mouseup', ()=>{ pan = null; });

svg.addEventListener('wheel', ev=>{
  ev.preventDefault();
  let dy = ev.deltaY;
  if(ev.deltaMode === 1) dy *= 16;                                   // 行模式
  else if(ev.deltaMode === 2) dy *= svg.getBoundingClientRect().height; // 页模式
  const factor = Math.min(1.6, Math.max(0.62, Math.exp(-dy * 0.0016)));
  applyZoomFactor(factor, ev.clientX, ev.clientY);
}, {passive:false});

try { if(localStorage.getItem('fe_zoom_anchor') === 'screen') zoomAnchor = 'screen'; } catch(e){}

function applyZoomFactor(factor, clientX, clientY){
  const rect = svg.getBoundingClientRect();
  const useMouse = zoomAnchor === 'mouse' && typeof clientX === 'number' && !isNaN(clientX);
  const ax = useMouse ? (clientX - rect.left) : rect.width / 2;
  const ay = useMouse ? (clientY - rect.top) : rect.height / 2;
  const k0 = view.k;
  const k1 = Math.min(32, Math.max(0.06, k0 * factor));   // 上限 32 倍：HOI4 的省界像素级编辑需要放大到很大
  if(Math.abs(k1 - k0) < 1e-4) return;
  const f = k1 / k0;
  // 让锚点下的场景坐标在缩放前后保持在同一屏幕位置
  view.x = ax - (ax - view.x) * f;
  view.y = ay - (ay - view.y) * f;
  view.k = k1;
  applyView();
  updateZoomLabel();
}

function updateZoomLabel(){
  const b = document.getElementById('zoomAnchorBtn');
  if(b) b.textContent = zoomAnchor === 'mouse' ? '🎯 鼠标缩放' : '🖥 屏幕缩放';
  const z = document.getElementById('zoomLevel');
  if(z) z.textContent = Math.round(view.k * 100) + '%';
}
