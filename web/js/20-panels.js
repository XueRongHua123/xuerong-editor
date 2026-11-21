// 20-panels：弹窗开合（P4）
// 本地化检查 / 日志 / 备份 / 卸载 / 文件夹选择 / 编辑面板索引条 / 诊断面板。

function _locEsc(t){
  return String(t==null?'':t).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

async function _loadLocBrowse(){
  const listEl = document.getElementById('locBrowseList');
  const statEl = document.getElementById('locBrowseStat');
  if(!listEl) return;
  const q = (document.getElementById('locSearch')?.value || '').trim();
  const scope = document.getElementById('locScope')?.value || 'all';
  const lang = document.getElementById('locLang')?.value || 'simp_chinese';
  listEl.innerHTML = '<div style="padding:12px;color:var(--muted);font-size:12px">查询中…</div>';
  try{
    const url = '/api/loc_list?q=' + encodeURIComponent(q) + '&scope=' + encodeURIComponent(scope) + '&lang=' + encodeURIComponent(lang) + '&limit=120';
    const r = await (await fetch(url)).json();
    if(!r.ok){ listEl.innerHTML = '<div style="padding:12px;color:var(--muted)">查询失败</div>'; return; }
    const items = r.items || [];
    if(statEl){
      statEl.textContent = '共匹配 ' + (r.total || 0) + ' 条' + (r.truncated ? '（显示前 ' + items.length + ' 条，请缩小关键词）' : '');
    }
    if(!items.length){
      listEl.innerHTML = '<div style="padding:18px;text-align:center;color:var(--muted);font-size:12px">没有匹配的本地化条目</div>';
      return;
    }
    listEl.innerHTML = items.map((it, idx)=>{
      const tag = it.edited ? '<span style="font-size:10px;padding:1px 5px;border-radius:3px;background:color-mix(in srgb,var(--accent) 20%,transparent);color:var(--accent)">本mod</span>' : '';
      return '<div class="loc-browse-row" data-loc-key="' + _locEsc(it.key) + '" style="display:flex;gap:6px;align-items:center;padding:5px 4px;border-bottom:1px solid var(--line);font-size:12px">'
        + '<div style="width:230px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;font-family:ui-monospace,Consolas,monospace;font-size:11px" title="' + _locEsc(it.key) + '">'
        + _locEsc(it.key) + ' ' + tag + '</div>'
        + '<input class="loc-val-inp" data-idx="' + idx + '" value="' + _locEsc(it.text || '') + '" style="flex:1;min-width:0;background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:4px;padding:3px 6px;font-size:12px">'
        + '<button class="btn loc-save-btn" data-key="' + _locEsc(it.key) + '" style="font-size:11px;padding:2px 8px">保存</button>'
        + '</div>';
    }).join('');
  }catch(e){
    listEl.innerHTML = '<div style="padding:12px;color:var(--muted)">请求失败：' + _locEsc(e) + '</div>';
  }
}

function _switchLocTab(tab){
  const bPane = document.getElementById('locBrowsePane');
  const mPane = document.getElementById('locMissingPane');
  const bBtn = document.getElementById('locTabBrowse');
  const mBtn = document.getElementById('locTabMissing');
  const isBrowse = (tab !== 'missing');
  if(bPane) bPane.style.display = isBrowse ? '' : 'none';
  if(mPane) mPane.style.display = isBrowse ? 'none' : '';
  if(bBtn) bBtn.classList.toggle('primary', isBrowse);
  if(mBtn) mBtn.classList.toggle('primary', !isBrowse);
}

(function(){
  const bBtn = document.getElementById('locTabBrowse');
  const mBtn = document.getElementById('locTabMissing');
  const qBtn = document.getElementById('locBrowseBtn');
  const qInp = document.getElementById('locSearch');
  const scSel = document.getElementById('locScope');
  const lgSel = document.getElementById('locLang');
  const bList = document.getElementById('locBrowseList');
  if(bBtn) bBtn.onclick = ()=>{ _switchLocTab('browse'); _loadLocBrowse(); };
  if(mBtn) mBtn.onclick = ()=>{ _switchLocTab('missing'); };
  if(qBtn) qBtn.onclick = _loadLocBrowse;
  if(scSel) scSel.onchange = _loadLocBrowse;
  if(lgSel) lgSel.onchange = _loadLocBrowse;
  if(qInp) qInp.addEventListener('keydown', e=>{ if(e.key === 'Enter') _loadLocBrowse(); });
  if(bList){
    bList.addEventListener('click', async e=>{
      const btn = e.target.closest('.loc-save-btn');
      if(!btn) return;
      const row = btn.closest('.loc-browse-row');
      const inp = row ? row.querySelector('.loc-val-inp') : null;
      const key = btn.dataset.key || '';
      const lang = document.getElementById('locLang')?.value || 'simp_chinese';
      if(!key || !inp) return;
      const root = (typeof _writableRoot === 'function' ? _writableRoot() : '') || (DATA && DATA.roots && DATA.roots[0]) || '';
      if(!root){ status('没有可写的模组目录', true); return; }
      const entries = {}; entries[lang] = {}; entries[lang][key] = inp.value;
      btn.disabled = true;
      try{
        const r = await (await fetch('/api/loc_save', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({root, entries})})).json();
        status(r.ok ? ('已保存本地化：' + key) : ('保存失败：' + (r.msg || '')), !r.ok);
        if(r.ok) _loadLocBrowse();
      }catch(err){
        status('保存失败：' + err, true);
      }finally{
        btn.disabled = false;
      }
    });
  }
})();

