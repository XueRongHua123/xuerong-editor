// 90-boot：启动（P4）
// loadData / updateWelcome / 加载进度与来源框 / 选项 / 只此一处的「加载时立即执行」接线。
// 必须最后一个加载：这里的顶层语句会立刻跑，它调用的函数得已经在别的文件里声明好。
// 立即执行语句的相对顺序与拆分前完全一致（同一文件内按原行号顺序）。

async function loadData(){ const r = await fetch('/api/data'); DATA = await r.json(); dirty.clear(); linkSrc = null; selId = null; cpCache = null; COUNTRY_DATA = null; LINT_DATA = null; if(!DATA.trees || current >= DATA.trees.length) current = 0; renderAll(); applySavedSkin(); updateWelcome(); if(typeof renderGuide === 'function') renderGuide(); if(typeof updateSourceBox === 'function') updateSourceBox(); if(typeof bindOptions === 'function') bindOptions(); if(typeof bindStepBar === 'function'){ bindStepBar(); renderStepBar(); }
  if(typeof bindGuideToggles === 'function') bindGuideToggles(); if(typeof loadOptions === 'function') loadOptions(); const _fp=document.getElementById('ftPick'); if(_fp){ delete _fp.dataset.loaded; _fp.innerHTML=''; } const _fsvg=document.getElementById('ftSvg'); if(_fsvg) _fsvg.innerHTML=''; const _finfo=document.getElementById('ftInfo'); if(_finfo) _finfo.textContent='';
  if(typeof window.techRefreshFolders === 'function') window.techRefreshFolders();
  if(typeof window.mapRefreshTerrainTypes === 'function') window.mapRefreshTerrainTypes(); }

// 启动等待：后端 main() 现在先起端口、再在后台线程里读 mod，所以页面会先出来。
// 加载期间数据类 /api/* 一律回 503（reload_data 要原地清 12 个容器，读到半清空的会崩），
// 所以这段必须在 loadData() 之前，而且只认 ready / failed，不看 active。
const BOOT_TIMEOUT_MS = 180000;

// 其它脚本想在「mod 数据就绪后」再跑一次的登记处。boot 期间后端对数据类接口
// 统一回 503，谁要是在这个时候抢跑，拿到的是 503 载荷而不是数据——所以这里排个队。
window.XRBOOT = {
  ready: false,
  queue: [],
  after: function(fn){
    if(typeof fn !== 'function') return;
    if(window.XRBOOT.ready){ try{ fn(); }catch(e){} }
    else window.XRBOOT.queue.push(fn);
  }
};

function bootPaint(j){
  const tr = document.querySelector('.busy-track');
  if(tr){
    tr.classList.add('det');
    const i = tr.querySelector('i');
    if(i) i.style.width = Math.max(2, Math.min(100, j.pct || 0)) + '%';
  }
  const parts = [];
  if(j.stage) parts.push(j.stage);
  if(j.sub) parts.push(j.sub);
  if(parts.length) updateLoading(parts.join(' · '));
}

async function bootWait(){
  const t0 = Date.now();
  startLoading('正在读取 mod 数据…');
  // startLoading 自带一个查 /api/load_progress 的轮询，那个有 10 秒陈旧兜底
  // （超过 10 秒没更新就谎报「已结束」），启动期不能信，换成本函数的 300ms 轮询。
  clearInterval(progTimer); progTimer = null;
  for(;;){
    if(Date.now() - t0 > BOOT_TIMEOUT_MS){
      stopLoading('启动超时：后端 180 秒内没报告就绪，请看控制台输出', true);
      return;
    }
    let j = null;
    try{
      const r = await fetch('/api/boot_status', {cache: 'no-store'});
      j = await r.json();
    }catch(e){ j = null; }
    if(j && j.failed){
      stopLoading('启动失败：' + (j.error || '后端报错，请看控制台'), true);
      return;
    }
    if(j && j.ready){
      stopLoading();
      await loadData();
      // 数据到位了才放行排队的预取（地形类型、科技目录等）
      window.XRBOOT.ready = true;
      const q = window.XRBOOT.queue.splice(0);
      for(const fn of q){ try{ fn(); }catch(e){} }
      return;
    }
    if(j && j.loading) bootPaint(j);
    await new Promise(res => setTimeout(res, 300));
  }
}


function updateGameDirUI(){
  const hasData = !!DATA;
  const gOk = !!(DATA && DATA.game_ok);
  const gDir = (DATA && DATA.game_dir) || '';

  const sBar = document.getElementById('srcGameBar');
  const sTxt = document.getElementById('srcGameState');
  if(sBar && sTxt){
    sBar.classList.toggle('ok', gOk);
    sBar.classList.toggle('warn', hasData && !gOk);
    if(!hasData){
      sTxt.textContent = '游戏目录：检测中…';
      sTxt.title = '';
    }else if(gOk){
      sTxt.textContent = '游戏目录：已就绪' + (gDir ? ' · ' + gDir : '');
      sTxt.title = gDir;
    }else if(gDir){
      sTxt.textContent = '游戏目录无效（缺 hoi4.exe）：' + gDir;
      sTxt.title = gDir;
    }else{
      sTxt.textContent = '未设置游戏目录（含 hoi4.exe）';
      sTxt.title = '点击右侧「选择游戏目录」指定 HOI4 安装目录';
    }
  }

  const wBar = document.getElementById('welcGameBar');
  const wTxt = document.getElementById('welcGameState');
  if(wBar && wTxt){
    wBar.classList.toggle('ok', gOk);
    wBar.classList.toggle('warn', hasData && !gOk);
    if(!hasData){
      wTxt.textContent = '游戏目录：检测中…';
      wTxt.title = '';
    }else if(gOk){
      wTxt.textContent = '✓ 游戏目录已就绪：' + (gDir || '已检测到 hoi4.exe');
      wTxt.title = gDir;
    }else if(gDir){
      wTxt.textContent = '⚠ 当前游戏目录无效（未含 hoi4.exe）：' + gDir;
      wTxt.title = gDir;
    }else{
      wTxt.textContent = '⚠ 未检测到游戏目录（含 hoi4.exe），原版参考与进游戏检查需先设置';
      wTxt.title = '';
    }
  }
}

function updateWelcome(){
  updateGameDirUI();
  const w = document.getElementById('welcome'); if(!w) return;
  const empty = !(DATA && DATA.roots && DATA.roots.length);
  if(empty && !sessionStorage.getItem('welcomeDismissed') && !sessionStorage.getItem('updShown')) w.classList.add('show');
  else w.classList.remove('show');
}

