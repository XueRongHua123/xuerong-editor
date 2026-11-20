// 21-tools：工具（P4）
// 设计器 / 图标选择 / 内容速加 / 命令面板 / 脚本检查 / lint / 写盘目标 / 接管校验。

function openDesigner(){
  designerSel = {};
  designerPicker = '';
  designerArch = '';
  document.getElementById('designerModal').classList.add('show');
  renderDesigner();
}

function designerArchetypes(){
  const out = [];
  ((DATA && DATA.equipment) || []).forEach(e=>{
    const p = e.props || {};
    if(String(p.is_archetype || '').toLowerCase() === 'yes') out.push(e);
  });
  if(!out.length){
    ((DATA && DATA.equipment) || []).forEach(e=>{ if((e.slots || []).length) out.push(e); });
  }
  if(!out.length){
    return ((DATA && DATA.equipment) || []).slice(0, 80);
  }
  return out;
}

function renderDesigner(){
  const body = document.getElementById('designerBody');
  const archs = designerArchetypes();
  if(!archs.length){ body.textContent = '没有找到可用的底盘/原型装备'; return; }
  if(!designerArch || !archs.some(a=>a.id === designerArch)) designerArch = archs[0].id;
  const orgs = (DATA && DATA.orgs) || [];
  const targets = ((DATA && DATA.roots) || []).filter(r=>!r.readonly);
  if(!designerTarget || !targets.some(t=>t.path === designerTarget)) designerTarget = targets[0] ? targets[0].path : '';
  const arch = archs.find(a=>a.id === designerArch) || archs[0];
  const opts = archs.map(a=>'<option value="' + escapeHtml(a.id) + '"' + (a.id === designerArch ? ' selected' : '') + '>' + escapeHtml(a.name || a.id) + '</option>').join('');
  body.innerHTML = '<div class="eqd2"><div class="eqd2-main">' +
    '<div class="eqd2-top"><select id="eqdArch" class="btn" style="flex:1">' + opts + '</select>' +
    '<select id="eqdOrg" class="btn" style="width:180px"><option value="">（未选军工）</option>' +
    orgs.map(o=>'<option value="' + escapeHtml(o.id) + '">' + escapeHtml(o.name) + '</option>').join('') + '</select>' +
    '<select id="eqdTarget" class="btn" style="width:200px">' +
    targets.map(t=>'<option value="' + escapeHtml(t.path) + '"' + (t.path === designerTarget ? ' selected' : '') + '>' + escapeHtml('写入：' + (t.name || t.path)) + '</option>').join('') +
    '</select></div>' +
    '<div id="eqdSlotArea" style="flex:1"></div>' +
    '<div class="eqd2-preview" id="eqdPreview">' + (arch && arch.picture ? '<img src="/api/icon?gfx=' + encodeURIComponent(arch.picture) + '" style="max-width:100%;max-height:100px;object-fit:contain" onerror="this.style.display=\'none\';this.parentNode.innerHTML=\'<span>该底盘没有可显示的图片</span>\'">' : '模型预览区<br><span>（该底盘没有可显示的图片）</span>') + '</div>' +
    '</div><div class="eqd2-side"><div class="eqd2-stats" id="eqdStats"></div>' +
    '<div class="eqd2-cost">生产花费 <b id="eqdCost">-</b></div>' +
    '<div style="display:flex;gap:6px;flex-wrap:wrap"><button class="btn" id="eqdReset">重置</button><button class="btn primary" id="eqdSave">生成变体</button><button class="btn" id="eqdInsert">插入当前国策</button></div></div></div>';
  document.getElementById('eqdArch').onchange = e=>{ designerArch = e.target.value; renderDesigner(); };
  const tEl = document.getElementById('eqdTarget');
  if(tEl) tEl.onchange = e=>{ designerTarget = e.target.value; };
  document.getElementById('eqdReset').onclick = ()=>{ designerSel = {}; designerPicker = ''; renderDesigner(); };
  document.getElementById('eqdSave').onclick = async ()=>{
    const orgEl = document.getElementById('eqdOrg');
    const org = orgEl ? orgEl.value : '';
    const hasSlots = !!archSlots();
    const url = hasSlots ? '/api/variant_save' : '/api/design_save';
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({archetype: designerArch, modules: designerSel, org,
        name: (arch && arch.name) || designerArch, target: designerTarget})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
  };
  document.getElementById('eqdInsert').onclick = async ()=>{
    const orgEl = document.getElementById('eqdOrg');
    const org = orgEl ? orgEl.value : '';
    const r = await fetch('/api/variant_save', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({archetype: designerArch, modules: designerSel, org,
        name: (arch && arch.name) || designerArch, target: designerTarget})});
    const j = await r.json();
    if(!j.ok){ status(j.msg || '生成失败', true); return; }
    const mm = /zzfe_variant_[A-Za-z0-9_]+/.exec(j.msg || '');
    if(mm){
      addFxLine(mm[0] + ' = yes');
      status('已生成并插入到当前国策效果：' + mm[0]);
    } else {
      status(j.msg || '已生成');
    }
  };
  renderDesignerSlots();
}