async function openLocCheck(){
  _switchLocTab('browse');
  const r = await fetch('/api/missing_loc');
  const j = await r.json();
  const box = document.getElementById('locList');
  const items = j.items || [];
  if(!items.length){ box.textContent = '没有缺失本地化的焦点。'; }
  else {
    box.innerHTML = '';
    items.slice(0, 800).forEach(it=>{
      const d = document.createElement('div');
      d.className = 'locrow';
      d.textContent = it.id + '   [' + it.tree + ']';
      d.onclick = ()=>{
        const idx = DATA.trees.findIndex(t=>t.id === it.tree);
        if(idx >= 0){
          current = idx; selId = it.id;
          document.getElementById('locModal').classList.remove('show');
          renderAll(); showPanel();
        }
      };
      box.appendChild(d);
    });
  }
  document.getElementById('locModal').classList.add('show');
  await _loadLocBrowse();
}

async function openLog(){
  document.getElementById('logModal').classList.add('show');
  if(window.__logOpen) await window.__logOpen();
}

async function openBackups(){
  const t = curTree();
  if(!t){ status('先选择一棵树'); return; }
  const file = t.file || (t.focuses[0] && t.focuses[0].file);
  if(!file){ status('这棵树没有关联文件'); return; }
  const r = await fetch('/api/backups?root=' + encodeURIComponent(rootOf(t)) + '&file=' + encodeURIComponent(file));
  const j = await r.json();
  const box = document.getElementById('backupList');
  const items = j.items || [];
  if(!items.length){ box.textContent = '这个文件还没有可恢复的历史备份。'; }
  else {
    box.innerHTML = '';
    items.slice().reverse().forEach(it=>{
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:4px 6px;border-bottom:1px solid #2b3234';
      row.innerHTML = '<span>' + escapeHtml(it.time) + '</span>';
      const b = document.createElement('button');
      b.className = 'btn'; b.textContent = '恢复此版本';
      b.onclick = ()=>restoreBackup(it.index);
      row.appendChild(b);
      box.appendChild(row);
    });
  }
  document.getElementById('backupModal').classList.add('show');
}

async function restoreBackup(index){
  const t = curTree(); if(!t) return;
  const file = t.file || (t.focuses[0] && t.focuses[0].file);
  if(!confirm('恢复会覆盖当前文件内容，确定？')) return;
  const r = await fetch('/api/restore_backup', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: rootOf(t), file, index})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok){ document.getElementById('backupModal').classList.remove('show'); await loadData(); }
}

function openUnloadModal(){
  return openUnloadModalRecent();
}


