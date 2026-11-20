// 12-tech：科技（P4）
// 科技列表面板 + 科技树画布（drawTechTree 163 行 / tt* 拖拽 / 国家科技清单）。

async function addTech(){
  const tid = prompt('新科技 ID（字母数字下划线）：');
  if(!tid) return;
  const folder = prompt('所属科技组 folder：', ttFolder || 'custom_folder');
  if(!folder) return;
  const root = _writableRoot();
  if(!root){ status('先加载或新建一个可写的模组', true); return; }
  const r = await fetch('/api/tech_add', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root, id: tid, folder})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok){ await loadData(); renderTechList(''); }
}

async function deleteTechSel(){
  if(!techSel){ status('先选择一项科技'); return; }
  if(!confirm('确定删除科技 ' + techSel.id + ' ？（可用 .bak 恢复）')) return;
  const r = await fetch('/api/tech_delete', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: rootByName(techSel.source), file: techSel.file, id: techSel.id})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok){ techSel = null; await loadData(); renderTechList(''); }
}

function openTech(){
  document.getElementById('techModal').style.display = 'flex';
  renderTechList('');
  const first = ((DATA && DATA.techs) || [])[0];
  if(first) selectTech(first);
  switchTechTab('edit');
}

function switchTechTab(mode){
  document.getElementById('techEditPane').style.display = mode === 'edit' ? 'flex' : 'none';
  document.getElementById('techTreePane').style.display = mode === 'tree' ? 'flex' : 'none';
  document.getElementById('techTabEdit').classList.toggle('on', mode === 'edit');
  document.getElementById('techTabTree').classList.toggle('on', mode === 'tree');
  if(mode === 'tree'){
    const folders = techFolderNames();
    if(!ttFolder || !folders.includes(ttFolder)) ttFolder = folders.includes('infantry_folder') ? 'infantry_folder' : (folders[0] || '');
    renderTechFolderTabs(folders);
    drawTechTree(ttFolder);
    ttView = {x:0, y:0, k:1};
    applyTT();
    fitTT();
  }
}

async function renderTechFolderTabs(folders){
  const box = document.getElementById('techFolderTabs');
  if(!box) return;
  if(!iconCache.tech){
    try {
      const r = await fetch('/api/icons?kind=tech');
      iconCache.tech = await r.json();
    } catch(e){ iconCache.tech = {list: [], map: {}}; }
  }
  const map = (iconCache.tech && iconCache.tech.map) || {};
  box.innerHTML = '';
  folders.forEach(f=>{
    const b = document.createElement('button');
    b.className = 'tt-tab' + (f === ttFolder ? ' on' : '');
    const icon = map['GFX_' + f + '_tab'];
    b.innerHTML = (icon ? '<img src="' + icon + '">' : '') + escapeHtml(f.replace(/_folder$/, ''));
    b.title = f;
    b.onclick = ()=>{ ttFolder = f; switchTechTab('tree'); };
    box.appendChild(b);
  });
}

function applyTechHighlight(){
  const view = document.getElementById('ttView');
  if(!view) return;
  const el = document.getElementById('techSearch');
  const q = ((el && el.value) || '').trim().toLowerCase();
  view.querySelectorAll('.tt-node').forEach(n=>{
    if(!q){ n.classList.remove('dim', 'hit'); return; }
    const hit = (n.textContent || '').toLowerCase().includes(q);
    n.classList.toggle('hit', hit);
    n.classList.toggle('dim', !hit);
  });
}