function currentArch(){
  return ((DATA && DATA.equipment) || []).find(e=>e.id === designerArch);
}

function archSlots(){
  const a = currentArch();
  return (a && a.slots && a.slots.length) ? a.slots : null;
}

function renderDesignerSlots(){
  const area = document.getElementById('eqdSlotArea');
  if(!area) return;
  if(designerPicker){ renderDesignerPicker(area); return; }
  const slots = archSlots();
  if(!slots){
    area.innerHTML = '<div class="k" style="padding:8px">该底盘没有 module_slots 定义，只能做模块属性预览。</div>';
    recomputeDesigner();
    return;
  }
  let html = '<div class="eqd2-slots">';
  slots.forEach(sd=>{
    const mid = designerSel[sd.slot];
    const m = mid ? ((DATA && DATA.modules) || []).find(x=>x.id === mid) : null;
    const icon = (m && m.gfx) ? '<img src="/api/icon?gfx=' + encodeURIComponent(m.gfx) + '">' : '<span class="eqd2-plus">+</span>';
    const label = (sd.name && sd.name !== sd.slot) ? sd.name : sd.slot.replace(/_slot$/, '').replace(/_/g, ' ');
    html += '<div class="eqd2-slot' + (m ? ' filled' : '') + '" data-slot="' + escapeHtml(sd.slot) + '">' +
      '<div class="ico">' + icon + '</div><div class="cat">' + escapeHtml(label) + (sd.required ? ' *' : '') + '</div></div>';
  });
  html += '</div>';
  area.innerHTML = html;
  area.querySelectorAll('.eqd2-slot').forEach(sl=>{
    sl.onclick = ()=>{ designerPicker = sl.dataset.slot; renderDesignerSlots(); };
  });
  recomputeDesigner();
}

function renderDesignerPicker(area){
  const slotId = designerPicker;
  const slots = archSlots() || [];
  const sd = slots.find(s=>s.slot === slotId);
  const cats = sd ? sd.categories : [];
  const mods = ((DATA && DATA.modules) || []).filter(m=>{
    if(!cats || !cats.length) return true;
    return cats.includes(m.category);
  });
  let html = '<div class="eqd2-picker"><div class="head">模块槽位：' + escapeHtml(slotId.replace(/_slot$/, '')) + '　<button class="btn" id="eqdBack">返回</button></div><div class="eqd2-grid">';
  html += '<div class="eqd2-mod" data-id=""><div class="eqd2-x">✕</div><div>不装 / 清空</div></div>';
  mods.forEach(m=>{
    const icon = m.gfx ? '<img src="/api/icon?gfx=' + encodeURIComponent(m.gfx) + '">' : '<div class="eqd2-x">?</div>';
    const st = Object.keys(m.stats || {}).map(k=>k + ' ' + m.stats[k]).join('　');
    html += '<div class="eqd2-mod' + (designerSel[slotId] === m.id ? ' on' : '') + '" data-id="' + escapeHtml(m.id) + '">' +
      icon + '<div><b>' + escapeHtml((m.name && m.name !== m.id) ? m.name : m.id) + '</b><div class="meta">' + escapeHtml(m.id + ' · ' + m.category) + '</div>' +
      (st ? '<div class="meta">' + escapeHtml(st) + '</div>' : '') + '</div></div>';
  });
  html += '</div></div>';
  area.innerHTML = html;
  document.getElementById('eqdBack').onclick = ()=>{ designerPicker = ''; renderDesignerSlots(); };
  area.querySelectorAll('.eqd2-mod').forEach(d=>{
    d.onclick = ()=>{
      const id = d.dataset.id;
      if(!id) delete designerSel[slotId]; else designerSel[slotId] = id;
      designerPicker = '';
      renderDesignerSlots();
    };
  });
}

function recomputeDesigner(){
  const arch = ((DATA && DATA.equipment) || []).find(e=>e.id === designerArch);
  const stats = {};
  if(arch){
    Object.entries(arch.props || {}).forEach(([k, v])=>{ const n = parseFloat(v); if(!isNaN(n)) stats[k] = n; });
  }
  ((DATA && DATA.modules) || []).forEach(m=>{
    if(!Object.values(designerSel).includes(m.id)) return;
    Object.entries(m.stats || {}).forEach(([k, v])=>{ stats[k] = (stats[k] || 0) + v; });
  });
  const groups = [
    ['基础数据', ['max_speed','maximum_speed','reliability','supply_consumption','fuel_capacity','build_cost_ic']],
    ['战斗数据', ['soft_attack','hard_attack','air_attack','defense','breakthrough','armor','piercing','combat_width','hardness']],
    ['其他数据', ['fuel_usage','recon','suppression','attack','organization','weight','air_agility','air_range','air_defence','naval_strike_attack','naval_strike_targetting']]
  ];
  const used = new Set();
  let html = '';
  groups.forEach(([title, keys])=>{
    const rows = [];
    keys.forEach(k=>{
      if(stats[k] !== undefined){ used.add(k); rows.push('<div class="row"><span>' + escapeHtml(k) + '</span><b>' + (Math.round(stats[k] * 100) / 100) + '</b></div>'); }
    });
    if(rows.length) html += '<div class="panel"><div class="ptitle">' + title + '</div>' + rows.join('') + '</div>';
  });
  const rest = Object.keys(stats).filter(k=>!used.has(k) && Math.abs(stats[k]) > 0.0001).sort();
  if(rest.length){
    html += '<div class="panel"><div class="ptitle">其他</div>' + rest.slice(0, 20).map(k=>'<div class="row"><span>' + escapeHtml(k) + '</span><b>' + (Math.round(stats[k] * 100) / 100) + '</b></div>').join('') + '</div>';
  }
  const el = document.getElementById('eqdStats');
  if(el) el.innerHTML = html ? ('<div class="ptitle" style="width:100%">总体数值</div>' + html) : '<div class="k">选择模块后显示属性</div>';
  const cost = stats.build_cost_ic || 0;
  const cel = document.getElementById('eqdCost');
  if(cel) cel.textContent = cost ? cost.toFixed(2) : '-';
}

