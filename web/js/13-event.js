// 13-event：事件（P4）
// 事件列表面板 + 事件关系图（214 行 IIFE）+ 事件改完写回编辑器。

function openEvents(){
  document.getElementById('eventModal').style.display = 'flex';
  renderEventList('');
  const first = ((DATA && DATA.events) || [])[0];
  if(first) selectEvent(first);
}

function renderEventList(q){
  const box = document.getElementById('eventList'); if(!box || !DATA) return;
  q = (q || '').toLowerCase();
  const items = (DATA.events || []).filter(e=>!q || e.id.toLowerCase().includes(q) || (e.title||'').toLowerCase().includes(q));
  box.innerHTML = '';
  items.slice(0, 800).forEach(e=>{
    const d = listRow(e.id, e.title, e.source, e.file);
    d.dataset.eventId = e.id;
    if(eventSel && eventSel.id === e.id) d.classList.add('on');
    d.onclick = ()=>selectEvent(e);
    box.appendChild(d);
  });
  if(!items.length) box.textContent = '没有匹配的事件';
}

function parseEventOptions(raw){
  const out = [];
  const re = /option\s*=\s*\{/g;
  let m;
  while((m = re.exec(raw))){
    const b = raw.indexOf('{', m.index);
    let d = 0, e = b;
    for(; e < raw.length; e++){
      if(raw[e] === '{') d++;
      else if(raw[e] === '}'){ d--; if(d === 0) break; }
    }
    const inner = raw.slice(b + 1, e);
    const nm = inner.match(/name\s*=\s*"?([A-Za-z0-9_.\-]+)"?/);
    out.push({start: m.index, end: e + 1, key: nm ? nm[1] : '', inner});
  }
  return out;
}

function renderEventOptions(raw, optLoc){
  const box = document.getElementById('eventOptions');
  if(!box) return;
  let locMap = optLoc;
  if(locMap === undefined){
    locMap = {};
    box.querySelectorAll('input[data-key]').forEach(inp=>{
      if(inp.dataset.key) locMap[inp.dataset.key] = inp.value || '';
    });
  }
  box.innerHTML = '';
  eventOptionBlocks = parseEventOptions(raw);
  if(!eventOptionBlocks.length){ box.textContent = '（这个事件还没有 option，建议至少加一个）'; return; }
  eventOptionBlocks.forEach((o, idx)=>{
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:4px';
    const key = document.createElement('span');
    key.className = 'k'; key.style.cssText = 'min-width:120px';
    key.textContent = o.key || ('option#' + idx);
    const txt = document.createElement('input');
    txt.type = 'text'; txt.placeholder = '选项文本（中文）';
    txt.dataset.key = o.key;
    txt.style.cssText = 'flex:1;min-width:0;margin:0';
    txt.value = (locMap && o.key && locMap[o.key]) || '';
    const del = document.createElement('button');
    del.className = 'btn'; del.textContent = '删除';
    del.onclick = ()=>{
      const kept = {};
      box.querySelectorAll('input[data-key]').forEach((inp, i2)=>{
        if(i2 !== idx && inp.dataset.key) kept[inp.dataset.key] = inp.value || '';
      });
      const el = document.getElementById('eventRaw');
      const b = eventOptionBlocks[idx];
      el.value = el.value.slice(0, b.start) + el.value.slice(b.end);
      renderEventOptions(el.value, kept);
    };
    row.appendChild(key); row.appendChild(txt); row.appendChild(del);
    box.appendChild(row);
  });
}

let _evSelSeq = 0;
async function selectEvent(e){
  if(!e) return;
  const seq = ++_evSelSeq;
  eventSel = e;
  document.querySelectorAll('#eventList .lr').forEach(el=>{
    el.classList.toggle('on', el.dataset.eventId === e.id);
  });
  document.getElementById('eventTitle').textContent = e.id + '   (' + e.file + ')';
  fillSrcHint('eventSrc', (typeof rootByName === 'function' ? rootByName(e.source) : '') || _lastRoot(), e.file, e.source);
  document.getElementById('eventNameZ').value = e.title || '';
  document.getElementById('eventDescZ').value = e.desc || '';
  document.getElementById('eventNameJa').value = '';
  document.getElementById('eventDescJa').value = '';
  document.getElementById('eventNameEn').value = '';
  document.getElementById('eventDescEn').value = '';
  const snap = _snapFieldValues([
    'eventNameZ', 'eventDescZ', 'eventNameJa', 'eventDescJa',
    'eventNameEn', 'eventDescEn', 'eventRaw', 'eventTrigger',
    'eventImmediate', 'eventPic'
  ]);
  const detail = await fetchRawDetail('event', e.id);
  if(seq !== _evSelSeq || eventSel !== e) return;
  const raw = detail.raw || '';
  const loc = detail.loc || {};
  const pm = /^\s*picture\s*=\s*"?([^\s#"]+)/m.exec(raw);
  _applyCleanFields(snap, [
    ['eventNameZ', (loc && (loc.title || loc.name)) || e.title || ''],
    ['eventDescZ', (loc && loc.desc) || e.desc || ''],
    ['eventNameJa', (loc && (loc.title_ja || loc.name_ja)) || ''],
    ['eventDescJa', (loc && loc.desc_ja) || ''],
    ['eventNameEn', (loc && (loc.title_en || loc.name_en)) || ''],
    ['eventDescEn', (loc && loc.desc_en) || ''],
    ['eventRaw', raw],
    ['eventTrigger', extractBlock(raw, 'trigger')],
    ['eventImmediate', extractBlock(raw, 'immediate')],
    ['eventPic', pm ? pm[1] : '']
  ]);
  renderEventOptions(raw, (loc && loc.options) || {});
}

