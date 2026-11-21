// 03-dom：DOM 句柄 + 跨面板复用的列表/来源提示小件（P4）
// themeSel / fsSel / search / mapOpEl 是 4 个在加载时求值的 getElementById 句柄；
// 其余是 tech / event / equip / idea 四个列表面板共用的「一行 + 来源说明 + 取原文」工具。

window.withBusy = async function(msg, fn){
  startLoading(msg);
  try{ return await fn(); }
  finally { stopLoading(); }
};

function openEquip(){
  document.getElementById('equipModal').style.display = 'flex';
  renderEquipList('');
  const first = ((DATA && DATA.equipment) || [])[0];
  if(first) selectEquip(first);
}

async function entrySource(root, file, layer){
  const k = (root || '') + '|' + (file || '') + '|' + (layer || '');
  if(_srcCache.has(k)) return _srcCache.get(k);
  let j = {};
  try{
    j = await (await fetch('/api/entry_source', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: root || '', file: file || '', layer: layer || ''})})).json();
  }catch(e){ return {}; }
  _srcCache.set(k, j);
  return j;
}

function srcHintHtml(j, elId){
  const idAttr = elId ? ' id="' + escapeHtml(elId) + '"' : '';
  if(!j || !j.ok || !j.layer) return '<div class="src-hint"' + idAttr + '></div>';
  const txt = j.readonly
    ? '来源: ' + j.layer + '（只读）· 保存时会复制到 ' + (j.adopt_to || '你的 mod')
    : '来源: ' + j.layer;
  return '<div class="src-hint' + (j.readonly ? ' ro' : '') + '"' + idAttr + '>' + escapeHtml(txt) + '</div>';
}

const _srcHintSeq = {};
function fillSrcHint(elId, root, file, layer){
  const el = document.getElementById(elId);
  if(!el) return;
  const seq = (_srcHintSeq[elId] = (_srcHintSeq[elId] || 0) + 1);
  el.outerHTML = '<div class="src-hint" id="' + elId + '">…</div>';
  entrySource(root, file, layer).then(function(j){
    if(_srcHintSeq[elId] !== seq) return;
    const el2 = document.getElementById(elId);
    if(el2) el2.outerHTML = srcHintHtml(j, elId);
  });
}

function _lastRoot(){
  const rs = (DATA && DATA.roots) || [];
  return rs.length ? rs[rs.length - 1].path : '';
}

function _writableRoot(){
  // 新建树/事件/科技/装备/精神优先写入最顶层非只读 mod（多级加载时防止写穿底层本体）
  const rs = (DATA && DATA.roots) || [];
  for(let i = rs.length - 1; i >= 0; i--){
    if(rs[i] && !rs[i].readonly && rs[i].path) return rs[i].path;
  }
  return _lastRoot();
}


function listRow(id, name, source, title){
  const d = document.createElement('div');
  d.className = 'lr';
  if(title) d.title = title;
  d.innerHTML = '<span class="lr-id">' + escapeHtml(id) + '</span>' +
                '<span class="lr-nm">' + escapeHtml(name || '') + '</span>' +
                (source ? '<span class="lr-src" title="来自 ' + escapeHtml(source) + '">' +
                          escapeHtml(source) + '</span>' : '');
  return d;
}


function renderEquipList(q){
  const box = document.getElementById('equipList'); if(!box || !DATA) return;
  q = (q || '').toLowerCase();
  const items = (DATA.equipment || []).filter(e=>!q || e.id.toLowerCase().includes(q) || (e.name||'').toLowerCase().includes(q));
  box.innerHTML = '';
  items.slice(0, 800).forEach(e=>{
    const d = listRow(e.id, e.name, e.source, e.file);
    d.onclick = ()=>selectEquip(e);
    box.appendChild(d);
  });
  if(!items.length) box.textContent = '没有匹配的装备';
}

function _snapFieldValues(ids){
  const snap = {};
  ids.forEach(fid=>{
    const el = document.getElementById(fid);
    if(el) snap[fid] = el.value;
  });
  return snap;
}

function _applyCleanFields(snap, pairs){
  pairs.forEach(([fid, val])=>{
    const el = document.getElementById(fid);
    if(el && el.value === snap[fid]) el.value = val;
  });
}