function openUnloadModalOld(){
  const box = document.getElementById('unloadList');
  const roots = (DATA && DATA.roots) || [];
  document.getElementById('unloadModal').classList.add('show');
  if(!roots.length){
    box.innerHTML = '<div class="ul-empty">还没有加载任何内容。用左侧「＋ 添加 mod」或「📖 加载原版参考」开始。</div>';
    return;
  }
  box.innerHTML = roots.map((r, i)=>
    '<div class="ul-row">' +
      '<div class="ul-main"><b>' + escapeHtml(r.name || r.path) + '</b><span>' + escapeHtml(r.path || '') + '</span></div>' +
      '<span class="ul-tag' + (r.readonly ? ' ro' : '') + '">' + (r.readonly ? '原版 · 只读' : '可编辑') + '</span>' +
      '<button class="btn" data-i="' + i + '">卸载</button>' +
    '</div>').join('');
  box.querySelectorAll('button[data-i]').forEach(b=>{
    b.onclick = ()=>unloadRoot(roots[Number(b.dataset.i)]);
  });
}

function closeUnloadModal(){ document.getElementById('unloadModal').classList.remove('show'); }

async function unloadRoot(r){
  if(!r){ return; }
  const label = r.name || r.path;
  if(!confirm('从编辑器卸载「' + label + '」？\n只影响当前会话，不会删除磁盘文件。')) return;
  const res = await fetch('/api/unload_mod', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({root: r.path})});
  const j = await res.json();
  status(j.msg || '', !j.ok);
  if(!j.ok) return;
  await loadData();
  openUnloadModal();
  if(!((DATA && DATA.roots) || []).length) closeUnloadModal();
}

function unloadMod(){ openUnloadModal(); }

async function loadModPath(){
  const p = prompt('输入 mod 根目录路径（含 descriptor.mod 的那一层）：');
  if(!p) return;
  await loadModByPath(p);
}

async function openFolderPicker(opts){
  fpMode = (opts && opts.mode === 'game') ? 'game' : 'mod';
  const headTitle = document.querySelector('#folderPick .fp-head b');
  const okBtn = document.getElementById('fpOk');
  if(headTitle){
    headTitle.textContent = fpMode === 'game'
      ? '选择《钢铁雄心 IV》安装目录（含 hoi4.exe）'
      : '选择 mod 文件夹';
  }
  if(okBtn){
    okBtn.textContent = fpMode === 'game' ? '设为游戏目录' : '选择此文件夹';
  }
  document.getElementById('folderPick').classList.add('show');
  document.getElementById('fpSel').textContent = '未选择文件夹';
  fpSelPath = '';
  const startDir = (fpMode === 'game' && DATA && DATA.game_dir) ? DATA.game_dir : fpDir;
  await fsGo(startDir);
}
window.openGameDirPicker = () => openFolderPicker({mode: 'game'});

let _fsSeq = 0;

async function fsGo(p){
  const seq = ++_fsSeq;
  try {
    const r = await fetch('/api/fs?path=' + encodeURIComponent(p || ''));
    const j = await r.json();
    if(seq !== _fsSeq) return;
    fpDir = j.path || '';
    fpParent = j.parent || '';
    document.getElementById('fpPath').value = fpDir;
    document.getElementById('fpSel').textContent = fpDir || '选择盘符或输入路径';
    renderFs(j);
  } catch(e){ if(seq === _fsSeq) status('读取目录失败', true); }
}

function renderFs(j){
  const list = document.getElementById('fpList');
  list.innerHTML = '';
  const add = (name, path, parent, hasMod, hasGame)=>{
    const d = document.createElement('div');
    d.className = 'fp-row';
    d.dataset.path = path;
    const badges = (hasMod ? '<span class="badge">mod</span>' : '') +
                   (hasGame ? '<span class="badge">HOI4</span>' : '');
    d.innerHTML = '<span>' + (parent ? '⬆ 上级目录' : '📁 ' + escapeHtml(name)) + '</span>' +
                  (badges ? '<span>' + badges + '</span>' : '');
    d.onclick = ()=>fsGo(path);
    list.appendChild(d);
  };
  if(j.parent) add('..', j.parent, true, false, false);
  (j.dirs || []).forEach(x=>add(x.name, x.path, false, x.has_mod, x.has_game));
  if(j.error) list.innerHTML = '<div class="fp-row">' + escapeHtml(j.error) + '</div>';
}