async function openUsages(iid){
  if(!iid){ status('先选择要查询的内容'); return; }
  const r = await fetch('/api/usages?id=' + encodeURIComponent(iid));
  const j = await r.json();
  const box = document.getElementById('usagesList');
  const items = j.items || [];
  if(!items.length){ box.textContent = '没有找到引用（或该 ID 未被国策/事件/科技引用）'; }
  else {
    box.innerHTML = '';
    items.forEach(it=>{
      const d = document.createElement('div');
      d.style.cssText = 'padding:4px 6px;border-bottom:1px solid #2b3234;font-size:12px;color:#d9d3c7';
      d.textContent = '[' + it.type + '] ' + it.id + '  —  ' + it.where + (it.file ? '   (' + it.file + ')' : '');
      box.appendChild(d);
    });
  }
  document.getElementById('usagesModal').classList.add('show');
}

async function openReport(){
  const r = await fetch('/api/report');
  const j = await r.json();
  const box = document.getElementById('reportList');
  const items = j.items || [];
  if(!items.length){ box.textContent = '没有发现问题。'; }
  else {
    box.innerHTML = '';
    items.slice(0, 800).forEach(it=>{
      const d = document.createElement('div');
      d.textContent = '[' + it.kind + '] ' + it.id + (it.where ? '  →  ' + it.where : '') + (it.file ? '   (' + it.file + ')' : '');
      if(it.kind.indexOf('花括号') >= 0){
        const b = document.createElement('button');
        b.className = 'btn'; b.textContent = '修复'; b.style.marginLeft = '8px';
        b.onclick = async ()=>{
          const r = await fetch('/api/repair_braces', {method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({file: it.file})});
          const j = await r.json();
          status(j.msg || '', !j.ok);
          if(j.ok) openReport();
        };
        d.appendChild(b);
      }
      box.appendChild(d);
    });
  }
  document.getElementById('reportModal').classList.add('show');
}

async function openIconPicker(source){
  iconSource = source || 'focus';
  document.getElementById('iconPick').classList.add('show');
  document.getElementById('ipSearch').value = '';
  const kind = iconSource === 'equip' ? 'equip' : 'focus';
  if(!iconCache[kind]){
    try {
      const r = await fetch('/api/icons?kind=' + kind);
      iconCache[kind] = await r.json();
    } catch(e){ iconCache[kind] = {list: [], map: {}}; }
  }
  renderIcons('');
}

function renderIcons(q){
  const g = document.getElementById('ipGrid'); if(!g) return;
  q = (q || '').toLowerCase();
  const kind = iconSource === 'equip' ? 'equip' : 'focus';
  const c = iconCache[kind] || {list: [], map: {}};
  const map = c.map || {};
  const list = (c.list || []).filter(n=>!q || n.toLowerCase().includes(q)).slice(0, 500);
  g.innerHTML = '';
  list.forEach(gfx=>{
    const d = document.createElement('div');
    d.className = 'ip-item';
    const m = map[gfx] || '';
    const src = m.startsWith('/') ? m : ('/icons/' + encodeURIComponent(m));
    d.innerHTML = '<img src="' + src + '" alt=""><span>' + escapeHtml(gfx) + '</span>';
    d.onclick = ()=>{
      if(batchIconMode){
        batchIconMode = false;
        document.getElementById('iconPick').classList.remove('show');
        applyBatchIcon(gfx);
        return;
      }
      if(iconPickTarget){
        const t = document.getElementById(iconPickTarget);
        if(t) t.value = gfx;
        iconPickTarget = null;
        document.getElementById('iconPick').classList.remove('show');
        return;
      }
      const el = document.getElementById('edIcon'); if(el) el.value = gfx;
      document.getElementById('iconPick').classList.remove('show');
    };
    g.appendChild(d);
  });
  if(!list.length) g.innerHTML = '<div class="ip-item">没有匹配的图标</div>';
}


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

