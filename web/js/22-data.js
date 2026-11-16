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

function openNewMod(){
  const b = document.getElementById('nmBase');
  if(!b.value) b.value = (DATA && DATA.mod_home) || '';
  document.getElementById('nmId').value = '';
  document.getElementById('nmName').value = '';
  document.getElementById('nmTreeId').value = '';
  document.getElementById('nmTag').value = '';
  document.getElementById('nmTree').checked = true;
  // 自动填「依赖本体」：取第一个非只读的已加载 mod
  const dep = document.getElementById('nmDep');
  const hint = document.getElementById('nmDepHint');
  const mine = ((DATA && DATA.roots) || []).filter(r => !r.readonly);
  if(dep){
    dep.value = mine.length ? (mine[0].name || mine[0].path || '') : '';
    if(hint){
      if(mine.length){
        hint.style.display = 'block';
        hint.textContent = '已填「' + dep.value + '」。建出来的是它的 submod：加载时会自动带上本体，'
                         + '原版数据不会漏进来。想从原版开始做，把这里清空。';
      }else{
        hint.style.display = 'block';
        hint.textContent = '当前没加载任何 mod，留空就是从原版开始做一个新 mod。';
      }
    }
  }
  document.getElementById('newMod').classList.add('show');
}

async function createNewMod(){
  const id = document.getElementById('nmId').value.trim();
  const name = document.getElementById('nmName').value.trim() || id;
  if(!id){ status('先填模组文件夹名'); return; }
  const body = {
    base: document.getElementById('nmBase').value.trim() || (DATA && DATA.mod_home) || '',
    id, name,
    version: document.getElementById('nmVer').value.trim() || '0.1.0',
    game_version: document.getElementById('nmGame').value.trim() || '1.19.*',
    create_tree: document.getElementById('nmTree').checked,
    tree_id: document.getElementById('nmTreeId').value.trim() || (id + '_tree'),
    tag: document.getElementById('nmTag').value.trim().toUpperCase(),
    dep: document.getElementById('nmDep') ? document.getElementById('nmDep').value.trim() : ''
  };
  const r = await fetch('/api/new_mod', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok){ document.getElementById('newMod').classList.remove('show'); await loadData(); }
}

async function addEquip(){
  const id = prompt('新装备 ID（字母数字下划线）：');
  if(!id) return;
  const r = await fetch('/api/equip_add', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: (DATA.roots[0]||{}).path, id})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok){ await loadData(); renderEquipList(''); selectEquip((DATA.equipment||[]).find(x=>x.id===id)); }
}

async function deleteEquip(){
  if(!equipSel){ status('先选择装备'); return; }
  if(!confirm('确定删除装备 ' + equipSel.id + ' ？（可用 .bak 恢复）')) return;
  const r = await fetch('/api/equip_delete', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: rootByName(equipSel.source), file: equipSel.file, id: equipSel.id})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok){ equipSel = null; await loadData(); renderEquipList(''); }
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