async function chooseFolder(){
  const rawInp = (document.getElementById('fpPath') && document.getElementById('fpPath').value || '').trim();
  const p = rawInp || fpDir;
  if(!p){ status('先选一个文件夹'); return; }
  if(fpMode === 'game'){
    try{
      const r = await fetch('/api/set_game_dir', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({path: p})
      });
      const j = await r.json();
      if(!j.ok){
        if(typeof showError === 'function') showError(j);
        else status(j.msg || '设置游戏目录失败', true);
        return;
      }
      document.getElementById('folderPick').classList.remove('show');
      status(j.msg || '已设置游戏目录');
      await loadData();
      const gvm = document.getElementById('gameVerifyModal');
      if(gvm && gvm.classList.contains('show') && typeof refreshGameVerifyStatus === 'function'){
        await refreshGameVerifyStatus();
      }
    }catch(e){
      status('设置游戏目录失败：' + e, true);
    }
    return;
  }
  // 先关掉选择器再加载：原先是在遮罩还开着的情况下同步等 /api/load_mod，
  // 20 秒里画面停在「选择 mod 文件夹」那一页，看起来像卡死，也没有任何进度。
  document.getElementById('folderPick').classList.remove('show');
  await loadModByPath(p);
}

function treeOptions(){
  treeList.innerHTML='';
  DATA.trees.forEach((t,i)=>{
    const d=document.createElement('div');
    d.textContent=`${t.id}  (${t.focuses.length})` + `  · ${t.source}`;
    d.className = i===current?'on':'';
    d.onclick=()=>{ current=i; treePicked=true; resetView(); renderAll(); };
    treeList.appendChild(d);
  });
}


// v1.9.6 日志行号跳转
(async function(){
  window.__logOpen = async function(){
    const r = await (await fetch('/api/errorlog')).json();
    const items = r.items || [];
    const body = document.getElementById('logBody');
    const stat = document.getElementById('logStat');
    const jump = document.getElementById('logJump');
    if(stat) stat.textContent = items.length
      ? (items.length + ' 行，其中 ' + (r.withLoc || 0) + ' 行能定位到文件')
      : '';
    if(jump) jump.style.display = 'none';
    if(!items.length){
      body.innerHTML = '<div class="cm-empty">没有发现相关的报错行。</div>';
      return;
    }
    const esc = function(t){
      return (t || '').replace(/[<>&]/g, function(c){
        return {'<':'&lt;','>':'&gt;','&':'&amp;'}[c];
      });
    };
    body.innerHTML = items.map(function(it){
      const loc = it.loc;
      const cls = 'log-line' + (loc ? ' clickable' : '');
      const tag = loc ? '<span class="log-loc">' + esc(loc.file) + ':' + loc.line + '</span>' : '';
      const tip = loc ? ('点这里看 ' + loc.file + ' 第 ' + loc.line + ' 行') : '';
      return '<div class="' + cls + '" data-file="' + (loc ? loc.file : '') +
             '" data-line="' + (loc ? loc.line : '') + '" title="' + tip + '">' +
             esc(it.text) + tag + '</div>';
    }).join('');

    body.querySelectorAll('.log-line.clickable').forEach(function(el){
      el.onclick = async function(){
        const f = el.dataset.file, ln = el.dataset.line;
        const jr = await (await fetch('/api/file_excerpt?file=' + encodeURIComponent(f) +
                                      '&line=' + encodeURIComponent(ln))).json();
        const head = document.getElementById('logJumpHead');
        const box = document.getElementById('logJumpBody');
        jump.style.display = 'block';
        if(!jr.ok){
          head.textContent = jr.msg || '打不开';
          box.innerHTML = '';
          return;
        }
        head.textContent = jr.file + '　第 ' + jr.line + ' 行 / 共 ' + jr.total + ' 行';
        box.innerHTML = (jr.excerpt || []).map(function(x){
          return '<div class="log-ex' + (x.hit ? ' hit' : '') + '">' +
                 String(x.n).padStart(4, ' ') + '  ' + esc(x.text) + '</div>';
        }).join('');
        const hit = box.querySelector('.log-ex.hit');
        if(hit) hit.scrollIntoView({block:'center'});
      };
    });
  };
})();