function contentItems(){
  const out = [];
  // v1.24.0：每项都带来源层，方便一眼看出「这是原版的还是我改过的」
  ((DATA && DATA.ideas) || []).forEach(i=>out.push({kind:'idea', label:'[精神] ' + i.id + '  ' + (i.name||''), id:i.id, source:i.source||''}));
  ((DATA && DATA.equipment) || []).forEach(e=>out.push({kind:'equip', label:'[装备] ' + e.id, id:e.id, source:e.source||''}));
  ((DATA && DATA.techs) || []).forEach(t=>out.push({kind:'tech', label:'[科技] ' + t.id + '  ' + (t.name||''), id:t.id, source:t.source||''}));
  ((DATA && DATA.events) || []).forEach(e=>out.push({kind:'event', label:'[事件] ' + e.id, id:e.id, source:e.source||''}));
  return out;
}

function openContent(kind){
  contentFilter = kind || '';
  document.getElementById('contentModal').classList.add('show');
  document.getElementById('contentSearch').value = '';
  renderContent('');
}

function renderContent(q){
  q = (q || '').toLowerCase();
  const box = document.getElementById('contentList');
  const items = contentItems().filter(x=> (!contentFilter || x.kind === contentFilter) &&
    (!q || x.label.toLowerCase().includes(q)));
  box.innerHTML = '';
  items.slice(0, 800).forEach(it=>{
    const d = document.createElement('div');
    d.className = 'ct-item';
    d.innerHTML = '<span class="ct-label">' + escapeHtml(it.label) + '</span>' +
      (it.source
        ? '<span class="ct-src" title="来自 ' + escapeHtml(it.source) + '">' +
          escapeHtml(it.source) + '</span>'
        : '');
    d.onclick = ()=>insertContent(it.kind, it.id);
    box.appendChild(d);
  });
  if(!items.length) box.textContent = '没有匹配的内容';
}

function insertContent(kind, id){
  const el = document.getElementById('edEffect');
  if(!el){ status('先选择一个国策节点'); return; }
  let line = '';
  if(kind === 'idea') line = 'add_ideas = ' + id;
  else if(kind === 'equip'){
    const ans = prompt('增加多少 ' + id + ' ？', '1000');
    if(ans === null) return;
    const amt = parseInt(ans, 10) || 1000;
    line = 'add_equipment_to_stockpile = {\n\ttype = ' + id + '\n\tamount = ' + amt + '\n}';
  }
  else if(kind === 'tech') line = 'set_technology = { ' + id + ' = 1 }';
  else line = 'country_event = { id = ' + id + ' days = 0 }';
  el.value = (el.value ? el.value.replace(/\s*$/, '') + '\n' : '') + line + '\n';
  if(contentFilter) document.getElementById('contentModal').classList.remove('show');
  status('已插入 ' + id + '，改完点顶部「💾 保存」');
}


function openIdea(){
  document.getElementById('ideaModal').style.display = 'flex';
  renderIdeaList('');
  const first = ((DATA && DATA.ideas) || [])[0];
  if(first) selectIdea(first);
}

function cpActions(){
  return [
    {cat:'操作', label:'适应屏幕', hint:'F', run:()=>fitView()},
    {cat:'操作', label:'保存全部改动', hint:'Ctrl+S', run:()=>saveAll()},
    {cat:'操作', label:'撤销', hint:'Ctrl+Z', run:()=>doUndo(false)},
    {cat:'操作', label:'重做', hint:'Ctrl+Y', run:()=>doUndo(true)},
    {cat:'操作', label:'切换编辑模式', run:()=>document.getElementById('editMode').click()},
    {cat:'操作', label:'加前置连线', run:()=>document.getElementById('linkPre').click()},
    {cat:'操作', label:'加互斥连线', run:()=>document.getElementById('linkMut').click()},
    {cat:'操作', label:'新建焦点', run:()=>addNode()},
    {cat:'操作', label:'自动布局当前树', run:()=>autoArrange()},
    {cat:'操作', label:'新建国策树', run:()=>addTree()},
    {cat:'操作', label:'复制当前树', run:()=>copyTree()},
    {cat:'操作', label:'树设置（country / default）', run:()=>openTreeSet()},
    {cat:'操作', label:'项目体检（跨系统引用检查）', hint:'', run:()=>openLint()},
    {cat:'操作', label:'国家中心', run:()=>openCountry()},
    {cat:'操作', label:'州 / 地块', run:()=>openStates()},
    {cat:'操作', label:'语法检查（花括号 / replace_path / namespace）', run:()=>openReport()},
    {cat:'操作', label:'本地化缺失检查', run:()=>openLocCheck()},
    {cat:'操作', label:'查看 error.log', run:()=>openLog()},
    {cat:'操作', label:'备份历史', run:()=>openBackups()},
    {cat:'操作', label:'游戏内预览当前焦点', run:()=>openFocusPreview()},
    {cat:'操作', label:'内容库（原版焦点/精神/装备/科技/事件）', run:()=>openContent()},
    {cat:'操作', label:'国家精神编辑器', run:()=>openIdea()},
    {cat:'操作', label:'装备编辑器', run:()=>openEquip()},
    {cat:'操作', label:'科技编辑器', run:()=>openTech()},
    {cat:'操作', label:'事件编辑器', run:()=>openEvents()},
    {cat:'操作', label:'换雪绒皮肤', run:()=>openSkinPick()},
    {cat:'操作', label:'键盘快捷键', hint:'H', run:()=>openKeys()},
    {cat:'操作', label:'使用教程', run:()=>window.open('/help?lang=' + LANG, '_blank')}
  ];
}