function showTechDetail(t){
  const d = document.getElementById('techDetail');
  if(!d) return;
  const pre = (t.prereq || []).join(', ') || '无';
  const leads = (t.leads || []).join(', ') || '无';
  const folderIds = new Set(((DATA && DATA.techs) || []).filter(x=>x.path === t.path).map(x=>x.id));
  const cross = (t.prereq || []).filter(p=>!folderIds.has(p));
  d.innerHTML = '<h4>' + escapeHtml(t.name || t.id) + '</h4>' +
    '<div class="row">id: ' + escapeHtml(t.id) + '</div>' +
    '<div class="row">年份: ' + escapeHtml(t.year || '') + '　花费: ' + escapeHtml(t.cost || '') + '</div>' +
    '<div class="row">科技组: ' + escapeHtml(t.path || '') + '</div>' +
    '<div class="row">前置: ' + escapeHtml(pre) + '</div>' +
    (cross.length ? '<div class="row" style="color:#d8b878">跨组前置: ' + escapeHtml(cross.join(', ')) + '</div>' : '') +
    '<div class="row">后续: ' + escapeHtml(leads) + '</div>' +
    '<div style="display:flex;gap:6px;margin-top:8px"><button class="btn" id="ttEditBtn">编辑此科技</button><button class="btn" id="ttCloseBtn">关闭</button></div>';
  d.classList.add('show');
  document.getElementById('ttCloseBtn').onclick = ()=>d.classList.remove('show');
  document.getElementById('ttEditBtn').onclick = ()=>{
    d.classList.remove('show');
    selectTech(t);
    switchTechTab('edit');
  };
}

function renderTechList(q){
  const box = document.getElementById('techList'); if(!box || !DATA) return;
  q = (q || '').toLowerCase();
  const items = (DATA.techs || []).filter(t=>!q || t.id.toLowerCase().includes(q) || (t.name||'').toLowerCase().includes(q));
  box.innerHTML = '';
  items.slice(0, 800).forEach(t=>{
    const d = listRow(t.id, t.name, t.source, t.file);
    d.onclick = ()=>selectTech(t);
    box.appendChild(d);
  });
  if(!items.length) box.textContent = '没有匹配的科技';
}

function extractBlock(text, key){
  const re = new RegExp('(^|\\n)\\s*' + key + '\\s*=\\s*\\{');
  const m = re.exec(text || '');
  if(!m) return '';
  let i = text.indexOf('{', m.index), d = 0;
  for(let j = i; j < text.length; j++){
    if(text[j] === '{') d++;
    else if(text[j] === '}'){ d--; if(d === 0) return text.slice(m.index, j + 1).trim(); }
  }
  return '';
}

async function selectTech(t){
  techSel = t;
  document.getElementById('techTitle').textContent = t.id + '   (' + t.file + ')';
  fillSrcHint('techSrc', _lastRoot(), t.file, t.source);
  document.getElementById('techNameZ').value = t.name || '';
  document.getElementById('techDescZ').value = '';
  document.getElementById('techNameJa').value = '';
  document.getElementById('techDescJa').value = '';
  document.getElementById('techNameEn').value = '';
  document.getElementById('techDescEn').value = '';
  document.getElementById('techYear').value = t.year || '';
  document.getElementById('techCost').value = t.cost || '';
  document.getElementById('techPath').value = t.path || '';
  const raw = await fetchRaw('tech', t.id);
  document.getElementById('techPrereq').value = extractBlock(raw, 'prerequisite');
  document.getElementById('techEnable').value = extractBlock(raw, 'enable_equipments');
  document.getElementById('techSub').value = extractBlock(raw, 'sub_technologies');
  document.getElementById('techRaw').value = raw;
}

async function saveTech(){
  if(!techSel){ status('先选择一项科技'); return; }
  const props = {
    year: document.getElementById('techYear').value.trim(),
    research_cost: document.getElementById('techCost').value.trim(),
    path: document.getElementById('techPath').value.trim(),
    prereq_raw: document.getElementById('techPrereq').value.trim(),
    enable_equipments_raw: document.getElementById('techEnable').value.trim(),
    sub_technologies_raw: document.getElementById('techSub').value.trim()
  };
  const r = await fetch('/api/tech_save', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: rootByName(techSel.source), file: techSel.file, id: techSel.id,
      raw: document.getElementById('techRaw').value, props,
      name: document.getElementById('techNameZ').value,
      desc: document.getElementById('techDescZ').value,
      name_ja: document.getElementById('techNameJa').value,
      desc_ja: document.getElementById('techDescJa').value,
      name_en: document.getElementById('techNameEn').value,
      desc_en: document.getElementById('techDescEn').value})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok){ await loadData(); renderTechList(document.getElementById('techSearch').value); }
}