// v1.23.6 面板索引条：编辑 tab 里十几个面板，加一条可点的目录
(function(){
  function build(){
    const pane = document.getElementById('pane-edit');
    if(!pane || pane.querySelector('#paneIndex')) return;
    const boards = [...pane.querySelectorAll('h4')];
    if(boards.length < 4) return;

    const bar = document.createElement('div');
    bar.id = 'paneIndex';
    bar.style.cssText = 'display:flex;flex-wrap:wrap;gap:3px;margin-bottom:8px;'
      + 'padding:5px;background:var(--panel2,rgba(255,255,255,.03));'
      + 'border:1px solid var(--line);border-radius:5px';

    const items = [];
    boards.forEach(function(h, i){
      const box = h.parentElement;
      if(!box || box === pane) return;
      const title = (h.textContent || '').replace(/[−+]/g, '').trim();
      if(!title) return;
      if(!box.id) box.id = 'sec_' + i;
      items.push({title: title, id: box.id});
    });

    items.forEach(function(it){
      const b = document.createElement('button');
      b.className = 'btn';
      b.textContent = it.title;
      b.style.cssText = 'font-size:10px;height:20px;padding:0 6px';
      b.onclick = function(){
        const el = pane.querySelector('#' + it.id);
        if(!el) return;
        el.scrollIntoView({behavior: 'smooth', block: 'start'});
        // 闪一下，让用户看清跳到哪了
        const old = el.style.outline;
        el.style.outline = '2px solid var(--accent, #4a9eff)';
        setTimeout(function(){ el.style.outline = old; }, 900);
      };
      bar.appendChild(b);
    });

    pane.insertBefore(bar, pane.firstChild);
  }
  if(document.readyState !== 'loading') setTimeout(build, 400);
  else document.addEventListener('DOMContentLoaded', function(){ setTimeout(build, 400); });
})();