function cpBuild(){
  const list = cpActions().map(a=>({cat:a.cat, label:a.label, hint:a.hint||'', run:a.run,
    _s:(a.label + ' ' + (a.hint||'') + ' ' + a.cat).toLowerCase()}));
  if(!DATA) return list;
  const cur = curTree();
  (DATA.trees || []).forEach(t=>{
    const n = (t.focuses || []).length;
    list.push({cat:'国策树', label:t.id + (cur && cur.id === t.id ? '（当前）' : ''), hint:n + ' 节点',
      _s:(t.id + ' 国策树 focus tree').toLowerCase(),
      run:()=>{
        const i = DATA.trees.indexOf(t);
        current = i; resetView(); renderAll();
        status('已切换国策树：' + t.id);
      }});
    (t.focuses || []).slice(0, 3000).forEach(f=>{
      const nm = f.name && f.name !== f.id ? f.name : '';
      list.push({cat:'焦点', label:(nm ? nm + ' · ' : '') + f.id, hint:t.id, scope:t.id,
        _s:(f.id + ' ' + (f.name||'') + ' ' + t.id + ' 焦点 focus').toLowerCase(),
        run:()=>jumpFocus(t.id, f.id)});
    });
  });
  (DATA.ideas || []).forEach(i=>{
    list.push({cat:'国家精神', label:(i.name && i.name !== i.id ? i.name + ' · ' : '') + i.id, hint:'idea',
      _s:(i.id + ' ' + (i.name||'') + ' 国家精神 spirit idea').toLowerCase(),
      run:()=>{ openIdea(); selectIdea(i); }});
  });
  (DATA.equipment || []).forEach(e=>{
    if(!e.id || /^\d+$/.test(String(e.id))) return;
    list.push({cat:'装备', label:(e.name && e.name !== e.id ? e.name + ' · ' : '') + e.id, hint:'equip',
      _s:(e.id + ' ' + (e.name||'') + ' 装备 equipment').toLowerCase(),
      run:()=>{ openEquip(); selectEquip(e); }});
  });
  (DATA.techs || []).forEach(t=>{
    list.push({cat:'科技', label:t.id + (t.name ? ' · ' + t.name : ''), hint:'tech',
      _s:(t.id + ' ' + (t.name||'') + ' 科技 technology').toLowerCase(),
      run:()=>{ openTech(); selectTech(t); }});
  });
  (DATA.events || []).forEach(ev=>{
    list.push({cat:'事件', label:ev.id, hint:(ev.file || 'event'),
      _s:(ev.id + ' 事件 event').toLowerCase(),
      run:()=>{
        openEvents();
        const box = document.getElementById('eventSearch');
        if(box){ box.value = ev.id; renderEventList(ev.id); }
        selectEvent(ev);
      }});
  });
  return list;
}


function applyDensity(mode){
  const v = NODE_SIZE[mode] || NODE_SIZE.normal;
  NODE_W = v[0];
  NODE_H = v[1];
  SCALE = v[2];
  try { localStorage.setItem('fe_density', mode); } catch(e){}
  const sel = document.getElementById('densitySel');
  if(sel) sel.value = mode;
  try { renderAll(); } catch(e){}
}


function initDensity(){
  let mode = 'normal';
  try { mode = localStorage.getItem('fe_density') || 'normal'; } catch(e){}
  if(!NODE_SIZE[mode]) mode = 'normal';
  applyDensity(mode);
}


function initNarrowMore(){
  const btn = document.getElementById('tbMore');
  const menu = document.getElementById('tbMoreMenu');
  if(!btn || !menu) return;
  const move = [
    ['💾 保存', 'btnSaveAll'],
    ['📦 打包发布', 'btnExport'],
    ['🩺 体检', 'btnLint'],
    ['🕘 备份', 'btnBackup'],
    ['📖 内容库', 'btnLibrary'],
    ['❓ 教程', 'btnTutorial']
  ];
  // 窄屏时把这些按钮收进「更多」，宽屏保持原样
  ['saveAll', 'exportBtn', 'backupBtn', 'contentBtn', 'helpBtn'].forEach(id=>{
    const el = document.getElementById(id);
    if(el) el.classList.add('tb-wide');
  });
  menu.innerHTML = move.map(([label])=>
    '<div class="tb-more-item" data-label="' + label + '">' + label + '</div>').join('');
  btn.onclick = e=>{
    e.stopPropagation();
    const r = btn.getBoundingClientRect();
    menu.style.left = Math.max(8, Math.min(window.innerWidth - 200, r.left)) + 'px';
    menu.style.top = (r.bottom + 4) + 'px';
    menu.classList.add('show');
  };
  menu.querySelectorAll('.tb-more-item').forEach(item=>{
    item.onclick = ()=>{
      menu.classList.remove('show');
      const map = {
        '💾 保存': 'saveAll', '📦 打包发布': 'exportBtn', '🩺 体检': 'lintEntry',
        '🕘 备份': 'backupBtn', '📖 内容库': 'contentBtn', '❓ 教程': 'helpBtn'
      };
      const id = map[item.dataset.label];
      const target = id && document.getElementById(id);
      if(target && target.click) target.click();
    };
  });
  document.addEventListener('click', e=>{
    if(!e.target.closest('#tbMore') && !e.target.closest('#tbMoreMenu')) menu.classList.remove('show');
  });
}