async function doUndo(redo){
  const r = await fetch('/api/' + (redo ? 'redo' : 'undo'), {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok) await loadData();
}


function startLoading(text){
  loadStartedAt = Date.now();
  const bar = document.getElementById('loadBar');
  if(bar) bar.classList.add('show');
  aiBubbleBusy(true);
  const st = document.getElementById('srcState');
  if(st){
    st.classList.add('busy');
    st.innerHTML = '<span class="spin"></span>' + escapeHtml(text || '加载中…') + ' <b id="loadSec">0.0s</b>';
  }
  // 中央遮罩：延迟 400ms 出现，短任务不闪一下
  clearTimeout(busyTimer);
  busyTimer = setTimeout(()=>{
    const mask = document.getElementById('busyMask');
    const tt = document.getElementById('busyTitle');
    const sub = document.getElementById('busySub');
    const hint = document.getElementById('busyHint');
    if(tt) tt.textContent = text || '正在加载…';
    if(sub) sub.textContent = '';
    if(hint) hint.textContent = '首次加载会比较慢，之后有缓存';
    if(mask) mask.classList.add('show');
  }, 400);
  clearInterval(loadTimer);
  loadTimer = setInterval(()=>{
    const s = ((Date.now() - loadStartedAt) / 1000).toFixed(1) + 's';
    const el = document.getElementById('loadSec');
    if(el) el.textContent = s;
    const bs = document.getElementById('busySec');
    if(bs) bs.textContent = s;
  }, 100);
  resetProgressBar();
  clearInterval(progTimer);
  progTimer = setInterval(pollProgress, 250);
}


// 进度条回到不定态（扫描动画）
function resetProgressBar(){
  const tr = document.querySelector('.busy-track');
  if(!tr) return;
  tr.classList.remove('det');
  const i = tr.querySelector('i');
  if(i) i.style.width = '';
}


// 后端 load_mod 每完成一段会更新 LOAD_PROGRESS，这里轮询把它映射成确定进度
async function pollProgress(){
  try{
    const r = await fetch('/api/load_progress', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const j = await r.json();
    if(!j || !j.active) return;
    const tr = document.querySelector('.busy-track');
    if(tr){
      tr.classList.add('det');
      const i = tr.querySelector('i');
      if(i) i.style.width = Math.max(2, j.pct) + '%';
    }
    const parts = [];
    if(j.stage) parts.push(j.stage);
    if(j.sub) parts.push(j.sub);
    if(parts.length) updateLoading(parts.join(' · '));
  }catch(e){}
}


function updateLoading(text){
  const st = document.getElementById('srcState');
  const sub = document.getElementById('busySub');
  const sec = ((Date.now() - loadStartedAt) / 1000).toFixed(1) + 's';
  if(sub) sub.textContent = text || '';
  if(!st) return;
  // 这里的 <b> 必须带 id="loadSec"，否则 startLoading 起的计时器每 100ms 找不到目标，
  // 秒数会永远停在 0.0s。
  st.innerHTML = '<span class="spin"></span>' + escapeHtml(text) + ' <b id="loadSec">' + sec + '</b>';
}


function stopLoading(msg, isErr){
  aiBubbleBusy(false);
  clearInterval(loadTimer); loadTimer = null;
  clearTimeout(busyTimer); busyTimer = null;
  clearInterval(progTimer); progTimer = null;
  resetProgressBar();
  const mask = document.getElementById('busyMask');
  if(mask) mask.classList.remove('show');
  const bar = document.getElementById('loadBar');
  if(bar) bar.classList.remove('show');
  const st = document.getElementById('srcState');
  if(st){
    st.classList.remove('busy');
    st.textContent = msg || '';
    if(isErr) st.style.color = 'var(--warn)';
    else st.style.color = '';
  }
  updateSourceBox();
}


function srcShortName(l){
  if(l.reason === 'game') return '原版';
  const n = l.name || l.path || '';
  return n.length > 18 ? n.slice(0, 17) + '…' : n;
}


function updateSourceBox(){
  updateGameDirUI();
  const roots = (DATA && DATA.roots) || [];
  const layers = (DATA && DATA.layers) || [];
  const badge = document.getElementById('srcBadge');
  if(badge) badge.textContent = String(layers.length || roots.length);

  const vb = document.getElementById('vanillaBtn');
  const gameLayer = layers.find(l => l.reason === 'game');
  if(vb){
    vb.innerHTML = gameLayer
      ? '<b>🚫 卸载原版参考</b><i>当前已加载（只读）</i>'
      : '<b>📖 加载原版参考</b><i>只读，可卸载</i>';
  }

  const st = document.getElementById('srcState');
  if(st && !loadTimer){
    if(!roots.length){
      st.textContent = '还没有加载 mod；先「添加 mod」或加载原版参考';
    } else {
      let txt = roots.map(r => (r.name || r.path) + (r.readonly ? '（原版·只读）' : '')).join(' ＋ ') + ' 已加载';
      // 只挂了一个非原版 mod，且树全来自别处：它是个空壳
      if(roots.length === 1 && !roots[0].readonly){
        const arr = (DATA && DATA.trees) || [];
        const mine = arr.filter(t => t.source === roots[0].name);
        if(arr.length && !mine.length){
          txt += ' · 里面还没有自己的内容，看到的是原版';
        }
      }
      st.textContent = txt;
      const hint = (DATA && DATA.deps_hint) || '';
      if(hint){
        st.innerHTML = escapeHtml(txt) +
          '<span class="src-auto" style="color:#c98f5a">⚠ ' + escapeHtml(hint) + '</span>';
      }
    }
  }

  // 加载链：每层都列，标「为什么在这」
  const chain = document.getElementById('srcChain');
  if(chain){
    if(!layers.length){
      chain.innerHTML = '';
    } else {
      const shadow = (DATA && DATA.layer_shadow) || {};
      chain.innerHTML = layers.map(function(l){
        const reason = l.reason || 'auto';
        let tag = SRC_REASON[reason] || '';
        if(reason === 'game') tag = '只读';
        else if(l.readonly) tag = tag + '·只读';
        // 只有「手动」的层能卸；自动带进来的卸了会断链
        const x = (reason === 'manual')
          ? '<button class="src-x" data-src-unload="' + escapeHtml(l.path) +
            '" title="从本次会话卸载（不改磁盘）">×</button>'
          : '';
        // 这一层压住了下面几层多少个同名文件（同名文件后加载的赢）
        const sw = shadow[l.path] || [];
        const warn = sw.length
          ? '<span class="src-warn" title="这一层盖住了下面 ' + sw.length + ' 个同名文件：\n' +
            escapeHtml(sw.slice(0, 12).join('\n')) +
            (sw.length > 12 ? '\n…' : '') + '">⚠ ' + sw.length + '</span>'
          : '';
        return '<div class="src-row src-' + reason + '" data-src-idx="' + layers.indexOf(l) + '" style="cursor:pointer" title="' + escapeHtml(l.path) + '（点击打开叠加链详情）">' +
               '<span class="src-dot"></span>' +
               '<span class="src-name">' + escapeHtml(l.name || l.path) + '</span>' +
               warn +
               '<span class="src-tag">' + escapeHtml(tag) + '</span>' + x + '</div>';
      }).join('');
      chain.querySelectorAll('[data-src-idx]').forEach(function(row){
        row.onclick = function(){
          if(typeof openLayerChain === 'function') openLayerChain({layer: row.dataset.srcIdx});
        };
      });
      chain.querySelectorAll('[data-src-unload]').forEach(function(b){
        b.onclick = function(ev){
          ev.stopPropagation();
          if(typeof unloadRoot === 'function') unloadRoot(b.dataset.srcUnload);
          else if(typeof unloadMod === 'function') unloadMod();
        };
      });
    }
  }

  // 覆盖关系：最上面的盖最下面的
  const cov = document.getElementById('srcCover');
  if(cov){
    if(layers.length < 2){
      cov.innerHTML = '';
    } else {
      const seq = layers.slice().reverse().map(srcShortName);
      cov.innerHTML = '覆盖关系：<b>' + escapeHtml(seq.join(' > ')) + '</b>';
    }
  }
}


/* ---------- v1.24.0 两个独立开关 ---------- */
async function loadOptions(){
  const dep = document.getElementById('optDep');
  const lch = document.getElementById('optLaunch');
  if(!dep && !lch) return;
  try{
    const r = await fetch('/api/options', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const j = await r.json();
    if(dep) dep.checked = !!j.follow_deps;
    if(lch) lch.checked = !!j.follow_launcher;
  }catch(e){}
}


function bindOptions(){
  const hint = function(msg){
    const el = document.getElementById('optHint');
    if(!el) return;
    el.textContent = msg;
    setTimeout(function(){ if(el.textContent === msg) el.textContent = ''; }, 7000);
  };
  function bindOne(el, key, label){
    if(!el || el.__bound) return;
    el.__bound = true;
    el.onchange = async function(){
      const on = this.checked;
      try{
        await fetch('/api/options', {method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({[key]: on})});
      }catch(e){}
      hint((on ? '已开启「' : '已关闭「') + label + '」 · 重新加载 mod 后生效');
    };
  }
  bindOne(document.getElementById('optDep'), 'follow_deps', '带上依赖的 mod');
  bindOne(document.getElementById('optLaunch'), 'follow_launcher', '同时读启动器已启用的 mod');
}


async function loadVanillaWithProgress(){
  const game = ((DATA && DATA.roots) || []).find(r=>r.readonly);
  if(game){
    if(!confirm('从编辑器卸载原版参考？\n只影响当前会话，不会删除磁盘文件。')) return;
    startLoading('正在卸载原版参考…');
    try{
      const r = await (await fetch('/api/unload_mod', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({root: game.path})})).json();
      await loadData();
      stopLoading(r.msg || '已卸载原版参考', !r.ok);
    }catch(e){ stopLoading('卸载失败：' + e.message, true); }
    return;
  }
  startLoading('正在加载原版参考…（首次会扫描图标，可能久一点）');
  try{
    const r = await (await fetch('/api/load_vanilla', {method:'POST', headers:{'Content-Type':'application/json'},
      body:'{}'})).json();
    updateLoading('读取国策树、科技、州与本地化…');
    await loadData();
    stopLoading(r.msg || '已加载原版参考', !r.ok);
  }catch(e){ stopLoading('加载失败：' + e.message, true); }
}

async function loadVanilla(){
  const r = await fetch('/api/load_vanilla', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok) await loadData();
}

async function copyTree(){
  const t = curTree();
  if(!t){ status('先选择一棵树'); return; }
  const id = prompt('新树 ID（会复制到你的模组）：', t.id + '_copy');
  if(!id) return;
  const r = await fetch('/api/copy_tree', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({id: t.id, new_id: id})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok) await loadData();
}

async function copyItem(kind, obj, defId){
  if(!obj){ status('先选择内容'); return; }
  const id = prompt('新 ID（会复制到你的模组）：', defId || (obj.id + '_copy'));
  if(!id) return;
  const r = await fetch('/api/copy_item', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({kind, id: obj.id, new_id: id})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok) await loadData();
}

async function pickMod(){
  // 先只选目录（系统对话框，不加遮罩），拿到路径后再走统一的加载流程
  const r = await fetch('/api/pick_mod', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
  const j = await r.json();
  if(!j.ok){ status(j.msg || '未选择目录', true); return; }
  await loadModByPath(j.path);
}

async function loadModByPath(p){
  if(!p) return;
  // v1.24.0：有未保存改动时先问一句，避免切个 mod 就把改动丢了
  if(typeof dirty !== 'undefined' && dirty && dirty.size){
    if(!confirm('还有 ' + dirty.size + ' 处改动没保存。\n现在加载别的 mod 会丢掉它们，继续吗？')) return;
  }
  startLoading('正在加载 mod…');
  try{
    const r = await fetch('/api/load_mod', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({path: p})});
    const j = await r.json();
    if(j.ok){
      updateLoading('读取国策树、科技、州与本地化…');
      await loadData();
      stopLoading(j.msg || '已加载');
    } else {
      stopLoading(j.msg || '加载失败', true);
      showError(j);
    }
    status(j.msg || '', !j.ok);
  }catch(e){ stopLoading('加载失败：' + e.message, true); }
}

document.getElementById('fit').onclick = ()=>{ fitView(); updateZoomLabel(); };

document.getElementById('zoomIn').onclick = ()=>applyZoomFactor(1.2);

document.getElementById('zoomOut').onclick = ()=>applyZoomFactor(1 / 1.2);

document.getElementById('zoomAnchorBtn').onclick = ()=>{
  zoomAnchor = zoomAnchor === 'mouse' ? 'screen' : 'mouse';
  try { localStorage.setItem('fe_zoom_anchor', zoomAnchor); } catch(e){}
  updateZoomLabel();
  status(zoomAnchor === 'mouse' ? '缩放锚点：鼠标位置（滚轮指着哪就放大哪）' : '缩放锚点：画布中心（视图整体缩放）');
};

document.getElementById('editMode').onclick = ()=>{
  editMode = !editMode;
  document.getElementById('editMode').classList.toggle('on', editMode);
  status(editMode ? '编辑模式已开启：拖动节点改位置' : '编辑模式已关闭');
};

function setLink(mode){
  linkMode = (linkMode === mode) ? null : mode;
  linkSrc = null;
  document.getElementById('linkPre').classList.toggle('on', linkMode==='prereq');
  document.getElementById('linkMut').classList.toggle('on', linkMode==='mutex');
  renderStats();
  status(linkMode ? ('连线模式：点两个节点（' + (linkMode==='prereq'?'前置':'互斥') + '）') : '已退出连线模式');
}

document.getElementById('linkPre').onclick = ()=>setLink('prereq');

document.getElementById('linkMut').onclick = ()=>setLink('mutex');

document.getElementById('addBtn').onclick = addNode;

document.getElementById('copyTreeBtn').onclick = copyTree;

document.getElementById('addTreeBtn').onclick = addTree;

document.getElementById('ideaCopy').onclick = ()=>copyItem('idea', ideaSel);

document.getElementById('equipCopy').onclick = ()=>copyItem('equip', equipSel);

document.getElementById('techCopy').onclick = ()=>copyItem('tech', techSel);

document.getElementById('eventCopy').onclick = ()=>copyItem('event', eventSel);

document.getElementById('ideaRef').onclick = ()=>openUsages(ideaSel && ideaSel.id);

document.getElementById('equipRef').onclick = ()=>openUsages(equipSel && equipSel.id);

document.getElementById('equipDesigner').onclick = openDesigner;

document.getElementById('designerClose').onclick = ()=>{ document.getElementById('designerModal').classList.remove('show'); };

document.getElementById('techRef').onclick = ()=>openUsages(techSel && techSel.id);

document.getElementById('eventRef').onclick = ()=>openUsages(eventSel && eventSel.id);

document.getElementById('usagesClose').onclick = ()=>{ document.getElementById('usagesModal').classList.remove('show'); };

document.getElementById('delTreeBtn').onclick = delTree;

document.getElementById('saveAll').onclick = saveAll;

document.getElementById('exportBtn').onclick = openPublishModal;

document.getElementById('showMutex').onchange = renderTree;

document.getElementById('langSel').value = LANG;

document.getElementById('langSel').onchange = (e)=>{
  try { localStorage.setItem('fe_lang', e.target.value); } catch(err){}
  const u = new URL(location.href);
  u.searchParams.set('lang', e.target.value);
  location.href = u.toString();
};

document.getElementById('helpBtn').onclick = ()=>{ window.open('/help?lang=' + LANG, '_blank'); };

try { themeSel.value = localStorage.getItem('fe_theme') || 'auto'; } catch(e){ themeSel.value = 'auto'; }

themeSel.onchange = ()=>{
  applyTheme(themeSel.value);
  try { localStorage.setItem('fe_theme', themeSel.value); } catch(e){}
};

window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', ()=>{
  if((localStorage.getItem('fe_theme') || 'auto') === 'auto') applyTheme('auto');
});