function ttUpdateHint(){
  const btn = document.getElementById('ttSavePos');
  const hint = document.getElementById('ttPosHint');
  if(!btn || !hint) return;
  const n = ttDirty.size;
  btn.textContent = n ? ('💾 保存位置（' + n + '）') : '💾 保存位置';
  btn.classList.toggle('primary', n > 0);
  if(!ttOrigin){
    hint.textContent = '这个 folder 里的科技还没有 position，先在文件里设置后再拖';
  } else if(ttEdit){
    hint.textContent = n ? ('已改 ' + n + ' 个，点保存写回 folder.position') : '拖动节点改位置，松手后点保存';
  } else {
    hint.textContent = '写回的是 folder.position 的 x / y，和游戏读的是同一处';
  }
}


function ttToggleEdit(){
  ttEdit = !ttEdit;
  document.getElementById('ttEditToggle').classList.toggle('on', ttEdit);
  updateTechTreeShell();
  status(ttEdit ? '科技树位置编辑已开启：拖动节点，然后点「保存位置」' : '科技树位置编辑已关闭');
}


function updateTechTreeShell(){
  const svg = document.getElementById('techSvg');
  if(svg) svg.style.cursor = ttEdit ? 'default' : '';
  if(ttFolder) drawTechTree(ttFolder);
  ttUpdateHint();
}


function ttStartDrag(ev, node){
  if(!ttEdit || !ttOrigin) return;
  ev.stopPropagation(); ev.preventDefault();
  const t = ((DATA && DATA.techs) || []).find(x=>x.id === node.dataset.id);
  if(!t) return;
  const m = /translate\(([-\d.]+),([-\d.]+)\)/.exec(node.getAttribute('transform')) || [0, 0, 0];
  ttDragNode = { node, t, ox: parseFloat(m[1]), oy: parseFloat(m[2]), sx: ev.clientX, sy: ev.clientY };
  window.addEventListener('mousemove', ttOnDrag);
  window.addEventListener('mouseup', ttEndDrag, { once: true });
}


function ttScale(){
  const svg = document.getElementById('techSvg');
  const r = svg.getBoundingClientRect();
  const vb = svg.viewBox && svg.viewBox.baseVal;
  const base = (vb && vb.width) ? (vb.width / r.width) : 1;
  return base / (ttView.k || 1);
}


function ttOnDrag(ev){
  if(!ttDragNode) return;
  const s = ttScale();
  const nx = ttDragNode.ox + (ev.clientX - ttDragNode.sx) * s;
  const ny = ttDragNode.oy + (ev.clientY - ttDragNode.sy) * s;
  ttDragNode.nx = nx; ttDragNode.ny = ny;
  ttDragNode.node.setAttribute('transform', 'translate(' + nx + ',' + ny + ')');
}


function ttEndDrag(){
  window.removeEventListener('mousemove', ttOnDrag);
  if(!ttDragNode) return;
  const d = ttDragNode; ttDragNode = null;
  if(d.nx == null) return;
  const fx = Math.round((d.nx - 120) / 300 + ttOrigin.minx);
  const fy = Math.round((d.ny - 70) / 110 + ttOrigin.miny);
  const snappedX = 120 + (fx - ttOrigin.minx) * 300;
  const snappedY = 70 + (fy - ttOrigin.miny) * 110;
  d.node.setAttribute('transform', 'translate(' + snappedX + ',' + snappedY + ')');
  d.t.fx = fx; d.t.fy = fy;
  ttDirty.set(d.t.id, { id: d.t.id, x: fx, y: fy, file: d.t.file, source: d.t.source });
  ttUpdateHint();
  status(d.t.id + '：x=' + fx + ' y=' + fy + '（未保存）');
}


async function ttSavePositions(){
  if(!ttDirty.size){ status('没有改过位置'); return; }
  const items = [...ttDirty.values()];
  let ok = 0, fail = [];
  for(const it of items){
    try{
      const r = await (await fetch('/api/tech_move', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({root: rootByName(it.source), rel: it.file, tid: it.id, x: it.x, y: it.y})})).json();
      if(r.ok) ok++; else fail.push(it.id + '：' + (r.msg || '失败'));
    }catch(e){ fail.push(it.id + '：' + e.message); }
  }
  ttDirty.clear();
  if(ok) await loadData();
  updateTechTreeShell();
  if(fail.length) status('保存 ' + ok + ' 个，失败 ' + fail.length + '：' + fail[0], true);
  else status('已保存 ' + ok + ' 个科技的位置（写回 folder.position）');
}