let _equipSelSeq = 0;
async function selectEquip(e){
  if(!e) return;
  const seq = ++_equipSelSeq;
  equipSel = e;
  document.getElementById('equipTitle').textContent = e.id + '   (' + e.file + ')';
  fillSrcHint('equipSrc', (typeof rootByName === 'function' ? rootByName(e.source) : '') || _lastRoot(), e.file, e.source);
  document.getElementById('equipNameZ').value = e.name || '';
  document.getElementById('equipPic').value = e.picture || '';
  const ep = e.props || {};
  document.getElementById('equipArch').value = ep.archetype || '';
  document.getElementById('equipIsArch').value = ep.is_archetype || '';
  document.getElementById('equipProduced').value = ep.can_be_produced || '';
  document.getElementById('equipDescZ').value = e.desc || '';
  document.getElementById('equipNameJa').value = '';
  document.getElementById('equipDescJa').value = '';
  document.getElementById('equipNameEn').value = '';
  document.getElementById('equipDescEn').value = '';
  const pg = document.getElementById('equipProps'); pg.innerHTML = '';
  const props = e.props || {};
  const keys = Object.keys(props);
  if(!keys.length){ pg.textContent = '（没有可识别的属性，请用脚本原文修改）'; }
  keys.forEach(k=>{
    const lab = document.createElement('label');
    lab.textContent = k;
    const inp = document.createElement('input');
    inp.type = 'text'; inp.value = props[k]; inp.dataset.prop = k;
    lab.appendChild(inp); pg.appendChild(lab);
  });
  const snap = _snapFieldValues([
    'equipNameZ', 'equipDescZ', 'equipNameJa', 'equipDescJa',
    'equipNameEn', 'equipDescEn', 'equipRaw', 'equipUpgrades', 'equipSlots'
  ]);
  const detail = await fetchRawDetail('equip', e.id);
  if(seq !== _equipSelSeq || equipSel !== e) return;
  const eqRaw = detail.raw || '';
  const loc = detail.loc || {};
  _applyCleanFields(snap, [
    ['equipNameZ', (loc && loc.name) || e.name || ''],
    ['equipDescZ', (loc && loc.desc) || e.desc || ''],
    ['equipNameJa', (loc && loc.name_ja) || ''],
    ['equipDescJa', (loc && loc.desc_ja) || ''],
    ['equipNameEn', (loc && loc.name_en) || ''],
    ['equipDescEn', (loc && loc.desc_en) || ''],
    ['equipRaw', eqRaw],
    ['equipUpgrades', extractBlock(eqRaw, 'upgrades')],
    ['equipSlots', extractBlock(eqRaw, 'module_slots')]
  ]);
}

async function saveEquip(){
  if(!equipSel){ status('先选择一件装备'); return; }
  const curId = equipSel.id;
  const btns = ['equipSave', 'equipSaveTop'].map(id=>document.getElementById(id)).filter(Boolean);
  btns.forEach(b=>{ b.disabled = true; });
  status('正在保存装备…');
  try{
    const props = {};
    document.querySelectorAll('#equipProps input[data-prop]').forEach(i=>{
      const v = (i.value || '').trim();
      if(v !== '') props[i.dataset.prop] = v;
    });
    [['archetype','equipArch'], ['is_archetype','equipIsArch'], ['can_be_produced','equipProduced']].forEach(pair=>{
      const v = (document.getElementById(pair[1]).value || '').trim();
      if(v !== '') props[pair[0]] = v;
    });
    const upg = (document.getElementById('equipUpgrades').value || '').trim();
    if(upg) props.upgrades_raw = upg;
    const slotsRaw = (document.getElementById('equipSlots').value || '').trim();
    if(slotsRaw) props.module_slots_raw = slotsRaw;
    const r = await fetch('/api/equip_save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootByName(equipSel.source), file: equipSel.file, id: equipSel.id,
        raw: document.getElementById('equipRaw').value,
        props,
        name: document.getElementById('equipNameZ').value,
        desc: document.getElementById('equipDescZ').value,
        name_ja: document.getElementById('equipNameJa').value,
        desc_ja: document.getElementById('equipDescJa').value,
        name_en: document.getElementById('equipNameEn').value,
        desc_en: document.getElementById('equipDescEn').value,
        picture: document.getElementById('equipPic').value.trim()})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
    if(j.ok){
      const q = document.getElementById('equipSearch')?.value || '';
      if(j.item){
        _upsertDataItem('equipment', j.item);
        renderEquipList(q);
        await selectEquip(j.item);
      } else {
        await loadData();
        renderEquipList(q);
        const hit = (DATA.equipment||[]).find(x=>x.id===curId);
        if(hit) await selectEquip(hit);
      }
    }
  } finally {
    btns.forEach(b=>{ b.disabled = false; });
  }
}

const themeSel = document.getElementById('themeSel');

const fsSel = document.getElementById('fsSel');

const search = document.getElementById('search');

const mapOpEl = document.getElementById('mapOpacity');

function _upsertDataItem(listKey, item){
  if(!DATA || !item || !item.id) return null;
  if(!Array.isArray(DATA[listKey])) DATA[listKey] = [];
  const arr = DATA[listKey];
  const idx = arr.findIndex(x=>x && x.id === item.id);
  if(idx >= 0) arr[idx] = item;
  else arr.unshift(item);
  return item;
}

function _removeDataItem(listKey, id){
  if(!DATA || !id || !Array.isArray(DATA[listKey])) return false;
  const arr = DATA[listKey];
  let removed = false;
  for(let i = arr.length - 1; i >= 0; i--){
    if(arr[i] && arr[i].id === id){
      arr.splice(i, 1);
      removed = true;
    }
  }
  return removed;
}

async function fetchRawDetail(kind, id){
  try {
    const r = await fetch('/api/raw?kind=' + encodeURIComponent(kind || '') + '&id=' + encodeURIComponent(id || ''));
    const j = await r.json();
    return {
      raw: (j && typeof j.raw === 'string') ? j.raw : '',
      loc: (j && j.loc && typeof j.loc === 'object') ? j.loc : {}
    };
  } catch(e){
    return {raw: '', loc: {}};
  }
}