try { fsSel.value = localStorage.getItem('fe_size') || 'normal'; } catch(e){ fsSel.value = 'normal'; }

fsSel.onchange = ()=>{
  applySize(fsSel.value);
  try { localStorage.setItem('fe_size', fsSel.value); } catch(e){}
};

(function(){
  document.querySelectorAll('img').forEach(i=>{ i.draggable = false; });
  try{ if(window.mapBindUpdate) window.mapBindUpdate(); }catch(e){}
  const bubble = document.getElementById('aiBubble');
  let drag = null;
  try {
    const saved = localStorage.getItem('fe_bubble_pos');
    if(saved){
      const p = JSON.parse(saved);
      bubble.style.left = p.x + 'px';
      bubble.style.top = p.y + 'px';
      bubble.style.right = 'auto';
      bubble.style.bottom = 'auto';
    }
  } catch(e){}
  bubble.addEventListener('contextmenu', e=>{
    e.preventDefault();
    closeAiMenu();
    toggleRadial();
  });
  bubble.addEventListener('pointerdown', e=>{
    e.preventDefault();
    const r = bubble.getBoundingClientRect();
    drag = {sx: e.clientX, sy: e.clientY, ox: r.left, oy: r.top, moved: false};
    bubble.classList.add('dragging');
    try { bubble.setPointerCapture(e.pointerId); } catch(err){}
  });
  bubble.addEventListener('pointermove', e=>{
    if(!drag) return;
    const dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
    if(Math.abs(dx) > 3 || Math.abs(dy) > 3) drag.moved = true;
    if(!drag.moved) return;
    const size = bubble.offsetWidth || 64;
    let x = drag.ox + dx, y = drag.oy + dy;
    x = Math.max(4, Math.min(window.innerWidth - size - 4, x));
    y = Math.max(4, Math.min(window.innerHeight - size - 4, y));
    bubble.style.left = x + 'px';
    bubble.style.top = y + 'px';
    bubble.style.right = 'auto';
    bubble.style.bottom = 'auto';
  });
  bubble.addEventListener('pointerup', e=>{
    if(!drag) return;
    const dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
    if(!drag.moved && (Math.abs(dx) > 5 || Math.abs(dy) > 5)){
      const size = bubble.offsetWidth || 64;
      let x = Math.max(4, Math.min(window.innerWidth - size - 4, drag.ox + dx));
      let y = Math.max(4, Math.min(window.innerHeight - size - 4, drag.oy + dy));
      bubble.style.left = x + 'px';
      bubble.style.top = y + 'px';
      bubble.style.right = 'auto';
      bubble.style.bottom = 'auto';
      drag.moved = true;
    }
    const moved = drag.moved;
    drag = null;
    bubble.classList.remove('dragging');
    if(moved){
      try {
        const r = bubble.getBoundingClientRect();
        localStorage.setItem('fe_bubble_pos', JSON.stringify({x: r.left, y: r.top}));
      } catch(err){}
    } else {
      toggleRadial();
    }
  });
})();

