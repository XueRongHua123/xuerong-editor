// 22-data：各国数据面板（P4）
// 国家 / 州 / 外交 / 历史 / 国家精神 / 驻外 / tag / gfx / 海军 / 空军 / 政治 /
// 已完成国策 / 剧本 / 人物 / 决议 / 部队模板 / 世界生成。
// 任务书里没有这一组，是 P4-5 拆剩下的那批「数据面板」——单列一个文件，避免 21-tools 变成 3000 行杂物间。

function openTreeSet(){
  const t = curTree();
  if(!t){ status('先选一棵国策树'); return; }
  document.getElementById('tsId').textContent = t.id + '   (' + t.file + ')';
  document.getElementById('tsDefault').value = t.default || '';
  const raw = (t.country_raw || '').trim();
  document.getElementById('tsCountry').value = raw ? ('country = {\n' + raw + '\n}') : '';
  document.getElementById('treeSet').classList.add('show');
}

async function saveTreeSet(){
  const t = curTree(); if(!t) return;
  const r = await fetch('/api/save_tree', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: rootOf(t), file: t.file, id: t.id,
      default: document.getElementById('tsDefault').value,
      country_raw: document.getElementById('tsCountry').value})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok){ document.getElementById('treeSet').classList.remove('show'); await loadData(); }
}

function openWorldGen(){
  const out = document.getElementById('wgOut');
  if(!out.value){
    const home = (DATA && DATA.mod_home) || '';
    out.value = home ? (home.replace(/[\\/]+$/, '') + '\\我的新世界') : '';
  }
  document.getElementById('worldGen').classList.add('show');
}

async function doWorldCreate(){
  const out = document.getElementById('wgOut').value.trim();
  if(!out){ status('先填输出目录', true); return; }
  const body = {
    out_dir: out,
    tag: (document.getElementById('wgTag').value.trim() || 'ZZV').toUpperCase(),
    country_name: document.getElementById('wgName').value.trim() || '新世界',
    n_provinces: parseInt(document.getElementById('wgProv').value, 10) || 40,
    seed: parseInt(document.getElementById('wgSeed').value, 10) || 11,
    n_focus: parseInt(document.getElementById('wgFocus').value, 10) || 24,
    per_state: parseInt(document.getElementById('wgPerState').value, 10) || 8,
    army: document.getElementById('wgArmy').checked,
    gen_focus: document.getElementById('wgFocusOn').checked,
    gen_event: document.getElementById('wgEvent').checked
  };
  document.getElementById('worldGen').classList.remove('show');
  startLoading('正在生成新世界…');
  updateLoading('生成地图、州、国家…');
  try{
    const r = await fetch('/api/world_create', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    const j = await r.json();
    if(j.ok){
      updateLoading('重新加载新世界…');
      await loadModByPath(out);
    }else{
      stopLoading(j.msg || '生成失败', true);
      status(j.msg || '生成失败', true);
    }
  }catch(e){
    stopLoading('生成失败：' + e.message, true);
  }
}

function _nmSourceLabel(src){
  return ({loaded:'已加载', launcher:'启动器', sibling:'同级目录', local:'本地', workshop:'创意工坊', extra:'目录'})[src] || src || '本地';
}

function _nmCollectModOptions(){
  const byPath = new Map();
  const ordered = [];
  const norm = p => String(p || '').replace(/[\\/]+$/, '').toLowerCase();
  const layers = ((DATA && DATA.layers) || []).filter(l => !l.game && l.path);
  const avail = (DATA && DATA.available_mods) || [];
  const availMap = new Map(avail.map(m => [norm(m.path), m]));

  // 当前叠加链按从顶层(最子)到基座(最父)优先排在最前，方便连续建多级 submod
  for(let i = layers.length - 1; i >= 0; i--){
    const l = layers[i];
    const k = norm(l.path);
    if(!k || byPath.has(k)) continue;
    const extra = availMap.get(k) || {};
    const item = {
      path: l.path,
      name: extra.descriptor_name || l.name || extra.folder || l.path,
      folder: extra.folder || l.path.split(/[\\/]/).filter(Boolean).pop() || '',
      readonly: !!l.readonly,
      loaded: true,
      tag: i === layers.length - 1 ? '当前顶层' : '当前链路',
    };
    byPath.set(k, item);
    ordered.push(item);
  }
  for(const m of avail){
    const k = norm(m.path);
    if(!k || byPath.has(k)) continue;
    const item = {
      path: m.path,
      name: m.descriptor_name || m.name || m.folder || m.path,
      folder: m.folder || '',
      readonly: !!m.readonly,
      loaded: !!m.loaded,
      tag: _nmSourceLabel(m.source),
    };
    byPath.set(k, item);
    ordered.push(item);
  }
  // 兜底：若 available_mods 为空（极早启动阶段），补入 DATA.roots
  for(const r of ((DATA && DATA.roots) || []).slice().reverse()){
    const k = norm(r.path);
    if(!k || byPath.has(k)) continue;
    const item = {
      path: r.path,
      name: r.name || r.path,
      folder: r.name || '',
      readonly: !!r.readonly,
      loaded: true,
      tag: '已加载',
    };
    byPath.set(k, item);
    ordered.push(item);
  }
  return ordered;
}

function _nmSyncTreeCheckbox(){
  const treeEl = document.getElementById('nmTree');
  if(!treeEl || treeEl.dataset.userTouched === '1') return;
  const tid = (document.getElementById('nmTreeId') && document.getElementById('nmTreeId').value || '').trim();
  const tag = (document.getElementById('nmTag') && document.getElementById('nmTag').value || '').trim();
  if(tid || tag){
    treeEl.checked = true;
    return;
  }
  const sel = document.getElementById('nmDepSel');
  const dep = document.getElementById('nmDep');
  const hasDep = !!((sel && sel.value && sel.value !== '__custom__') || (dep && dep.value.trim()));
  treeEl.checked = !hasDep;
}

function _nmUpdateDepHint(){
  const sel = document.getElementById('nmDepSel');
  const dep = document.getElementById('nmDep');
  const hint = document.getElementById('nmDepHint');
  if(!hint) return;
  const val = dep ? dep.value.trim() : '';
  const hasPath = dep && dep.dataset && dep.dataset.depPath;
  hint.style.display = 'block';
  if(!val && (!sel || !sel.value || sel.value === '__custom__')){
    hint.textContent = '留空表示不依赖任何 mod，直接从原版开始制作独立 mod。';
    return;
  }
  const opt = sel && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex] : null;
  const treeNote = ' 已选父 mod，默认不生成示例国策树；独立全新开树可再勾上。';
  if(opt && opt.value && opt.value !== '__custom__' && hasPath){
    const ro = opt.dataset.readonly === '1' ? '（只读底层，不会改动原文件）' : '';
    hint.textContent = '已选依赖「' + (opt.dataset.depName || val) + '」' + ro
                     + '；将写出 descriptor 真实 name= 到 dependencies，多级 submod 可直接继承其完整链路。'
                     + treeNote;
  }else{
    hint.textContent = '将按填写的「' + val + '」解析其 descriptor.mod 真实 name= 并写入 dependencies。' + treeNote;
  }
}

function openNewMod(){
  const b = document.getElementById('nmBase');
  if(!b.value) b.value = (DATA && DATA.mod_home) || '';
  document.getElementById('nmId').value = '';
  document.getElementById('nmName').value = '';
  document.getElementById('nmGame').value = (DATA && DATA.game_version) || '1.19.*';
  const tidEl = document.getElementById('nmTreeId');
  const tagEl = document.getElementById('nmTag');
  if(tidEl){ tidEl.value = ''; tidEl.oninput = _nmSyncTreeCheckbox; }
  if(tagEl){ tagEl.value = ''; tagEl.oninput = _nmSyncTreeCheckbox; }
  const treeEl = document.getElementById('nmTree');
  if(treeEl){
    delete treeEl.dataset.userTouched;
    treeEl.checked = true;
    treeEl.onchange = ()=>{ treeEl.dataset.userTouched = '1'; };
  }

  const sel = document.getElementById('nmDepSel');
  const dep = document.getElementById('nmDep');
  const mods = _nmCollectModOptions();

  if(sel){
    sel.innerHTML = '';
    const emptyOpt = document.createElement('option');
    emptyOpt.value = '';
    emptyOpt.textContent = '（不依赖任何 mod，从原版开始）';
    sel.appendChild(emptyOpt);

    for(const m of mods){
      const o = document.createElement('option');
      o.value = m.path;
      o.dataset.depName = m.name;
      o.dataset.readonly = m.readonly ? '1' : '0';
      const fPart = m.folder && m.folder !== m.name ? ' (' + m.folder + ')' : '';
      o.textContent = m.name + fPart + ' [' + m.tag + ']';
      sel.appendChild(o);
    }
    const customOpt = document.createElement('option');
    customOpt.value = '__custom__';
    customOpt.textContent = '（手动输入其它 mod 名或目录…）';
    sel.appendChild(customOpt);

    // 默认选中：优先叠加链最后一个已加载非只读层（支持多级 submod），其次已加载只读底层
    const loadedWritable = mods.find(m => m.loaded && !m.readonly);
    const loadedAny = mods.find(m => m.loaded);
    const defMod = loadedWritable || loadedAny || null;

    if(defMod){
      sel.value = defMod.path;
      if(dep){
        dep.value = defMod.name;
        dep.dataset.depPath = defMod.path;
      }
    }else{
      sel.value = '';
      if(dep){
        dep.value = '';
        dep.dataset.depPath = '';
      }
    }

    sel.onchange = ()=>{
      const opt = sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex] : null;
      if(!dep) return;
      if(!sel.value){
        dep.value = '';
        dep.dataset.depPath = '';
      }else if(sel.value === '__custom__'){
        dep.dataset.depPath = '';
        dep.focus();
      }else{
        dep.value = (opt && opt.dataset.depName) || '';
        dep.dataset.depPath = sel.value;
      }
      _nmSyncTreeCheckbox();
      _nmUpdateDepHint();
    };
  }else if(dep){
    const mine = ((DATA && DATA.roots) || []).filter(r => !r.readonly);
    const tail = mine.length ? mine[mine.length - 1] : null;
    dep.value = tail ? (tail.name || tail.path || '') : '';
  }

  if(dep){
    dep.oninput = ()=>{
      dep.dataset.depPath = '';
      if(sel){
        const v = dep.value.trim();
        if(!v){
          sel.value = '';
        }else{
          const match = Array.from(sel.options).find(
            o => o.value && o.value !== '__custom__' &&
                 ((o.dataset.depName || '').toLowerCase() === v.toLowerCase() ||
                  o.value.toLowerCase() === v.toLowerCase()));
          if(match){
            sel.value = match.value;
            dep.dataset.depPath = match.value;
          }else{
            sel.value = '__custom__';
          }
        }
      }
      _nmSyncTreeCheckbox();
      _nmUpdateDepHint();
    };
  }
  _nmSyncTreeCheckbox();
  _nmUpdateDepHint();
  document.getElementById('newMod').classList.add('show');
}

async function createNewMod(){
  const id = document.getElementById('nmId').value.trim();
  const name = document.getElementById('nmName').value.trim() || id;
  if(!id){ status('先填模组文件夹名'); return; }
  const depEl = document.getElementById('nmDep');
  const selEl = document.getElementById('nmDepSel');
  let depVal = depEl ? depEl.value.trim() : '';
  if(depEl && depEl.dataset && depEl.dataset.depPath && selEl && selEl.value === depEl.dataset.depPath){
    depVal = depEl.dataset.depPath;
  }
  const createTree = document.getElementById('nmTree').checked;
  const rawTag = document.getElementById('nmTag').value.trim().toUpperCase();
  const body = {
    base: document.getElementById('nmBase').value.trim() || (DATA && DATA.mod_home) || '',
    id, name,
    version: document.getElementById('nmVer').value.trim() || '0.1.0',
    game_version: document.getElementById('nmGame').value.trim() || (DATA && DATA.game_version) || '',
    create_tree: createTree,
    tree_id: document.getElementById('nmTreeId').value.trim() || (id + '_tree'),
    tag: (createTree && !rawTag) ? 'GER' : rawTag,
    dep: depVal
  };
  const okBtn = document.getElementById('nmOk');
  if(okBtn) okBtn.disabled = true;
  try{
    await withBusy('正在创建并加载模组…', async ()=>{
      const r = await fetch('/api/new_mod', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      const j = await r.json();
      status(j.msg || '', !j.ok);
      if(j.ok){ document.getElementById('newMod').classList.remove('show'); await loadData(); }
    });
  }finally{
    if(okBtn) okBtn.disabled = false;
  }
}

async function addEquip(){
  const id = prompt('新装备 ID（字母数字下划线）：');
  if(!id) return;
  const root = _writableRoot();
  if(!root){ status('先加载或新建一个可写的模组', true); return; }
  const btn = document.getElementById('equipAdd');
  if(btn) btn.disabled = true;
  status('正在新建装备…');
  try{
    const r = await fetch('/api/equip_add', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root, id})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
    if(j.ok){
      const sInp = document.getElementById('equipSearch');
      if(sInp) sInp.value = '';
      let hit = null;
      if(j.item){
        hit = _upsertDataItem('equipment', j.item);
      } else {
        await loadData();
        hit = (DATA.equipment||[]).find(x=>x.id===id);
      }
      renderEquipList('');
      if(hit) await selectEquip(hit);
    }
  } finally {
    if(btn) btn.disabled = false;
  }
}

async function deleteEquip(){
  if(!equipSel){ status('先选择装备'); return; }
  if(!confirm('确定删除装备 ' + equipSel.id + ' ？（可用 .bak 恢复）')) return;
  const cur = equipSel;
  const btn = document.getElementById('equipDelete');
  if(btn) btn.disabled = true;
  status('正在删除装备…');
  try{
    const r = await fetch('/api/equip_delete', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: rootByName(cur.source), file: cur.file, id: cur.id})});
    const j = await r.json();
    status(j.msg || '', !j.ok);
    if(j.ok){
      const q = document.getElementById('equipSearch')?.value || '';
      if(j.restored){
        _upsertDataItem('equipment', j.restored);
        renderEquipList(q);
        await selectEquip(j.restored);
      } else {
        if(j.deleted_id) _removeDataItem('equipment', j.deleted_id);
        else await loadData();
        equipSel = null;
        ['equipTitle', 'equipSrc'].forEach(id=>{ const el = document.getElementById(id); if(el) el.textContent = ''; });
        const propsBox = document.getElementById('equipProps');
        if(propsBox) propsBox.innerHTML = '';
        ['equipNameZ', 'equipDescZ', 'equipNameJa', 'equipDescJa', 'equipNameEn', 'equipDescEn',
         'equipPic', 'equipArch', 'equipIsArch', 'equipProduced', 'equipUpgrades', 'equipSlots', 'equipRaw'].forEach(id=>{
          const el = document.getElementById(id); if(el) el.value = '';
        });
        renderEquipList(q);
      }
    }
  } finally {
    if(btn) btn.disabled = false;
  }
}

function techFolderNames(){
  const set = new Set(((DATA && DATA.techs) || []).map(t=>t.path || '其他'));
  return Array.from(set).sort();
}


