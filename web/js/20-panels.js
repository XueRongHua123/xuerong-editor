// 20-panels：弹窗开合（P4）
// 本地化检查 / 日志 / 备份 / 卸载 / 文件夹选择 / 编辑面板索引条 / 诊断面板。

async function openLocCheck(){
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

async function openFolderPicker(){
  document.getElementById('folderPick').classList.add('show');
  document.getElementById('fpSel').textContent = '未选择文件夹';
  fpSelPath = '';
  await fsGo(fpDir);
}

async function fsGo(p){
  try {
    const r = await fetch('/api/fs?path=' + encodeURIComponent(p || ''));
    const j = await r.json();
    fpDir = j.path || '';
    fpParent = j.parent || '';
    document.getElementById('fpPath').value = fpDir;
    document.getElementById('fpSel').textContent = fpDir || '选择盘符或输入路径';
    renderFs(j);
  } catch(e){ status('读取目录失败', true); }
}

function renderFs(j){
  const list = document.getElementById('fpList');
  list.innerHTML = '';
  const add = (name, path, parent, has)=>{
    const d = document.createElement('div');
    d.className = 'fp-row';
    d.dataset.path = path;
    d.innerHTML = '<span>' + (parent ? '⬆ 上级目录' : '📁 ' + escapeHtml(name)) + '</span>' +
                  (has ? '<span class="badge">mod</span>' : '');
    d.onclick = ()=>fsGo(path);
    list.appendChild(d);
  };
  if(j.parent) add('..', j.parent, true, false);
  (j.dirs || []).forEach(x=>add(x.name, x.path, false, x.has_mod));
  if(j.error) list.innerHTML = '<div class="fp-row">' + escapeHtml(j.error) + '</div>';
}

async function chooseFolder(){
  const p = fpDir;
  if(!p){ status('先选一个文件夹'); return; }
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

  const SEV = { error:['#e05','严重'], warning:['#e90','警告'], info:['#39c','提示'] };

  function esc(t){
    return String(t==null?'':t).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  }

  // 后端 fix.options 里有哪几个就渲染哪几个，名字只在这里翻译
  const OPT_LABEL = { drop_replace:'撤销 replace', adopt_ref_dir:'接管该目录', ignore:'忽略' };
  const OPT_ACT   = { drop_replace:'drop', adopt_ref_dir:'adopt', ignore:'ignore' };

  function fixButtons(f){
    const fx = f.fix;
    if(!fx || !fx.options || !fx.options.length) return '';
    const subs = (fx.subs && fx.subs.length ? fx.subs : [fx.sub]).filter(Boolean).join(',');
    return '<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;align-items:center">'
      + fx.options.map(function(o){
          const act = OPT_ACT[o] || o;
          return '<button class="btn" style="font-size:11px;padding:2px 7px"'
            + ' data-act="'+act+'" data-subs="'+esc(subs)+'" data-ref="'+esc(fx.ref_dir||'')+'"'
            + ' data-group="'+esc(fx.group||'')+'">'
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
    const adoptable = dg.filter(function(x){
      return ((x.fix||{}).options||[]).indexOf('adopt_ref_dir') >= 0; }).length;
    bar.innerHTML = '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;'
      + 'background:color-mix(in srgb,#e05577 10%,var(--panel2));border:1px solid color-mix(in srgb,#e05577 35%,var(--line));'
      + 'padding:7px 9px;border-radius:5px;font-size:12px">'
      + '<span>检测到 <b>'+dg.length+'</b> 个目录引用了已被 replace 替换掉的内容</span>'
      + '<span style="flex:1"></span>'
      + '<button class="btn" data-act="drop-all" style="font-size:11px;padding:2px 7px">全部撤销 replace</button>'
      + (adoptable ? '<button class="btn" data-act="adopt-all" style="font-size:11px;padding:2px 7px">全部接管（'+adoptable+' 个）</button>' : '')
      + '</div>'
      + msgHtml();
  }

  async function post(url, payload){
    const r = await (await fetch(url, {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload||{})})).json();
    return r;
  }

  async function act(actName, subs, ref, group){
    const subList = (subs||'').split(',').filter(Boolean);
    try{
      if(actName === 'drop' || actName === 'drop-all'){
        setStatus('正在撤销 replace…');
        const r = await post('/api/replace_fix_all', {kind:'drop_replace', subs: actName==='drop' ? subList : null});
        setStatus(r.msg || (r.ok === false ? '失败' : '完成'));
        const bad = (r.done||[]).filter(function(d){ return !d.ok; });
        if(bad.length) setStatus((r.msg||'') + '　' + bad.map(function(d){ return d.sub+'：'+d.msg; }).join('；'));
      }else if(actName === 'adopt' || actName === 'adopt-all'){
        if(!confirm('接管会把引用方目录整个复制进本 mod，并写入 replace_path。\n文件多时会有几百个，确定继续？')) return;
        setStatus('正在接管…');
        const r = await post('/api/replace_fix_all', {kind:'adopt_ref_dir',
          subs: actName==='adopt' ? [ref] : null, force:true});
        setStatus((r.msg||'') + '　引用仍需自行修改，或点「忽略」');
        const bad = (r.done||[]).filter(function(d){ return !d.ok; });
        if(bad.length) setStatus((r.msg||'') + '　' + bad.map(function(d){ return d.sub+'：'+d.msg; }).join('；'));
      }else if(actName === 'ignore'){
        setStatus('已忽略…');
        const r = await post('/api/replace_ignore', {subs: subList, ref_dir: ref, group: group});
        setStatus(r.msg || '完成');
      }
    }catch(e){
      setStatus('请求失败：' + e);
      return;
    }
    await run();
  }

  if(bar){
    bar.addEventListener('click', function(e){
      const b = e.target.closest('button[data-act]');
      if(!b) return;
      act(b.dataset.act, b.dataset.subs || '', b.dataset.ref || '', b.dataset.group || '');
    });
  }
  list.addEventListener('click', function(e){
    const b = e.target.closest('button[data-act]');
    if(!b) return;
    act(b.dataset.act, b.dataset.subs || '', b.dataset.ref || '', b.dataset.group || '');
  });

  async function run(){
    cnt.textContent = '扫描中…';
    try{
      const r = await post('/api/diagnose', {});
      if(r.ok === false){ cnt.textContent = r.msg || '失败'; render([]); renderBar([]); return; }
      const items = r.findings || [];
      const bad = items.filter(function(x){ return x.severity === 'error'; }).length;
      const warn = items.filter(function(x){ return x.severity === 'warning'; }).length;
      cnt.textContent = items.length
        ? (items.length + ' 项（严重 ' + bad + ' / 警告 ' + warn + '）')
        : '没有发现问题';
      renderBar(items);
      render(items);
    }catch(e){
      cnt.textContent = '请求失败';
    }
  }

  entry.onclick = function(){ panel.style.display = 'block'; run(); };
  document.getElementById('diagClose').onclick = function(){ panel.style.display = 'none'; };
  document.getElementById('diagRun').onclick = run;
})();