// ---------- 诊断 ----------
// v1.23.34 replace 断链从「一句话建议」变成可点的按钮：
//   撤销 replace / 接管该目录 / 忽略，外加面板顶部的批量条。
(function(){
  const entry = document.getElementById('diagEntry');
  const panel = document.getElementById('diagPanel');
  if(!entry || !panel) return;
  const list  = document.getElementById('diagList');
  const cnt   = document.getElementById('diagCount');
  const bar   = document.getElementById('diagFixBar');
  const ignBtn = document.getElementById('diagIgnoredBtn');
  const ignBox = document.getElementById('diagIgnoredBox');

  const SEV = { error:['#e05','严重'], warning:['#e90','警告'], info:['#39c','提示'] };

  function esc(t){
    return String(t==null?'':t).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  }

  // 后端 fix.options 里有哪几个就渲染哪几个，名字只在这里翻译
  const OPT_LABEL = { drop_replace:'撤销 replace', adopt_ref_dir:'接管该目录', adopt_file:'接管这个文件', ignore:'忽略' };
  const OPT_ACT   = { drop_replace:'drop', adopt_ref_dir:'adopt', adopt_file:'adopt-file', ignore:'ignore' };

  function fixButtons(f){
    const fx = f.fix;
    if(!fx || !fx.options || !fx.options.length) return '';
    const subs = (fx.subs && fx.subs.length ? fx.subs : [fx.sub]).filter(Boolean).join(',');
    const filesAttr = fx.adopt_files != null ? String(fx.adopt_files) : '';
    return '<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;align-items:center">'
      + fx.options.map(function(o){
          const act = OPT_ACT[o] || o;
          return '<button class="btn" style="font-size:11px;padding:2px 7px"'
            + ' data-act="'+act+'" data-subs="'+esc(subs)+'" data-ref="'+esc(fx.ref_dir||'')+'"'
            + ' data-group="'+esc(fx.group||'')+'" data-file="'+esc(fx.ref_file||'')+'"'
            + ' data-from="'+esc(fx.adopt_from||'')+'" data-files="'+esc(filesAttr)+'">'
            + esc(OPT_LABEL[o] || o) + '</button>';
        }).join('')
      + (fx.note ? '<span style="font-size:10.5px;color:var(--muted)">'+esc(fx.note)+'</span>' : '')
      + '</div>';
  }

  function render(items){
    if(!items || !items.length){
      list.innerHTML = '<div style="padding:18px;text-align:center;color:var(--muted);font-size:12px">没有发现问题</div>';
      return;
    }
    list.innerHTML = items.map(function(f, i){
      const sev = SEV[f.severity] || ['#888','?'];
      return '<div style="border-left:3px solid '+sev[0]+';background:color-mix(in srgb,'+sev[0]+' 6%,var(--panel2));padding:7px 9px;margin-bottom:6px;border-radius:4px">'
        + '<div style="display:flex;gap:6px;align-items:baseline;font-size:11px">'
        + '<span style="color:'+sev[0]+';font-weight:600">'+sev[1]+'</span>'
        + '<span style="color:var(--muted)">'+esc(f.code)+'</span>'
        + '<span style="flex:1"></span>'
        + '<span style="color:var(--muted)">'+esc(f.file||'')+(f.line?' : '+f.line:'')+'</span>'
        + '</div>'
        + '<div style="font-size:12px;margin-top:3px;line-height:1.5">'+esc(f.msg)+'</div>'
        + (f.excerpt ? '<div style="font-family:ui-monospace,Consolas,monospace;font-size:10.5px;color:var(--muted);background:rgba(0,0,0,.18);padding:3px 6px;margin-top:4px;border-radius:3px;white-space:pre-wrap;overflow-wrap:anywhere">'+esc(f.excerpt)+'</div>' : '')
        + (f.repair ? '<div style="font-size:11px;color:var(--accent-2);margin-top:4px">修：'+esc(f.repair)+'</div>' : '')
        + fixButtons(f)
        + '</div>';
    }).join('');
  }

  // 最近一次操作结果。批量操作后危险目录可能清零、汇总条会被收起，
  // 这条消息必须留在面板上，否则用户看不到「撤销了几条、还剩几个」。
  let lastMsg = '';

  function msgHtml(){
    return '<div id="diagFixMsg" style="font-size:11px;color:var(--muted);margin-top:4px;line-height:1.5">'
      + esc(lastMsg) + '</div>';
  }

  function setStatus(t){
    lastMsg = t || '';
    const el = document.getElementById('diagFixMsg');
    if(el) el.textContent = lastMsg;
  }

  function renderBar(items){
    if(!bar) return;
    const dg = (items||[]).filter(function(x){ return x.code === 'replace.dangling_refs'; });
    if(!dg.length){
      if(lastMsg){ bar.style.display = 'block'; bar.innerHTML = msgHtml(); }
      else { bar.style.display = 'none'; bar.innerHTML = ''; }
      return;
    }
    bar.style.display = 'block';
    const adoptItems = dg.filter(function(x){
      return ((x.fix||{}).options||[]).indexOf('adopt_ref_dir') >= 0; });
    const adoptable = adoptItems.length;
    const seenRef = {};
    let adoptDirs = 0, adoptTotalFiles = 0;
    adoptItems.forEach(function(x){
      const fx = x.fix || {};
      const rd = fx.ref_dir || '';
      if(rd && seenRef[rd]) return;
      if(rd) seenRef[rd] = 1;
      adoptDirs++;
      adoptTotalFiles += Number(fx.adopt_files || 0);
    });
    bar.innerHTML = '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;'
      + 'background:color-mix(in srgb,#e05577 10%,var(--panel2));border:1px solid color-mix(in srgb,#e05577 35%,var(--line));'
      + 'padding:7px 9px;border-radius:5px;font-size:12px">'
      + '<span>检测到 <b>'+dg.length+'</b> 个目录引用了已被 replace 替换掉的内容</span>'
      + '<span style="flex:1"></span>'
      + '<button class="btn" data-act="drop-all" style="font-size:11px;padding:2px 7px">全部撤销 replace</button>'
      + (adoptable ? '<button class="btn" data-act="adopt-all" data-dirs="'+adoptDirs+'" data-files="'+adoptTotalFiles+'" style="font-size:11px;padding:2px 7px">全部接管（'+adoptable+' 个）</button>' : '')
      + '</div>'
      + msgHtml();
  }

  async function post(url, payload){
    const r = await (await fetch(url, {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload||{})})).json();
    return r;
  }

  function fmtTs(ts){
    if(ts == null || ts === '') return '';
    if(typeof ts === 'number'){
      const d = new Date(ts < 1e12 ? ts * 1000 : ts);
      if(!isNaN(d.getTime())) return d.toLocaleString();
    }
    return String(ts);
  }

  function renderIgnored(items){
    const arr = items || [];
    if(ignBtn) ignBtn.textContent = '已忽略（' + arr.length + '）';
    if(!ignBox) return;
    if(!arr.length){
      ignBox.innerHTML = '<div style="font-size:11.5px;color:var(--muted)">暂无已忽略的条目</div>';
      return;
    }
    ignBox.innerHTML = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
      + '<b style="font-size:11.5px">已忽略列表（' + arr.length + ' 条）</b>'
      + '<span style="flex:1"></span>'
      + '<button class="btn" data-ign-act="clear" style="font-size:11px;padding:2px 7px">全部清空</button>'
      + '</div>'
      + arr.map(function(it){
          const subsTxt = Array.isArray(it.subs) ? it.subs.join(', ') : (it.subs || it.sub || '');
          const refTxt = it.group || it.ref_dir || '';
          const tsTxt = fmtTs(it.ts);
          return '<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-top:1px solid var(--line);font-size:11px">'
            + '<span style="font-family:ui-monospace,Consolas,monospace">' + esc(subsTxt || '-') + '</span>'
            + '<span style="color:var(--muted)">引用方：' + esc(refTxt || '-') + '</span>'
            + (tsTxt ? '<span style="color:var(--muted)">' + esc(tsTxt) + '</span>' : '')
            + '<span style="flex:1"></span>'
            + '<button class="btn" data-ign-act="remove" data-key="' + esc(it.key || '') + '" style="font-size:11px;padding:2px 7px">恢复</button>'
            + '</div>';
        }).join('');
  }

  async function loadIgnored(){
    try{
      const r = await post('/api/replace_ignore', {act:'list'});
      if(r && r.ok !== false) renderIgnored(r.items || []);
    }catch(e){}
  }

  async function act(actName, subs, ref, group, file, from, files, dirs){
    const subList = (subs||'').split(',').filter(Boolean);
    let busyOn = false;
    const withBusy = function(label){
      if(typeof startLoading === 'function'){
        busyOn = true;
        startLoading(label);
      }
    };
    const endBusy = function(msg, isErr){
      if(busyOn && typeof stopLoading === 'function'){
        busyOn = false;
        stopLoading(msg, isErr);
      }
    };
    try{
      if(actName === 'drop' || actName === 'drop-all'){
        setStatus('正在撤销 replace…');
        if(actName === 'drop-all') withBusy('正在批量撤销 replace…');
        const r = await post('/api/replace_fix_all', {kind:'drop_replace', subs: actName==='drop' ? subList : null});
        endBusy(r.msg || '完成', r.ok === false);
        setStatus(r.msg || (r.ok === false ? '失败' : '完成'));
        const bad = (r.done||[]).filter(function(d){ return !d.ok; });
        if(bad.length) setStatus((r.msg||'') + '　' + bad.map(function(d){ return d.sub+'：'+d.msg; }).join('；'));
        if(r.ok && typeof loadData === 'function') await loadData();
      }else if(actName === 'adopt' || actName === 'adopt-all'){
        if(actName === 'adopt'){
          const fromName = from || '父层';
          const fileCount = files !== '' && files != null ? Number(files) : 0;
          if(!confirm('接管会复制 ' + fromName + ' 的全部 ' + ref + '（共 ' + fileCount + ' 个文件）到当前 mod 并写入 replace_path，确认吗？')) return;
        }else{
          const dirCount = dirs !== '' && dirs != null ? Number(dirs) : 0;
          const fileCount = files !== '' && files != null ? Number(files) : 0;
          if(!confirm('接管会复制全部 ' + dirCount + ' 个可接管目录（共 ' + fileCount + ' 个文件）到当前 mod 并写入 replace_path，确认吗？')) return;
        }
        setStatus('正在扫描并接管目录…');
        withBusy(actName === 'adopt' ? ('正在接管 ' + ref + '…') : '正在批量接管目录…');
        const r = await post('/api/replace_fix_all', {kind:'adopt_ref_dir',
          subs: actName==='adopt' ? [ref] : null, force:true});
        endBusy(r.msg || '完成', r.ok === false);
        setStatus((r.msg||'') + '　引用仍需自行修改，或点「忽略」');
        const bad = (r.done||[]).filter(function(d){ return !d.ok; });
        if(bad.length) setStatus((r.msg||'') + '　' + bad.map(function(d){ return d.sub+'：'+d.msg; }).join('；'));
        if(r.ok && typeof loadData === 'function') await loadData();
      }else if(actName === 'adopt-file'){
        if(!file){ setStatus('缺少文件路径'); return; }
        if(!confirm('仅复制单文件 ' + file + ' 到当前 mod（不写 replace_path），确认吗？')) return;
        setStatus('正在接管文件…');
        const r = await post('/api/replace_fix_all', {kind:'adopt_file', subs:[file]});
        setStatus(r.msg || (r.ok === false ? '失败' : '完成'));
        const bad = (r.done||[]).filter(function(d){ return !d.ok; });
        if(bad.length) setStatus((r.msg||'') + '　' + bad.map(function(d){ return d.sub+'：'+d.msg; }).join('；'));
      }else if(actName === 'ignore'){
        setStatus('已忽略…');
        const r = await post('/api/replace_ignore', {subs: subList, ref_dir: ref, group: group});
        setStatus(r.msg || '完成');
      }
    }catch(e){
      endBusy('请求失败', true);
      setStatus('请求失败：' + e);
      return;
    }finally{
      endBusy();
    }
    await run();
    await loadIgnored();
  }

  if(bar){
    bar.addEventListener('click', function(e){
      const b = e.target.closest('button[data-act]');
      if(!b) return;
      act(b.dataset.act, b.dataset.subs || '', b.dataset.ref || '', b.dataset.group || '',
          b.dataset.file || '', b.dataset.from || '', b.dataset.files || '', b.dataset.dirs || '');
    });
  }
  list.addEventListener('click', function(e){
    const b = e.target.closest('button[data-act]');
    if(!b) return;
    act(b.dataset.act, b.dataset.subs || '', b.dataset.ref || '', b.dataset.group || '',
        b.dataset.file || '', b.dataset.from || '', b.dataset.files || '', b.dataset.dirs || '');
  });

  if(ignBtn && ignBox){
    ignBtn.onclick = function(){
      const show = ignBox.style.display === 'none' || !ignBox.style.display;
      ignBox.style.display = show ? 'block' : 'none';
      if(show) loadIgnored();
    };
    ignBox.addEventListener('click', async function(e){
      const b = e.target.closest('button[data-ign-act]');
      if(!b) return;
      const ia = b.dataset.ignAct;
      try{
        if(ia === 'remove'){
          const r = await post('/api/replace_ignore', {act:'remove', key: b.dataset.key || ''});
          setStatus(r.msg || '已恢复');
        }else if(ia === 'clear'){
          const r = await post('/api/replace_ignore', {act:'clear'});
          setStatus(r.msg || '已清空忽略表');
        }
      }catch(err){
        setStatus('请求失败：' + err);
        return;
      }
      await loadIgnored();
      await run();
    });
  }

  const fullScope = document.getElementById('diagFullScope');

  async function run(){
    const useAll = !!(fullScope && fullScope.checked);
    cnt.textContent = useAll ? '全链扫描中（含地图与父层，较慢）…' : '扫描当前 mod 中…';
    try{
      const r = await post('/api/diagnose', {scope: useAll ? 'all' : 'current'});
      if(r.ok === false){ cnt.textContent = r.msg || '失败'; render([]); renderBar([]); await loadIgnored(); return; }
      const items = r.findings || [];
      const bad = items.filter(function(x){ return x.severity === 'error'; }).length;
      const warn = items.filter(function(x){ return x.severity === 'warning'; }).length;
      const secTxt = (r.elapsed_ms != null) ? (' · ' + (r.elapsed_ms / 1000).toFixed(2) + 's') : '';
      cnt.textContent = (items.length
        ? (items.length + ' 项（严重 ' + bad + ' / 警告 ' + warn + '）')
        : '没有发现问题') + secTxt;
      renderBar(items);
      render(items);
    }catch(e){
      cnt.textContent = '请求失败';
    }
    await loadIgnored();
  }

  function openDiagPanel(){ panel.style.display = 'block'; run(); }
  window.openDiag = openDiagPanel;
  entry.onclick = openDiagPanel;
  const bundleBtn = document.getElementById('diagBundleBtn');
  if(bundleBtn){
    bundleBtn.onclick = function(){
      if(typeof window.downloadSupportBundle === 'function') window.downloadSupportBundle();
    };
  }
  document.getElementById('diagClose').onclick = function(){ panel.style.display = 'none'; };
  document.getElementById('diagRun').onclick = run;
})();