function applyTT(){
  const v = document.getElementById('ttView');
  if(v) v.setAttribute('transform', 'translate(' + ttView.x + ',' + ttView.y + ') scale(' + ttView.k + ')');
}

function drawTechTree(folder){
  const svg = document.getElementById('techSvg');
  const list = ((DATA && DATA.techs) || []).filter(t=>(t.path || '其他') === folder);
  const hasPos = list.some(t=>typeof t.fx === 'number' && typeof t.fy === 'number');
  const pos = {}; let maxRow = 0;
  if(hasPos){
    const xs = list.map(t=>typeof t.fx === 'number' ? t.fx : 0);
    const ys = list.map(t=>typeof t.fy === 'number' ? t.fy : 0);
    const minx = Math.min.apply(null, xs), miny = Math.min.apply(null, ys);
    ttOrigin = {minx: minx, miny: miny};
    list.forEach(t=>{
      const x = typeof t.fx === 'number' ? t.fx : 0;
      const y = typeof t.fy === 'number' ? t.fy : 0;
      pos[t.id] = {x: 120 + (x - minx) * 300, y: 70 + (y - miny) * 110, t};
      maxRow = Math.max(maxRow, y - miny);
    });
  } else {
    ttOrigin = null;
    const byYear = {};
    list.forEach(t=>{ const y = t.year || '?'; (byYear[y] = byYear[y] || []).push(t); });
    const years = Object.keys(byYear).sort((a,b)=>(parseInt(a)||9999)-(parseInt(b)||9999) || a.localeCompare(b));
    const byId = {};
    list.forEach(t=>{ byId[t.id] = t; });
    const depth = {};
    function dep(id, seen){
      if(depth[id] != null) return depth[id];
      if(seen.has(id)) return 0;
      seen.add(id);
      let d = 0;
      const ps = (byId[id] && byId[id].prereq) || [];
      const visit = p=>{ if(byId[p]) d = Math.max(d, dep(p, seen) + 1); };
      ps.forEach(g=>{
        if(Array.isArray(g)) g.forEach(visit);
        else if(typeof g === 'string') visit(g);
      });
      depth[id] = d;
      return d;
    }
    // 循环依赖（A→B→A）在两边的 depth 会算成同一个值，节点直接叠在一起看不清。
    // 这里记录「同一年 + 同一深度」已经用了几个位置，多出来的横向错开。
    years.forEach((y, xi)=>{
      const arr = byYear[y].sort((a,b)=>dep(a.id, new Set()) - dep(b.id, new Set()) || a.id.localeCompare(b.id));
      const used = {};
      arr.forEach(t=>{
        const d = dep(t.id, new Set());
        const k = String(d);
        const slot = used[k] || 0;
        used[k] = slot + 1;
        // 第一个占正常位置，后面的往右挪 34px 并轻微下移，形成斜排
        pos[t.id] = {x: 140 + xi * 340 + slot * 34, y: 70 + d * 100 + slot * 8, t};
        maxRow = Math.max(maxRow, d);
      });
    });
  }
  let edges = '';
  const hasExplicit = new Set();
  list.forEach(t=>{
    const drawEdge = p=>{
      if(pos[p]){
        hasExplicit.add(t.id);
        edges += '<line class="tt-edge" x1="' + (pos[p].x + 260) + '" y1="' + (pos[p].y + 32) + '" x2="' + pos[t.id].x + '" y2="' + (pos[t.id].y + 32) + '"/>';
      }
    };
    (t.prereq || []).forEach(p=>{
      if(Array.isArray(p)) p.forEach(drawEdge);
      else if(typeof p === 'string') drawEdge(p);
    });
  });
  list.forEach(t=>{
    if(hasExplicit.has(t.id)) return;
    const b = pos[t.id]; if(!b) return;
    let best = null;
    list.forEach(o=>{
      if(o.id === t.id) return;
      const a = pos[o.id]; if(!a) return;
      if(Math.abs(a.x - b.x) < 1 && a.y < b.y){
        if(!best || a.y > pos[best.id].y) best = o;
      }
    });
    if(!best){
      list.forEach(o=>{
        if(o.id === t.id) return;
        const a = pos[o.id]; if(!a) return;
        if(Math.abs(a.y - b.y) < 1 && a.x < b.x){
          if(!best || a.x > pos[best.id].x) best = o;
        }
      });
    }
    if(best){
      const a = pos[best.id];
      edges += '<line class="tt-edge inferred" x1="' + (a.x + 260) + '" y1="' + (a.y + 32) + '" x2="' + b.x + '" y2="' + (b.y + 32) + '"/>';
    }
  });
  let nodes = '';
  const map = (DATA && DATA.techIconMap) || {};
  const folderIcon = map['GFX_' + folder + '_tab'] || '';
  list.forEach(t=>{
    const p = pos[t.id]; if(!p) return;
    const icon = folderIcon ? '<image href="' + folderIcon + '" x="8" y="16" width="32" height="32" preserveAspectRatio="xMidYMid meet"/>' : '';
    nodes += '<g class="tt-node" data-id="' + escapeHtml(t.id) + '" transform="translate(' + p.x + ',' + p.y + ')">' +
      '<rect width="260" height="64" rx="8"/>' + icon +
      '<text x="48" y="22">' + escapeHtml((t.name && t.name !== t.id) ? t.name : t.id) + '</text>' +
      '<text class="meta" x="48" y="38">' + escapeHtml(t.id) + '</text>' +
      '<text class="meta" x="48" y="54">cost ' + escapeHtml(String(t.cost || 1)) + '</text>' +
      '<text class="meta" x="250" y="22" text-anchor="end">' + escapeHtml(t.year || '') + '</text>' +
      '<title>' + escapeHtml((t.name || t.id) + '  (' + t.id + ')') + '\n前置: ' + escapeHtml((t.prereq || []).join(', ') || '无') + '</title>' +
      '<circle class="tt-link" data-id="' + escapeHtml(t.id) + '" cx="260" cy="32" r="7"/></g>';
  });
  const view = document.getElementById('ttView');
  view.innerHTML = edges + nodes;
  applyTechHighlight();
  let maxX = 0;
  Object.values(pos).forEach(p=>{ maxX = Math.max(maxX, p.x + 260); });
  const w = Math.max(400, maxX + 140), h = 70 + (maxRow + 1) * 110 + 80;
  view.dataset.w = w; view.dataset.h = h;
  view.querySelectorAll('.tt-node').forEach(n=>{
    n.addEventListener('mousedown', e=>ttStartDrag(e, n));
    n.addEventListener('click', e=>{
      e.stopPropagation();
      const t = ((DATA && DATA.techs) || []).find(x=>x.id === n.dataset.id);
      if(t){ showTechDetail(t); }
    });
  });
  ttUpdateHint();
  view.querySelectorAll('.tt-link').forEach(h=>{
    h.addEventListener('mousedown', ev=>{
      ev.stopPropagation(); ev.preventDefault();
      const srcEl = h.closest('.tt-node');
      const srcId = h.dataset.id;
      const tSrc = ((DATA && DATA.techs) || []).find(x=>x.id === srcId);
      if(!tSrc) return;
      const m = /translate\(([-\d.]+),([-\d.]+)\)/.exec(srcEl.getAttribute('transform')) || [0, 0, 0];
      const x0 = parseFloat(m[1]) + 260, y0 = parseFloat(m[2]) + 32;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('class', 'tt-temp');
      line.setAttribute('x1', x0); line.setAttribute('y1', y0);
      line.setAttribute('x2', x0); line.setAttribute('y2', y0);
      view.appendChild(line);
      const toSvg = e2=>{
        const p = svg.createSVGPoint(); p.x = e2.clientX; p.y = e2.clientY;
        return p.matrixTransform(view.getScreenCTM().inverse());
      };
      const mv = e2=>{ const p = toSvg(e2); line.setAttribute('x2', p.x); line.setAttribute('y2', p.y); };
      const up = e2=>{
        window.removeEventListener('mousemove', mv);
        line.remove();
        const el = document.elementFromPoint(e2.clientX, e2.clientY);
        const target = el && el.closest ? el.closest('.tt-node') : null;
        if(target && target.dataset.id !== srcId){
          fetch('/api/tech_link', {method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({root: rootByName(tSrc.source), file: tSrc.file,
              source: srcId, target: target.dataset.id})})
            .then(r=>r.json()).then(j=>{
              status(j.msg || '', !j.ok);
              if(j.ok) loadData().then(()=>drawTechTree(ttFolder));
            });
        }
      };
      window.addEventListener('mousemove', mv);
      window.addEventListener('mouseup', up, {once:true});
    });
  });
}