document.getElementById('aiSettingsBtn').onclick = ()=>{
  const s = document.getElementById('aiSettings');
  s.style.display = s.style.display === 'none' ? '' : 'none';
};

document.getElementById('aiClose').onclick = closeAI;

document.getElementById('aiSave').onclick = saveAIConfig;

document.getElementById('aiSend').onclick = sendAI;

document.getElementById('aiCopy').onclick = async ()=>{
  const t = document.getElementById('aiOut').textContent;
  if(!t || !t.trim()){ status('还没有可复制的结果'); return; }
  try { await navigator.clipboard.writeText(t); status('已复制到剪贴板'); }
  catch(e){ status('复制失败，请手动选择文本'); }
};

document.getElementById('aiInsert').onclick = ()=>{
  const tgt = document.getElementById('aiTarget').value;
  const txt = (document.getElementById('aiOut').textContent || '').trim();
  if(!tgt){ status('先选择要插入的位置'); return; }
  if(!txt){ status('还没有 AI 结果'); return; }
  if(tgt === 'edEffect'){ addFxLine(txt); status('已插入到当前国策效果'); return; }
  const el = document.getElementById(tgt);
  if(!el){ status('对应的编辑器没有打开'); return; }
  el.value = txt;
  status('已插入到编辑器原文');
};