async function saveEvent(){
  if(!eventSel){ status('先选择一个事件'); return; }
  const curId = eventSel.id;
  const btns = ['eventSave', 'eventSaveTop'].map(id=>document.getElementById(id)).filter(Boolean);
  btns.forEach(b=>{ b.disabled = true; });
  status('正在保存事件…');
  try{
    const options = [...document.querySelectorAll('#eventOptions input[data-key]')]
      .map(i=>({key: i.dataset.key, text: (i.value || '').trim()}))
      .filter(o=>o.key && o.text);
    const r = await fetch('/api/event_save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootByName(eventSel.source), file: eventSel.file, id: eventSel.id,
        raw: document.getElementById('eventRaw').value, options,
        trigger_raw: document.getElementById('eventTrigger').value,
        immediate_raw: document.getElementById('eventImmediate').value,
        picture: document.getElementById('eventPic').value.trim(),
        title: document.getElementById('eventNameZ').value,
        desc: document.getElementById('eventDescZ').value,
        title_ja: document.getElementById('eventNameJa').value,
        desc_ja: document.getElementById('eventDescJa').value,
        title_en: document.getElementById('eventNameEn').value,
        desc_en: document.getElementById('eventDescEn').value})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
    if(j.ok){
      const q = document.getElementById('eventSearch')?.value || '';
      if(j.item){
        _upsertDataItem('events', j.item);
        renderEventList(q);
        await selectEvent(j.item);
      } else {
        await loadData();
        renderEventList(q);
        const hit = (DATA.events||[]).find(x=>x.id===curId);
        if(hit) await selectEvent(hit);
      }
    }
  } finally {
    btns.forEach(b=>{ b.disabled = false; });
  }
}


async function addEvent(){
  const id = prompt('新事件 ID（namespace.member，例如 my_ns.1）：');
  if(!id) return;
  const root = _writableRoot();
  if(!root){ status('先加载或新建一个可写的模组', true); return; }
  const btn = document.getElementById('eventAdd');
  if(btn) btn.disabled = true;
  status('正在新建事件…');
  try{
    const r = await fetch('/api/event_add', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root, id})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
    if(j.ok){
      const sInp = document.getElementById('eventSearch');
      if(sInp) sInp.value = '';
      let hit = null;
      if(j.item){
        hit = _upsertDataItem('events', j.item);
      } else {
        await loadData();
        hit = (DATA.events||[]).find(x=>x.id===id);
      }
      renderEventList('');
      if(hit){
        await selectEvent(hit);
        const nmEl = document.getElementById('eventNameZ');
        if(nmEl) nmEl.focus();
      }
    }
  } finally {
    if(btn) btn.disabled = false;
  }
}

async function deleteEventSel(){
  if(!eventSel){ status('先选择事件'); return; }
  if(!confirm('确定删除事件 ' + eventSel.id + ' ？')) return;
  const cur = eventSel;
  const btn = document.getElementById('eventDelete');
  if(btn) btn.disabled = true;
  status('正在删除事件…');
  try{
    const r = await fetch('/api/event_delete', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootByName(cur.source), file: cur.file, id: cur.id})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
    if(j.ok){
      const q = document.getElementById('eventSearch')?.value || '';
      if(j.restored){
        _upsertDataItem('events', j.restored);
        renderEventList(q);
        await selectEvent(j.restored);
      } else {
        if(j.deleted_id) _removeDataItem('events', j.deleted_id);
        else await loadData();
        eventSel = null;
        ['eventTitle', 'eventSrc'].forEach(id=>{ const el = document.getElementById(id); if(el) el.textContent = ''; });
        const optBox = document.getElementById('eventOptions');
        if(optBox) optBox.innerHTML = '';
        ['eventNameZ', 'eventDescZ', 'eventNameJa', 'eventDescJa', 'eventNameEn', 'eventDescEn',
         'eventPic', 'eventTrigger', 'eventImmediate', 'eventRaw'].forEach(id=>{
          const el = document.getElementById(id); if(el) el.value = '';
        });
        renderEventList(q);
      }
    }
  } finally {
    if(btn) btn.disabled = false;
  }
}

async function addShared(){
  const id = prompt('新共享焦点 ID（字母数字下划线）：');
  if(!id) return;
  const root = _writableRoot();
  if(!root){ status('先加载或新建一个可写的模组', true); return; }
  const r = await fetch('/api/shared_add', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root, id})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok) await loadData();
}

async function deleteShared(){
  const t = curTree();
  let node = (t && t.id === 'shared_focuses' && selId) ? nodeById(t, selId) : null;
  const id = node ? node.id : prompt('要删除的共享焦点 ID：');
  if(!id) return;
  if(!node){
    const st = (DATA.trees || []).find(x=>x.id === 'shared_focuses');
    node = st ? nodeById(st, id) : null;
  }
  if(!node){ status('没有找到这个共享焦点'); return; }
  if(!confirm('确定删除共享焦点 ' + id + ' ？')) return;
  const r = await fetch('/api/shared_delete', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: rootByName(node.source), file: node.file, id})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok) await loadData();
}