// v1.21.3 师团模板编辑（编制格可视化）
(function(){
  let TPLS = [], TPL = null, BATS = [], GRID = {}, SUP = {};
  const ROWS = 5, COLS = 5;

  function msg(t, bad){
    const el = document.getElementById('tplMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function loadBats(){
    if(BATS.length) return;
    try{
      const r = await (await fetch('/api/battalions', {method:'POST',
        headers:{'Content-Type':'application/json'}, body:'{}'})).json();
      if(r.ok){
        BATS = [];
        (r.groups || []).forEach(function(g){
          (g.items || []).forEach(function(x){ x.group = g.group; BATS.push(x); });
        });
      }
    }catch(e){}
  }

  function pickBat(x, y, isSup){
    const opts = BATS.map(function(b){
      return '<option value="' + b.id + '">[' + b.group + '] ' + b.id + '</option>';
    }).join('');
    const cur = (isSup ? SUP : GRID)[x + ',' + y] || '';
    const sel = prompt('格子 (' + x + ',' + y + ') 填兵种 id（留空删除）：\n\n可选：' + BATS.slice(0, 12).map(b=>b.id).join(', '), cur);
    if(sel === null) return;
    const v = sel.trim();
    const map = isSup ? SUP : GRID;
    if(!v) delete map[x + ',' + y];
    else map[x + ',' + y] = v;
    renderGrid();
  }

  function renderGrid(){
    const g = document.getElementById('tplGrid');
    if(g){
      let h = '';
      for(let y=0; y<ROWS; y++){
        for(let x=0; x<COLS; x++){
          const v = GRID[x+','+y];
          const short = v ? v.replace(/^MVLV_/, '').slice(0, 6) : '';
          h += '<div class="tpl-cell" data-x="' + x + '" data-y="' + y + '" data-sup="0"'
            + ' style="display:flex;align-items:center;justify-content:center;cursor:pointer;'
            + 'font-size:9px;font-family:Consolas,monospace;border:1px solid var(--line);border-radius:3px;'
            + 'background:' + (v ? 'var(--accent,#2d5)' : 'var(--input)') + ';color:' + (v ? '#fff' : 'var(--t3)') + '">'
            + (short || '+') + '</div>';
        }
      }
      g.innerHTML = h;
      g.querySelectorAll('.tpl-cell').forEach(function(c){
        c.onclick = function(){ pickBat(Number(c.dataset.x), Number(c.dataset.y), false); };
      });
    }
    const sp = document.getElementById('tplSup');
    if(sp){
      // 师级支援连：5 个固定槽位，每个用下拉选兵种（按组分类）
      let opts = '<option value="">— 空 —</option>';
      const byGroup = {};
      BATS.forEach(function(b){ (byGroup[b.group] = byGroup[b.group] || []).push(b); });
      Object.keys(byGroup).sort().forEach(function(g){
        opts += '<optgroup label="' + g + '">';
        byGroup[g].forEach(function(b){
          opts += '<option value="' + b.id + '">' + b.id + '</option>';
        });
        opts += '</optgroup>';
      });
      let h = '';
      for(let i=0; i<5; i++){
        const v = SUP[i+',0'] || '';
        h += '<div style="display:flex;align-items:center;gap:4px">'
          + '<span style="width:16px;font-size:10px;color:var(--t3);text-align:right">' + (i+1) + '</span>'
          + '<select class="tpl-sup-sel" data-x="' + i + '"'
          + ' style="flex:1;min-width:0;height:22px;font-size:10.5px;background:var(--input);'
          + 'border:1px solid ' + (v ? 'var(--warn,#a83)' : 'var(--line)') + ';'
          + 'color:' + (v ? 'var(--text)' : 'var(--t3)') + ';border-radius:3px">'
          + opts + '</select></div>';
      }
      sp.innerHTML = h;
      sp.querySelectorAll('.tpl-sup-sel').forEach(function(sel){
        const x = Number(sel.dataset.x);
        sel.value = SUP[x+',0'] || '';
        sel.onchange = function(){
          const v = sel.value;
          if(!v) delete SUP[x+',0'];
          else SUP[x+',0'] = v;
          msg('支援 ' + (x+1) + ' → ' + (v || '空'));
          renderGrid();
        };
      });
    }
  }

  function openTpl(t){
    TPL = t;
    GRID = {}; SUP = {};
    (t.regiments || []).forEach(function(r){ GRID[r.x + ',' + r.y] = r.unit; });
    (t.support || []).forEach(function(r){ SUP[r.x + ',' + r.y] = r.unit; });
    const box = document.getElementById('tplEditor');
    if(box) box.style.display = '';
    const nm = document.getElementById('tplName');
    if(nm) nm.value = t.name;
    renderGrid();
    msg('编制 ' + (t.regiments||[]).length + ' 格，支援 ' + (t.support||[]).length + ' 格');
  }

  async function loadTpls(){
    msg('读取模板…');
    const r = await (await fetch('/api/units', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    TPLS = r.templates || [];
    const box = document.getElementById('tplList');
    if(box){
      box.innerHTML = TPLS.map(function(t, i){
        return '<div class="tpl-row" data-i="' + i + '" style="display:flex;gap:4px;'
          + 'font-size:11px;font-family:Consolas,monospace;padding:1px 3px;cursor:pointer;'
          + 'border-bottom:1px solid var(--line)">'
          + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + t.name + '</span>'
          + '<span style="color:var(--t3);font-size:10px">' + t.regiment_count + '/' + t.support_count + '</span>'
          + '</div>';
      }).join('');
      box.querySelectorAll('.tpl-row').forEach(function(row){
        row.onclick = function(){ openTpl(TPLS[Number(row.dataset.i)]); };
      });
    }
    msg('共 ' + TPLS.length + ' 个模板，点一行编辑');
    await loadBats();
  }

  async function saveTpl(){
    if(!TPL){ msg('先选一个模板', true); return; }
    const regs = Object.keys(GRID).map(function(k){
      const a = k.split(',');
      return {unit: GRID[k], x: Number(a[0]), y: Number(a[1])};
    });
    const sup = Object.keys(SUP).map(function(k){
      const a = k.split(',');
      return {unit: SUP[k], x: Number(a[0]), y: Number(a[1])};
    });
    const nm = (document.getElementById('tplName')||{}).value || TPL.name;
    msg('保存中…');
    const r = await (await fetch('/api/template_save', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name: TPL.name, fields:{new_name: nm, regiments: regs, support: sup}})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await loadTpls(); }
  }

  async function delTpl(){
    if(!TPL){ msg('先选一个模板', true); return; }
    if(!confirm('删除模板「' + TPL.name + '」？')) return;
    const r = await (await fetch('/api/template_delete', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({name: TPL.name})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      document.getElementById('tplEditor').style.display = 'none';
      await loadTpls();
    }
  }

  async function newTpl(){
    const nm = prompt('新模板名（英文/数字/下划线）：','');
    if(!nm) return;
    const unit = prompt('第一格兵种 id：','infantry') || 'infantry';
    const r = await (await fetch('/api/template_add', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name: nm, unit: unit, x: 0, y: 0,
                            tag: ((document.getElementById('tplTag')||{}).value||'').trim().toUpperCase() || null})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await loadTpls(); }
  }

  function bind(){
    [['tplLoad', loadTpls], ['tplSave', saveTpl], ['tplDel', delTpl], ['tplNew', newTpl]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.7 国家精神（add_ideas）
(function(){
  let CIDEAS = [], CCHOSEN = new Set(), CTAG2 = '';

  function msg(t, bad){
    const el = document.getElementById('cideaMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function renderOn(){
    const box = document.getElementById('cideaOn');
    if(!box) return;
    const arr = [...CCHOSEN];
    if(!arr.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:2px">（无）</div>'; return; }
    box.innerHTML = arr.map(function(id){
      return '<div style="display:flex;gap:4px;align-items:center;font-size:10.5px;'
        + 'font-family:Consolas,monospace;padding:1px 0">'
        + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + id + '</span>'
        + '<button class="btn ci-del" data-id="' + id + '" style="height:17px;font-size:9px;padding:0 4px">删</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.ci-del').forEach(function(b){
      b.onclick = function(){ toggle(b.dataset.id, false); };
    });
  }

  function renderHits(q){
    const box = document.getElementById('cideaHits');
    if(!box) return;
    q = (q || '').trim().toLowerCase();
    let hits;
    if(!q){ hits = CIDEAS.slice(0, 40); }
    else{
      hits = CIDEAS.filter(function(x){
        return x.id.toLowerCase().indexOf(q) >= 0
          || (x.name || '').toLowerCase().indexOf(q) >= 0;
      }).slice(0, 60);
    }
    if(!hits.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:2px">没有匹配</div>'; return; }
    box.innerHTML = hits.map(function(x){
      const on = CCHOSEN.has(x.id);
      return '<div style="display:flex;gap:5px;align-items:center;font-size:10.5px;'
        + 'font-family:Consolas,monospace;padding:1px 0">'
        + '<input type="checkbox" class="ci-add" data-id="' + x.id + '"' + (on ? ' checked disabled' : '') + '>'
        + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + (x.name||'') + '">'
        + x.id + (x.name && x.name !== x.id ? '　' + x.name : '') + '</span>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.ci-add').forEach(function(cb){
      cb.onchange = function(){ if(cb.checked) toggle(cb.dataset.id, true); };
    });
  }

  async function load(){
    const tag = ((document.getElementById('cideaTag')||{}).value || '').trim().toUpperCase();
    if(!tag){ msg('填 tag', true); return; }
    CTAG2 = tag;
    msg('读取中…');
    const r = await (await fetch('/api/country_ideas', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({tag: tag})})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    CCHOSEN = new Set(r.ideas || []);
    CIDEAS = r.items || [];
    msg(r.msg || '');
    renderOn();
    renderHits('');
  }

  async function toggle(id, on){
    if(!CTAG2) return;
    msg('写入中…');
    const r = await (await fetch('/api/country_idea_toggle', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: CTAG2, idea: id, on: on})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      if(on) CCHOSEN.add(id); else CCHOSEN.delete(id);
      renderOn();
      renderHits((document.getElementById('cideaQ')||{}).value || '');
    }
  }

  function bind(){
    const b = document.getElementById('cideaLoad');
    if(b && !b.dataset.bound){ b.dataset.bound = '1'; b.onclick = load; }
    const t = document.getElementById('cideaTag');
    if(t && !t.dataset.bound){ t.dataset.bound = '1';
      t.addEventListener('keydown', function(e){ if(e.key === 'Enter') load(); }); }
    const q = document.getElementById('cideaQ');
    if(q && !q.dataset.bound){ q.dataset.bound = '1';
      let tm = null;
      q.addEventListener('input', function(){
        clearTimeout(tm);
        tm = setTimeout(function(){ renderHits(q.value); }, 200);
      }); }
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.8 国家离岸建筑
(function(){
  let OTAG = '', OITEMS = [], OTYPES = [];

  function msg(t, bad){
    const el = document.getElementById('ofsMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function renderList(){
    const box = document.getElementById('ofsList');
    if(!box) return;
    if(!OITEMS.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:2px">（无）</div>'; return; }
    box.innerHTML = OITEMS.map(function(it){
      return '<div style="display:flex;gap:4px;align-items:center;font-size:10.5px;'
        + 'font-family:Consolas,monospace;padding:1px 0">'
        + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + it.type + '</span>'
        + '<span style="color:var(--t3)">×' + it.level + '</span>'
        + '<button class="btn ofs-edit" data-i="' + it.i + '" data-t="' + it.type + '" data-l="' + it.level + '" style="height:17px;font-size:9px;padding:0 3px">改</button>'
        + '<button class="btn ofs-del" data-i="' + it.i + '" style="height:17px;font-size:9px;padding:0 3px">删</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.ofs-del').forEach(function(b){
      b.onclick = async function(){
        if(!confirm('删除这一项？')) return;
        const r = await (await fetch('/api/country_offsite_delete', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({tag: OTAG, index: Number(b.dataset.i)})})).json();
        msg(r.msg || '', !r.ok);
        if(r.ok){ status(r.msg); await load(); }
      };
    });
    box.querySelectorAll('.ofs-edit').forEach(function(b){
      b.onclick = async function(){
        const nt = prompt('建筑类型：', b.dataset.t);
        if(nt === null) return;
        const nl = prompt('数量：', b.dataset.l);
        if(nl === null) return;
        const r = await (await fetch('/api/country_offsite_set', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({tag: OTAG, index: Number(b.dataset.i),
                                type: nt.trim(), level: Number(nl)})})).json();
        msg(r.msg || '', !r.ok);
        if(r.ok){ status(r.msg); await load(); }
      };
    });
  }

  async function load(){
    const tag = ((document.getElementById('ofsTag')||{}).value || '').trim().toUpperCase();
    if(!tag){ msg('填 tag', true); return; }
    OTAG = tag;
    msg('读取中…');
    const r = await (await fetch('/api/country_starter', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({tag: tag})})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    OITEMS = r.items || [];
    OTYPES = r.types || [];
    msg(r.msg || '');
    renderList();
    const sel = document.getElementById('ofsType');
    if(sel && !sel.dataset.filled){
      sel.innerHTML = OTYPES.map(function(t){ return '<option value="' + t + '">' + t + '</option>'; }).join('');
      sel.dataset.filled = '1';
    }
  }

  async function add(){
    const sel = document.getElementById('ofsType');
    const lv = (document.getElementById('ofsLevel')||{}).value || '1';
    if(!OTAG){ msg('先载入', true); return; }
    if(!sel || !sel.value){ msg('选类型', true); return; }
    msg('写入中…');
    const r = await (await fetch('/api/country_offsite_add', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: OTAG, type: sel.value, level: Number(lv)})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await load(); }
  }

  function bind(){
    [['ofsLoad', load], ['ofsAdd', add]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
    const t = document.getElementById('ofsTag');
    if(t && !t.dataset.bound){ t.dataset.bound = '1';
      t.addEventListener('keydown', function(e){ if(e.key === 'Enter') load(); }); }
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.9 国家 TAG 增删
(function(){
  let TAGS = [];

  function msg(t, bad){
    const el = document.getElementById('ctagMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function render(){
    const box = document.getElementById('ctagList');
    if(!box) return;
    const q = ((document.getElementById('ctagQ')||{}).value || '').trim().toUpperCase();
    const list = q ? TAGS.filter(function(x){ return x.tag.indexOf(q) >= 0 || (x.def||'').toUpperCase().indexOf(q) >= 0; }) : TAGS;
    if(!list.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:2px">没有匹配</div>'; return; }
    box.innerHTML = list.slice(0, 200).map(function(x){
      return '<div style="display:flex;gap:4px;align-items:center;font-size:10.5px;'
        + 'font-family:Consolas,monospace;padding:1px 0">'
        + '<span style="width:38px">' + x.tag + '</span>'
        + '<span style="flex:1;color:var(--t3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (x.def||'') + '</span>'
        + '<button class="btn ct-del" data-t="' + x.tag + '" style="height:16px;font-size:9px;padding:0 3px">删</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.ct-del').forEach(function(b){
      b.onclick = function(){ del(b.dataset.t); };
    });
  }

  async function load(){
    msg('读取中…');
    const r = await (await fetch('/api/country_tags', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    TAGS = r.items || [];
    msg(r.msg || '');
    render();
  }

  async function add(){
    const tag = ((document.getElementById('ctagNew')||{}).value || '').trim().toUpperCase();
    const col = ((document.getElementById('ctagColor')||{}).value || '').trim();
    if(!tag){ msg('填 TAG', true); return; }
    let color = null;
    if(col){
      const parts = col.split(/[,\s]+/).map(Number).filter(function(x){ return !isNaN(x); });
      if(parts.length !== 3){ msg('颜色要三个数，如 200,80,60', true); return; }
      color = parts;
    }
    msg('写入中…');
    const r = await (await fetch('/api/country_tag_add', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: tag, color: color})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await load(); }
  }

  async function del(tag){
    let r = await (await fetch('/api/country_tag_delete', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({tag: tag})})).json();
    if(!r.ok && r.need_confirm){
      if(!confirm(r.msg + '\n\n仍然要删？')){ msg('已取消', true); return; }
      msg('引用检查拦住时不能强删，请先清掉引用', true);
      return;
    }
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await load(); }
  }

  function bind(){
    [['ctagLoad', load], ['ctagAdd', add]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
    const q = document.getElementById('ctagQ');
    if(q && !q.dataset.bound){ q.dataset.bound = '1';
      q.addEventListener('input', function(){ render(); }); }
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.10 图标导入
(function(){
  function msg(t, bad){
    const el = document.getElementById('gfxMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function doImport(){
    const src = ((document.getElementById('gfxSrc')||{}).value || '').trim();
    const kind = (document.getElementById('gfxKind')||{}).value || 'goal';
    const size = Number((document.getElementById('gfxSize')||{}).value || 64);
    const name = ((document.getElementById('gfxName')||{}).value || '').trim();
    if(!src){ msg('填源文件路径', true); return; }
    msg('导入中…');
    let r = await (await fetch('/api/gfx_import', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({src: src, kind: kind, size: size,
                            name: name || null, overwrite: false})})).json();
    if(!r.ok && r.need_confirm){
      if(!confirm(r.msg + '\n\n覆盖？')){ msg('已取消', true); return; }
      r = await (await fetch('/api/gfx_import', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({src: src, kind: kind, size: size,
                              name: name || null, overwrite: true})})).json();
    }
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); }
  }

  async function listSprites(){
    const box = document.getElementById('gfxList');
    const q = ((document.getElementById('gfxQ')||{}).value || '').trim();
    msg('查询中…');
    const r = await (await fetch('/api/gfx_sprites', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({pattern: q})})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    msg(r.msg || '');
    if(!box) return;
    box.innerHTML = (r.items || []).map(function(x){
      return '<div style="font-size:10px;font-family:Consolas,monospace;padding:1px 0;'
        + 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + (x.texture||'') + '">'
        + x.name + '</div>';
    }).join('') || '<div style="font-size:11px;color:var(--t3);padding:2px">没有匹配</div>';
  }

  function bind(){
    [['gfxDo', doImport], ['gfxListBtn', listSprites]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.11 开局舰队
(function(){
  let FLEETS = [];

  function msg(t, bad){
    const el = document.getElementById('navyMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function render(){
    const box = document.getElementById('navyList');
    if(!box) return;
    if(!FLEETS.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:2px">（无舰队）</div>'; return; }
    box.innerHTML = FLEETS.map(function(f, fi){
      const tfs = (f.task_forces || []).map(function(t, ti){
        return '<div style="display:flex;gap:4px;align-items:center;padding-left:10px;font-size:10px;'
          + 'font-family:Consolas,monospace;color:var(--t3)">'
          + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
          + '　' + t.name + '（' + t.ship_count + ' 艘）</span>'
          + '<button class="btn nv-deltf" data-fi="' + fi + '" data-ti="' + ti + '" style="height:15px;font-size:8px;padding:0 3px">删</button>'
          + '</div>';
      }).join('');
      return '<details style="margin-bottom:2px">'
        + '<summary style="font-size:10.5px;font-family:Consolas,monospace;cursor:pointer;padding:1px 2px">'
        + f.name + ' <span style="color:var(--t3)">基地 ' + f.naval_base + '｜' + f.tf_count + ' 队｜' + f.ship_total + ' 艘</span>'
        + '</summary>'
        + '<div style="display:flex;justify-content:flex-end">'
        + '<button class="btn nv-delf" data-fi="' + fi + '" style="height:15px;font-size:8px;padding:0 4px">删整支</button>'
        + '</div>'
        + tfs + '</details>';
    }).join('');
    box.querySelectorAll('.nv-delf').forEach(function(b){
      b.onclick = async function(e){
        e.preventDefault();
        if(!confirm('删掉整支舰队？')) return;
        const r = await (await fetch('/api/navy_delete_fleet', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({fi: Number(b.dataset.fi)})})).json();
        msg(r.msg || '', !r.ok);
        if(r.ok){ status(r.msg); await load(); }
      };
    });
    box.querySelectorAll('.nv-deltf').forEach(function(b){
      b.onclick = async function(e){
        e.preventDefault();
        if(!confirm('删掉这个特遣队？')) return;
        const r = await (await fetch('/api/navy_delete_tf', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({fi: Number(b.dataset.fi), ti: Number(b.dataset.ti)})})).json();
        msg(r.msg || '', !r.ok);
        if(r.ok){ status(r.msg); await load(); }
      };
    });
  }

  async function load(){
    msg('读取中…');
    const r = await (await fetch('/api/navy', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    FLEETS = r.fleets || [];
    msg(r.msg || '');
    render();
  }

  function bind(){
    const b = document.getElementById('navyLoad');
    if(b && !b.dataset.bound){ b.dataset.bound = '1'; b.onclick = load; }
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.12 舰队增改前端
(function(){
  function msg(t, bad){
    const el = document.getElementById('navyMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }
  function v(id, dflt){
    const el = document.getElementById(id);
    return el && el.value !== '' ? el.value : dflt;
  }

  async function addShip(){
    const fi = Number(v('nvFi', 0)), ti = Number(v('nvTi', 0));
    const name = v('nvShipName', '');
    const def = v('nvShipDef', 'destroyer');
    const exp = v('nvShipExp', '0.3');
    msg('加船中…');
    const r = await (await fetch('/api/navy_add_ship', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({fi: fi, ti: ti, name: name || null,
                            definition: def, exp: exp,
                            tag: ((document.getElementById('nvTag')||{}).value||'').trim().toUpperCase() || null})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); }
  }

  async function addTf(){
    const fi = Number(v('nvTfFi', 0));
    const name = v('nvTfName', '');
    const loc = v('nvTfLoc', '');
    msg('加队中…');
    const r = await (await fetch('/api/navy_add_tf', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({fi: fi, name: name || null,
                            location: loc ? Number(loc) : null,
                            tag: ((document.getElementById('nvTag')||{}).value||'').trim().toUpperCase() || null})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); }
  }

  function bind(){
    [['nvAddShip', addShip], ['nvAddTf', addTf]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.13 开局空军
(function(){
  let WINGS = [];

  function msg(t, bad){
    const el = document.getElementById('airMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function render(){
    const box = document.getElementById('airList');
    if(!box) return;
    if(!WINGS.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:2px">（无联队）</div>'; return; }
    box.innerHTML = WINGS.map(function(w, i){
      const eq = (w.equipment || []).map(function(x){
        return x.type.replace(/_equipment.*$/, '') + '×' + x.amount;
      }).join(', ');
      return '<div style="display:flex;gap:4px;align-items:center;font-size:10px;'
        + 'font-family:Consolas,monospace;padding:1px 0">'
        + '<span style="width:44px;color:var(--t3)">省' + w.province + '</span>'
        + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + eq + '">'
        + w.name + '</span>'
        + '<span style="color:var(--t3);font-size:9px">' + w.eq_count + '</span>'
        + '<button class="btn air-del" data-i="' + i + '" style="height:15px;font-size:8px;padding:0 3px">删</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.air-del').forEach(function(b){
      b.onclick = async function(){
        if(!confirm('删掉这支联队？')) return;
        const r = await (await fetch('/api/air_wing_delete', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({index: Number(b.dataset.i)})})).json();
        msg(r.msg || '', !r.ok);
        if(r.ok){ status(r.msg); await load(); }
      };
    });
  }

  async function load(){
    msg('读取中…');
    const r = await (await fetch('/api/air_wings', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    WINGS = r.wings || [];
    msg(r.msg || '');
    render();
  }

  async function add(){
    const prov = Number((document.getElementById('airProv')||{}).value || 0);
    const name = ((document.getElementById('airName')||{}).value || '').trim();
    const type = ((document.getElementById('airType')||{}).value || 'fighter_equipment_1').trim();
    const owner = ((document.getElementById('airOwner')||{}).value || '').trim().toUpperCase();
    const amt = Number((document.getElementById('airAmt')||{}).value || 10);
    if(!prov){ msg('填省号', true); return; }
    if(!owner){ msg('填 TAG', true); return; }
    msg('写入中…');
    const r = await (await fetch('/api/air_wing_add', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({province: prov, name: name || null, type: type,
                            owner: owner, amount: amt})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await load(); }
  }

  function bind(){
    [['airLoad', load], ['airAdd', add]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.14 开局政治与外交
(function(){
  let PTAG = '';

  function msg(t, bad){
    const el = document.getElementById('polMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function render(data){
    const body = document.getElementById('polBody');
    if(body) body.style.display = '';
    const p = data.politics || {};
    const party = document.getElementById('polParty');
    if(party && p.ruling_party){
      for(const o of party.options){ if(o.value === p.ruling_party){ party.value = p.ruling_party; break; } }
    }
    const el = document.getElementById('polElect');
    if(el && p.elections_allowed) el.value = p.elections_allowed;
    const pops = data.popularities || {};
    const map = {popDem: 'democratic', popFas: 'fascism', popCom: 'communism', popNeu: 'neutrality'};
    Object.keys(map).forEach(function(id){
      const inp = document.getElementById(id);
      if(inp) inp.value = (pops[map[id]] != null ? pops[map[id]] : '');
    });
    const box = document.getElementById('warList');
    if(box){
      const ws = data.wars || [];
      box.innerHTML = ws.length ? ws.map(function(w, i){
        return '<div style="display:flex;gap:4px;align-items:center;font-size:10px;'
          + 'font-family:Consolas,monospace;padding:1px 0">'
          + '<span style="flex:1">' + w.target + ' <span style="color:var(--t3)">' + w.type + '</span></span>'
          + '<button class="btn war-del" data-i="' + i + '" style="height:15px;font-size:8px;padding:0 3px">删</button>'
          + '</div>';
      }).join('') : '<div style="font-size:11px;color:var(--t3);padding:2px">（无战争）</div>';
      box.querySelectorAll('.war-del').forEach(function(b){
        b.onclick = async function(){
          if(!confirm('删掉这条宣战？')) return;
          const r = await (await fetch('/api/war_delete', {method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({tag: PTAG, index: Number(b.dataset.i)})})).json();
          msg(r.msg || '', !r.ok);
          if(r.ok){ status(r.msg); await load(); }
        };
      });
    }
  }

  async function load(){
    const tag = ((document.getElementById('polTag')||{}).value || '').trim().toUpperCase();
    if(!tag){ msg('填 tag', true); return; }
    PTAG = tag;
    msg('读取中…');
    const r = await (await fetch('/api/politics', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({tag: tag})})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    msg(r.msg || '');
    render(r);
  }

  async function savePol(){
    if(!PTAG) return;
    const party = (document.getElementById('polParty')||{}).value;
    const elect = (document.getElementById('polElect')||{}).value;
    msg('写入中…');
    const r = await (await fetch('/api/politics_save', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: PTAG, fields:{ruling_party: party, elections_allowed: elect}})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); }
  }

  async function savePops(){
    if(!PTAG) return;
    const g = function(id){ const v = (document.getElementById(id)||{}).value; return v === '' ? null : Number(v); };
    const pops = {};
    const map = {popDem: 'democratic', popFas: 'fascism', popCom: 'communism', popNeu: 'neutrality'};
    Object.keys(map).forEach(function(id){
      const v = g(id);
      if(v !== null && !isNaN(v)) pops[map[id]] = v;
    });
    if(!Object.keys(pops).length){ msg('一个支持率都没填', true); return; }
    msg('写入中…');
    const r = await (await fetch('/api/popularities_save', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: PTAG, pops: pops})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await load(); }
  }

  async function addWar(){
    if(!PTAG) return;
    const tgt = ((document.getElementById('warTarget')||{}).value || '').trim().toUpperCase();
    const type = ((document.getElementById('warType')||{}).value || 'annex').trim();
    if(!tgt){ msg('填目标 TAG', true); return; }
    msg('写入中…');
    const r = await (await fetch('/api/war_add', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: PTAG, target: tgt, type: type})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await load(); }
  }

  function bind(){
    [['polLoad', load], ['polSave', savePol], ['popSave', savePops], ['warAdd', addWar]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.15 开局已完成国策
(function(){
  let CTAG2 = '', ITEMS = [];

  function msg(t, bad){
    const el = document.getElementById('cfMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function render(){
    const box = document.getElementById('cfList');
    if(!box) return;
    if(!ITEMS.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:2px">（无）</div>'; return; }
    box.innerHTML = ITEMS.map(function(x, i){
      const tip = x.known ? (x.name || x.tree) : '未在国策树里找到';
      return '<div style="display:flex;gap:4px;align-items:center;font-size:10px;'
        + 'font-family:Consolas,monospace;padding:1px 0">'
        + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + tip + '">'
        + x.focus + (x.known ? '' : ' ⚠') + '</span>'
        + '<button class="btn cf-del" data-i="' + i + '" style="height:15px;font-size:8px;padding:0 3px">删</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.cf-del').forEach(function(b){
      b.onclick = async function(){
        if(!confirm('删掉这条？')) return;
        const r = await (await fetch('/api/focus_complete_delete', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({tag: CTAG2, index: Number(b.dataset.i)})})).json();
        msg(r.msg || '', !r.ok);
        if(r.ok){ status(r.msg); await load(); }
      };
    });
  }

  async function load(){
    const tag = ((document.getElementById('cfTag')||{}).value || '').trim().toUpperCase();
    if(!tag){ msg('填 tag', true); return; }
    CTAG2 = tag;
    msg('读取中…');
    const r = await (await fetch('/api/completed_focuses', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({tag: tag})})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    ITEMS = r.items || [];
    msg(r.msg || '');
    render();
  }

  async function add(){
    const fid = ((document.getElementById('cfId')||{}).value || '').trim();
    if(!CTAG2){ msg('先载入', true); return; }
    if(!fid){ msg('填国策 id', true); return; }
    msg('写入中…');
    const r = await (await fetch('/api/focus_complete_add', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: CTAG2, focus: fid})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await load(); }
  }

  function bind(){
    [['cfLoad', load], ['cfAdd', add]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.16 开局剧本 bookmark
(function(){
  let BMS = [];

  function msg(t, bad){
    const el = document.getElementById('bmMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function render(){
    const box = document.getElementById('bmList');
    if(!box) return;
    if(!BMS.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:2px">（无剧本）</div>'; return; }
    box.innerHTML = BMS.map(function(x, i){
      return '<div style="display:flex;gap:4px;align-items:center;font-size:10px;'
        + 'font-family:Consolas,monospace;padding:1px 0">'
        + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + (x.file||'') + '">'
        + (x.name || '(无名)') + '</span>'
        + '<span style="color:var(--t3);width:74px;text-align:right">' + x.date + '</span>'
        + '<span style="color:var(--t3);width:26px;text-align:right">' + x.country_count + '</span>'
        + '<button class="btn bm-del" data-i="' + i + '" style="height:15px;font-size:8px;padding:0 3px">删</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.bm-del').forEach(function(b){
      b.onclick = async function(){
        if(!confirm('删掉这个剧本？')) return;
        const r = await (await fetch('/api/bookmark_delete', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({index: Number(b.dataset.i)})})).json();
        msg(r.msg || '', !r.ok);
        if(r.ok){ status(r.msg); await load(); }
      };
    });
  }

  async function load(){
    msg('读取中…');
    const r = await (await fetch('/api/bookmarks', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    BMS = r.items || [];
    msg(r.msg || '');
    render();
  }

  async function add(){
    const name = ((document.getElementById('bmName')||{}).value || '').trim();
    const date = ((document.getElementById('bmDate')||{}).value || '').trim();
    const desc = ((document.getElementById('bmDesc')||{}).value || '').trim();
    const dc = ((document.getElementById('bmCountry')||{}).value || 'GER').trim().toUpperCase();
    if(!name){ msg('填名称 key', true); return; }
    if(!date){ msg('填日期，如 1936.1.1', true); return; }
    msg('写入中…');
    const r = await (await fetch('/api/bookmark_add', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name: name, date: date, desc: desc || null,
                            default_country: dc})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await load(); }
  }

  function bind(){
    [['bmLoad', load], ['bmAdd', add]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.18 人物编辑
(function(){
  let ALL = [], CUR = null;

  function msg(t, bad){
    const el = document.getElementById('chMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function render(){
    const box = document.getElementById('chList');
    if(!box) return;
    const q = ((document.getElementById('chQ')||{}).value || '').trim().toLowerCase();
    const list = q ? ALL.filter(function(x){
      return x.id.toLowerCase().indexOf(q) >= 0
        || (x.name || '').toLowerCase().indexOf(q) >= 0;
    }) : ALL;
    if(!list.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:2px">没有匹配</div>'; return; }
    box.innerHTML = list.slice(0, 200).map(function(x){
      const sk = (x.skills || {}).skill;
      return '<div class="ch-row" data-id="' + x.id + '" style="display:flex;gap:4px;'
        + 'align-items:center;font-size:10px;font-family:Consolas,monospace;padding:1px 0;cursor:pointer">'
        + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
        + x.name + ' <span style="color:var(--t3)">' + (x.type || '') + '</span></span>'
        + (sk != null ? '<span style="color:var(--t3);width:16px;text-align:right">' + sk + '</span>' : '')
        + '<button class="btn ch-del" data-id="' + x.id + '" style="height:15px;font-size:8px;padding:0 3px">删</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.ch-row').forEach(function(row){
      row.onclick = function(e){
        if(e.target.classList && e.target.classList.contains('ch-del')) return;
        pick(row.dataset.id);
      };
    });
    box.querySelectorAll('.ch-del').forEach(function(b){
      b.onclick = async function(e){
        e.stopPropagation();
        if(!confirm('删掉这个人物？')) return;
        const r = await (await fetch('/api/character_delete', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({id: b.dataset.id})})).json();
        msg(r.msg || '', !r.ok);
        if(r.ok){ status(r.msg); await load(); }
      };
    });
  }

  function pick(id){
    CUR = ALL.find(function(x){ return x.id === id; }) || null;
    if(!CUR) return;
    const nm = document.getElementById('chName');
    if(nm) nm.value = CUR.name || '';
    const sk = CUR.skills || {};
    const set = function(k, v){ const e = document.getElementById(k); if(e) e.value = (v != null ? v : ''); };
    const tp = document.getElementById('chType');
    if(tp) tp.value = CUR.type || '';
    set('chSkill', sk.skill); set('chAtk', sk.attack_skill);
    set('chDef', sk.defense_skill); set('chPlan', sk.planning_skill);
    set('chLog', sk.logistics_skill);
    msg('已选中 ' + CUR.name + '（' + CUR.id + '）');
  }

  async function load(){
    msg('读取中…');
    const r = await (await fetch('/api/characters', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    ALL = r.items || [];
    msg(r.msg || '');
    render();
  }

  async function save(){
    if(!CUR){ msg('先选一个人物', true); return; }
    const fields = {};
    const nm = (document.getElementById('chName')||{}).value;
    if(nm && nm !== CUR.name) fields.name = nm;
    const tpSel = document.getElementById('chType');
    if(tpSel && tpSel.value && tpSel.value !== CUR.type) fields.type = tpSel.value;
    const pairs = [['chSkill', 'skill'], ['chAtk', 'attack_skill'], ['chDef', 'defense_skill'],
                   ['chPlan', 'planning_skill'], ['chLog', 'logistics_skill']];
    pairs.forEach(function(p){
      const e = document.getElementById(p[0]);
      if(e && e.value !== '') fields[p[1]] = Number(e.value);
    });
    if(!Object.keys(fields).length){ msg('没有改动', true); return; }
    msg('写入中…');
    const r = await (await fetch('/api/character_set', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: CUR.id, fields: fields})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await load(); }
  }

  function bind(){
    [['chLoad', load], ['chSave', save]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
    const q = document.getElementById('chQ');
    if(q && !q.dataset.bound){ q.dataset.bound = '1';
      q.addEventListener('input', function(){ render(); }); }
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.19 决议编辑
(function(){
  let ALL = [], CUR = null;

  function msg(t, bad){
    const el = document.getElementById('decMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function render(){
    const box = document.getElementById('decList');
    if(!box) return;
    const q = ((document.getElementById('decQ')||{}).value || '').trim().toLowerCase();
    const list = q ? ALL.filter(function(x){
      return x.id.toLowerCase().indexOf(q) >= 0 || (x.cat||'').toLowerCase().indexOf(q) >= 0;
    }) : ALL;
    if(!list.length){ box.innerHTML = '<div style="font-size:11px;color:var(--t3);padding:2px">没有匹配</div>'; return; }
    box.innerHTML = list.slice(0, 200).map(function(x){
      const f = x.fields || {};
      const tip = 'cost=' + (f.cost || '-') + ' days=' + (f.days_remove || '-');
      return '<div class="dec-row" data-id="' + x.id + '" style="display:flex;gap:4px;'
        + 'align-items:center;font-size:10px;font-family:Consolas,monospace;padding:1px 0;cursor:pointer"'
        + ' title="' + tip + '">'
        + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
        + x.id + ' <span style="color:var(--t3)">' + x.cat + '</span></span>'
        + '<button class="btn dec-del" data-id="' + x.id + '" style="height:15px;font-size:8px;padding:0 3px">删</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.dec-row').forEach(function(row){
      row.onclick = function(e){
        if(e.target.classList && e.target.classList.contains('dec-del')) return;
        pick(row.dataset.id);
      };
    });
    box.querySelectorAll('.dec-del').forEach(function(b){
      b.onclick = async function(e){
        e.stopPropagation();
        if(!confirm('删掉这条决议？')) return;
        const r = await (await fetch('/api/decision_delete', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({id: b.dataset.id})})).json();
        msg(r.msg || '', !r.ok);
        if(r.ok){ status(r.msg); await load(); }
      };
    });
  }

  function pick(id){
    CUR = ALL.find(function(x){ return x.id === id; }) || null;
    if(!CUR) return;
    const f = CUR.fields || {};
    const set = function(k, v){ const e = document.getElementById(k); if(e) e.value = (v != null ? v : ''); };
    set('decCost', f.cost); set('decDays', f.days_remove); set('decPrio', f.priority);
    msg('已选中 ' + CUR.id + '（' + CUR.cat + '）');
  }

  async function load(){
    msg('读取中…');
    const r = await (await fetch('/api/decisions', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    if(!r.ok){ msg(r.msg || '失败', true); return; }
    ALL = r.decisions || [];
    msg(r.msg || '');
    render();
  }

  async function save(){
    if(!CUR){ msg('先选一条决议', true); return; }
    const fields = {};
    const v = function(id){ const e = document.getElementById(id); return e && e.value !== '' ? e.value : null; };
    const c = v('decCost'); if(c !== null) fields.cost = c;
    const d = v('decDays'); if(d !== null) fields.days_remove = d;
    const p = v('decPrio'); if(p !== null) fields.priority = p;
    if(!Object.keys(fields).length){ msg('没有改动', true); return; }
    msg('写入中…');
    const r = await (await fetch('/api/decision_set', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: CUR.id, fields: fields})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await load(); }
  }

  function bind(){
    [['decLoad', load], ['decSave', save]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
    const q = document.getElementById('decQ');
    if(q && !q.dataset.bound){ q.dataset.bound = '1';
      q.addEventListener('input', function(){ render(); }); }
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.23.8 人物与决议新建
(function(){
  function msgOf(id){
    return function(t, bad){
      const el = document.getElementById(id);
      if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
    };
  }

  async function addChar(){
    const msg = msgOf('chMsg');
    const id = ((document.getElementById('chNewId')||{}).value || '').trim();
    const name = ((document.getElementById('chNewName')||{}).value || '').trim();
    const type = (document.getElementById('chNewType')||{}).value || 'corps_commander';
    const country = ((document.getElementById('chNewCountry')||{}).value || '').trim().toUpperCase();
    const skill = Number((document.getElementById('chNewSkill')||{}).value || 3);
    const psrc = ((document.getElementById('chPortrait')||{}).value || '').trim();
    if(!id){ msg('填 id', true); return; }
    if(!name){ msg('填名字', true); return; }
    if(!country){ msg('填国家 TAG（决定写进哪个文件）', true); return; }
    msg(psrc ? '新建并导入头像中…' : '新建中…');
    const r = await (await fetch('/api/character_add', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: id, name: name, type: type, skill: skill,
                            country: country,
                            portrait_src: psrc || null,
                            attack: skill, defense: skill, planning: skill,
                            logistics: skill})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      const load = document.getElementById('chLoad');
      if(load) load.click();
    }
  }

  async function addDec(){
    const msg = msgOf('decMsg');
    const id = ((document.getElementById('decNewId')||{}).value || '').trim();
    const cat = ((document.getElementById('decNewCat')||{}).value || '').trim();
    const icon = ((document.getElementById('decNewIcon')||{}).value || 'GFX_decision_generic').trim();
    const cost = Number((document.getElementById('decNewCost')||{}).value || 50);
    const eff = ((document.getElementById('decNewEff')||{}).value || 'add_political_power = 50').trim();
    if(!id){ msg('填决议 id', true); return; }
    if(!cat){ msg('填类别 id', true); return; }
    msg('新建中…');
    const r = await (await fetch('/api/decision_add', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: id, category: cat, icon: icon, cost: cost,
                            effect: eff})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      const load = document.getElementById('decLoad');
      if(load) load.click();
    }
  }

  function bind(){
    [['chAddBtn', addChar], ['decAddBtn', addDec]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


function rgbOf(c){
  if(!c || c.length < 3) return '';
  const f = v => Math.round(Math.max(0, Math.min(1, v)) * 255);
  return 'rgb(' + f(c[0]) + ',' + f(c[1]) + ',' + f(c[2]) + ')';
}


async function openCountry(tag){
  document.getElementById('countryModal').classList.add('show');
  const prev = tag || countrySel;
  status('正在读取国家数据…');
  try {
    COUNTRY_DATA = await (await fetch('/api/countries')).json();
  } catch(e){
    if(!COUNTRY_DATA){ status('国家数据读取失败：' + e.message, true); return; }
    status('刷新失败，显示上次的数据：' + e.message, true);
  }
  renderCountryList('');
  const list = COUNTRY_DATA.list || [];
  if(!list.length){
    countrySel = null;
    document.getElementById('countryCount').textContent = '0';
    document.getElementById('countryBody').innerHTML =
      '<div class="cm-empty">还没有读取到任何国家。<br>先用左侧「＋ 添加 mod」或「📖 加载原版参考」，再打开这里。</div>';
    status('国家中心：0 个 tag（还没有加载 mod）');
    return;
  }
  const pick = (prev && list.some(x=>x.tag === prev)) ? prev : (list.find(x=>x.trees.length) || list[0] || {}).tag;
  if(pick) await selectCountry(pick);
  status('国家中心：' + list.length + ' 个 tag');
}


function closeCountry(){ document.getElementById('countryModal').classList.remove('show'); }


function renderCountryList(q){
  q = (q || '').toLowerCase();
  const box = document.getElementById('countryList');
  const list = (COUNTRY_DATA && COUNTRY_DATA.list) || [];
  const only = !document.getElementById('countryOnly') || document.getElementById('countryOnly').checked;
  const hits = list.filter(x=>{
    if(only && !(x.trees.length || x.owned || x.ideas || x.history_file)) return false;
    return !q || x.tag.toLowerCase().includes(q) || (x.name||'').toLowerCase().includes(q);
  });
  document.getElementById('countryCount').textContent = hits.length + ' / ' + list.length + (only ? '（有内容的）' : '');
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
    '</div>' +
    '<div style="margin:-2px 0 12px"><button class="btn primary" data-hist="1">✏️ 编辑历史</button> ' +
    '<span class="k" style="margin:0">改首都 / 执政党 / 政治点 / 开局精神 / 国策树</span></div>';

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
    '<div class="cm-line" data-state="' + s.id + '"><b style="font-size:12px">' + s.id + '</b>' +
    '<span>' + escapeHtml(s.loc || s.name) + '</span>' +
    '<span class="cm-sub">人力 ' + escapeHtml(s.manpower || '-') + ' · ' + escapeHtml(s.category || '') + (s.core ? ' · 核心' : '') + '</span></div>'
  ).join('') + (d.states.length > 60 ? '<div class="cm-empty">…另有 ' + (d.states.length - 60) + ' 个州</div>' : '');

  html += '<div class="cm-sec">问题<span>' + d.issues.length + ' 条</span></div>';
  if(!d.issues.length) html = html.replace('<div class="cm-sec">问题<span>0 条</span></div>', '<div class="cm-sec">问题<span>0 条</span></div><div class="cm-empty">没有发现结构性问题</div>');
  d.issues.forEach(it=>{
    html += '<div class="cm-issue ' + it.level + '">' + escapeHtml(it.text) + '</div>';
  });

  body.innerHTML = html;
  body.querySelectorAll('[data-state]').forEach(el=>{
    el.onclick = ()=>{ closeCountry(); openStates(el.dataset.state); };
  });
  body.querySelectorAll('[data-hist]').forEach(el=>{
    el.onclick = ()=>openHistoryEditor(d.tag);
  });
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
      // v1.24.2 来源标签：平时隐藏，hover/选中才出现——三个信息一直占位太挤
      '<span class="lr-src st-src" title="来自 ' + escapeHtml(x.source || '?') +
        '：' + escapeHtml(x.file || '') + '">' + escapeHtml(x.source || '?') + '</span>' +
    '</div>').join('') + (hits.length > shown.length ?
      '<div class="cm-empty">…另有 ' + (hits.length - shown.length) + ' 个，输入关键词缩小范围</div>' : '');
  box.querySelectorAll('[data-sid]').forEach(el=>{
    el.onclick = ()=>selectState(Number(el.dataset.sid));
  });
}


async function selectState(id, full){
  stateSel = id;
  renderStateList(document.getElementById('stateSearch').value || '');
  const body = document.getElementById('stateBody');
  body.innerHTML = '<div class="cm-empty">读取中…</div>';
  let d;
  try { d = await (await fetch('/api/state?id=' + encodeURIComponent(id) + (full ? '&full=1' : ''))).json(); }
  catch(e){ body.innerHTML = '<div class="cm-empty">读取失败：' + escapeHtml(e.message) + '</div>'; return; }
  if(!d.ok){ body.innerHTML = '<div class="cm-empty">' + escapeHtml(d.msg || '没有这个州') + '</div>'; return; }
  renderStateBody(d);
}


function renderStateBody(d){
  const body = document.getElementById('stateBody');
  const side = document.getElementById('stateSide');
  const cell = (k, v) => '<div class="cm-cell"><i>' + k + '</i><b>' +
    escapeHtml(v == null || v === '' ? '——' : String(v)) + '</b></div>';
  const ownerOpts = ['<option value="">（不改）</option>'].concat(
    d.owners.map(t=>'<option value="' + t + '">' + t + (LOC_NAME(t) ? ' · ' + escapeHtml(LOC_NAME(t)) : '') + '</option>')).join('');

  /* 中栏 = 主体：建筑 / 资源 / 省份 */
  let html = '<div class="cm-title"><h3>' + d.id + ' ' + escapeHtml(d.name || d.raw_name || '') + '</h3>' +
    '<code>' + escapeHtml(d.file || '') + '</code>' +
    '<div class="src-hint" id="stSrc"></div>' +
    (d.writable ? '' : '<span class="cm-sub" style="font-size:11px;color:var(--warn)">只读来源</span>') + '</div>';
  html += stateBuildingsHtml(d);
  html += stateResourcesHtml(d);

  const vpMap = {};
  (d.victory_points || []).forEach(v=>{ vpMap[v[0]] = v[1]; });
  const pbMap = d.province_buildings || {};
  if(d.provinces.length){
    html += '<div class="cm-sec">省份 · 建筑 · 胜利点<span>建筑留空=不改，0=删掉；胜利点留空=不写</span></div>' +
      '<div class="st-tablewrap"><table class="st-table"><thead><tr>' +
      '<th>省</th><th>naval_base</th><th>coastal_bunker</th><th>胜利点</th></tr></thead><tbody>' +
      d.provinces.map(p=>{
        const b = pbMap[p] || pbMap[String(p)] || {};
        const vv = vpMap[p] != null ? vpMap[p] : '';
        return '<tr><td>' + p + '</td>' +
          '<td><input type="number" min="0" data-pb="' + p + '" data-k="naval_base" value="' +
            (b.naval_base != null ? b.naval_base : '') + '"></td>' +
          '<td><input type="number" min="0" data-pb="' + p + '" data-k="coastal_bunker" value="' +
            (b.coastal_bunker != null ? b.coastal_bunker : '') + '"></td>' +
          '<td><input type="number" min="0" data-vp="' + p + '" value="' + vv + '"></td></tr>';
      }).join('') +
      '</tbody></table></div>' +
      (d.province_count > d.provinces.length ?
        '<div class="k">只列出前 ' + d.provinces.length + ' / ' + d.province_count +
        ' 个省 <button class="btn" id="stShowAll" style="margin-left:6px">显示全部</button></div>' : '');
  }

  /* 右栏 = 属性与操作 */
  let sideHtml = '<div class="cm-sec">属性<span>从文件读出来的当前值</span></div>' +
    '<div class="cm-grid">' +
      cell('所属国家', (d.owner || '') + (d.owner_name ? ' · ' + d.owner_name : '')) +
      cell('核心数', d.cores.length) +
      cell('人力', d.manpower) +
      cell('州类别', d.category) +
      cell('省份数', d.province_count) +
      cell('胜利点', d.victory_points.length) +
      cell('建筑合计', Object.values(d.buildings).reduce((a, b)=>a + b, 0)) +
      cell('历史日期', d.history_date) +
    '</div>' +
    '<div class="cm-sec">编辑<span>只改填写的字段，注释与省份子块原样保留</span></div>' +
    '<div class="st-grid">' +
      '<label>owner<select id="stOwner">' + ownerOpts + '</select></label>' +
      '<label>人力<input type="number" id="stManpower" value="' + escapeHtml(d.manpower || '') + '"></label>' +
      '<label>州类别<select id="stCategory"><option value="">（不改）</option>' +
        d.categories.map(c=>'<option value="' + c + '">' + c + '</option>').join('') + '</select></label>' +
      '<label>核心（逗号或换行分隔）<textarea id="stCores" style="height:56px">' +
        escapeHtml(d.cores.join(', ')) + '</textarea></label>' +
    '</div>' +
    '<div class="dp-acts"><button class="btn primary" id="stSave">保存</button>' +
      '<button class="btn" id="stReload">重新读取</button></div>' +
    '<div id="stDiff" class="hist-diff" style="display:none"></div>';

  body.innerHTML = html;
  if(side) side.innerHTML = sideHtml;
  document.getElementById('stOwner').value = d.owner || '';
  document.getElementById('stCategory').value = d.category || '';
  const showAll = document.getElementById('stShowAll');
  if(showAll) showAll.onclick = ()=>selectState(d.id, true);
  document.getElementById('stSave').onclick = ()=>saveState(d);
  document.getElementById('stReload').onclick = ()=>selectState(d.id);
  bindStateBuildingUI(d);
  // v1.24.2：州文件从哪层来、保存会写到哪
  fillSrcHint('stSrc', d.root, d.file, d.source);
}


function stateBuildingsHtml(d){
  const meta = d.building_meta || [];
  const coastal = d.coastal;
  const rows = meta.map(m=>{
    const v = d.buildings[m.key];
    const dis = (m.coastal && coastal === false);
    return '<div class="bld-row' + (dis ? ' off' : '') + '" data-row="' + m.key + '" title="' + m.key + '">' +
      '<span class="bld-name">' + escapeHtml(m.label) + '</span>' +
      '<button type="button" class="bld-step" data-step="-1" data-for="' + m.key + '">−</button>' +
      '<input type="number" min="0" max="' + m.max + '" data-b="' + m.key + '" data-max="' + m.max +
        '" value="' + (v != null ? v : '') + '" placeholder="—">' +
      '<button type="button" class="bld-step" data-step="1" data-for="' + m.key + '">＋</button>' +
      '<span class="bld-max">/' + m.max + '</span>' +
      '<span class="bld-warn"></span>' +
      '</div>';
  }).join('');
  const presets = Object.keys(BLD_PRESETS).map(k=>
    '<button type="button" class="btn bld-preset" data-preset="' + k + '">' + BLD_PRESETS[k].label + '</button>').join('');
  return '<div class="cm-sec">开局建筑<span>留空 = 不改；填 0 = 把那一行删掉</span></div>' +
    '<div class="bld-presets">' + presets + '</div>' +
    '<div class="bld-list">' + rows + '</div>' +
    (coastal === false ? '<div class="bld-note">这个州没有海岸线：海军基地 / 船坞 / 海军补给中心保存时会被拒绝</div>' : '') +
    '<div class="bld-batch"><button type="button" class="btn" id="stBatchOpen">套用到其他州…</button>' +
    '<label><input type="checkbox" id="stBatchEmpty"> 只填空缺（不覆盖已有值）</label></div>';
}


function stateResourcesHtml(d){
  const meta = d.resource_meta || [];
  const res = d.resources || {};
  const rows = meta.map(m=>{
    const v = res[m.key];
    return '<div class="res-row"><span class="res-name">' + escapeHtml(m.label) + '</span>' +
      '<input type="number" min="0" data-r="' + m.key + '" value="' + (v != null ? v : '') + '" placeholder="—">' +
      '<span class="res-hint">' + escapeHtml(m.hint) + '</span></div>';
  }).join('');
  return '<div class="cm-sec">战略资源<span>填 0 会把那一行从文件里删掉</span></div>' +
    '<div class="res-list">' + rows + '</div>' +
    '<div class="res-auto"><button type="button" class="btn" id="stResAuto">按面积推荐</button>' +
    '<span class="k" id="stResMsg">省份数 × 密度，给个起点</span></div>';
}


function bindStateBuildingUI(d){
  document.querySelectorAll('#stateBody .bld-step').forEach(btn=>{
    btn.onclick = ()=>{
      const k = btn.dataset.for;
      const inp = document.querySelector('#stateBody [data-b="' + k + '"]');
      if(!inp) return;
      const max = Number(inp.dataset.max || 99);
      let v = Number(inp.value || 0) + Number(btn.dataset.step);
      v = Math.max(0, Math.min(max, v));
      inp.value = v;
      inp.classList.add('dirty');
      const row = inp.closest('.bld-row');
      const warn = row && row.querySelector('.bld-warn');
      if(warn) warn.textContent = '';
      inp.classList.remove('bad');
    };
  });
  document.querySelectorAll('#stateBody [data-b]').forEach(inp=>{
    inp.oninput = ()=>{
      const max = Number(inp.dataset.max || 99);
      const v = Number(inp.value || 0);
      const row = inp.closest('.bld-row');
      const warn = row && row.querySelector('.bld-warn');
      const bad = inp.value !== '' && (v < 0 || v > max);
      if(warn) warn.textContent = bad ? '0–' + max : '';
      inp.classList.toggle('bad', bad);
      inp.classList.add('dirty');
    };
  });
  document.querySelectorAll('#stateBody .bld-preset').forEach(btn=>{
    btn.onclick = ()=>{
      const p = BLD_PRESETS[btn.dataset.preset];
      if(!p) return;
      document.querySelectorAll('#stateBody [data-b]').forEach(inp=>{
        const v = p.buildings[inp.dataset.b];
        inp.value = (v != null) ? v : 0;
        inp.classList.add('dirty');
        inp.classList.remove('bad');
        const warn = inp.closest('.bld-row') && inp.closest('.bld-row').querySelector('.bld-warn');
        if(warn) warn.textContent = '';
      });
      const usesSea = Object.keys(p.buildings).some(k=>SEA_BUILDINGS.indexOf(k) >= 0);
      if(d.coastal === false && usesSea){
        status('已填入「' + p.label + '」（其余建筑置 0），但这个州没有海岸线，海军建筑保存时会被拒绝', true);
      } else {
        status('已填入「' + p.label + '」（这是一整套，未列出的建筑会置 0），可再微调后保存');
      }
    };
  });
  const ra = document.getElementById('stResAuto');
  if(ra) ra.onclick = ()=>{
    const n = Math.max(1, Number(d.province_count || 1));
    const dens = {oil:1.2, rubber:0.6, steel:2.0, aluminium:1.2, tungsten:0.6, chromium:0.6};
    document.querySelectorAll('#stateBody [data-r]').forEach(inp=>{
      inp.value = Math.round(n * (dens[inp.dataset.r] || 0.6));
      inp.classList.add('dirty');
    });
    const m = document.getElementById('stResMsg');
    if(m) m.textContent = '按 ' + n + ' 个省估算，可再调';
  };
  const bo = document.getElementById('stBatchOpen');
  if(bo) bo.onclick = ()=>openBldBatch(d);
}


function collectBldValues(){
  const b = {};
  document.querySelectorAll('#stateBody [data-b]').forEach(inp=>{
    const v = inp.value.trim();
    if(v !== '') b[inp.dataset.b] = Number(v);
  });
  const r = {};
  document.querySelectorAll('#stateBody [data-r]').forEach(inp=>{
    const v = inp.value.trim();
    if(v !== '') r[inp.dataset.r] = Number(v);
  });
  return {buildings: b, resources: r};
}


function openBldBatch(d){
  const vals = collectBldValues();
  if(!Object.keys(vals.buildings).length && !Object.keys(vals.resources).length){
    status('先把建筑或资源填好，再套用', true);
    return;
  }
  const list = (STATE_DATA && STATE_DATA.list) || [];
  const wrap = document.createElement('div');
  wrap.className = 'show';
  wrap.id = 'bldBatchModal';
  wrap.innerHTML = '<div class="cm-card" style="width:min(760px,calc(100% - 60px))">' +
    '<div class="cm-head"><b>把这一套数值套用到…</b>' +
    '<input id="bbSearch" placeholder="搜索 id / 名称 / owner" autocomplete="off">' +
    '<span id="bbCount" class="k"></span>' +
    '<button class="btn" id="bbClose" style="margin-left:auto">取消</button></div>' +
    '<div class="cm-body" style="display:block">' +
    '<div id="bbList" class="bb-list"></div>' +
    '<div class="bb-foot"><label><input type="checkbox" id="bbEmpty"> 只填空缺（不覆盖已有值）</label>' +
    '<span class="k">当前州 #' + d.id + ' 不参与</span>' +
    '<button class="btn primary" id="bbGo" style="margin-left:auto">套用</button></div></div></div>';
  document.body.appendChild(wrap);
  const box = document.getElementById('bbList');
  const cnt = document.getElementById('bbCount');
  const picked = new Set();
  function render(){
    const q = (document.getElementById('bbSearch').value || '').toLowerCase();
    const hits = list.filter(x=>x.id !== d.id && (!q ||
      String(x.id).includes(q) || (x.name||'').toLowerCase().includes(q) ||
      (x.owner||'').toLowerCase().includes(q)));
    const shown = hits.slice(0, 300);
    box.innerHTML = shown.map(x=>
      '<label class="bb-item"><input type="checkbox" data-sid="' + x.id + '"' +
      (picked.has(x.id) ? ' checked' : '') + '><span>' + x.id + ' ' +
      escapeHtml(x.name || x.raw_name || '') + '</span><i>' + escapeHtml(x.owner || '—') + '</i></label>').join('') +
      (hits.length > shown.length ? '<div class="cm-empty">…另有 ' + (hits.length - shown.length) + ' 个，输入关键词缩小范围</div>' : '');
    box.querySelectorAll('[data-sid]').forEach(el=>{
      el.onchange = ()=>{
        const id = Number(el.dataset.sid);
        if(el.checked) picked.add(id); else picked.delete(id);
        cnt.textContent = '已选 ' + picked.size + ' 个';
      };
    });
    cnt.textContent = '已选 ' + picked.size + ' 个';
  }
  render();
  document.getElementById('bbSearch').oninput = render;
  document.getElementById('bbClose').onclick = ()=>wrap.remove();
  document.getElementById('bbGo').onclick = async ()=>{
    if(!picked.size){ status('先勾几个州', true); return; }
    const onlyEmpty = document.getElementById('bbEmpty').checked;
    const btn = document.getElementById('bbGo');
    btn.disabled = true;
    btn.textContent = '写入中…';
    let r;
    try{
      r = await (await fetch('/api/state_buildings_batch', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ids: [...picked], buildings: vals.buildings,
                              resources: vals.resources, only_empty: onlyEmpty})})).json();
    }catch(e){ status('套用失败：' + e.message, true); btn.disabled = false; btn.textContent = '套用'; return; }
    status(r.msg || '', !r.ok);
    if(r.ok){
      wrap.remove();
      STATE_DATA = null;
      await loadData();
      await openStates(d.id);
    } else {
      btn.disabled = false;
      btn.textContent = '套用';
    }
  };
}


function diploTagsHtml(tags){
  return tags.map(t=>'<option value="' + t.tag + '">' + (t.own ? '★ ' : '') + t.tag +
    (t.name && t.name !== t.tag ? ' · ' + escapeHtml(t.name) : '') + '</option>').join('');
}


async function openDiplo(tag){
  document.getElementById('diploModal').classList.add('show');
  const t = tag || (DIPLO && DIPLO.tag) || '';
  // 空 tag 交给后端挑（它会选本 mod 里第一个有自己历史文件的国家）
  await loadDiplo(t);
}


async function loadDiplo(tag){
  const body = document.getElementById('diploBody');
  body.innerHTML = '<div class="cm-empty">读取中…</div>';
  let d;
  try { d = await (await fetch('/api/diplomacy?tag=' + encodeURIComponent(tag))).json(); }
  catch(e){ body.innerHTML = '<div class="cm-empty">读取失败：' + escapeHtml(e.message) + '</div>'; return; }
  if(!d.ok){ body.innerHTML = '<div class="cm-empty">' + escapeHtml(d.msg || '读不到这个国家') + '</div>'; return; }
  DIPLO = d;
  document.getElementById('diploTagSearch').value = d.tag;
  document.getElementById('diploFile').textContent = d.file || '';
  document.getElementById('diploTagList').innerHTML =
    d.tags.map(x=>'<option value="' + x.tag + '">' + escapeHtml(x.name || '') + '</option>').join('');
  renderDiplo(d);
}


function dpPuppetRowHtml(opts, autOpts, tag, aut){
  return '<div class="dp-row">' +
    '<select class="dp-p-tag">' + opts + '</select>' +
    '<select class="dp-p-aut">' + autOpts + '</select>' +
    '<button type="button" class="btn dp-p-del">移除</button></div>';
}


function renderDiplo(d){
  const body = document.getElementById('diploBody');
  const opts = diploTagsHtml(d.tags);
  const autOpts = d.autonomies.map(a=>'<option value="' + a.key + '">' + a.label + '</option>').join('');
  const cur = d.overlords[0] || null;
  let html = '';

  html += '<div class="cm-sec">' + d.tag + (d.name && d.name !== d.tag ? ' · ' + escapeHtml(d.name) : '') +
    '<span>关系写在国家历史文件里</span></div>';
  html += '<div class="cm-grid" style="grid-template-columns:repeat(4,1fr)">' +
    '<div class="cm-cell"><i>本国附庸</i><b>' + d.puppets.length + '</b></div>' +
    '<div class="cm-cell"><i>宗主</i><b>' + (cur ? cur.tag : '无') + '</b></div>' +
    '<div class="cm-cell"><i>保证独立</i><b>' + d.guarantees.length + '</b></div>' +
    '<div class="cm-cell"><i>军事通行</i><b>' + d.access.length + '</b></div></div>';

  html += '<div class="cm-sec">本国是谁的附庸<span>这一项会写到宗主国的文件里（HOI4 只在那里读 set_autonomy）</span></div>' +
    '<div class="dp-grid">' +
    '<label>宗主<select id="dpOverlord"><option value="">（独立，没有宗主）</option>' + opts + '</select></label>' +
    '<label>自治度<select id="dpAutonomy">' + autOpts + '</select></label>' +
    '</div>';
  if(d.overlords.length > 1){
    html += '<div class="bld-note">现在有多个国家声明了本国（' +
      d.overlords.map(o=>o.tag).join('、') + '），保存后只保留上面选的那一个</div>';
  }

  html += '<div class="cm-sec">本国的附庸<span>写在本国的文件里，对方文件不用改</span></div>' +
    '<div id="dpPuppets"></div>' +
    '<div class="dp-acts"><button type="button" class="btn" id="dpAddPuppet">＋ 添加附庸</button>' +
    '<span class="k">自治度决定它在游戏里有多独立</span></div>';

  html += '<div class="cm-sec">保证独立 / 军事通行<span>按住 Ctrl 点选多行；一个都不选 = 清空这一项</span></div>' +
    '<div class="dp-grid2">' +
    '<label>本国保证这些国家的独立<select multiple size="7" id="dpGuarantees" style="height:auto;min-height:150px">' + opts + '</select></label>' +
    '<label>本国给这些国家军事通行<select multiple size="7" id="dpAccess" style="height:auto;min-height:150px">' + opts + '</select></label>' +
    '</div>';

  if(d.conflict) html += '<div class="bld-note">⚠ ' + escapeHtml(d.conflict) + '</div>';
  html += '<div class="dp-acts"><button type="button" class="btn primary" id="dpSave">写入</button>' +
    '<span id="dpMsg" class="k"></span></div>';
  body.innerHTML = html;

  const pbox = document.getElementById('dpPuppets');
  function addRow(tag, aut){
    const div = document.createElement('div');
    // 新增行留一个空选项，避免默认就选中列表第一个国家（很容易误存）
    div.innerHTML = dpPuppetRowHtml('<option value="">（选一个国家）</option>' + opts,
                                    autOpts, tag, aut);
    const row = div.firstChild;
    pbox.appendChild(row);          // 先进文档再设 value，detached 时设值偶发不生效
    const tsel = row.querySelector('.dp-p-tag');
    const asel = row.querySelector('.dp-p-aut');
    if(tag) tsel.value = tag;
    asel.value = aut || 'autonomy_puppet';
    row.querySelector('.dp-p-del').onclick = ()=>row.remove();
  }
  d.puppets.forEach(p=>addRow(p.tag, p.autonomy));
  document.getElementById('dpAddPuppet').onclick = ()=>addRow('', 'autonomy_puppet');

  const ov = document.getElementById('dpOverlord');
  const au = document.getElementById('dpAutonomy');
  if(cur){ ov.value = cur.tag; au.value = cur.autonomy; }
  const setMulti = (id, vals)=>{
    const sel = document.getElementById(id);
    [...sel.options].forEach(o=>{ o.selected = vals.indexOf(o.value) >= 0; });
  };
  setMulti('dpGuarantees', d.guarantees);
  setMulti('dpAccess', d.access);
  document.getElementById('dpSave').onclick = ()=>saveDiplo(d);
}


async function saveDiplo(d){
  const _rows = [...document.querySelectorAll('#dpPuppets .dp-row')];
  if(_rows.some(r=>!r.querySelector('.dp-p-tag').value)){
    status('附庸列表里有一行没选国家：先选好，或者点「移除」', true);
    return;
  }
  const puppets = _rows.map(r=>({
    tag: r.querySelector('.dp-p-tag').value,
    autonomy: r.querySelector('.dp-p-aut').value
  })).filter(x=>x.tag);
  const overlay = {
    tag: d.tag,
    overlord: document.getElementById('dpOverlord').value,
    autonomy: document.getElementById('dpAutonomy').value,
    puppets: puppets,
    guarantees: [...document.getElementById('dpGuarantees').selectedOptions].map(o=>o.value),
    access: [...document.getElementById('dpAccess').selectedOptions].map(o=>o.value)
  };
  const msg = document.getElementById('dpMsg');
  if(msg) msg.textContent = '写入中…';
  let r;
  try{
    r = await (await fetch('/api/diplomacy_save', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(overlay)})).json();
  }catch(e){ if(msg) msg.textContent = '失败：' + e.message; return; }
  if(!r.ok){ if(msg) msg.textContent = r.msg || '写入失败'; status(r.msg || '', true); return; }
  status(r.msg || '已保存');
  await loadDiplo(d.tag);
  const box = document.getElementById('dpMsg');
  if(box){
    box.innerHTML = (r.diff || []).map(x=>'<div>' + escapeHtml(x.label) + '：' +
      escapeHtml(x.old || '无') + ' → ' + escapeHtml(x.new || '无') + '</div>').join('') || '（没有改动）';
  }
}


function LOC_NAME(tag){
  const c = ((COUNTRY_DATA && COUNTRY_DATA.list) || []).find(x=>x.tag === tag);
  return c ? c.name : '';
}


async function saveState(d){
  const coresRaw = document.getElementById('stCores').value;
  const cores = coresRaw.split(/[,，\s]+/).map(s=>s.trim()).filter(Boolean);
  const buildings = {};
  document.querySelectorAll('#stateBody [data-b]').forEach(inp=>{
    const v = inp.value.trim();
    if(v !== '') buildings[inp.dataset.b] = Number(v);
  });
  const resources = {};
  document.querySelectorAll('#stateBody [data-r]').forEach(inp=>{
    const v = inp.value.trim();
    if(v !== '') resources[inp.dataset.r] = Number(v);
  });
  const fields = {
    owner: document.getElementById('stOwner').value,
    cores: cores,
    manpower: document.getElementById('stManpower').value.trim(),
    category: document.getElementById('stCategory').value,
    buildings: buildings,
    resources: resources,
    province_buildings: (function(){
      const pb = {};
      document.querySelectorAll('#stateBody [data-pb]').forEach(inp=>{
        const v = inp.value.trim();
        if(v === '') return;
        (pb[inp.dataset.pb] = pb[inp.dataset.pb] || {})[inp.dataset.k] = Number(v);
      });
      return pb;
    })(),
    victory_points: [...document.querySelectorAll('#stateBody [data-vp]')]
      .filter(inp=>inp.value.trim() !== '')
      .map(inp=>[Number(inp.dataset.vp), Number(inp.value)])
  };
  if(!confirm('写入州 ' + d.id + ' 的文件？\n会先自动备份，只改你填写的字段。')) return;
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


async function openHistoryEditor(tag){
  histTag = tag;
  document.getElementById('histTag').textContent = tag;
  document.getElementById('historyModal').classList.add('show');
  await loadHistoryIntoForm();
}


/* ---------- v0.68 变体写入 ---------- */
function renderHistVariants(list){
  const box = document.getElementById('histVariants');
  if(!box) return;
  const rows = (list || []).map(v=>
    '<div class="hv-row"><span class="nm">' + escapeHtml(v.name) + '</span>' +
    '<span class="ty">' + escapeHtml(v.type || '?') + '</span>' +
    '<span class="md">' + (v.modules || 0) + ' 模块</span>' +
    '<button class="btn" data-hvdel="' + escapeHtml(v.name) + '" style="padding:2px 8px">删除</button></div>'
  ).join('');
  box.innerHTML =
    '<div class="hv-bar"><button class="btn" id="histVarAdd">＋ 新增变体</button>' +
      '<span class="k">写文件后可用「🕘 备份」回滚</span></div>' +
    '<div id="histVarForm">' +
      '<div class="hv-grid"><input id="hvName" placeholder="变体名称，如 TestJet">' +
      '<input id="hvType" placeholder="底盘 type，如 fighter_equipment_0"></div>' +
      '<input id="hvIcon" placeholder="图标 GFX 名（可留空）">' +
      '<textarea id="hvMods" placeholder="每行一个模块：槽位 = 模块&#10;fixed_main_weapon_slot = fighter_weapon_1"></textarea>' +
      '<div class="hv-bar"><button class="btn primary" id="hvSave">写入</button>' +
        '<button class="btn" id="hvCancel">取消</button><span class="k" id="hvHint"></span></div>' +
    '</div>' +
    '<div class="hist-diff" style="margin:2px 0 8px">' + (rows || '<div class="k">这个国家还没有开局变体</div>') + '</div>';

  const form = document.getElementById('histVarForm');
  document.getElementById('histVarAdd').onclick = ()=>{
    form.classList.toggle('show');
    if(form.classList.contains('show')) document.getElementById('hvName').focus();
  };
  document.getElementById('hvCancel').onclick = ()=>form.classList.remove('show');
  document.getElementById('hvSave').onclick = ()=>saveVariantForm();
  box.querySelectorAll('[data-hvdel]').forEach(b=>{
    b.onclick = ()=>deleteVariant(b.dataset.hvdel);
  });
}


function parseModuleLines(raw){
  const out = {};
  (raw || '').split(/\r?\n/).forEach(line=>{
    const s = line.trim();
    if(!s) return;
    const m = s.split(/\s*=\s*/);
    if(m.length === 2 && m[0] && m[1]) out[m[0].trim()] = m[1].trim();
  });
  return out;
}


async function saveVariantForm(){
  const hint = document.getElementById('hvHint');
  const name = document.getElementById('hvName').value.trim();
  const type = document.getElementById('hvType').value.trim();
  const icon = document.getElementById('hvIcon').value.trim();
  const modules = parseModuleLines(document.getElementById('hvMods').value);
  if(!name || !type || !Object.keys(modules).length){
    hint.textContent = '名称、底盘、至少一个模块都要填';
    return;
  }
  hint.textContent = '写入中…';
  try{
    const r = await (await fetch('/api/country_variant', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: histTag, action: 'add', name, type, icon, modules})})).json();
    if(!r.ok){ hint.textContent = r.msg || '失败'; return; }
    renderHistVariants(r.variants || []);
    status(r.msg || '已新增变体');
  }catch(e){ hint.textContent = '失败：' + e.message; }
}


async function deleteVariant(name){
  if(!confirm('删除变体 ' + name + '？\n会直接改文件，可用「🕘 备份」回滚。')) return;
  try{
    const r = await (await fetch('/api/country_variant', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tag: histTag, action: 'del', name})})).json();
    if(!r.ok){ status(r.msg || '删除失败', true); return; }
    renderHistVariants(r.variants || []);
    status(r.msg || '已删除变体');
  }catch(e){ status('删除失败：' + e.message, true); }
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
  document.getElementById('histIdeas').value = (f.ideas || []).join('\n');
  const sel = document.getElementById('histTree');
  sel.innerHTML = '<option value="">（不挂/不改）</option>' +
    ((DATA && DATA.trees) || []).map(t=>
      '<option value="' + escapeHtml(t.id) + '">' + escapeHtml(t.id) + '（' + (t.focuses || []).length + ' 焦点）</option>'
    ).join('');
  sel.value = f.focus_tree || '';
  const pops = f.popularities || {};
  document.getElementById('histPopD').value = pops.democratic != null ? pops.democratic : '';
  document.getElementById('histPopF').value = pops.fascism != null ? pops.fascism : '';
  document.getElementById('histPopC').value = pops.communism != null ? pops.communism : '';
  document.getElementById('histPopN').value = pops.neutrality != null ? pops.neutrality : '';
  document.getElementById('histOob').value = f.oob || '';
  document.getElementById('histTechs').value = (f.techs || []).join('\n');
  renderHistVariants(f.variants || []);
  document.getElementById('histOpinions').value =
    (f.opinions || []).map(p=>p[0] + ' ' + p[1]).join('\n');
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
    ideas: ideasRaw.split(/\r?\n/).map(s=>s.trim()).filter(Boolean),
    oob: document.getElementById('histOob').value.trim(),
    techs: document.getElementById('histTechs').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean),
    opinions: document.getElementById('histOpinions').value.split(/\r?\n/)
      .map(s=>s.trim()).filter(Boolean)
      .map(s=>{ const p = s.split(/[,，\s]+/); return [p[0], Number(p[1] || 0)]; }),
    popularities: {
      democratic: document.getElementById('histPopD').value,
      fascism: document.getElementById('histPopF').value,
      communism: document.getElementById('histPopC').value,
      neutrality: document.getElementById('histPopN').value
    }
  };
  if(!fields.capital && !fields.ruling_party && !fields.political_power && !fields.stability &&
     !fields.war_support && !fields.focus_tree && !fields.ideas.length && !fields.oob &&
     !fields.techs.length && !Object.values(fields.popularities).some(v=>String(v).trim())){
    status('没有填写任何字段', true); return;
  }
  if(!confirm('把修改写入 ' + histTag + ' 的历史文件？\n会先自动备份（.bak 与历史记录），只改你填写的字段。')) return;
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
  await loadData();
  await loadHistoryIntoForm();
  if(document.getElementById('countryModal').classList.contains('show')) await selectCountry(histTag);
  diffEl.innerHTML = rows ? '<div class="hist-diff">' + rows + '</div>' : '';
  document.getElementById('histWarn').textContent = (r.warnings || []).join('；');
}


function closeHistoryEditor(){ document.getElementById('historyModal').classList.remove('show'); }


/* ---------- 7-2 叠加链可视化 ---------- */
const _lcState = {
  tab: 'files',
  layerFilter: '',
  rpFilter: '',
  data: null,
};

function _lcReasonLabel(l){
  const m = {game:'原版·只读', manual:'手动加载', dep:'dependencies 带入', launcher:'启动器带入', auto:'自动'};
  const base = m[l.reason] || '自动';
  return (l.readonly && l.reason !== 'game') ? (base + '·只读') : base;
}

function _lcSetTab(tab){
  _lcState.tab = tab;
  const fPane = document.getElementById('lcFilesPane');
  const rPane = document.getElementById('lcReplacePane');
  const oPane = document.getElementById('lcObjectsPane');
  const tFiles = document.getElementById('lcTabFiles');
  const tRep = document.getElementById('lcTabReplace');
  const tObj = document.getElementById('lcTabObjects');
  if(fPane) fPane.style.display = tab === 'files' ? 'flex' : 'none';
  if(rPane) rPane.style.display = tab === 'replace' ? 'flex' : 'none';
  if(oPane) oPane.style.display = tab === 'objects' ? 'flex' : 'none';
  if(tFiles) tFiles.classList.toggle('primary', tab === 'files');
  if(tRep) tRep.classList.toggle('primary', tab === 'replace');
  if(tObj) tObj.classList.toggle('primary', tab === 'objects');
  if(tab === 'objects') loadObjectDiff();
}

function _lcRenderFilterChip(){
  const chip = document.getElementById('lcFilterChip');
  if(!chip) return;
  const parts = [];
  if(_lcState.layerFilter !== ''){
    const ls = (_lcState.data && _lcState.data.layers) || [];
    const hit = ls.find(x => String(x.index) === String(_lcState.layerFilter));
    parts.push('仅看涉及 #' + (Number(_lcState.layerFilter) + 1) + ' ' + (hit ? hit.name : ''));
  }
  if(_lcState.rpFilter){
    parts.push('replace_path: ' + _lcState.rpFilter);
  }
  chip.innerHTML = parts.length
    ? ('<span class="lc-badge warn">' + escapeHtml(parts.join(' · ')) +
       ' <a href="#" id="lcClearFilter" style="color:inherit;margin-left:4px">[清除]</a></span>')
    : '';
  const clr = document.getElementById('lcClearFilter');
  if(clr){
    clr.onclick = e => {
      e.preventDefault();
      _lcState.layerFilter = '';
      _lcState.rpFilter = '';
      const kSel = document.getElementById('lcKind');
      if(kSel && kSel.value === 'blocked') kSel.value = 'interacted';
      loadLayerChain();
      if(_lcState.tab === 'objects') loadObjectDiff();
    };
  }
}

function renderLayerChain(res){
  _lcState.data = res;
  const layers = res.layers || [];
  const rules = res.replace_rules || [];
  const files = res.files || [];

  const sum = document.getElementById('lcSummary');
  if(sum){
    sum.textContent = layers.length + ' 层 · 总 ' + (res.total_files || 0) + ' 个文件 · 同名覆盖 '
      + (res.overridden_count || 0) + ' · replace_path ' + rules.length + ' 条（屏蔽 ' + (res.blocked_count || 0) + ' 项）';
  }
  _lcRenderFilterChip();

  // 1. 链条顺序卡片
  const strip = document.getElementById('lcChainStrip');
  if(strip){
    if(!layers.length){
      strip.innerHTML = '<div style="color:var(--muted);font-size:12px;padding:8px">当前未加载任何游戏目录或 mod。</div>';
    }else{
      strip.innerHTML = layers.map((l, idx) => {
        const active = String(_lcState.layerFilter) === String(l.index) ? ' active' : '';
        const rpCnt = (l.replace_paths || []).length;
        const card = '<button type="button" class="lc-card' + active + '" data-lc-layer="' + l.index + '" title="' + escapeHtml(l.path || '') + '">'
          + '<div class="lc-card-head"><span class="lc-ord">#' + l.order + '</span><b>' + escapeHtml(l.name || l.folder) + '</b></div>'
          + '<div class="lc-card-meta">'
          + '<div>' + escapeHtml(_lcReasonLabel(l)) + '</div>'
          + '<div>自有文件 ' + l.file_count + ' · 最终生效 <b style="color:var(--text)">' + l.win_count + '</b></div>'
          + '<div>覆盖下层 ' + l.override_count + ' · replace_path ' + rpCnt + '（屏蔽下层 ' + l.blocked_others_count + '）</div>'
          + '</div></button>';
        return (idx > 0 ? '<div class="lc-arrow">→</div>' : '') + card;
      }).join('');
      strip.querySelectorAll('[data-lc-layer]').forEach(btn => {
        btn.onclick = () => {
          const val = btn.dataset.lcLayer;
          _lcState.layerFilter = (String(_lcState.layerFilter) === String(val)) ? '' : val;
          loadLayerChain();
          if(_lcState.tab === 'objects') loadObjectDiff();
        };
      });
    }
  }

  // 目录筛选下拉同步
  const dirSel = document.getElementById('lcDir');
  if(dirSel){
    const prev = dirSel.value;
    dirSel.innerHTML = '<option value="">全部目录</option>' + (res.top_dirs || []).map(d =>
      '<option value="' + escapeHtml(d.dir === '(root)' ? '' : d.dir) + '">' + escapeHtml(d.dir) + ' (' + d.count + ')</option>'
    ).join('');
    if(prev) dirSel.value = prev;
  }

  // 2. 文件覆盖列表
  const stat = document.getElementById('lcFileStat');
  const qEl = document.getElementById('lcQuery');
  const kEl = document.getElementById('lcKind');
  if(stat){
    let msg = '命中 ' + (res.matched_count || 0) + ' 项（当前展示 ' + files.length + ' 项）';
    if((res.matched_count || 0) > files.length) msg += '，请补充关键词或目录缩小范围';
    stat.innerHTML = '<span>' + escapeHtml(msg) + '</span>'
      + (kEl && kEl.value !== 'all' && qEl && qEl.value.trim()
        ? '<button type="button" class="btn" id="lcSearchAllBtn" style="padding:1px 7px;font-size:11px">在全部文件（含单层原版）中搜索</button>'
        : '');
    const allBtn = document.getElementById('lcSearchAllBtn');
    if(allBtn){
      allBtn.onclick = () => { kEl.value = 'all'; loadLayerChain(); };
    }
  }

  const list = document.getElementById('lcFileList');
  if(list){
    if(!files.length){
      list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);font-size:12px">当前筛选下没有匹配文件；搜索未被修改的原版文件可切换「全部文件」。</div>';
    }else{
      const stLabel = s => ({winner:'✓ 生效', overridden:'被覆盖', blocked:'✕ 被 replace 屏蔽', shadow_above:'⚠ 在父 replace_path 之上'})[s] || s;
      const stCls = s => ({winner:'win', overridden:'overridden', blocked:'blocked', shadow_above:'warn'})[s] || '';
      list.innerHTML = files.map(f => {
        const winBadge = f.winner !== null && f.winner !== undefined
          ? '<span class="lc-badge win">最终生效：#' + f.winner_order + ' ' + escapeHtml(f.winner_name) + '</span>'
          : '<span class="lc-badge blocked">无生效副本（已被 #' + (f.replace_by ? f.replace_by.order + ' ' + escapeHtml(f.replace_by.name) : '') + ' 的 replace_path 屏蔽）</span>';
        const rpTag = f.replace_by
          ? '<span class="lc-badge warn">replace_path="' + escapeHtml(f.replace_by.path) + '"</span>'
          : '';
        const trail = (f.sources || []).map((s, idx) =>
          (idx > 0 ? '<span style="color:var(--muted)">→</span>' : '')
          + '<span class="lc-badge ' + stCls(s.state) + '">#' + s.order + ' ' + escapeHtml(s.name) + ' [' + stLabel(s.state) + ']</span>'
        ).join('');
        return '<div class="lc-row">'
          + '<div class="lc-row-top"><span class="lc-path">' + escapeHtml(f.rel) + '</span>' + winBadge + rpTag + '</div>'
          + '<div class="lc-trail">' + trail + '</div>'
          + '</div>';
      }).join('');
    }
  }

  // 3. replace_path 屏蔽清单
  const repList = document.getElementById('lcReplaceList');
  const repTab = document.getElementById('lcTabReplace');
  if(repTab) repTab.textContent = '③ replace_path 屏蔽下层清单 (' + rules.length + ')';
  if(repList){
    if(!rules.length){
      repList.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);font-size:12px">当前叠加链未声明任何 replace_path，所有目录均按逐文件覆盖合并。</div>';
    }else{
      repList.innerHTML = rules.map(rl => {
        const bfiles = rl.blocked_files || [];
        const fileRows = bfiles.length
          ? '<div class="lc-rp-files">' + bfiles.slice(0, 80).map(bf =>
              '<div>' + escapeHtml(bf.rel) + ' <span style="color:var(--muted)">← 被屏蔽自 #' + (bf.from_idx + 1) + ' ' + escapeHtml(bf.from_name) + '</span></div>'
            ).join('') + (rl.blocked_total > 80 ? '<div style="color:var(--muted)">… 共屏蔽 ' + rl.blocked_total + ' 条下层文件，点右上按钮去文件视图筛选完整列表</div>' : '') + '</div>'
          : '<div style="font-size:11.5px;color:var(--muted)">该 replace_path 目录在下层链中未命中需要屏蔽的文件。</div>';
        return '<div class="lc-rp-card">'
          + '<div class="lc-row-top">'
          + '<span class="lc-badge warn">#' + rl.owner_order + ' ' + escapeHtml(rl.owner_name) + '</span>'
          + '<span class="lc-path">replace_path = "' + escapeHtml(rl.path) + '"</span>'
          + '<span class="lc-badge">本层提供 ' + rl.own_files + ' 个文件</span>'
          + '<span class="lc-badge blocked">屏蔽下层 ' + rl.blocked_unique + ' 个路径（' + rl.blocked_total + ' 份层文件）</span>'
          + '<button type="button" class="btn" style="margin-left:auto;padding:2px 8px;font-size:11px" data-lc-rp="' + escapeHtml(rl.path) + '">在文件视图筛选</button>'
          + '</div>' + fileRows + '</div>';
      }).join('');
      repList.querySelectorAll('[data-lc-rp]').forEach(btn => {
        btn.onclick = () => {
          _lcState.rpFilter = btn.dataset.lcRp || '';
          const kSel = document.getElementById('lcKind');
          if(kSel) kSel.value = 'blocked';
          _lcSetTab('files');
          loadLayerChain();
        };
      });
    }
  }
}

async function loadLayerChain(opts){
  const o = opts || {};
  const qEl = document.getElementById('lcQuery');
  const kEl = document.getElementById('lcKind');
  const dEl = document.getElementById('lcDir');
  const params = new URLSearchParams();
  if(qEl && qEl.value.trim()) params.set('q', qEl.value.trim());
  if(kEl && kEl.value) params.set('kind', kEl.value);
  if(dEl && dEl.value) params.set('dir', dEl.value);
  if(_lcState.layerFilter !== '') params.set('layer', String(_lcState.layerFilter));
  if(_lcState.rpFilter) params.set('rp', _lcState.rpFilter);
  if(o.refresh) params.set('refresh', '1');
  try{
    const r = await fetch('/api/layer_chain?' + params.toString());
    const j = await r.json();
    renderLayerChain(j);
  }catch(e){
    const list = document.getElementById('lcFileList');
    if(list) list.innerHTML = '<div style="padding:16px;color:#ff7b7b">读取叠加链失败：' + escapeHtml(e.message) + '</div>';
  }
}

function openLayerChain(opts){
  const o = opts || {};
  _lcState.layerFilter = o.layer != null ? String(o.layer) : '';
  _lcState.rpFilter = o.rp || '';
  const qEl = document.getElementById('lcQuery');
  const kEl = document.getElementById('lcKind');
  const dEl = document.getElementById('lcDir');
  if(qEl && o.query !== undefined) qEl.value = o.query;
  if(kEl && o.kind) kEl.value = o.kind;
  if(dEl && o.dir !== undefined) dEl.value = o.dir;
  _lcSetTab(o.tab || 'files');
  document.getElementById('layerModal').classList.add('show');
  loadLayerChain({refresh: !!o.refresh});
}

function closeLayerChain(){
  document.getElementById('layerModal').classList.remove('show');
}


/* ---------- 7-3 对象级覆盖对比（国策 / 事件 / 国家精神） ---------- */
function _odCatLabel(cat, subtype){
  if(cat === 'focus'){
    if(subtype === 'focus_tree') return '国策树';
    if(subtype === 'shared_focus') return '共享国策';
    return '国策';
  }
  if(cat === 'event') return '事件';
  if(cat === 'idea') return '国家精神';
  return cat;
}

function _odStatusInfo(it){
  const st = it.status;
  if(st === 'file_override') return ['win', '同名文件覆写：#' + it.winner_order + ' ' + (it.winner_name || '') + ' 生效'];
  if(st === 'id_override') return ['win', '后加载覆写：#' + it.winner_order + ' ' + (it.winner_name || '') + ' 生效'];
  if(st === 'cross_tree') return ['warn', '跨不同 focus_tree 同名（各树各自生效）'];
  if(st === 'duplicate_error') return ['blocked', '⚠ 重复冲突（HOI4 报错：不同文件名重定义）'];
  if(st === 'blocked') return ['blocked', '无生效副本（被 replace_path 屏蔽）'];
  if(st === 'removed_by_file') return ['blocked', '无生效副本（上层同名文件覆写未保留）'];
  return ['overridden', '仅单层：#' + it.winner_order + ' ' + (it.winner_name || '')];
}

function _odRecLabel(state){
  return ({
    winner: '✓ 最终生效',
    file_replaced: '被同名文件覆写',
    blocked_by_replace: '✕ 被 replace_path 屏蔽',
    def_overridden: '被后加载覆写',
    conflict_dup: '⚠ 重复报错冲突',
    cross_tree: '跨树保留',
  })[state] || state;
}

function _odRecCls(state){
  return ({
    winner: 'win',
    file_replaced: 'overridden',
    blocked_by_replace: 'blocked',
    def_overridden: 'overridden',
    conflict_dup: 'blocked',
    cross_tree: 'warn',
  })[state] || '';
}

function renderObjectDiff(res){
  const stats = res.stats || {};
  const items = res.items || [];
  const statEl = document.getElementById('odStat');
  const qEl = document.getElementById('odQuery');
  const sEl = document.getElementById('odStatus');
  if(statEl){
    const msg = '总对象 ' + (stats.total || 0)
      + '（国策 ' + ((stats.by_cat && stats.by_cat.focus) || 0)
      + ' / 事件 ' + ((stats.by_cat && stats.by_cat.event) || 0)
      + ' / 精神 ' + ((stats.by_cat && stats.by_cat.idea) || 0) + '）'
      + ' · 交互/冲突 ' + (stats.interacted || 0)
      + '（重复报错冲突 ' + (stats.duplicate_error || 0)
      + ' / 同名文件覆写 ' + (stats.file_override || 0)
      + ' / 命中 ' + (res.matched_count || 0) + '）';
    statEl.innerHTML = '<span>' + escapeHtml(msg) + '</span>'
      + (sEl && sEl.value !== 'all' && qEl && qEl.value.trim()
        ? '<button type="button" class="btn" id="odSearchAllBtn" style="padding:1px 7px;font-size:11px">在全部对象（含单层未改动）中搜索</button>'
        : '');
    const allBtn = document.getElementById('odSearchAllBtn');
    if(allBtn) allBtn.onclick = () => { sEl.value = 'all'; loadObjectDiff(); };
  }

  const list = document.getElementById('odList');
  if(!list) return;
  if(!items.length){
    list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);font-size:12px">当前筛选下没有匹配对象；可切换到「全部对象」检索未改动的单层定义。</div>';
    return;
  }
  list.innerHTML = items.map(it => {
    const [bCls, bTxt] = _odStatusInfo(it);
    const recs = (it.records || []).map(r => {
      const fPart = r.rel ? (' · ' + r.rel) : '';
      const sumPart = r.summary ? (' (' + r.summary + ')') : '';
      return '<span class="lc-badge ' + _odRecCls(r.state) + '" title="' + escapeHtml(r.summary || '') + '">'
        + '#' + r.order + ' ' + escapeHtml(r.layer_name) + escapeHtml(fPart)
        + ' [' + _odRecLabel(r.state) + ']' + escapeHtml(sumPart)
        + '</span>';
    }).join('');
    return '<div class="lc-row" data-od-row="' + escapeHtml(it.key) + '">'
      + '<div class="lc-row-top">'
      + '<span class="lc-badge">' + escapeHtml(_odCatLabel(it.cat, it.subtype)) + '</span>'
      + '<span class="lc-path">' + escapeHtml(it.id) + '</span>'
      + '<span class="lc-badge ' + bCls + '">' + escapeHtml(bTxt) + '</span>'
      + '<button type="button" class="btn" style="margin-left:auto;padding:2px 8px;font-size:11px" data-od-detail="' + escapeHtml(it.key) + '">对比源码</button>'
      + '</div>'
      + '<div class="lc-trail">' + recs + '</div>'
      + (it.rule_note ? '<div class="lc-note">' + escapeHtml(it.rule_note) + '</div>' : '')
      + '<div class="lc-detail" style="display:none"></div>'
      + '</div>';
  }).join('');

  list.querySelectorAll('[data-od-detail]').forEach(btn => {
    btn.onclick = () => toggleObjectDetail(btn, btn.dataset.odDetail);
  });
}

async function toggleObjectDetail(btn, objKey){
  const row = btn.closest('[data-od-row]');
  const box = row ? row.querySelector('.lc-detail') : null;
  if(!box) return;
  if(box.style.display !== 'none'){
    box.style.display = 'none';
    btn.textContent = '对比源码';
    return;
  }
  if(!box.dataset.loaded){
    btn.textContent = '读取中…';
    try{
      const r = await fetch('/api/object_diff?key=' + encodeURIComponent(objKey));
      const j = await r.json();
      if(!j.ok || !j.item){
        box.innerHTML = '<div class="lc-note" style="color:#ff7b7b">' + escapeHtml(j.msg || '读取失败') + '</div>';
      }else{
        const it = j.item;
        const blocks = (it.records || []).map(rec =>
          '<div>'
          + '<div class="lc-note" style="margin-bottom:3px">#' + rec.order + ' ' + escapeHtml(rec.layer_name)
          + ' · <code>' + escapeHtml(rec.rel) + '</code> [' + escapeHtml(_odRecLabel(rec.state)) + ']</div>'
          + '<pre class="lc-pre">' + escapeHtml(rec.raw || '（空块）') + '</pre>'
          + '</div>'
        ).join('');
        const diffHtml = it.diff
          ? '<div><div class="lc-note" style="margin-bottom:3px">行级差异（unified diff）</div><pre class="lc-pre">' + escapeHtml(it.diff) + '</pre></div>'
          : '';
        box.innerHTML = diffHtml + blocks;
        box.dataset.loaded = '1';
      }
    }catch(e){
      box.innerHTML = '<div class="lc-note" style="color:#ff7b7b">读取失败：' + escapeHtml(e.message) + '</div>';
    }
  }
  box.style.display = 'flex';
  btn.textContent = '收起源码';
}

async function loadObjectDiff(opts){
  const o = opts || {};
  const qEl = document.getElementById('odQuery');
  const cEl = document.getElementById('odCat');
  const sEl = document.getElementById('odStatus');
  const params = new URLSearchParams();
  if(qEl && qEl.value.trim()) params.set('q', qEl.value.trim());
  if(cEl && cEl.value) params.set('cat', cEl.value);
  if(sEl && sEl.value) params.set('status', sEl.value);
  if(_lcState.layerFilter !== '') params.set('layer', String(_lcState.layerFilter));
  if(o.refresh) params.set('refresh', '1');
  try{
    const r = await fetch('/api/object_diff?' + params.toString());
    const j = await r.json();
    renderObjectDiff(j);
  }catch(e){
    const list = document.getElementById('odList');
    if(list) list.innerHTML = '<div style="padding:16px;color:#ff7b7b">加载对象覆盖失败：' + escapeHtml(e.message) + '</div>';
  }
}


/* ---------- 7-4 一键进游戏校验 ---------- */
let _gvTimer = null;
let _gvConfirmed = false;
let _gvRunning = false;

function _gvStopPoll(){
  if(_gvTimer){ clearInterval(_gvTimer); _gvTimer = null; }
}

function renderGameVerify(st){
  _gvConfirmed = !!st.confirmed;
  _gvRunning = !!st.running;

  const badge = document.getElementById('gvEnvBadge');
  const envPath = document.getElementById('gvEnvPath');
  const recBanner = document.getElementById('gvRecoverBanner');
  const runBtn = document.getElementById('gvRunBtn');
  const cancelBtn = document.getElementById('gvCancelBtn');
  const progBox = document.getElementById('gvProgressBox');
  const progMsg = document.getElementById('gvProgMsg');
  const progBar = document.getElementById('gvProgBar');
  const sumEl = document.getElementById('gvResultSummary');
  const listEl = document.getElementById('gvErrList');

  if(recBanner){
    if(st.recovered_msg){
      recBanner.style.display = 'block';
      recBanner.className = 'gv-banner warn';
      recBanner.textContent = '⚠ ' + st.recovered_msg;
    }else if(!st.env_ok && st.env_reason){
      recBanner.style.display = 'block';
      recBanner.className = 'gv-banner err';
      recBanner.textContent = '✖ ' + st.env_reason;
    }else{
      recBanner.style.display = 'none';
    }
  }

  if(badge){
    if(st.running){ badge.className = 'lc-badge warn'; badge.textContent = '检查进行中'; }
    else if(st.env_ok){ badge.className = 'lc-badge win'; badge.textContent = '游戏就绪'; }
    else{ badge.className = 'lc-badge blocked'; badge.textContent = '环境未就绪'; }
  }
  if(envPath){
    const mods = (st.mod_dirs || []).map(p => p.split(/[\\/]/).filter(Boolean).pop() || p);
    envPath.textContent = '游戏目录：' + (st.game_dir || '未检测到 hoi4.exe')
      + ' · 待测链：' + (mods.length ? mods.join(' → ') : '（未加载 mod）');
  }
  if(runBtn){
    runBtn.disabled = !!st.running || !st.env_ok || !(st.mod_dirs && st.mod_dirs.length);
  }
  if(cancelBtn){
    cancelBtn.style.display = st.running ? 'inline-flex' : 'none';
  }
  if(progBox){
    progBox.style.display = st.running ? 'flex' : 'none';
  }
  if(progMsg && st.running){ progMsg.textContent = st.msg || '检查运行中…'; }
  if(progBar && st.running){ progBar.style.width = Math.max(4, Math.min(100, Number(st.pct || 0))) + '%'; }

  const res = st.result;
  if(sumEl){
    if(!res){
      sumEl.innerHTML = st.msg && !st.running ? ('<span>' + escapeHtml(st.msg) + '</span>') : '';
    }else{
      const cls = res.ok ? 'win' : 'blocked';
      const head = res.ok ? '✓ 检查通过' : ('✕ 检查发现异常（' + (res.status || 'FAIL') + '）');
      const baseNote = res.baseline && res.baseline.status === 'CACHED' ? '复用基线缓存' : ('基线 ' + ((res.baseline && res.baseline.error_count) ?? '-') + ' 行');
      sumEl.innerHTML = '<span class="lc-badge ' + cls + '">' + escapeHtml(head) + '</span>'
        + '<span>' + escapeHtml(res.msg || '') + '（' + escapeHtml(baseNote) + ' · 目标 error.log ' + (res.target_error_count ?? 0) + ' 行）</span>';
    }
  }
  if(listEl){
    if(!res){
      listEl.innerHTML = '<div style="padding:18px;text-align:center;color:var(--muted);font-size:12px">点击「开始进游戏检查」后，将自动对比主菜单 error.log 并把新增报错定位到具体文件与行号。</div>';
    }else if(res.ok){
      listEl.innerHTML = '<div style="padding:18px;text-align:center;color:#5bd188;font-size:12.5px">✓ 主菜单启动正常，相对基线 0 条新增 error.log 报错。</div>';
    }else{
      const items = res.added || [];
      if(!items.length){
        const cr = (res.new_crashes || []).map(c => c.dir + (c.head ? (' (' + c.head + ')') : '')).join('；');
        listEl.innerHTML = '<div class="lc-row"><div class="lc-path" style="color:#ff7b7b">'
          + escapeHtml(res.msg || '游戏未能正常到达主菜单') + (cr ? (' · 崩溃转储：' + escapeHtml(cr)) : '')
          + '</div></div>';
      }else{
        listEl.innerHTML = items.map((it, idx) => {
          const locs = (it.locations || []).map(loc =>
            '<div style="margin-top:4px">'
            + '<span class="lc-badge win">' + escapeHtml(loc.layer || '') + ' · ' + escapeHtml(loc.file || loc.path)
            + (loc.line ? (' : 第 ' + loc.line + ' 行') : '') + '</span>'
            + (loc.excerpt ? '<pre class="lc-pre" style="margin-top:3px">' + escapeHtml(loc.excerpt) + '</pre>' : '')
            + '</div>'
          ).join('');
          const noLoc = !locs
            ? ('<div class="lc-note">未定位到具体文件' + (it.line ? ('（报错提及第 ' + it.line + ' 行）') : '') + '</div>')
            : '';
          return '<div class="lc-row">'
            + '<div class="lc-row-top"><span class="lc-badge blocked">#' + (idx + 1) + '</span>'
            + '<span class="lc-path">' + escapeHtml(it.norm || it.raw || '') + '</span></div>'
            + (locs || noLoc)
            + '</div>';
        }).join('');
      }
    }
  }
}

async function refreshGameVerifyStatus(){
  try{
    const r = await fetch('/api/game_verify/status', {cache: 'no-store'});
    const st = await r.json();
    renderGameVerify(st);
    if(st.running && !_gvTimer){
      _gvTimer = setInterval(refreshGameVerifyStatus, 1200);
    }else if(!st.running){
      _gvStopPoll();
    }
    return st;
  }catch(e){
    _gvStopPoll();
    return null;
  }
}

async function startGameVerifyFlow(withConfirm){
  const cb = document.getElementById('gvConfirmBox');
  if(!_gvConfirmed && !withConfirm){
    if(cb) cb.style.display = 'block';
    return;
  }
  if(cb) cb.style.display = 'none';
  const modeEl = document.getElementById('gvBaseMode');
  const reuseEl = document.getElementById('gvReuseBase');
  const r = await fetch('/api/game_verify/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      confirm: !!withConfirm,
      baseline_mode: modeEl ? modeEl.value : 'parents',
      reuse_baseline: reuseEl ? !!reuseEl.checked : true,
    }),
  });
  const j = await r.json();
  if(j.need_confirm){
    if(cb) cb.style.display = 'block';
    return;
  }
  if(!j.ok){
    status(j.msg || '无法启动检查', true);
    await refreshGameVerifyStatus();
    return;
  }
  await refreshGameVerifyStatus();
}

async function cancelGameVerifyFlow(){
  await fetch('/api/game_verify/cancel', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
  await refreshGameVerifyStatus();
}

function openGameVerify(){
  const cb = document.getElementById('gvConfirmBox');
  if(cb) cb.style.display = 'none';
  document.getElementById('gameVerifyModal').classList.add('show');
  refreshGameVerifyStatus();
}

function closeGameVerify(){
  _gvStopPoll();
  document.getElementById('gameVerifyModal').classList.remove('show');
}


/* ---------- 7-5 打包发布 ---------- */
let _pubPreview = null;

function _pubReadOverrides(){
  const nameEl = document.getElementById('pubName');
  const verEl = document.getElementById('pubVer');
  const gvEl = document.getElementById('pubGameVer');
  const tagsEl = document.getElementById('pubTags');
  const depsEl = document.getElementById('pubDeps');
  return {
    name: nameEl ? nameEl.value.trim() : '',
    version: verEl ? verEl.value.trim() : '',
    supported_version: gvEl ? gvEl.value.trim() : '',
    tags: tagsEl ? tagsEl.value.trim() : '',
    dependencies: depsEl ? depsEl.value.trim() : '',
  };
}

function renderPublishModal(data, keepInputs){
  _pubPreview = data;
  const badge = document.getElementById('pubBadge');
  const sel = document.getElementById('pubModSel');
  const statEl = document.getElementById('pubStat');
  const listEl = document.getElementById('pubChecklist');
  const runBtn = document.getElementById('pubRunBtn');

  if(sel){
    const cands = data.candidates || [];
    const curVal = data.mod_root || sel.value || '';
    sel.innerHTML = '';
    if(!cands.length){
      const o = document.createElement('option');
      o.value = '';
      o.textContent = '（未加载本地 mod）';
      sel.appendChild(o);
    }else{
      for(const c of cands){
        const o = document.createElement('option');
        o.value = c.path;
        o.textContent = (c.name || c.folder) + ' (' + c.folder + ')' + (c.readonly ? ' [只读]' : '');
        sel.appendChild(o);
      }
      if(curVal) sel.value = curVal;
    }
  }

  if(!data || !data.ok){
    if(badge){ badge.className = 'lc-badge blocked'; badge.textContent = '未就绪'; }
    if(statEl) statEl.innerHTML = '<span>' + escapeHtml((data && data.msg) || '无法预览') + '</span>';
    if(listEl) listEl.innerHTML = '';
    if(runBtn) runBtn.disabled = true;
    return;
  }

  if(runBtn) runBtn.disabled = false;
  if(badge){
    badge.className = 'lc-badge win';
    badge.textContent = '预检完成 · ' + (data.included_count || 0) + ' 文件';
  }

  if(!keepInputs){
    const meta = data.meta || {};
    const nameEl = document.getElementById('pubName');
    const verEl = document.getElementById('pubVer');
    const gvEl = document.getElementById('pubGameVer');
    const tagsEl = document.getElementById('pubTags');
    const depsEl = document.getElementById('pubDeps');
    const fidEl = document.getElementById('pubFolderId');
    const outEl = document.getElementById('pubOutDir');
    if(nameEl) nameEl.value = meta.name || '';
    if(verEl) verEl.value = meta.version || '0.1.0';
    if(gvEl) gvEl.value = meta.supported_version || '1.19.*';
    if(tagsEl) tagsEl.value = (meta.tags || []).join(', ');
    if(depsEl) depsEl.value = (meta.dependencies || []).join(', ');
    if(fidEl && !fidEl.dataset.edited) fidEl.value = data.folder_id || '';
    if(outEl && !outEl.value.trim()) outEl.value = data.default_out_dir || '';
  }

  const excludedCnt = data.excluded_count || 0;
  const bomAdd = data.bom_add || [];
  const bomStrip = data.bom_strip || [];
  const warns = data.brace_warns || [];
  if(statEl){
    statEl.innerHTML = ''
      + '<span class="lc-badge win">纳入 ' + (data.included_count || 0) + ' 个文件</span>'
      + '<span class="lc-badge ' + (excludedCnt ? 'warn' : 'win') + '">剔除备份/缓存 ' + excludedCnt + ' 项</span>'
      + '<span class="lc-badge ' + ((bomAdd.length + bomStrip.length) ? 'warn' : 'win') + '">自动规范 BOM ' + (bomAdd.length + bomStrip.length) + ' 个</span>'
      + (warns.length ? '<span class="lc-badge blocked">括号异常 ' + warns.length + ' 个</span>' : '');
  }

  if(listEl){
    const rows = [];
    rows.push('<div class="lc-row"><div class="lc-row-top">'
      + '<span class="lc-badge ' + (data.descriptor_exists ? 'win' : 'warn') + '">descriptor.mod</span>'
      + '<span>' + (data.descriptor_exists ? '源目录已有 descriptor.mod，导出时将规范化字段（UTF-8 无 BOM）' : '源目录缺少 descriptor.mod，导出时将自动生成') + '</span>'
      + '</div></div>');

    rows.push('<div class="lc-row"><div class="lc-row-top">'
      + '<span class="lc-badge ' + (data.has_picture ? 'win' : 'warn') + '">thumbnail.png</span>'
      + '<span>' + (data.has_picture ? '已存在封面图，将随包导出' : '源目录缺少封面图，导出时将自动生成 256×256 占位图') + '</span>'
      + '</div></div>');

    const dchecks = data.dep_checks || [];
    const sug = data.suggested_deps || [];
    if(dchecks.length){
      const dHtml = dchecks.map(dc =>
        '<div><span class="lc-badge ' + (dc.found ? 'win' : 'warn') + '">'
        + (dc.found ? '✓ 已匹配' : '⚠ 未在本地找到') + '</span> '
        + escapeHtml(dc.resolved)
        + (dc.changed ? (' <span class="lc-note">（原填：' + escapeHtml(dc.raw) + ' → 自动校准为真实 name=）</span>') : '')
        + '</div>'
      ).join('');
      rows.push('<div class="lc-row"><div class="lc-row-top"><span class="lc-badge win">dependencies</span><span>依赖校验（' + dchecks.length + ' 项）</span></div>' + dHtml + '</div>');
    }else if(sug.length){
      rows.push('<div class="lc-row"><div class="lc-row-top"><span class="lc-badge warn">dependencies</span>'
        + '<span>当前依赖为空，叠加链前层包含：' + escapeHtml(sug.join(', ')) + '</span></div></div>');
    }

    const lc = data.launcher_conflict || {};
    if(lc.conflict){
      rows.push('<div class="lc-row"><div class="lc-row-top"><span class="lc-badge warn">启动器 .mod 冲突</span>'
        + '<span>启动器目录已存在同名 <code>' + escapeHtml((data.folder_id || '') + '.mod') + '</code>（指向 '
        + escapeHtml(lc.existing_path || '其它位置') + '），可勾选「更新同名」或改用其它导出文件夹名。</span></div></div>');
    }

    if(data.target_nested_warning){
      rows.push('<div class="lc-row"><div class="lc-row-top"><span class="lc-badge blocked">目录冲突</span>'
        + '<span>目标导出目录不能与源 mod 目录相同或嵌套，请调整导出父目录或文件夹名。</span></div></div>');
    }

    const ex = data.excluded_files || [];
    if(ex.length){
      const exLines = ex.slice(0, 60).map(it => escapeHtml(it.rel) + '  —  ' + escapeHtml(it.detail || it.reason)).join('\n');
      rows.push('<div class="lc-row"><div class="lc-row-top"><span class="lc-badge warn">将剔除的无关文件</span>'
        + '<span>共 ' + excludedCnt + ' 项（导出时自动排除，不污染工坊包）</span></div>'
        + '<pre class="lc-pre">' + exLines + (ex.length > 60 ? ('\n… 其余 ' + (ex.length - 60) + ' 项') : '') + '</pre></div>');
    }

    if(bomAdd.length || bomStrip.length){
      const lines = []
        .concat(bomAdd.map(f => '[+BOM 补全] ' + f))
        .concat(bomStrip.map(f => '[-BOM 剥离] ' + f));
      rows.push('<div class="lc-row"><div class="lc-row-top"><span class="lc-badge warn">编码 BOM 规范化</span>'
        + '<span>本地化 .yml 补齐 BOM（' + bomAdd.length + '），其余文本剥离多余 BOM（' + bomStrip.length + '）</span></div>'
        + '<pre class="lc-pre">' + escapeHtml(lines.slice(0, 60).join('\n')) + '</pre></div>');
    }

    if(warns.length){
      rows.push('<div class="lc-row"><div class="lc-row-top"><span class="lc-badge blocked">花括号未配平</span>'
        + '<span>以下脚本文件大括号不成对，建议进游戏前修复：</span></div>'
        + '<pre class="lc-pre">' + escapeHtml(warns.map(w => w.rel + ' (差值 ' + w.depth + ')').join('\n')) + '</pre></div>');
    }

    listEl.innerHTML = rows.join('');
  }
}

async function loadPublishPreview(keepInputs){
  const sel = document.getElementById('pubModSel');
  const outEl = document.getElementById('pubOutDir');
  const fidEl = document.getElementById('pubFolderId');
  const body = {
    mod_root: sel ? sel.value : '',
    out_dir: outEl ? outEl.value.trim() : '',
    folder_id: (keepInputs && fidEl) ? fidEl.value.trim() : '',
    overrides: keepInputs ? _pubReadOverrides() : null,
  };
  try{
    const r = await fetch('/api/publish/preview', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const j = await r.json();
    renderPublishModal(j, !!keepInputs);
    return j;
  }catch(e){
    const statEl = document.getElementById('pubStat');
    if(statEl) statEl.innerHTML = '<span style="color:#ff7b7b">预检失败：' + escapeHtml(e.message) + '</span>';
    return null;
  }
}

async function openPublishModal(){
  const resBox = document.getElementById('pubResultBox');
  if(resBox){ resBox.style.display = 'none'; resBox.innerHTML = ''; }
  const fidEl = document.getElementById('pubFolderId');
  if(fidEl){ delete fidEl.dataset.edited; fidEl.value = ''; }
  const outEl = document.getElementById('pubOutDir');
  if(outEl) outEl.value = '';
  const sel = document.getElementById('pubModSel');
  if(sel) sel.value = '';
  const badge = document.getElementById('pubBadge');
  if(badge){ badge.className = 'lc-badge'; badge.textContent = '预检中…'; }
  const runBtn = document.getElementById('pubRunBtn');
  if(runBtn) runBtn.disabled = true;
  document.getElementById('publishModal').classList.add('show');
  await loadPublishPreview(false);
}

function closePublishModal(){
  document.getElementById('publishModal').classList.remove('show');
}

function useLauncherModDirForPublish(){
  const home = (DATA && DATA.mod_home) || (_pubPreview && _pubPreview.launcher_mod_dir) || '';
  if(!home){ status('未探测到 Paradox 启动器 mod 目录', true); return; }
  const outEl = document.getElementById('pubOutDir');
  const fidEl = document.getElementById('pubFolderId');
  const sel = document.getElementById('pubModSel');
  if(outEl) outEl.value = home;
  if(fidEl && sel && sel.value){
    const srcNorm = sel.value.replace(/[\\/]+$/, '').toLowerCase();
    const tgtNorm = (home.replace(/[\\/]+$/, '') + '\\' + (fidEl.value.trim() || '')).toLowerCase();
    if(srcNorm === tgtNorm){
      fidEl.value = (fidEl.value.trim() || 'mod') + '_release';
      fidEl.dataset.edited = '1';
    }
  }
  loadPublishPreview(true);
}

async function runPublishExport(){
  const sel = document.getElementById('pubModSel');
  const outEl = document.getElementById('pubOutDir');
  const fidEl = document.getElementById('pubFolderId');
  const regEl = document.getElementById('pubRegLauncher');
  const ovModEl = document.getElementById('pubOverwriteMod');
  const zipEl = document.getElementById('pubAlsoZip');
  const resBox = document.getElementById('pubResultBox');
  const runBtn = document.getElementById('pubRunBtn');
  const origTxt = runBtn ? runBtn.textContent : '';
  if(runBtn){ runBtn.disabled = true; runBtn.textContent = '⏳ 正在打包导出…'; }

  const body = {
    mod_root: sel ? sel.value : '',
    out_dir: outEl ? outEl.value.trim() : '',
    folder_id: fidEl ? fidEl.value.trim() : '',
    register_launcher: regEl ? !!regEl.checked : true,
    overwrite_launcher_mod: ovModEl ? !!ovModEl.checked : false,
    also_zip: zipEl ? !!zipEl.checked : false,
    overrides: _pubReadOverrides(),
  };
  try{
    const r = await fetch('/api/publish/export', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if(resBox){
      resBox.style.display = 'block';
      if(j.ok){
        resBox.className = 'gv-banner';
        resBox.innerHTML = '<div style="font-weight:600;color:#5bd188;margin-bottom:4px">✓ ' + escapeHtml(j.msg || '导出成功') + '</div>'
          + '<div style="font-size:11.5px;line-height:1.6">'
          + '<div><b>工坊导出目录：</b><code>' + escapeHtml(j.export_dir || '') + '</code></div>'
          + (j.launcher_mod ? ('<div><b>官方启动器 .mod：</b><code>' + escapeHtml(j.launcher_mod) + '</code></div>') : '')
          + (j.zip_path ? ('<div><b>ZIP 压缩包：</b><code>' + escapeHtml(j.zip_path) + '</code></div>') : '')
          + '<div style="color:var(--muted);margin-top:4px">下一步：打开 Paradox 官方启动器 → 所有已安装模组 → 上传模组，即可在列表中选择并上传到 Steam 创意工坊。</div>'
          + '</div>';
        status(j.msg || '打包发布成功');
      }else{
        resBox.className = 'gv-banner err';
        resBox.textContent = '✖ ' + (j.msg || '导出失败');
        status(j.msg || '导出失败', true);
      }
    }
  }catch(e){
    if(resBox){
      resBox.style.display = 'block';
      resBox.className = 'gv-banner err';
      resBox.textContent = '✖ 导出请求异常：' + (e.message || e);
    }
    status('导出请求异常', true);
  }finally{
    if(runBtn){ runBtn.disabled = false; runBtn.textContent = origTxt || '🚀 导出工坊就绪目录'; }
  }
}

async function runLegacyPatchExport(){
  const r = await fetch('/api/export', {method:'POST'});
  const j = await r.json();
  status(j.path ? ('覆盖包已导出：' + j.path) : ('导出失败：' + j.msg), !j.path);
  const resBox = document.getElementById('pubResultBox');
  if(resBox){
    resBox.style.display = 'block';
    resBox.className = j.path ? 'gv-banner' : 'gv-banner err';
    resBox.textContent = j.path ? ('✓ 本次改动覆盖包已导出：' + j.path) : ('✖ ' + (j.msg || '没有改动'));
  }
}