document.getElementById('ideaEntry').onclick = ()=>openIdea();

document.getElementById('ideaClose').onclick = ()=>{ document.getElementById('ideaModal').style.display = 'none'; };

document.getElementById('ideaSearch').oninput = (e)=>renderIdeaList(e.target.value.trim().toLowerCase());

document.getElementById('ideaSave').onclick = saveIdea;

document.getElementById('ideaSaveTop').onclick = saveIdea;

document.getElementById('ideaModAdd').onclick = addIdeaMod;

document.getElementById('ideaModVal').addEventListener('keydown', e=>{
  if(e.key === 'Enter'){ e.preventDefault(); addIdeaMod(); }
});

document.getElementById('ideaAdd').onclick = addIdea;

document.getElementById('ideaDelete').onclick = deleteIdeaSel;

const _ideaScopeAll = document.getElementById('ideaScopeAll');
if(_ideaScopeAll) _ideaScopeAll.onclick = ()=>setIdeaScope('all');

const _ideaScopeMod = document.getElementById('ideaScopeMod');
if(_ideaScopeMod) _ideaScopeMod.onclick = ()=>setIdeaScope('mod');

const _ideaTabBasic = document.getElementById('ideaTabBasic');
if(_ideaTabBasic) _ideaTabBasic.onclick = ()=>switchIdeaTab('basic');

const _ideaTabCond = document.getElementById('ideaTabCond');
if(_ideaTabCond) _ideaTabCond.onclick = ()=>switchIdeaTab('cond');

const _ideaTabRaw = document.getElementById('ideaTabRaw');
if(_ideaTabRaw) _ideaTabRaw.onclick = ()=>switchIdeaTab('raw');

const _ideaRawEl = document.getElementById('ideaRaw');
if(_ideaRawEl) _ideaRawEl.addEventListener('input', ()=>{ _ideaRawDirty = true; });

document.querySelectorAll('#ideaModal .idea-chip').forEach(btn=>{
  btn.onclick = ()=>addIdeaMod(btn.dataset.k || '', btn.dataset.v ?? '');
});

document.getElementById('equipEntry').onclick = openEquip;

document.getElementById('equipClose').onclick = ()=>{ document.getElementById('equipModal').style.display = 'none'; };

document.getElementById('equipSearch').addEventListener('input', e=>renderEquipList(e.target.value.trim().toLowerCase()));

document.getElementById('equipSave').onclick = saveEquip;

document.getElementById('equipSaveTop').onclick = saveEquip;

document.getElementById('techEntry').onclick = openTech;

document.getElementById('techClose').onclick = ()=>{ document.getElementById('techModal').style.display = 'none'; };

document.getElementById('techSearch').addEventListener('input', e=>{
  renderTechList(e.target.value.trim().toLowerCase());
  applyTechHighlight();
});

document.getElementById('techSave').onclick = saveTech;

document.getElementById('techSaveTop').onclick = saveTech;

document.getElementById('techAdd').onclick = addTech;

document.getElementById('techDelete').onclick = deleteTechSel;

document.getElementById('techTabEdit').onclick = ()=>switchTechTab('edit');

document.getElementById('techTabTree').onclick = ()=>switchTechTab('tree');

document.getElementById('ttFit').onclick = fitTT;

document.getElementById('ttEditToggle').onclick = ttToggleEdit;

document.getElementById('ttSavePos').onclick = ttSavePositions;

(function(){
  const svg = document.getElementById('techSvg');
  svg.addEventListener('wheel', e=>{
    e.preventDefault();
    const k0 = ttView.k, k = Math.max(0.1, Math.min(3, k0 * (e.deltaY < 0 ? 1.15 : 0.87)));
    const r = svg.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    ttView.x = mx - (mx - ttView.x) * k / k0;
    ttView.y = my - (my - ttView.y) * k / k0;
    ttView.k = k; applyTT();
  }, {passive:false});
  svg.addEventListener('mousedown', e=>{
    if(e.target.closest('.tt-node')) return;
    ttDrag = {x: e.clientX, y: e.clientY, vx: ttView.x, vy: ttView.y};
    svg.style.cursor = 'grabbing';
  });
  window.addEventListener('mousemove', e=>{
    if(!ttDrag) return;
    ttView.x = ttDrag.vx + (e.clientX - ttDrag.x);
    ttView.y = ttDrag.vy + (e.clientY - ttDrag.y);
    applyTT();
  });
  window.addEventListener('mouseup', ()=>{
    if(ttDrag){ ttDrag = null; svg.style.cursor = 'grab'; }
  });
})();

document.getElementById('eventEntry').onclick = openEvents;

document.getElementById('eventClose').onclick = ()=>{ document.getElementById('eventModal').style.display = 'none'; };

document.getElementById('eventSearch').addEventListener('input', e=>renderEventList(e.target.value.trim().toLowerCase()));

document.getElementById('eventSave').onclick = saveEvent;

document.getElementById('eventSaveTop').onclick = saveEvent;

document.getElementById('eventAdd').onclick = addEvent;

document.getElementById('eventDelete').onclick = deleteEventSel;

document.getElementById('eventAddOption').onclick = ()=>{
  const el = document.getElementById('eventRaw');
  const raw = el.value || '';
  const n = parseEventOptions(raw).length + 1;
  const key = (eventSel ? eventSel.id : 'event') + '.a' + n;
  const idx = raw.lastIndexOf('}');
  if(idx < 0) return;
  el.value = raw.slice(0, idx) + '\n\toption = {\n\t\tname = ' + key + '\n\t}\n' + raw.slice(idx);
  renderEventOptions(el.value);
};

document.getElementById('sharedAddBtn').onclick = addShared;

document.getElementById('sharedDelBtn').onclick = deleteShared;

document.getElementById('equipAdd').onclick = addEquip;

document.getElementById('equipDelete').onclick = deleteEquip;

function dismissWelcome(){
  sessionStorage.setItem('welcomeDismissed', '1');
  document.getElementById('welcome').classList.remove('show');
}

function openWelcome(){
  sessionStorage.removeItem('welcomeDismissed');
  updateGameDirUI();
  document.getElementById('welcome').classList.add('show');
}

function setFlow(k){
  localStorage.setItem('workflow', k);
  if(typeof renderGuide === 'function') renderGuide();
}

document.getElementById('wayEdit').onclick = ()=>{ setFlow('edit'); dismissWelcome(); openFolderPicker(); };

