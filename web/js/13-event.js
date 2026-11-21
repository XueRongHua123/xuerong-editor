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

function renderEventOptions(raw){
  const box = document.getElementById('eventOptions');
  if(!box) return;
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
    txt.style.cssText = 'flex:1;background:#141719;border:1px solid #3a4346;color:#d9d3c7;border-radius:5px;padding:4px 6px';
    const del = document.createElement('button');
    del.className = 'btn'; del.textContent = '删除';
    del.onclick = ()=>{
      const el = document.getElementById('eventRaw');
      const b = eventOptionBlocks[idx];
      el.value = el.value.slice(0, b.start) + el.value.slice(b.end);
      renderEventOptions(el.value);
    };
    row.appendChild(key); row.appendChild(txt); row.appendChild(del);
    box.appendChild(row);
  });
}

async function selectEvent(e){
  eventSel = e;
  document.getElementById('eventTitle').textContent = e.id + '   (' + e.file + ')';
  fillSrcHint('eventSrc', (typeof rootByName === 'function' ? rootByName(e.source) : '') || _lastRoot(), e.file, e.source);
  document.getElementById('eventNameZ').value = '';
  document.getElementById('eventDescZ').value = '';
  document.getElementById('eventNameJa').value = '';
  document.getElementById('eventDescJa').value = '';
  document.getElementById('eventNameEn').value = '';
  document.getElementById('eventDescEn').value = '';
  const raw = await fetchRaw('event', e.id);
  document.getElementById('eventRaw').value = raw;
  document.getElementById('eventTrigger').value = extractBlock(raw, 'trigger');
  document.getElementById('eventImmediate').value = extractBlock(raw, 'immediate');
  const pm = /^\s*picture\s*=\s*"?([^\s#"]+)/m.exec(raw);
  document.getElementById('eventPic').value = pm ? pm[1] : '';
  renderEventOptions(raw);
}

async function saveEvent(){
  if(!eventSel){ status('先选择一个事件'); return; }
  const curId = eventSel.id;
  await withBusy('正在保存事件并刷新…', async ()=>{
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
      await loadData();
      renderEventList(document.getElementById('eventSearch').value);
      const hit = (DATA.events||[]).find(x=>x.id===curId);
      if(hit) await selectEvent(hit);
    }
  });
}


async function addEvent(){
  const id = prompt('新事件 ID（namespace.member，例如 my_ns.1）：');
  if(!id) return;
  const root = _writableRoot();
  if(!root){ status('先加载或新建一个可写的模组', true); return; }
  await withBusy('正在新建事件并刷新…', async ()=>{
    const r = await fetch('/api/event_add', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root, id})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
    if(j.ok){
      await loadData();
      const sInp = document.getElementById('eventSearch');
      if(sInp) sInp.value = '';
      renderEventList('');
      const hit = (DATA.events||[]).find(x=>x.id===id);
      if(hit) await selectEvent(hit);
    }
  });
}

async function deleteEventSel(){
  if(!eventSel){ status('先选择事件'); return; }
  if(!confirm('确定删除事件 ' + eventSel.id + ' ？')) return;
  await withBusy('正在删除事件并刷新…', async ()=>{
    const r = await fetch('/api/event_delete', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootByName(eventSel.source), file: eventSel.file, id: eventSel.id})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
    if(j.ok){
      eventSel = null;
      document.getElementById('eventRaw').value = '';
      document.getElementById('eventTitle').textContent = '';
      await loadData();
      renderEventList('');
    }
  });
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