function fitTT(){
  const view = document.getElementById('ttView');
  const svg = document.getElementById('techSvg');
  const w = parseFloat(view.dataset.w || 1000), h = parseFloat(view.dataset.h || 800);
  const r = svg.getBoundingClientRect();
  const k = Math.min((r.width - 40) / w, (r.height - 40) / h, 1.4);
  ttView.k = Math.max(0.1, k);
  ttView.x = (r.width - w * ttView.k) / 2;
  ttView.y = (r.height - h * ttView.k) / 2;
  applyTT();
}


// v1.21.4 国家初始科技（列表式）
(function(){
  let CTAG = '', CTECH = null;

  function msg(t, bad){
    const el = document.getElementById('ctechMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function renderGroups(groups){
    const box = document.getElementById('ctechList');
    if(!box) return;
    if(!groups.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:4px">没有科技</div>'; return; }
    box.innerHTML = groups.map(function(g, gi){
      const onN = g.techs.filter(function(x){ return x.on; }).length;
      return '<details' + (gi < 2 ? ' open' : '') + ' style="margin-bottom:2px">'
        + '<summary style="font-size:11px;cursor:pointer;padding:2px 4px;'
        + 'background:var(--input);border-radius:3px">'
        + g.folder + ' <span style="color:var(--t3);font-size:10px">' + onN + '/' + g.techs.length + '</span>'
        + '</summary>'
        + '<div style="padding:2px 0 4px 8px">'
        + g.techs.map(function(t){
            return '<label style="display:flex;gap:5px;align-items:center;font-size:10.5px;'
              + 'font-family:Consolas,monospace;padding:1px 0;cursor:pointer"'
              + ' title="' + (t.name || t.id) + (t.year ? '　' + t.year + ' 年' : '') + '">'
              + '<input type="checkbox" class="ctech-cb" data-id="' + t.id + '"' + (t.on ? ' checked' : '') + '>'
              + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
              + (t.on ? 'color:var(--text)' : 'color:var(--t3)') + '">' + t.id + '</span>'
              + (t.year ? '<span style="color:var(--t3);font-size:9px">' + t.year + '</span>' : '')
              + '</label>';
          }).join('')
        + '</div></details>';
    }).join('');
    box.querySelectorAll('.ctech-cb').forEach(function(cb){
      cb.onchange = function(){ toggle(cb.dataset.id, cb.checked); };
    });
  }

  async function load(){
    const tag = ((document.getElementById('ctechTag')||{}).value || '').trim().toUpperCase();
    if(!tag){ msg('填国家 tag', true); return; }
    CTAG = tag;
    msg('读取中…');
    const r = await (await fetch('/api/country_techs', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({tag: tag})})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    CTECH = r;
    msg(r.msg || '');
    renderGroups(r.groups || []);
  }

  async function toggle(id, on){
    if(!CTAG) return;
    msg('写入中…');
    const r = await (await fetch('/api/country_tech_toggle', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: CTAG, tech: id, on: on})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok) status(r.msg);
  }

  function bind(){
    const b = document.getElementById('ctechLoad');
    if(b && !b.dataset.bound){ b.dataset.bound = '1'; b.onclick = load; }
    const t = document.getElementById('ctechTag');
    if(t && !t.dataset.bound){
      t.dataset.bound = '1';
      t.addEventListener('keydown', function(e){ if(e.key === 'Enter') load(); });
    }
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.5 科技树预览（SVG）
(function(){
  const CW = 76, CH = 30, GAPX = 8, GAPY = 14, PAD = 20;

  function msg(t, bad){
    const el = document.getElementById('ttMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function chainSig(){
    const d = (typeof DATA !== 'undefined' && DATA) ? DATA : {};
    const arr = (d.layers && d.layers.length) ? d.layers : (d.roots || []);
    return arr.map(function(x){ return x.path || x.name || ''; }).join('|');
  }

  async function loadFolders(){
    const sel = document.getElementById('ttFolder');
    if(!sel) return;
    // 启动期接口回 503，拿到的是 {"ok":false,"code":"LOADING"}，会被下面当成错误弹出来。
    // 排队到 boot 就绪后再取。
    if(window.XRBOOT && !window.XRBOOT.ready){
      window.XRBOOT.after(loadFolders);
      return;
    }
    const sig = chainSig();
    if(sel.dataset.sig === sig && sel.options.length > 1) return;
    const prev = sel.value;
    const r = await (await fetch('/api/tech_graph', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({folder:''})})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    sel.innerHTML = '<option value="">（选目录）</option>' + (r.folders || []).map(function(f){
      return '<option value="' + f.folder + '">' + f.folder + '（' + f.count + '）</option>';
    }).join('');
    if(prev && Array.from(sel.options).some(function(o){ return o.value === prev; })){
      sel.value = prev;
    }
    sel.dataset.sig = sig;
    msg(r.msg || '');
  }

  function shortName(n){
    const s = (n.name && n.name !== n.id) ? n.name : n.id;
    return s.length > 9 ? s.slice(0, 9) + '…' : s;
  }

  async function draw(){
    const sel = document.getElementById('ttFolder');
    const svg = document.getElementById('techTreeSvg');
    const body = document.getElementById('ttBody');
    if(!sel || !svg) return;
    const folder = sel.value;
    if(!folder){ msg('先选目录', true); return; }
    const tag = ((document.getElementById('ctechTag')||{}).value || '').trim().toUpperCase();
    msg('读取中…');
    const g = await (await fetch('/api/tech_graph', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({folder: folder, tag: tag || null})})).json();
    if(!g.ok){ msg(g.msg || '失败', true); svg.innerHTML = ''; return; }
    msg(g.msg || '');
    const nodes = g.nodes || [];
    if(!nodes.length){ svg.innerHTML = ''; return; }

    // 坐标去重：fx/fy 是格子坐标，可能有小数
    const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
    const minX = Math.min(...xs), minY = Math.min(...ys);
    const maxX = Math.max(...xs), maxY = Math.max(...ys);
    const cols = Math.max(1, Math.round(maxX - minX * 1) + 1);
    const rows = Math.max(1, Math.round(maxY - minY * 1) + 1);
    const W = Math.max(200, (maxX - minX + 1) * (CW + GAPX) + PAD * 2);
    const H = Math.max(120, (maxY - minY + 1) * (CH + GAPY) + PAD * 2);

    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('data-w', W);
    svg.setAttribute('data-h', H);
    svg.style.width = '100%';
    svg.style.height = '100%';

    const px = function(v){ return PAD + (v - minX) * (CW + GAPX) + CW / 2; };
    const py = function(v){ return PAD + (v - minY) * (CH + GAPY) + CH / 2; };
    const pos = {};
    nodes.forEach(function(n){ pos[n.id] = [px(n.x), py(n.y)]; });

    // 前置表（用于高亮）
    const PRE = {};
    nodes.forEach(function(n){ PRE[n.id] = []; });
    (g.edges || []).forEach(function(e){
      if(PRE[e[1]]) PRE[e[1]].push(e[0]);
    });

    let out = '<g id="ttEdges">';
    (g.edges || []).forEach(function(e){
      const a = pos[e[0]], b = pos[e[1]];
      if(!a || !b) return;
      out += '<line class="tt-edge" data-a="' + e[0] + '" data-b="' + e[1] + '"'
        + ' x1="' + a[0] + '" y1="' + (a[1] + CH/2 - 2) + '"'
        + ' x2="' + b[0] + '" y2="' + (b[1] - CH/2 + 2) + '"'
        + ' stroke="#3d4653" stroke-width="1.2"' + ((e[0] === e[1]) ? ' opacity="0"' : '') + '/>';
    });
    out += '</g><g id="ttNodes">';
    nodes.forEach(function(n){
      const p = pos[n.id];
      const fill = n.on ? '#2e6b3a' : '#1f2530';
      const stroke = n.on ? '#5fd07a' : '#3a4453';
      const tc = n.on ? '#d9ffe2' : '#9aa5b4';
      out += '<g class="tt-node" data-id="' + n.id + '" data-year="' + (n.year||'') + '">'
        + '<rect x="' + (p[0] - CW/2) + '" y="' + (p[1] - CH/2) + '" width="' + CW + '" height="' + CH
        + '" rx="3" fill="' + fill + '" stroke="' + stroke + '" stroke-width="1"/>'
        + '<text x="' + p[0] + '" y="' + (p[1] - 1) + '" text-anchor="middle" font-size="9"'
        + ' font-family="Consolas,monospace" fill="' + tc + '">' + shortName(n) + '</text>'
        + '<text x="' + p[0] + '" y="' + (p[1] + 9) + '" text-anchor="middle" font-size="7.5"'
        + ' font-family="Consolas,monospace" fill="' + (n.on ? '#a7e8b8' : '#6b7688') + '">'
        + (n.year || '') + '</text>'
        + '<title>' + n.id + '\n' + (n.name || '') + (n.year ? '\n' + n.year + ' 年' : '') + '</title>'
        + '</g>';
    });
    out += '</g>';
    svg.innerHTML = out;

    // 接缩放拖拽
    if(body && !svg._pan && typeof makePannable === 'function'){
      try{ svg._pan = makePannable(svg, body); }catch(e){}
    }

    // 点节点：高亮整条前置链
    let curHi = null;
    svg.querySelectorAll('.tt-node').forEach(function(gn){
      gn.style.cursor = 'pointer';
      gn.onclick = function(){
        const id = gn.dataset.id;
        if(curHi === id){ curHi = null; clearHi(svg); msg('已取消高亮'); return; }
        curHi = id;
        const chain = new Set([id]);
        const walk = function(x){
          (PRE[x] || []).forEach(function(p){ if(!chain.has(p)){ chain.add(p); walk(p); } });
        };
        walk(id);
        clearHi(svg);
        svg.querySelectorAll('.tt-node').forEach(function(g2){
          if(chain.has(g2.dataset.id)){
            const r = g2.querySelector('rect');
            if(r) r.setAttribute('stroke', '#e8b34a');
            if(r) r.setAttribute('stroke-width', '2');
          }
        });
        svg.querySelectorAll('.tt-edge').forEach(function(l){
          if(chain.has(l.dataset.a) && chain.has(l.dataset.b)){
            l.setAttribute('stroke', '#e8b34a');
            l.setAttribute('stroke-width', '2');
          }
        });
        msg(id + ' 的前置链：' + (chain.size - 1) + ' 个');
      };
    });
  }

  function clearHi(svg){
    svg.querySelectorAll('.tt-node rect').forEach(function(r){
      r.setAttribute('stroke-width', '1');
      const parent = r.parentNode;
      const on = parent.querySelector('text').getAttribute('fill') === '#d9ffe2';
      r.setAttribute('stroke', on ? '#5fd07a' : '#3a4453');
    });
    svg.querySelectorAll('.tt-edge').forEach(function(l){
      l.setAttribute('stroke', '#3d4653');
      l.setAttribute('stroke-width', '1.2');
    });
  }

  function bind(){
    const b = document.getElementById('ttDraw');
    if(b && !b.dataset.bound){ b.dataset.bound = '1'; b.onclick = draw; }
    const s2 = document.getElementById('ttFolder');
    if(s2 && !s2.dataset.bound){
      s2.dataset.bound = '1';
      s2.onchange = draw;
      s2.onfocus = function(){ loadFolders(); };
    }
    if(s2) loadFolders();
  }
  window.techRefreshFolders = function(){ return loadFolders(); };
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();