document.getElementById('wayNew').onclick = ()=>{ setFlow('new'); dismissWelcome(); openNewMod(); };

document.getElementById('wayWorld').onclick = ()=>{ setFlow('world'); dismissWelcome(); openWorldGen(); };

document.getElementById('welcomePath').onclick = loadModPath;

const _welcGameBtn = document.getElementById('welcGameBtn');
if(_welcGameBtn) _welcGameBtn.onclick = ()=>{ if(typeof openGameDirPicker === 'function') openGameDirPicker(); };

const _srcGameBtn = document.getElementById('srcGameBtn');
if(_srcGameBtn) _srcGameBtn.onclick = ()=>{ if(typeof openGameDirPicker === 'function') openGameDirPicker(); };

const _welcDiagBundle = document.getElementById('welcDiagBundle');
if(_welcDiagBundle) _welcDiagBundle.onclick = ()=>{ if(typeof downloadSupportBundle === 'function') downloadSupportBundle(); };

document.getElementById('welcomeBtn').onclick = openWelcome;

// v1.24.2：「❓ 打开引导」按钮换成侧栏两个勾选框（bindGuideToggles），openGuide 保留给别处用
document.getElementById('gbClose').onclick = ()=>{ localStorage.setItem('guideHidden', '1'); document.getElementById('guideBox').classList.remove('show'); if(typeof syncGuideToggle === 'function') syncGuideToggle(); };

// #gbBody 的 .gb-btn[data-act] 事件委托已移至 40-guide.js bindGuideActions()

document.getElementById('welcomeMore').onclick = ()=>{
  const x = document.getElementById('welcomeExtra');
  const b = document.getElementById('welcomeMore');
  const on = x.classList.toggle('show');
  b.textContent = on ? '收起说明' : '更多说明';
};

document.getElementById('welcomeClose').onclick = ()=>{ sessionStorage.setItem('welcomeDismissed', '1'); document.getElementById('welcome').classList.remove('show'); };

document.getElementById('addModBtn').onclick = openFolderPicker;

document.getElementById('unloadModBtn').onclick = unloadMod;

document.getElementById('vanillaBtn').onclick = loadVanillaWithProgress;

document.getElementById('ideaPicBtn').onclick = ()=>{ iconPickTarget = 'ideaPic'; openIconPicker(); };

document.getElementById('equipPicBtn').onclick = ()=>{ iconPickTarget = 'equipPic'; openIconPicker('equip'); };

document.getElementById('newModBtn').onclick = openNewMod;

document.getElementById('nmClose').onclick = ()=>{ document.getElementById('newMod').classList.remove('show'); };

document.getElementById('nmCancel').onclick = ()=>{ document.getElementById('newMod').classList.remove('show'); };

document.getElementById('nmOk').onclick = createNewMod;

// Esc 关掉所有模态框（都挂在各自的 show 类上）
document.addEventListener('keydown', function(e){
  if(e.key !== 'Escape') return;
  ['newMod', 'worldGen', 'folderPick'].forEach(function(id){
    const el = document.getElementById(id);
    if(el && el.classList.contains('show')) el.classList.remove('show');
  });
});

document.getElementById('wgClose').onclick = ()=>{ document.getElementById('worldGen').classList.remove('show'); };

document.getElementById('wgCancel').onclick = ()=>{ document.getElementById('worldGen').classList.remove('show'); };

document.getElementById('wgOk').onclick = doWorldCreate;

document.getElementById('treeSetBtn').onclick = openTreeSet;

document.getElementById('locCheckBtn').onclick = openLocCheck;

document.getElementById('logBtn').onclick = openLog;

document.getElementById('reportBtn').onclick = ()=>openLint();

document.getElementById('reportClose').onclick = ()=>{ document.getElementById('reportModal').classList.remove('show'); };

document.getElementById('repairAllBtn').onclick = async ()=>{
  if(!confirm('将尝试修复所有检测到的花括号不平衡文件（自动备份），继续？')) return;
  const r = await fetch('/api/repair_all', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok) openReport();
};

document.getElementById('backupBtn').onclick = openBackups;

document.getElementById('backupClose').onclick = ()=>{ document.getElementById('backupModal').classList.remove('show'); };

document.getElementById('contentBtn').onclick = ()=>openContent();

document.getElementById('contentClose').onclick = ()=>{ document.getElementById('contentModal').classList.remove('show'); };

document.getElementById('contentSearch').addEventListener('input', e=>renderContent(e.target.value.trim().toLowerCase()));

document.getElementById('locClose').onclick = ()=>{ document.getElementById('locModal').classList.remove('show'); };

document.getElementById('skinClose').onclick = ()=>{ document.getElementById('skinPick').classList.remove('show'); };

document.getElementById('skinShow').onclick = ()=>{ document.getElementById('mascotFloat').style.display = 'block'; };

document.getElementById('skinHide').onclick = ()=>{ document.getElementById('mascotFloat').style.display = 'none'; };

document.getElementById('logClose').onclick = ()=>{ document.getElementById('logModal').classList.remove('show'); };

document.getElementById('tsClose').onclick = ()=>{ document.getElementById('treeSet').classList.remove('show'); };

document.getElementById('tsOk').onclick = saveTreeSet;

document.getElementById('diffClose').onclick = ()=>{ pendingSave = null; document.getElementById('diffModal').classList.remove('show'); };

document.getElementById('diffOk').onclick = async ()=>{
  if(!pendingSave){ document.getElementById('diffModal').classList.remove('show'); return; }
  const {f, fields} = pendingSave;
  pendingSave = null;
  document.getElementById('diffModal').classList.remove('show');
  await postSave(f, fields);
  status('已保存：' + f.id);
};

document.getElementById('undoBtn').onclick = ()=>doUndo(false);

document.getElementById('redoBtn').onclick = ()=>doUndo(true);

document.getElementById('ipClose').onclick = ()=>{ document.getElementById('iconPick').classList.remove('show'); };

document.getElementById('ipSearch').addEventListener('input', e=>renderIcons(e.target.value.trim().toLowerCase()));