// v1.20.6 目录写入目标 + 接管
(function(){
  function msg(t, bad){
    const el = document.getElementById('wtMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function loadWT(){
    const box = document.getElementById('wtList');
    msg('读取中…');
    const r = await (await fetch('/api/write_targets', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({})})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    msg(r.msg);
    if(!box) return;
    box.innerHTML = (r.items || []).map(function(x){
      const tag = x.blocked
        ? '<span style="color:#e8a33d">独占</span>'
        : '<span style="color:#7bc47f">可写</span>';
      const modName = String(x.mod || '父层').replace(/"/g, '&quot;');
      const fcount = Number(x.file_count || 0);
      const btn = x.blocked
        ? '<button class="btn wt-adopt" data-sub="' + x.sub + '" data-mod="' + modName + '" data-count="' + fcount + '" style="height:20px;font-size:10px;padding:0 6px">接管</button>'
        : '';
      return '<div style="display:flex;align-items:center;gap:6px;padding:2px 4px;'
        + 'font-size:11px;font-family:Consolas,monospace;border-bottom:1px solid var(--line)">'
        + '<span style="flex:1" title="' + x.note + '">' + x.sub + '</span>'
        + '<span style="width:92px;text-align:right;font-size:10px;color:var(--t3)">' + (x.mod || '-') + '</span>'
        + '<span style="width:34px;text-align:center;font-size:10px">' + tag + '</span>'
        + btn
        + '</div>';
    }).join('');
    box.querySelectorAll('.wt-adopt').forEach(function(b){
      b.onclick = async function(){
        const sub = b.dataset.sub;
        const mod = b.dataset.mod || '父层';
        const count = Number(b.dataset.count || 0);
        if(!confirm('接管会复制 ' + mod + ' 的全部 ' + sub + '（共 ' + count + ' 个文件）到当前 mod 并写入 replace_path，之后只读自己的副本，确认吗？')) return;
        msg('接管 ' + sub + ' 中…');
        let r2 = await (await fetch('/api/adopt_dir', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({sub: sub})})).json();
        if(!r2.ok && r2.need_confirm){
          if(!confirm(r2.msg + '\n\n继续？')){ msg('已取消', true); return; }
          r2 = await (await fetch('/api/adopt_dir', {method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({sub: sub, force: true})})).json();
        }
        if(r2.ok && r2.check && window.__wtRenderCheck){
          const box = document.getElementById('wtList');
          if(box){
            box.innerHTML = '<div style="padding:4px">'
              + '<div style="font-size:11px;font-family:Consolas,monospace">' + r2.sub + '</div>'
              + window.__wtRenderCheck(r2.check) + '</div>';
          }
        }
        msg(r2.msg || '', !r2.ok);
        if(r2.ok) status(r2.msg);
      };
    });
  }

  function bind(){
    const b = document.getElementById('wtBtn');
    if(b && !b.dataset.bound){ b.dataset.bound = '1'; b.onclick = loadWT; }
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.20.7 接管完整性校验
(function(){
  function msg(t, bad){
    const el = document.getElementById('wtMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function renderCheck(c){
    if(!c) return '';
    const ok = c.ok !== false;
    const color = ok ? '#7bc47f' : '#e8a33d';
    let html = '<div style="font-size:11px;color:' + color + ';padding:2px 4px">'
      + (ok ? '✔ ' : '⚠ ') + (c.msg || '') + '</div>';
    if((c.missing || []).length){
      html += '<div style="font-size:10px;font-family:Consolas,monospace;color:var(--danger);'
        + 'padding:2px 4px;max-height:80px;overflow:auto">缺：'
        + c.missing.map(function(f){ return f; }).join('<br>') + '</div>';
    }
    if((c.differ || []).length){
      html += '<div style="font-size:10px;font-family:Consolas,monospace;color:var(--t3);'
        + 'padding:2px 4px">改了 ' + c.differ_count + ' 个：'
        + c.differ.slice(0, 5).join(', ') + (c.differ_count > 5 ? ' …' : '') + '</div>';
    }
    return html;
  }

  async function runVerify(){
    const box = document.getElementById('wtList');
    msg('校验中…');
    const r = await (await fetch('/api/verify_adopt', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({})})).json();
    if(!r.items){ msg(r.msg || '失败', true); return; }
    msg(r.msg, !r.ok);
    if(!box) return;
    box.innerHTML = r.items.map(function(x){
      return '<div style="padding:3px 4px;border-bottom:1px solid var(--line)">'
        + '<div style="font-size:11px;font-family:Consolas,monospace">' + x.sub + '</div>'
        + renderCheck(x)
        + '</div>';
    }).join('') || '<div style="font-size:11px;color:var(--t3);padding:4px">还没有接管任何目录</div>';
  }

  function bind(){
    const b = document.getElementById('wtVerify');
    if(b && !b.dataset.bound){ b.dataset.bound = '1'; b.onclick = runVerify; }
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);

  // 接管结果里带 check 时，把详情补到消息后面
  window.__wtRenderCheck = renderCheck;
})();


function cpRecentList(){
  try{
    const a = JSON.parse(localStorage.getItem(CP_RECENT_KEY) || '[]');
    return Array.isArray(a) ? a.filter(x=>x && x.cat && x.label) : [];
  }catch(e){ return []; }
}


function cpRecentPush(cat, label){
  if(!cat || !label) return;
  const list = cpRecentList().filter(x=>!(x.cat === cat && x.label === label));
  list.unshift({cat, label});
  try{ localStorage.setItem(CP_RECENT_KEY, JSON.stringify(list.slice(0, 8))); }catch(e){}
}


function cpScore(q, s){
  if(!q) return 1;
  const i = s.indexOf(q);
  if(i >= 0) return 200 - Math.min(i, 120) + (s.startsWith(q) ? 40 : 0);
  let si = 0, qi = 0, gaps = 0, last = -1;
  while(si < s.length && qi < q.length){
    if(s[si] === q[qi]){
      if(last >= 0) gaps += si - last - 1;
      last = si; qi++;
    }
    si++;
  }
  return qi === q.length ? Math.max(1, 90 - gaps) : 0;
}

function openCmd(){
  if(!cpCache) cpCache = cpBuild();
  const box = document.getElementById('cmdPalette');
  const input = document.getElementById('cpInput');
  box.classList.add('show');
  input.value = '';
  cpRender();
  setTimeout(()=>{ try{ input.focus(); input.select(); }catch(e){} }, 30);
}

function closeCmd(){ document.getElementById('cmdPalette').classList.remove('show'); }

function cpRender(){
  const input = document.getElementById('cpInput');
  const q = (input.value || '').trim().toLowerCase();
  let all = cpCache || (cpCache = cpBuild());
  const curId = (curTree() || {}).id;
  if(!q){
    const seen = {};
    const rec = [];
    cpRecentList().forEach(r=>{
      const key = r.cat + '\u0001' + r.label;
      if(seen[key]) return;
      seen[key] = 1;
      const it = all.find(x=>x.cat === r.cat && x.label === r.label);
      if(it) rec.push(Object.assign({}, it, {cat: '最近使用', hint: it.cat}));
    });
    if(rec.length) all = rec.concat(all);
  }
  const scored = [];
  for(let i = 0; i < all.length; i++){
    const it = all[i];
    if(!q && it.cat === '焦点' && it.scope !== curId) continue;
    const s = cpScore(q, it._s);
    if(s > 0) scored.push([s, it]);
  }
  scored.sort((a, b)=> b[0] - a[0]);
  const perCat = {}, picked = [];
  const capFor = cat => q ? 12 : (cat === '操作' ? 40 : (cat === '国策树' ? 12 : 8));
  for(let i = 0; i < scored.length && picked.length < 90; i++){
    const it = scored[i][1];
    perCat[it.cat] = (perCat[it.cat] || 0) + 1;
    if(perCat[it.cat] > capFor(it.cat)) continue;
    picked.push(it);
  }
  cpItems = picked; cpIdx = 0;
  const list = document.getElementById('cpList');
  if(!picked.length){
    list.innerHTML = '<div class="cp-empty">没有匹配项。试试焦点 id、精神名、或命令关键词（保存 / 校验 / 备份）。</div>';
    document.getElementById('cpCount').textContent = '0 项';
    return;
  }
  const groups = {};
  picked.forEach((it, idx)=>{
    (groups[it.cat] = groups[it.cat] || []).push([idx, it]);
  });
  let html = '';
  CP_CAT_ORDER.forEach(cat=>{
    const rows = groups[cat]; if(!rows) return;
    html += '<div class="cp-group">' + cat + ' · ' + rows.length + '</div>';
    rows.forEach(([idx, it])=>{
      html += '<div class="cp-item' + (idx === 0 ? ' on' : '') + '" data-i="' + idx + '">' +
        '<span class="cp-cat">' + cat + '</span>' +
        '<span class="cp-label">' + escapeHtml(it.label) + '</span>' +
        (it.hint ? '<span class="cp-hint">' + escapeHtml(it.hint) + '</span>' : '') +
        '</div>';
    });
  });
  list.innerHTML = html;
  document.getElementById('cpCount').textContent = picked.length + ' 项';
  list.querySelectorAll('.cp-item').forEach(el=>{
    el.addEventListener('click', ()=>cpRun(Number(el.dataset.i)));
    el.addEventListener('mouseenter', ()=>{ cpIdx = Number(el.dataset.i); cpMark(); });
  });
  list.scrollTop = 0;
}

function cpMark(){
  const list = document.getElementById('cpList'); if(!list) return;
  list.querySelectorAll('.cp-item').forEach(el=>{
    const on = Number(el.dataset.i) === cpIdx;
    el.classList.toggle('on', on);
    if(on) el.scrollIntoView({block:'nearest'});
  });
}

function cpMove(step){
  if(!cpItems.length) return;
  cpIdx = (cpIdx + step + cpItems.length) % cpItems.length;
  cpMark();
}

function cpRun(i){
  const it = cpItems[i]; if(!it) return;
  cpRecentPush(it.cat === '最近使用' ? (it.hint || '操作') : it.cat, it.label);
  closeCmd();
  setTimeout(()=>{
    try { it.run(); } catch(e){ status('执行失败：' + (e && e.message || e), true); }
  }, 20);
}

function jumpFocus(tid, fid){
  const i = (DATA.trees || []).findIndex(t=>t.id === tid);
  if(i < 0){ status('找不到国策树：' + tid, true); return; }
  const switched = i !== current;
  current = i; selId = fid;
  renderAll();
  centerOnFocus(fid);
  showPanel();
  status((switched ? '已切换到 ' + tid + '，' : '') + '已定位：' + fid);
}

function centerOnFocus(fid){
  const t = curTree(); const f = t && nodeById(t, fid); if(!f) return;
  const rect = svg.getBoundingClientRect();
  const k = Math.max(view.k || 1, 0.85);
  view.k = k;
  view.x = rect.width / 2 - ((f.ax ?? f.x ?? 0) * SCALE + NODE_W / 2) * k;
  view.y = rect.height / 2 - ((f.ay ?? f.y ?? 0) * SCALE + NODE_H / 2) * k;
  applyView();
  updateZoomLabel();
}

function renderSearchHits(q){
  const box = document.getElementById('searchHits'); if(!box) return;
  box.innerHTML = '';
  q = (q || '').trim().toLowerCase();
  if(!q){ return; }
  const cur = curTree();
  const hits = [];
  const trees = (DATA && DATA.trees) || [];
  trees.forEach(t=>{
    (t.focuses || []).forEach(f=>{
      if(hits.length >= 400) return;
      if(String(f.id).toLowerCase().includes(q) || String(f.name || '').toLowerCase().includes(q)){
        hits.push({tid:t.id, fid:f.id, name:f.name || '', here: !!(cur && cur.id === t.id)});
      }
    });
  });
  hits.sort((a, b)=> (b.here - a.here));
  const shown = hits.slice(0, 24);
  shown.forEach((h, idx)=>{
    const row = document.createElement('div');
    row.className = 'sr-item' + (idx === 0 ? ' on' : '');
    row.innerHTML = '<b>' + escapeHtml(h.name && h.name !== h.fid ? h.name + ' · ' + h.fid : h.fid) + '</b>' +
      '<span>' + escapeHtml(h.tid) + '</span>';
    row.onclick = ()=>{ jumpFocus(h.tid, h.fid); };
    box.appendChild(row);
  });
  if(hits.length > shown.length){
    const more = document.createElement('div');
    more.className = 'sr-more';
    more.textContent = '另有 ' + (hits.length - shown.length) + ' 项，按 Ctrl+K 搜索全部';
    box.appendChild(more);
  }
  if(!hits.length){
    const none = document.createElement('div');
    none.className = 'sr-more';
    none.textContent = '没有命中的焦点';
    box.appendChild(none);
  }
}

function openKeys(){
  const grid = document.getElementById('keysGrid');
  grid.innerHTML = CP_KEYS.map(([k, d])=>
    '<div class="km-row"><span>' + escapeHtml(d) + '</span><kbd>' + escapeHtml(k) + '</kbd></div>').join('');
  document.getElementById('keysModal').classList.add('show');
}

function closeKeys(){ document.getElementById('keysModal').classList.remove('show'); }


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


function lintGoto(g){
  if(!g) return;
  if(g.type === 'tree'){ closeLint(); openTreeById(g.id); return; }
  if(g.type === 'country'){ closeLint(); openCountry(g.id); return; }
  if(g.type === 'idea'){ closeLint(); openIdeaById(g.id); return; }
  if(g.type === 'tech'){ closeLint(); openTechById(g.id); return; }
  if(g.type === 'event'){ closeLint(); openEvents(); const s = document.getElementById('eventSearch');
    if(s){ s.value = g.id; renderEventList(g.id); } return; }
  if(g.type === 'loc'){ navigator.clipboard && navigator.clipboard.writeText(g.id); status('已复制本地化键：' + g.id); return; }
  if(g.type === 'state'){ closeLint(); openStates(g.id); return; }
}