document.addEventListener('keydown', e=>{
  const tag = (e.target && e.target.tagName) || '';
  const inField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
  const k = (e.key || '').toLowerCase();
  if((e.ctrlKey || e.metaKey) && k === 'k'){
    e.preventDefault();
    if(document.getElementById('cmdPalette').classList.contains('show')) closeCmd(); else openCmd();
    return;
  }
  if((e.ctrlKey || e.metaKey) && k === 's'){
    e.preventDefault();
    saveAll();
    return;
  }
  if((e.ctrlKey || e.metaKey) && k === 'z'){
    e.preventDefault();
    doUndo(e.shiftKey);
    return;
  }
  if((e.ctrlKey || e.metaKey) && k === 'y'){
    e.preventDefault();
    doUndo(true);
    return;
  }
  if(inField || e.ctrlKey || e.metaKey || e.altKey) return;
  if(k === 'escape'){
    const ai = document.getElementById('aiModal');
    if(ai && ai.classList.contains('show')){ closeAI(); return; }
  }
  if(k === 'escape'){
    if(document.getElementById('keysModal').classList.contains('show')){ closeKeys(); return; }
    if(linkMode){ setLink(null); return; }
    if(document.getElementById('panel').classList.contains('show')){ selId = null; renderTree(); showPanel(); }
    return;
  }
  if(k === 'h' || (e.shiftKey && k === '?')){ e.preventDefault(); openKeys(); return; }
  if(k === 'f'){ e.preventDefault(); fitView(); return; }
  if(k === 'delete' || k === 'backspace'){
    if(editMode && selId){
      const f = curTree() && nodeById(curTree(), selId);
      if(f){ e.preventDefault(); delNode(f); }
    }
  }
});

document.getElementById('fpClose').onclick = ()=>{ document.getElementById('folderPick').classList.remove('show'); };

document.getElementById('fpOk').onclick = chooseFolder;

document.getElementById('fpUp').onclick = ()=>{ fsGo(fpParent || ''); };

document.getElementById('fpPath').addEventListener('keydown', e=>{ if(e.key === 'Enter') fsGo(e.target.value); });

search.oninput = ()=>renderSearchHits(search.value);

search.addEventListener('keydown', e=>{
  if(e.key === 'Enter'){
    e.preventDefault();
    const first = document.querySelector('#searchHits .sr-item');
    if(first) first.click();
  } else if(e.key === 'ArrowDown'){
    e.preventDefault();
    const first = document.querySelector('#searchHits .sr-item');
    if(first) first.classList.add('on');
  } else if(e.key === 'Escape'){
    search.value = ''; renderSearchHits('');
  }
});


/* ---------- v0.82 选择与拖拽防护 ---------- */
(function(){
  // 1) 图片一律不可拖拽（包括后加入 DOM 的）
  const killDrag = el=>{ if(el && el.tagName === 'IMG') el.draggable = false; };
  document.querySelectorAll('img').forEach(killDrag);
  const mo = new MutationObserver(list=>{
    list.forEach(rec=>{
      rec.addedNodes && rec.addedNodes.forEach(n=>{
        if(n.nodeType !== 1) return;
        if(n.tagName === 'IMG') killDrag(n);
        else if(n.querySelectorAll) n.querySelectorAll('img').forEach(killDrag);
      });
    });
  });
  mo.observe(document.body, {childList: true, subtree: true});

  // 2) 任何 dragstart 都拦掉：不让浏览器把选中的文本/图片拖成新页面
  document.addEventListener('dragstart', e=>{
    const t = e.target;
    if(t && (t.tagName === 'IMG' || t.closest && t.closest('#mapModal, #aiBubble, .mascot-float, svg'))){
      e.preventDefault();
      return;
    }
    // 其它元素上的拖拽也一并禁止（界面上没有需要拖放的功能）
    e.preventDefault();
  }, true);

  // 3) 右键菜单：输入框/可复制区域保留，其余拦掉
  document.addEventListener('contextmenu', e=>{
    const t = e.target;
    if(t && t.closest && t.closest('input, textarea, select, [contenteditable="true"], pre, code, #aiOut, #lintList, #scriptBody, #cpList')){
      return;
    }
    e.preventDefault();
  }, true);

  // 4) 长按选中：把 body 上的 mousedown 默认行为也限制住（拖动地图时）
  document.addEventListener('selectstart', e=>{
    const t = e.target;
    if(t && t.closest && t.closest('input, textarea, select, [contenteditable="true"], pre, code, #aiOut, #lintList, #scriptBody, #cpList')){
      return;
    }
    e.preventDefault();
  }, true);
})();

document.getElementById('stateEntry').onclick = ()=>openStates();

document.getElementById('diploEntry').onclick = ()=>openDiplo();

document.getElementById('diploClose').onclick = ()=>document.getElementById('diploModal').classList.remove('show');

document.getElementById('diploTagSearch').onchange = (ev)=>{
  const v = ((ev.target && ev.target.value) || '').trim().toUpperCase();
  if(v) loadDiplo(v);
};

document.getElementById('stateClose').onclick = closeStates;

document.getElementById('stateSearch').addEventListener('input', e=>renderStateList(e.target.value.trim().toLowerCase()));

document.getElementById('stateModal').addEventListener('click', e=>{ if(e.target.id === 'stateModal') closeStates(); });

document.getElementById('countryEntry').onclick = ()=>openCountry();

document.getElementById('lintEntry').onclick = openLint;

document.getElementById('scriptEntry').onclick = ()=>openScriptCheck(true);

document.getElementById('densitySel').addEventListener('change', e=>applyDensity(e.target.value));

initNarrowMore();

document.getElementById('mapEntry').onclick = ()=>{ openMap(); mapBindEvents(); };

// v1.23.7 左侧导航直达「编辑」面板：原来要先点地图、再点右侧的编辑 tab，三步
document.getElementById('navEditEntry').onclick = ()=>{
  openMap();
  mapBindEvents();
  setTimeout(()=>{
    const b = document.querySelector('.side-tab[data-tab="edit"]');
    if(b) b.click();
  }, 120);
};

document.getElementById('mapClose').onclick = ()=>{ document.getElementById('mapModal').classList.remove('show'); };

document.getElementById('mapSource').addEventListener('change', e=>mapSwitchSource(e.target.value));

document.getElementById('mapFit').onclick = mapFit;

document.getElementById('mapOne').onclick = ()=>{
  const wrap = document.getElementById('mapStageWrap').getBoundingClientRect();
  const cx = (wrap.width / 2 - MAP.x) / MAP.k, cy = (wrap.height / 2 - MAP.y) / MAP.k;
  mapGoto(cx, cy, 1);
  status('1:1 原始像素（' + MAP.w + '×' + MAP.h + '）');
};

document.getElementById('mapBuild').onclick = mapBuild;

document.getElementById('mapClear').onclick = mapClearCache;

document.getElementById('mapCheckBtn').onclick = mapRunCheck;

document.getElementById('mckRun').onclick = mapRunCheck;

document.getElementById('mckTabCheck').onclick = mapRunCheck;

document.getElementById('mckTabRank').onclick = mapShowRank;

document.getElementById('mckRepair').onclick = mapRepair;

document.getElementById('mckLoc').onclick = mapShowLocMissing;

document.getElementById('mckGfx').onclick = mapShowGfxMissing;

document.getElementById('mckClose').onclick = ()=>{ document.getElementById('mapCheckModal').classList.remove('show'); };


document.getElementById('mapSearch').addEventListener('keydown', e=>{ if(e.key === 'Enter') mapSearchGo(); });

['mapLProv','mapLState','mapLEdges','mapLBase','mapLPolit','mapLRegion','mapLTerrain','mapLContinent'].forEach(id=>{  const el = document.getElementById(id); if(el) el.addEventListener('change', mapApplyLayers); });

 if(mapOpEl) mapOpEl.addEventListener('input', mapApplyLayers);

document.getElementById('scriptClose').onclick = ()=>{ document.getElementById('scriptModal').classList.remove('show'); };

document.getElementById('scriptReload').onclick = ()=>openScriptCheck(true);

document.getElementById('scriptSearch').addEventListener('input', renderScriptList);

document.getElementById('scriptKind').addEventListener('change', renderScriptList);

document.getElementById('scriptSort').addEventListener('change', renderScriptList);

document.getElementById('histClose').onclick = closeHistoryEditor;

document.getElementById('histReload').onclick = loadHistoryIntoForm;

document.getElementById('histSave').onclick = saveHistory;

document.getElementById('historyModal').addEventListener('click', e=>{ if(e.target.id === 'historyModal') closeHistoryEditor(); });

document.getElementById('countryClose').onclick = closeCountry;

document.getElementById('countrySearch').addEventListener('input', e=>renderCountryList(e.target.value.trim().toLowerCase()));

document.getElementById('countryOnly').addEventListener('change', ()=>renderCountryList(document.getElementById('countrySearch').value.trim().toLowerCase()));

document.getElementById('countryModal').addEventListener('click', e=>{ if(e.target.id === 'countryModal') closeCountry(); });

document.getElementById('lintClose').onclick = closeLint;

document.getElementById('lintFilter').addEventListener('change', renderLint);

document.getElementById('lintRun').onclick = runLint;

document.getElementById('lintSyntax').onclick = ()=>openReport();

document.getElementById('lintModal').addEventListener('click', e=>{ if(e.target.id === 'lintModal') closeLint(); });

document.getElementById('layerViewBtn').onclick = ()=>openLayerChain();
document.getElementById('objDiffBtn').onclick = ()=>openLayerChain({tab:'objects'});
document.getElementById('layerClose').onclick = closeLayerChain;
document.getElementById('lcRefresh').onclick = ()=>{
  loadLayerChain({refresh:true});
  if(_lcState.tab === 'objects') loadObjectDiff({refresh:true});
};
document.getElementById('lcTabFiles').onclick = ()=>_lcSetTab('files');
document.getElementById('lcTabReplace').onclick = ()=>_lcSetTab('replace');
document.getElementById('lcTabObjects').onclick = ()=>_lcSetTab('objects');
document.getElementById('lcKind').addEventListener('change', ()=>loadLayerChain());
document.getElementById('lcDir').addEventListener('change', ()=>loadLayerChain());
let _lcTimer = null;
document.getElementById('lcQuery').addEventListener('input', ()=>{
  clearTimeout(_lcTimer);
  _lcTimer = setTimeout(()=>loadLayerChain(), 180);
});
document.getElementById('odCat').addEventListener('change', ()=>loadObjectDiff());
document.getElementById('odStatus').addEventListener('change', ()=>loadObjectDiff());
let _odTimer = null;
document.getElementById('odQuery').addEventListener('input', ()=>{
  clearTimeout(_odTimer);
  _odTimer = setTimeout(()=>loadObjectDiff(), 180);
});
document.getElementById('layerModal').addEventListener('click', e=>{ if(e.target.id === 'layerModal') closeLayerChain(); });

document.getElementById('gameVerifyEntry').onclick = openGameVerify;
document.getElementById('gameVerifyBtn').onclick = openGameVerify;
document.getElementById('gvClose').onclick = closeGameVerify;
document.getElementById('gvRunBtn').onclick = ()=>startGameVerifyFlow(false);
document.getElementById('gvConfirmYes').onclick = ()=>startGameVerifyFlow(true);
document.getElementById('gvConfirmNo').onclick = ()=>{ document.getElementById('gvConfirmBox').style.display = 'none'; };
document.getElementById('gvCancelBtn').onclick = cancelGameVerifyFlow;
document.getElementById('gameVerifyModal').addEventListener('click', e=>{ if(e.target.id === 'gameVerifyModal') closeGameVerify(); });

document.getElementById('publishBtn').onclick = openPublishModal;
document.getElementById('pubClose').onclick = closePublishModal;
document.getElementById('pubRefreshBtn').onclick = ()=>loadPublishPreview(true);
document.getElementById('pubModSel').onchange = ()=>{
  const fidEl = document.getElementById('pubFolderId');
  if(fidEl){ delete fidEl.dataset.edited; fidEl.value = ''; }
  loadPublishPreview(false);
};
document.getElementById('pubFolderId').addEventListener('input', e=>{ e.target.dataset.edited = '1'; });
document.getElementById('pubUseModHomeBtn').onclick = useLauncherModDirForPublish;
document.getElementById('pubRunBtn').onclick = runPublishExport;
document.getElementById('pubPatchZipBtn').onclick = runLegacyPatchExport;
document.getElementById('publishModal').addEventListener('click', e=>{ if(e.target.id === 'publishModal') closePublishModal(); });

document.getElementById('cmdBtn').onclick = openCmd;

document.getElementById('keysClose').onclick = closeKeys;

document.getElementById('unloadClose').onclick = closeUnloadModal;

document.getElementById('unloadModal').addEventListener('click', e=>{ if(e.target.id === 'unloadModal') closeUnloadModal(); });

document.getElementById('keysModal').addEventListener('click', e=>{ if(e.target.id === 'keysModal') closeKeys(); });

document.getElementById('cmdPalette').addEventListener('click', e=>{ if(e.target.id === 'cmdPalette') closeCmd(); });

document.getElementById('cpInput').addEventListener('input', cpRender);

document.getElementById('cpInput').addEventListener('keydown', e=>{
  if(e.key === 'ArrowDown'){ e.preventDefault(); cpMove(1); }
  else if(e.key === 'ArrowUp'){ e.preventDefault(); cpMove(-1); }
  else if(e.key === 'Enter'){ e.preventDefault(); cpRun(cpIdx); }
  else if(e.key === 'Escape'){ e.preventDefault(); closeCmd(); }
});

initMascot();

initMascotFloatSize();

initDensity();

// 不直接 loadData()：启动期后端还在后台读 mod，先等它报 ready
bootWait();
