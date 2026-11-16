// 11-map：地图（P4）
// 40 个 IIFE 整体搬来，一个都没拆开（IIFE 内部 200+ 个函数和局部变量，拆开作用域就断）。
// 这些 IIFE 本来就是模块形态：内部定义，末尾 window.map* = 导出，HTML 的 onclick="mapApply()" 靠它。
// window.* 赋值一行未改。

/* ---------- v0.85 地图检查 ---------- */
function mapFocusProvince(pid){
  // 注意：MAP 是 const 声明，不会挂到 window 上，这里只能用词法变量
  if(typeof MAP === 'undefined' || !MAP.ready){ status('图层未就绪，先构建图层', true); return false; }
  const c = MAP.centers && MAP.centers[String(pid)];
  if(!c){ status('省 ' + pid + ' 没有中心点（可能不在当前地图上）', true); return false; }
  mapGoto(c[0], c[1], 1.2);
  mapSelectProvince(pid);
  status('已定位到省 ' + pid);
  return true;
}


function mapRenderLayers(d){
  const listEl = document.getElementById('mapLayersList');
  if(!listEl) return;
  if(!d || !Array.isArray(d.layers) || !d.layers.length){
    listEl.textContent = '（未读到 descriptor）';
    return;
  }
  const src = (d.source || '').replace(/[\/]+$/, '');
  listEl.innerHTML = d.layers.map((L, i)=>{
    const isSrc = src && L.path && L.path.replace(/[\/]+$/, '').indexOf(src) >= 0;
    const tag = L.is_game ? '原版（游戏本体）' : (L.mod_name || L.name);
    const extra = [];
    if(L.replace_count) extra.push('replace_path ' + L.replace_count);
    if(L.deps && L.deps.length) extra.push('依赖 ' + L.deps.join(', '));
    if(!L.has_descriptor && !L.is_game) extra.push('无 descriptor.mod');
    return '<div style="margin:3px 0">' + (i + 1) + '. ' + escapeHtml(tag) +
      (isSrc ? ' <span style="color:var(--accent)">← 地图</span>' : '') +
      (extra.length ? '<div style="color:var(--t3);padding-left:12px">' + escapeHtml(extra.join(' · ')) + '</div>' : '') +
      '</div>';
  }).join('');
}


async function mapRunCheck(){
  const list = document.getElementById('mckList');
  const stats = document.getElementById('mckStats');
  document.getElementById('mapCheckModal').classList.add('show');
  list.innerHTML = '<div class="cm-empty">检查中…（约 10–20 秒）</div>';
  stats.innerHTML = '';
  try{
    const r = await (await fetch('/api/map_integrity', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({root: (typeof MAP !== 'undefined' && MAP.root) || ''})})).json();
    if(!r.ok){ list.innerHTML = '<div class="cm-empty">' + escapeHtml(r.msg || '检查失败') + '</div>'; return; }
    const st = r.stats || {};
    stats.innerHTML = '<span class="e">错误 ' + (st.error || 0) + '</span>' +
      '<span class="w">警告 ' + (st.warn || 0) + '</span>' +
      '<span class="i">提示 ' + (st.info || 0) + '</span>';
    const items = r.items || [];
    if(!items.length){
      list.innerHTML = '<div class="cm-empty">没有发现问题（' + (r.sizes ? r.sizes.provinces + ' 省，' + r.ms + ' ms' : '') + '）</div>';
      return;
    }
    list.innerHTML = items.map((it, i)=>{
      const lv = it.level === 'error' ? '错误' : (it.level === 'warn' ? '警告' : '提示');
      return '<div class="mck-row" data-i="' + i + '">' +
        '<span class="mck-lv ' + it.level + '">' + lv + '</span>' +
        '<span class="mck-main"><div class="mck-t">' + escapeHtml(it.title) + '</div>' +
        (it.detail ? '<div class="mck-d">' + escapeHtml(it.detail) + '</div>' : '') + '</span>' +
        (it.provinces && it.provinces.length
          ? '<button class="btn mck-go" data-p="' + it.provinces[0] + '">定位</button>' : '') +
        '</div>';
    }).join('');
    list.querySelectorAll('.mck-go').forEach(b=>{
      b.onclick = e=>{
        e.stopPropagation();
        const pid = Number(b.dataset.p);
        document.getElementById('mapCheckModal').classList.remove('show');
        mapFocusProvince(pid);
      };
    });
  }catch(e){
    list.innerHTML = '<div class="cm-empty">检查失败：' + escapeHtml(e.message) + '</div>';
  }
}


// v0.94 涂色交互（前端逻辑）
(function(){
  let pending = 0, painting = false, lastDab = 0;

  async function paintCall(body){
    try{
      const r = await (await fetch('/api/map_paint', {method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)})).json();
      return r;
    }catch(e){ return {ok:false, msg:e.message}; }
  }

  function targetPid(){
    const v = (document.getElementById('paintTarget').value || '').trim();
    return /^\d+$/.test(v) ? Number(v) : 0;
  }

  function paintStat(msg){
    const el = document.getElementById('paintStat');
    if(el && msg) el.textContent = msg;
  }

  async function paintBegin(){
    const r = await paintCall({act:'begin', root: MAP.root || ''});
    if(!r.ok){ status(r.msg || '无法开始涂色', true); return false; }
    pending = 0;
    paintStat('待涂 0 像素');
    status('涂色就绪：可在地图上拖动');
    return true;
  }

  async function paintDab(imgX, imgY){
    const pid = targetPid();
    if(!pid){ status('先在右侧填目标省号', true); return; }
    const radius = Number(document.getElementById('paintR').value || 4);
    const r = await paintCall({act:'dab', x: Math.round(imgX), y: Math.round(imgY), r: radius, pid: pid});
    if(r.ok){
      pending += r.pixels || 0;
      paintStat('待涂 ' + pending + ' 像素');
      const tp = document.getElementById('paintPid');
      if(tp) tp.textContent = String(pid);
    }
  }

  async function paintApply(){
    if(!pending){ status('还没有涂抹', true); return; }
    const r = await paintCall({act:'commit'});
    if(!r.ok){ status(r.msg || '写入失败', true); return; }
    pending = 0;
    paintStat('已写盘（撤销栈 ' + (r.undo_depth || 0) + '）');
    status('已写入 ' + (r.pixels || 0) + ' 像素，正在重建图层…');
    // 地图变了，缓存键虽未变但像素变了 → 强制重建
    try{ await mapBuild(true); }catch(e){}
  }

  async function paintUndo(){
    const r = await paintCall({act:'undo'});
    status(r.ok ? ('已撤销（剩 ' + (r.undo_depth || 0) + ' 步）') : (r.msg || '没有可撤销'), !r.ok);
    if(r.ok){ try{ await mapBuild(true); }catch(e){} }
  }

  async function paintRedo(){
    const r = await paintCall({act:'redo'});
    status(r.ok ? '已重做' : (r.msg || '没有可重做'), !r.ok);
    if(r.ok){ try{ await mapBuild(true); }catch(e){} }
  }

  function bindPaint(){
    const applyBtn = document.getElementById('paintApply');
    if(!applyBtn || applyBtn.dataset.bound) return;
    applyBtn.dataset.bound = '1';
    applyBtn.onclick = paintApply;
    document.getElementById('paintUndo').onclick = paintUndo;
    document.getElementById('paintRedo').onclick = paintRedo;
    document.getElementById('paintR').oninput = e=>{
      document.getElementById('paintRVal').textContent = e.target.value;
    };
    const wrap = document.getElementById('mapStageWrap');
    wrap.addEventListener('pointerdown', async e=>{
      if(MAP.mode !== 'paint') return;
      if(e.button !== 0) return;
      if(mapEventOverUI(e)) return;
      const ok = await paintBegin();
      if(!ok) return;
      painting = true;
      wrap.classList.add('dragging');
      const p = mapScreenToImage(e.clientX, e.clientY);
      lastDab = Date.now();
      paintDab(p.x, p.y);
    }, true);
    wrap.addEventListener('pointermove', e=>{
      if(!painting || MAP.mode !== 'paint') return;
      const now = Date.now();
      if(now - lastDab < 40) return;   // 节流
      lastDab = now;
      const p = mapScreenToImage(e.clientX, e.clientY);
      paintDab(p.x, p.y);
    }, true);
    window.addEventListener('pointerup', ()=>{
      if(painting){
        painting = false;
        wrap.classList.remove('dragging');
        paintStat('待涂 ' + pending + ' 像素（点「应用」写盘）');
      }
    }, true);
  }

  window.mapBindPaint = bindPaint;
})();


// v0.99 省份合并 UI
(function(){
  function mgStat(msg, isErr){
    const el = document.getElementById('mgStat');
    if(el){ el.textContent = msg; el.style.color = isErr ? 'var(--warn)' : ''; }
  }

  async function call(d){
    try{
      const r = await (await fetch('/api/map_merge', {method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify(d)})).json();
      return r;
    }catch(e){ return {ok:false, msg:e.message}; }
  }

  function num(id){
    const v = (document.getElementById(id).value || '').trim();
    return /^\d+$/.test(v) ? Number(v) : 0;
  }

  async function showNeighbors(){
    const src = num('mgSrcPid');
    if(!src){ mgStat('先填源省号', true); return; }
    const list = document.getElementById('mgNbList');
    list.textContent = '读取中…';
    const r = await call({act:'neighbors', src: src, root: MAP.root || ''});
    if(!r.ok){ list.textContent = ''; mgStat(r.msg || '读取失败', true); return; }
    if(!r.neighbors.length){ list.textContent = '没有相邻省（孤立省）'; return; }
    document.getElementById('mgSrc').textContent = String(src);
    list.innerHTML = r.neighbors.map(n=>
      '<span style="display:inline-block;margin:2px 6px 2px 0;cursor:pointer;border-bottom:1px dotted var(--line2)" ' +
      'data-pid="' + n.pid + '">' + n.pid + '<span style="color:var(--t3)">(' + n.share + ')</span></span>'
    ).join('');
    list.querySelectorAll('[data-pid]').forEach(el=>{
      el.onclick = ()=>{
        document.getElementById('mgDstPid').value = el.dataset.pid;
        mgStat('已选目标省 ' + el.dataset.pid);
      };
    });
    mgStat('点一个相邻省作为目标');
  }

  async function preview(){
    const src = num('mgSrcPid'), dst = num('mgDstPid');
    if(!src || !dst){ mgStat('源省和目标省都要填', true); return; }
    const r = await call({act:'preview', src: src, dst: dst, root: MAP.root || ''});
    if(!r.ok){ mgStat(r.msg || '预览失败', true); return; }
    const parts = ['省 ' + src + ' → ' + dst, r.pixels + ' 像素'];
    if(r.states && r.states.length) parts.push('州 ' + r.states.join(','));
    if(r.regions && r.regions.length) parts.push('战略区 ' + r.regions.join(','));
    if(r.states_empty_after && r.states_empty_after.length)
      parts.push('⚠ 州 ' + r.states_empty_after.join(',') + ' 会变空');
    mgStat(parts.join(' · '));
  }

  async function apply(){
    const src = num('mgSrcPid'), dst = num('mgDstPid');
    if(!src || !dst){ mgStat('源省和目标省都要填', true); return; }
    if(!confirm('把省 ' + src + ' 合并进省 ' + dst + '？\n\n会改写 provinces.bmp 与相关州文件的省份列表，可用「撤销上一笔」回退。')) return;
    mgStat('执行中…');
    const r = await call({act:'apply', src: src, dst: dst, root: MAP.root || ''});
    if(!r.ok){ mgStat(r.msg || '合并失败', true); return; }
    mgStat('已合并 ' + r.pixels + ' 像素，改动 ' + (r.states || []).length + ' 个州文件；重建图层中…');
    try{ await mapBuild(true); }catch(e){}
    mgStat('合并完成：省 ' + r.src + ' → ' + r.dst + '（撤销栈 ' + r.undo_depth + '）');
  }

  function bindMerge(){
    const b = document.getElementById('mgApply');
    if(!b || b.dataset.bound) return;
    b.dataset.bound = '1';
    document.getElementById('mgNeighbors').onclick = showNeighbors;
    document.getElementById('mgPreview').onclick = preview;
    b.onclick = apply;
  }

  window.mapBindMerge = bindMerge;
})();


// v1.0 新建州 UI
(function(){
  function nsStat(msg, isErr){
    const el = document.getElementById('nsStat');
    if(el){ el.textContent = msg; el.style.color = isErr ? 'var(--warn)' : ''; }
  }

  async function createState(){
    const raw = (document.getElementById('nsProvinces').value || '').trim();
    const pids = raw.split(/[\s,;]+/).map(x=>parseInt(x,10)).filter(n=>n > 0);
    if(!pids.length){ nsStat('先填省份（空格分隔）', true); return; }
    const name = (document.getElementById('nsName').value || '').trim();
    const cat = document.getElementById('nsCategory').value;
    const mp = parseInt(document.getElementById('nsManpower').value, 10) || 100000;
    nsStat('创建中…');
    try{
      const r = await (await fetch('/api/state_create', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({provinces: pids, root: MAP.root || '', name: name,
                              category: cat, manpower: mp})})).json();
      if(!r.ok){ nsStat(r.msg || '创建失败', true); return; }
      nsStat('已建州 ' + r.id + '（' + r.provinces.length + ' 个省）· ' + (r.note || ''));
      if(r.moved_from && r.moved_from.length)
        nsStat('已建州 ' + r.id + '，从原州 ' + r.moved_from.join(',') + ' 移出 ' + r.provinces.length + ' 个省');
    }catch(e){ nsStat('请求失败：' + e.message, true); }
  }

  function bindNewState(){
    const b = document.getElementById('nsCreate');
    if(!b || b.dataset.bound) return;
    b.dataset.bound = '1';
    b.onclick = createState;
  }
  window.mapBindNewState = bindNewState;
})();


// v1.0.1 更新检查 UI
(function(){
  const SNOOZE_KEY = 'xuerong_update_snooze';

  function fmtVer(v){ return v ? ('v' + String(v).replace(/^v/, '')) : 'v—'; }

  function snoozed(){
    try{
      const t = Number(localStorage.getItem(SNOOZE_KEY) || 0);
      return t && (Date.now() - t) < 7 * 24 * 3600 * 1000;
    }catch(e){ return false; }
  }

  function showModal(info){
    try{ sessionStorage.setItem('updShown', '1'); document.getElementById('welcome').classList.remove('show'); }catch(e){}   // F16：弹过就记一笔，并让欢迎页当场让位
    document.getElementById('updVer').textContent = fmtVer(info.current) + ' → ' + fmtVer(info.latest);
    const body = document.getElementById('updBody');
    const lines = [];
    if(info.published) lines.push('发布时间：' + info.published);
    lines.push('');
    lines.push(info.notes || '（这次发布没有填写说明）');
    body.textContent = lines.join('\n');
    document.getElementById('updPage').href = info.url;
    const dl = document.getElementById('updDl');
    dl.disabled = false;
    dl.textContent = '下载并解压新版';
    dl.onclick = async function(){
      dl.disabled = true;
      dl.textContent = '下载中…';
      const body = document.getElementById('updBody');
      try {
        const r = await (await fetch('/api/update_apply', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({act:'prepare'})})).json();
        if (!r.ok) {
          body.textContent += String.fromCharCode(10, 10) + '[失败] ' + (r.msg || '');
          dl.disabled = false;
          dl.textContent = '重试';
          return;
        }
        dl.textContent = '已解压';
        body.textContent += String.fromCharCode(10, 10) + '[完成] ' + r.msg;
        status('新版已解压到 ' + (r.dir || ''));
      } catch (e) {
        body.textContent += String.fromCharCode(10, 10) + '[异常] ' + e.message;
        dl.disabled = false;
        dl.textContent = '重试';
      }
    };
    document.getElementById('updModal').classList.add('show');
  }

  async function check(force){
    const badge = document.getElementById('verBadge');
    try{
      const r = await (await fetch('/api/update' + (force ? '?force=1' : ''))).json();
      if(badge){
        badge.textContent = fmtVer(r.current);
        badge.title = r.latest ? ('当前 v' + r.current + '，最新 v' + r.latest) : '检查更新';
      }
      if(r.ok && r.newer){
        badge.classList.add('new');
        badge.textContent = fmtVer(r.current) + ' → ' + fmtVer(r.latest);
        if(force || !snoozed()) showModal(r);
      }else if(force){
        status(r.ok ? ('已是最新版本 v' + r.current) : (r.msg || '检查失败'));
      }
    }catch(e){
      if(force) status('检查更新失败：' + e.message, true);
    }
  }

  function bindUpdate(){
    const badge = document.getElementById('verBadge');
    if(!badge || badge.dataset.bound) return;
    badge.dataset.bound = '1';
    badge.onclick = ()=> check(true);
    document.getElementById('updClose').onclick = ()=>{
      document.getElementById('updModal').classList.remove('show');
    };
    document.getElementById('updLater').onclick = ()=>{
      try{ localStorage.setItem(SNOOZE_KEY, String(Date.now())); }catch(e){}
      document.getElementById('updModal').classList.remove('show');
    };
    // 启动后延迟 4 秒静默检查，不打断首屏
    setTimeout(()=> check(false), 4000);
  }

  window.mapBindUpdate = bindUpdate;
})();


// v1.0.2 省份排行
async function mapShowRank(){
  const list = document.getElementById('mckList');
  const stats = document.getElementById('mckStats');
  document.getElementById('mapCheckModal').classList.add('show');
  document.getElementById('mckTitle').textContent = '省份排行';
  document.getElementById('mckHint').textContent = '按面积排序 · 细化候选';
  stats.innerHTML = '';
  list.innerHTML = '<div class="cm-empty">读取中…</div>';
  try{
    const r = await (await fetch('/api/map_analysis?limit=60&min_px=800')).json();
    if(!r.ok){ list.innerHTML = '<div class="cm-empty">' + escapeHtml(r.msg || '读取失败') + '</div>'; return; }
    stats.innerHTML = '<span class="i">陆地省 ' + r.count + '</span>' +
      '<span class="i">中位 ' + r.median + 'px</span>' +
      '<span class="w">超 800px ' + r.big_count + '</span>';
    const rows = r.big || [];
    if(!rows.length){ list.innerHTML = '<div class="cm-empty">没有超过 800px 的陆地省份</div>'; return; }
    list.innerHTML = rows.map((x, i)=>{
      const bad = x.state ? '' : '<span style="color:var(--warn)"> 无州</span>';
      return '<div class="mck-row" data-i="' + i + '">' +
        '<span class="mck-lv info">' + (i + 1) + '</span>' +
        '<span class="mck-main"><div class="mck-t">省 ' + x.pid + ' · ' + x.px + ' px' + bad + '</div>' +
        '<div class="mck-d">州 ' + (x.state || '无') + ' · 战略区 ' + (x.region || '无') +
        (x.terrain ? ' · ' + escapeHtml(x.terrain) : '') + '</div></span>' +
        '<button class="btn mck-go" data-p="' + x.pid + '">定位</button></div>';
    }).join('');
    list.querySelectorAll('.mck-go').forEach(b=>{
      b.onclick = e=>{
        e.stopPropagation();
        document.getElementById('mapCheckModal').classList.remove('show');
        mapFocusProvince(Number(b.dataset.p));
      };
    });
  }catch(e){
    list.innerHTML = '<div class="cm-empty">读取失败：' + escapeHtml(e.message) + '</div>';
  }
}


// v1.0.4 一键修复
async function mapRepair(){
  const list = document.getElementById('mckList');
  const stats = document.getElementById('mckStats');
  document.getElementById('mapCheckModal').classList.add('show');
  document.getElementById('mckTitle').textContent = '一键修复';
  document.getElementById('mckHint').textContent = '只修能安全自动处理的项';
  list.innerHTML = '<div class="cm-empty">检查中…</div>';
  try{
    const p = await (await fetch('/api/map_repair?act=preview')).json();
    if(!p.ok){ list.innerHTML = '<div class="cm-empty">' + escapeHtml(p.msg || '检查失败') + '</div>'; return; }
    const rows = [];
    rows.push(['幽灵省', p.ghost_count + ' 个',
      p.ghost_count ? ('删除 definition.csv 里这些行：' + (p.ghost || []).slice(0, 10).join(', ')) : '无需处理',
      p.ghost_count > 0]);
    // 十字交叉：单独查一次
    let cross = {found: 0, msg: ''};
    try{
      cross = await (await fetch('/api/map_repair_cross')).json();
    }catch(e){}
    rows.push(['十字交叉像素', (cross.found || 0) + ' 处',
      cross.found ? ('把 2×2 的 A B / B A 解成横切或纵切；' + (cross.msg || '')) : '无需处理',
      (cross.found || 0) > 0]);
    stats.innerHTML = '<span class="w">幽灵省 ' + p.ghost_count + '</span>' +
      '<span class="w">十字交叉 ' + (cross.found || 0) + '</span>';
    list.innerHTML = rows.map(([name, count, detail, canFix])=>
      '<div class="mck-row"><span class="mck-lv ' + (canFix ? 'warn' : 'info') + '">' +
      (canFix ? '可修' : '跳过') + '</span><span class="mck-main">' +
      '<div class="mck-t">' + name + ' · ' + count + '</div>' +
      '<div class="mck-d">' + escapeHtml(detail) + '</div></span>' +
      (canFix ? '<button class="btn" data-fix="' + name + '" style="font-size:11px">执行</button>' : '') +
      '</div>').join('');
    list.querySelectorAll('[data-fix]').forEach(btn=>{
      btn.onclick = async ()=>{
        const kind = btn.dataset.fix;
        if(kind === '幽灵省'){
          if(!confirm('删除 ' + p.ghost_count + ' 个幽灵省？会改写 definition.csv（有备份）。')) return;
          btn.disabled = true; btn.textContent = '修复中…';
          const r = await (await fetch('/api/map_repair?act=ghost')).json();
          if(!r.ok){ btn.textContent = '失败'; status(r.msg || '修复失败', true); return; }
          status('已删除 ' + r.removed + ' 个幽灵省，正在重建图层…');
          btn.textContent = '已修';
          try{ await mapBuild(true); }catch(e){}
          mapRepair();
        } else {
          if(!confirm('修复 ' + (cross.found || 0) + ' 处十字交叉？会改写 provinces.bmp（可撤销）。')) return;
          btn.disabled = true; btn.textContent = '修复中…';
          const r = await (await fetch('/api/map_repair_cross?apply=1')).json();
          if(!r.ok){ btn.textContent = '失败'; status(r.msg || '修复失败', true); return; }
          status(r.msg || '已修复');
          btn.textContent = '已修';
          try{ await mapBuild(true); }catch(e){}
          mapRepair();
        }
      };
    });
  }catch(e){
    list.innerHTML = '<div class="cm-empty">失败：' + escapeHtml(e.message) + '</div>';
  }
}


// v1.0.7 地图快捷键
(function(){
  function inInput(){
    const a = document.activeElement;
    if(!a) return false;
    const tag = (a.tagName || '').toLowerCase();
    return tag === 'input' || tag === 'textarea' || tag === 'select' || a.isContentEditable;
  }

  function mapOpen(){
    const m = document.getElementById('mapModal');
    return m && m.classList.contains('show');
  }

  function mapBindHotkeys(){
    if(window.__mapHotkeysBound) return;
    window.__mapHotkeysBound = true;
    document.addEventListener('keydown', e=>{
      if(!mapOpen() || inInput()) return;
      const k = (e.key || '').toLowerCase();
      // 切模式
      if(!e.ctrlKey && !e.metaKey && !e.altKey){
        if(k === 'v'){ mapSetMode('view'); e.preventDefault(); return; }
        if(k === 'p'){ mapSetMode('paint'); e.preventDefault(); return; }
        if(k === 's'){ mapSetMode('state'); e.preventDefault(); return; }
        if(k === 'i'){ mapSetMode('pick'); e.preventDefault(); return; }
        // 视图
        if(k === '0' || k === 'f'){ mapFit(); e.preventDefault(); return; }
        if(k === '1'){ document.getElementById('mapOne').click(); e.preventDefault(); return; }
        if(k === '+' || k === '='){
          mapGoto((MAP.w/2), (MAP.h/2), Math.min(16, MAP.k * 1.25)); e.preventDefault(); return;
        }
        if(k === '-' || k === '_'){
          mapGoto((MAP.w/2), (MAP.h/2), Math.max(0.05, MAP.k / 1.25)); e.preventDefault(); return;
        }
        if(k === 'escape'){
          const cm = document.getElementById('mapCheckModal');
          if(cm && cm.classList.contains('show')){ cm.classList.remove('show'); return; }
          MAP.sel = []; mapRenderSel();
          status('已清空选择'); e.preventDefault(); return;
        }
      }
      // Ctrl+Z / Ctrl+Y 接地图撤销
      if((e.ctrlKey || e.metaKey) && (k === 'z' || k === 'y')){
        e.preventDefault();
        const act = k === 'z' ? 'undo' : 'redo';
        fetch('/api/map_paint', {method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({act})}).then(r=>r.json()).then(r=>{
          status(r.ok ? (k === 'z' ? '已撤销一步地图编辑' : '已重做') : (r.msg || '没有可撤销的操作'), !r.ok);
          if(r.ok) mapBuild(true).catch(()=>{});
        }).catch(()=>{});
      }
    });
    // Alt + 滚轮：调笔刷半径
    document.getElementById('mapStageWrap').addEventListener('wheel', e=>{
      if(!e.altKey || !mapOpen()) return;
      const r = document.getElementById('paintR');
      if(!r) return;
      e.preventDefault();
      let v = Number(r.value || 4) + (e.deltaY < 0 ? 1 : -1);
      v = Math.max(1, Math.min(30, v));
      r.value = v;
      const lab = document.getElementById('paintRVal');
      if(lab) lab.textContent = v;
      status('笔刷半径 ' + v + ' px');
    }, {capture: true, passive: false});
  }

  window.mapBindHotkeys = mapBindHotkeys;
})();

// v1.0.9 独立透明度 + Shift 多选 + 播放集
(function(){
  // ---- 每层独立透明度 ----
  function layerOp(){
    const out = {};
    document.querySelectorAll('.lt-op').forEach(el=>{
      out[el.dataset.op] = Number(el.value) / 100;
    });
    return out;
  }
  window.mapLayerOp = layerOp;

  document.addEventListener('input', e=>{
    if(e.target && e.target.classList && e.target.classList.contains('lt-op')){
      mapApplyLayers();
    }
  });

  // ---- Shift 多选 ----
  window.mapToggleSel = function(pid){
    MAP.sel = Array.isArray(MAP.sel) ? MAP.sel : [];
    const i = MAP.sel.indexOf(pid);
    if(i >= 0) MAP.sel.splice(i, 1); else MAP.sel.push(pid);
    mapRenderSel();
    mapSelectProvince(pid);
  };

  window.mapRenderSel = function(){
    const box = document.getElementById('msSel');
    if(box) box.textContent = (MAP.sel && MAP.sel.length) ? ('已选 ' + MAP.sel.length) : '';
    const info = document.getElementById('msInfo');
    if(MAP.sel && MAP.sel.length > 1 && info){
      info.textContent = '已选 ' + MAP.sel.length + ' 个省：' + MAP.sel.slice(0, 6).join(', ')
        + (MAP.sel.length > 6 ? ' …' : '');
    }
  };

  // ---- 播放集面板 ----
  let psLayers = [];

  function psRender(){
    const list = document.getElementById('psList');
    if(!psLayers.length){
      list.innerHTML = '<div class="mp-k">还没有 mod。点下面「添加 mod 目录」。</div>';
      return;
    }
    list.innerHTML = psLayers.map((L, i)=>
      '<div class="ps-row"><span class="ps-idx">' + (i + 1) + '</span>' +
      '<span class="ps-name" title="' + escapeHtml(L.path) + '">' + escapeHtml(L.name) + '</span>' +
      (L.has_map ? '<span class="ps-tag map">地图</span>' : '') +
      (L.replace_count ? '<span class="ps-tag">replace ' + L.replace_count + '</span>' : '') +
      '<button class="ps-btn" data-up="' + i + '" title="上移">↑</button>' +
      '<button class="ps-btn" data-down="' + i + '" title="下移">↓</button>' +
      '<button class="ps-btn" data-del="' + i + '" title="移除">✕</button></div>'
    ).join('');
    list.querySelectorAll('[data-up]').forEach(b=>{
      b.onclick = ()=>{ const i = Number(b.dataset.up); if(i > 0){ [psLayers[i-1], psLayers[i]] = [psLayers[i], psLayers[i-1]]; psRender(); } };
    });
    list.querySelectorAll('[data-down]').forEach(b=>{
      b.onclick = ()=>{ const i = Number(b.dataset.down); if(i < psLayers.length-1){ [psLayers[i+1], psLayers[i]] = [psLayers[i], psLayers[i+1]]; psRender(); } };
    });
    list.querySelectorAll('[data-del]').forEach(b=>{
      b.onclick = ()=>{ psLayers.splice(Number(b.dataset.del), 1); psRender(); };
    });
  }

  function psAddPath(p){
    p = (p || '').trim();
    if(!p) return;
    if(psLayers.some(x=>x.path === p)){ document.getElementById('psMsg').textContent = '这个目录已经在列表里'; return; }
    psLayers.push({path: p, name: p.split(/[\\/]/).filter(Boolean).pop() || p,
                   has_map: false, replace_count: 0, deps: []});
    psRender();
    document.getElementById('psMsg').textContent = '已加入，保存后重启生效';
  }

  async function psOpen(){
    const m = document.getElementById('psModal');
    m.classList.add('show');
    document.getElementById('psMsg').textContent = '读取中…';
    try{
      const r = await (await fetch('/api/playset')).json();
      psLayers = (r.layers || []).map(L=>({path: L.path, name: L.name, has_map: L.has_map,
                                           replace_count: L.replace_count, deps: L.deps}));
      psRender();
      document.getElementById('psMsg').textContent = psLayers.length
        ? '拖动顺序用 ↑ ↓ 调整，越靠下优先级越高'
        : '还没有 mod；可以点「添加 mod 目录」或粘贴路径';
    }catch(e){
      document.getElementById('psMsg').textContent = '读取失败：' + e.message;
    }
  }

  async function psSave(){
    const paths = psLayers.map(x=>x.path);
    const r = await (await fetch('/api/playset_save', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({paths})})).json();
    const msg = document.getElementById('psMsg');
    if(!r.ok){ msg.textContent = r.msg || '保存失败'; return; }
    msg.textContent = r.msg + ((r.bad && r.bad.length) ? ('　被跳过：' + r.bad.map(b=>b.path.split(/[\\/]/).pop() + '（' + b.why + '）').join('、')) : '');
  }

  function psBind(){
    const btn = document.getElementById('psOpen');
    if(!btn || btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.onclick = psOpen;
    document.getElementById('psClose').onclick = ()=>document.getElementById('psModal').classList.remove('show');
    document.getElementById('psSave').onclick = psSave;
    document.getElementById('psAdd').onclick = async ()=>{
      try{
        const r = await (await fetch('/api/playset_pick', {method:'POST',
          headers:{'Content-Type':'application/json'}, body:'{}'})).json();
        if(r.ok && r.path) psAddPath(r.path);
        else document.getElementById('psMsg').textContent = r.msg || '没有选择目录';
      }catch(e){ document.getElementById('psMsg').textContent = '选择失败：' + e.message; }
    };
    document.getElementById('psManual').addEventListener('keydown', e=>{
      if(e.key === 'Enter'){ psAddPath(e.target.value); e.target.value = ''; }
    });
  }
  window.mapBindPlayset = psBind;
})();


// v1.1.0 右侧 Tab 切换
(function(){
  function sideTab(name){
    // 切到铁路页时自动拉一次列表（不管是从按钮点进来还是恢复的）
    if(name === 'equip'){
      setTimeout(function(){
        const b = document.getElementById('eqRefresh');
        if(b && !b.dataset.loaded){ b.dataset.loaded = '1'; b.click(); }
      }, 200);
    }
    if(name === 'rail'){
      setTimeout(function(){
        const b = document.getElementById('railRefresh');
        if(b && !b.dataset.loaded){ b.dataset.loaded = '1'; b.click(); }
      }, 200);
    }
    document.querySelectorAll('.side-tab').forEach(b=>{
      b.classList.toggle('on', b.dataset.tab === name);
    });
    document.querySelectorAll('.side-pane').forEach(p=>{
      p.classList.toggle('on', p.id === 'pane-' + name);
    });
    try{ localStorage.setItem('xuerong_side_tab', name); }catch(e){}
  }
  window.mapSideTab = sideTab;

  function bindSideTabs(){
    const tabs = document.querySelectorAll('.side-tab');
    if(!tabs.length || tabs[0].dataset.bound) return;
    tabs.forEach(b=>{
      b.dataset.bound = '1';
      b.onclick = ()=> sideTab(b.dataset.tab);
    });
    let last = 'layers';
    try{ last = localStorage.getItem('xuerong_side_tab') || 'layers'; }catch(e){}
    if(last !== 'layers') sideTab(last);
    if(last === 'rail' && window.mapBindRail){
      setTimeout(function(){
        const b = document.getElementById('railRefresh');
        if(b && !b.dataset.loaded){ b.dataset.loaded = '1'; b.click(); }
      }, 200);
    }
  }
  window.mapBindSideTabs = bindSideTabs;
})();


// v1.1.1 输出模式
(function(){
  async function outRefresh(){
    try{
      const r = await (await fetch('/api/output')).json();
      const btn = document.getElementById('outModeBtn');
      if(btn){ btn.textContent = '输出模式：' + (r.on ? '开启' : '关闭'); btn.classList.toggle('primary', !!r.on); }
      const st = document.getElementById('outStat');
      if(st) st.textContent = r.on
        ? ('已写 ' + r.files + ' 个文件 · ' + (r.size / 1024).toFixed(0) + ' KB · 源 mod 未改动')
        : '关闭时直接写 mod 目录（有备份）';
    }catch(e){}
  }

  function bindOutput(){
    const btn = document.getElementById('outModeBtn');
    if(!btn || btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.onclick = async ()=>{
      const r = await (await fetch('/api/output?act=toggle')).json();
      status(r.msg || '');
      await outRefresh();
    };
    document.getElementById('outApply').onclick = async ()=>{
      if(!confirm('把输出目录里的文件复制回 mod？原文件会先做备份。')) return;
      const r = await (await fetch('/api/output_apply', {method:'POST',
        headers:{'Content-Type':'application/json'}, body:'{}'})).json();
      status(r.msg || (r.ok ? '已回源' : '回源失败'), !r.ok);
      document.getElementById('psMsg').textContent = (r.msg || '') +
        ((r.skipped && r.skipped.length) ? ('　跳过 ' + r.skipped.length + ' 个') : '');
      await outRefresh();
    };
    document.getElementById('outClear').onclick = async ()=>{
      if(!confirm('清空输出目录？（不影响源 mod）')) return;
      const r = await (await fetch('/api/output?act=clear')).json();
      status(r.msg || '');
      await outRefresh();
    };
    outRefresh();
  }
  window.mapBindOutput = bindOutput;
})();


/* ---------- v1.2.1 选中省份描边 ---------- */
(function () {
  function selCanvas() {
    const c = document.getElementById('mapSelCanvas');
    const wrap = document.getElementById('mapStageWrap');
    if (!c || !wrap) return null;
    const r = wrap.getBoundingClientRect();
    const z = uiZoom();
    const w = Math.max(1, Math.round(r.width / z));
    const h = Math.max(1, Math.round(r.height / z));
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    return { c: c, ctx: c.getContext('2d'), w: w, h: h };
  }

  function drawOutline(ctx, pid, color, size) {
    if (!MAP.idCanvas || !MAP.ready) return 0;
    const idc = MAP.idCanvas.getContext('2d');
    const k = MAP.k;
    const cv = document.getElementById('mapSelCanvas');
    const x0 = Math.max(0, Math.floor(-MAP.x / k) - 2);
    const y0 = Math.max(0, Math.floor(-MAP.y / k) - 2);
    const x1 = Math.min(MAP.w, Math.ceil((cv.width - MAP.x) / k) + 2);
    const y1 = Math.min(MAP.h, Math.ceil((cv.height - MAP.y) / k) + 2);
    const cw = x1 - x0, ch = y1 - y0;
    if (cw <= 0 || ch <= 0) return 0;
    let data;
    try { data = idc.getImageData(x0, y0, cw, ch).data; } catch (e) { return 0; }
    const at = function (x, y) {
      if (x < 0 || y < 0 || x >= cw || y >= ch) return 0;
      const i = (y * cw + x) * 4;
      return (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
    };
    ctx.fillStyle = color;
    let n = 0;
    for (let y = 0; y < ch; y++) {
      for (let x = 0; x < cw; x++) {
        if (at(x, y) !== pid) continue;
        const edge = at(x - 1, y) !== pid || at(x + 1, y) !== pid ||
                     at(x, y - 1) !== pid || at(x, y + 1) !== pid;
        if (!edge) continue;
        const cx = (x0 + x) * k + MAP.x;
        const cy = (y0 + y) * k + MAP.y;
        ctx.fillRect(cx - size / 2, cy - size / 2, size, size);
        n++;
      }
    }
    return n;
  }

  // v1.8.0 细化预览的形状叠层（复用 mapSelCanvas）
  window.mapDrawRefine = function (parts) {
    const c = document.getElementById('mapSelCanvas');
    if (!c || !MAP.ready) return;
    const ctx = c.getContext('2d');
    const colors = ['rgba(255,90,90,.78)','rgba(90,200,120,.78)','rgba(90,150,250,.78)',
                    'rgba(250,200,80,.78)','rgba(200,120,240,.78)','rgba(120,220,220,.78)',
                    'rgba(230,150,90,.78)','rgba(150,150,90,.78)'];
    const px = Math.max(1, MAP.k);
    (parts || []).forEach(function (p, i) {
      const bb = p.bbox || [0, 0];
      const bx = bb[0], by = bb[1];
      ctx.fillStyle = colors[i % colors.length];
      (p.pts || []).forEach(function (v) {
        const rx = Math.floor(v / 100000), ry = v % 100000;
        const cx = (bx + rx) * MAP.k + MAP.x;
        const cy = (by + ry) * MAP.k + MAP.y;
        if (cx < -4 || cy < -4 || cx > c.width + 4 || cy > c.height + 4) return;
        ctx.fillRect(cx, cy, px, px);
      });
    });
  };

  window.mapRenderSelection = function () {
    const sc = selCanvas();
    if (!sc) return;
    const ctx = sc.ctx;
    ctx.clearRect(0, 0, sc.w, sc.h);
    if (!MAP.ready) return;
    if (window.REFINE_PREVIEW && REFINE_PREVIEW.parts) window.mapDrawRefine(REFINE_PREVIEW.parts);
    const sel = Array.isArray(MAP.sel) ? MAP.sel : [];
    const base = Math.max(1, Math.round(MAP.k * 1.4));
    sel.forEach(function (pid) {
      if (pid === MAP.lastPid) return;
      drawOutline(ctx, pid, 'rgba(255,255,255,0.6)', base);
    });
    if (MAP.lastPid) {
      const big = Math.max(2, Math.round(MAP.k * 2.4));
      drawOutline(ctx, MAP.lastPid, 'rgba(18,20,16,0.9)', big);
      drawOutline(ctx, MAP.lastPid, 'rgba(255,214,120,1)', Math.max(1, Math.round(MAP.k * 1.5)));
    }
  };

  // 每次视图变换后重绘（mapApply 是唯一的变换出口）
  const origApply = window.mapApply;
  if (typeof origApply === 'function') {
    window.mapApply = function () {
      origApply.apply(this, arguments);
      window.mapRenderSelection();
    };
  }
})();


// v1.3.0 省份细化
(function(){
  let lastPid = 0, lastK = 0, previewOk = false;

  function rfStat(msg, bad){
    const el = document.getElementById('rfStat');
    if(el){ el.textContent = msg; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function rfDoPreview(){
    const pid = MAP.lastPid;
    const k = Number(document.getElementById('rfK').value || 4);
    if(!pid){ rfStat('先在图上点一个省', true); return; }
    rfStat('计算中…');
    document.getElementById('rfApply').disabled = true;
    try{
      const r = await (await fetch('/api/refine_preview?pid=' + pid + '&k=' + k)).json();
      if(!r.ok){ rfStat(r.msg || '预览失败', true); previewOk = false; return; }
      previewOk = true;
      lastPid = pid; lastK = r.k;
      const sizes = (r.parts || []).map(p=>p.px).sort((a,b)=>b-a);
      const warns = (r.warnings || []);
      rfStat('省 ' + pid + ' 切成 ' + r.k + ' 块，面积 ' + sizes.join(' / ') +
             '（共 ' + r.total + ' 像素）· 形状已画到地图上' +
             (warns.length ? String.fromCharCode(10) + warns.map(w=>'⚠ ' + w).join(String.fromCharCode(10)) : ''));
      window.REFINE_PREVIEW = r;
      if (window.mapRenderSelection) window.mapRenderSelection();
      document.getElementById('rfApply').disabled = false;
    }catch(e){ rfStat('预览失败：' + e.message, true); }
  }

  async function rfDoApply(){
    const pid = MAP.lastPid;
    const k = Number(document.getElementById('rfK').value || 4);
    if(!pid){ rfStat('先在图上点一个省', true); return; }
    if(!previewOk || pid !== lastPid || k !== lastK){
      rfStat('参数变了，先点一次「预览」', true); return;
    }
    if(!confirm('把省 ' + pid + ' 切成 ' + k + ' 块？会改写 provinces.bmp 和 definition.csv（有备份）。')) return;
    rfStat('写入中…');
    const btn = document.getElementById('rfApply');
    btn.disabled = true;
    try{
      const r = await (await fetch('/api/refine_apply', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({pid: pid, k: k})})).json();
      if(!r.ok){ rfStat(r.msg || '应用失败', true); btn.disabled = false; return; }
      window.REFINE_PREVIEW = null;
      if (window.mapRenderSelection) window.mapRenderSelection();
      rfStat(r.msg + '，正在重建图层…');
      status(r.msg || '已细化');
      previewOk = false;
      try{ await mapBuild(true); }catch(e){}
      if(window.mapLoadMeta) mapLoadMeta();
    }catch(e){ rfStat('应用失败：' + e.message, true); btn.disabled = false; }
  }

  function rfBind(){
    const pv = document.getElementById('rfPreview');
    if(!pv || pv.dataset.bound) return;
    pv.dataset.bound = '1';
    pv.onclick = rfDoPreview;
    document.getElementById('rfApply').onclick = rfDoApply;
    document.getElementById('rfK').addEventListener('input', ()=>{
      previewOk = false;
      document.getElementById('rfApply').disabled = true;
      window.REFINE_PREVIEW = null;
      if (window.mapRenderSelection) window.mapRenderSelection();
    });
  }
  window.mapBindRefine = rfBind;
})();

async function mapShowLocMissing(){
  const list = document.getElementById('mckList');
  const stats = document.getElementById('mckStats');
  list.innerHTML = '<div class="cm-empty">扫描中…</div>';
  if(stats) stats.textContent = '';
  const r = await (await fetch('/api/loc_missing?limit=600')).json();
  if(!r.ok){ list.innerHTML = '<div class="cm-empty">' + escapeHtml(r.msg || '扫描失败') + '</div>'; return; }
  LOC_MISS = r;
  const kinds = r.by_kind || {};
  if(stats) stats.innerHTML = r.total
    ? ('<span class="w" style="margin-right:8px">缺 ' + r.total + '</span><span class="k">' + (r.defined || 0) + ' 已定义</span>')
    : '<span class="k">全部都有定义</span>';
  if(!r.total){
    list.innerHTML = '<div class="cm-empty">' + (r.msg || '没有缺失') + '</div>';
    return;
  }
  const tag = {focus:'国策', event:'事件', idea:'精神'};
  const head = '<div class="mck-row" style="align-items:center">'
    + '<div><div class="mck-t">缺 ' + r.total + ' 个本地化键</div>'
    + '<div class="mck-d">' + Object.keys(kinds).map(k=>(tag[k]||k)+' ' + kinds[k]).join(' · ')
    + '　游戏里会直接显示键名</div></div>'
    + '<button class="btn" id="locGen" style="font-size:11px">生成占位</button></div>';
  const rows = (r.missing || []).map(x=>
    '<div class="mck-row"><div><div class="mck-t" style="font-family:monospace">' + escapeHtml(x.key) + '</div>'
    + '<div class="mck-d">' + (tag[x.kind] || x.kind) + '　' + escapeHtml(x.file || '') + '</div></div></div>'
  ).join('');
  list.innerHTML = head + rows + (r.truncated ? '<div class="cm-empty">只显示前 600 条</div>' : '');
  const btn = document.getElementById('locGen');
  if(btn) btn.onclick = async ()=>{
    if(!confirm('把 ' + r.total + ' 个缺失的键写进 zz_xuerong_autogen_l_simp_chinese.yml？' + String.fromCharCode(10) + '占位值就是键名，之后自己改。')) return;
    btn.disabled = true; btn.textContent = '写入中…';
    const g = await (await fetch('/api/loc_generate', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({keys: (r.missing || []).map(x=>x.key)})})).json();
    status(g.msg || (g.ok ? '已生成' : '生成失败'), !g.ok);
    btn.textContent = g.ok ? ('已写 ' + (g.written || 0)) : '失败';
    if(g.ok) mapShowLocMissing();
  };
}

// v1.3.2 gfx / sprite 引用检查（参考 CWTools 的 sprite 存在性校验）
async function mapShowGfxMissing(){
  const list = document.getElementById('mckList');
  const stats = document.getElementById('mckStats');
  list.innerHTML = '<div class="cm-empty">扫描中（要读原版 145 个 gfx，约 3 秒）…</div>';
  if(stats) stats.textContent = '';
  const r = await (await fetch('/api/gfx_missing?limit=600')).json();
  if(!r.ok){ list.innerHTML = '<div class="cm-empty">' + escapeHtml(r.msg || '扫描失败') + '</div>'; return; }
  const bad = r.bad_texture_total || 0;
  if(stats) stats.innerHTML = '<span class="w" style="margin-right:8px">缺 ' + (r.total || 0) + '</span>'
    + '<span class="k">' + (r.defined || 0) + ' 已定义</span>'
    + (bad ? '<span class="w" style="margin-left:8px">贴图缺 ' + bad + '</span>' : '');
  let html = '';
  if(!r.total && !bad){
    list.innerHTML = '<div class="cm-empty">' + escapeHtml(r.msg || '全部都有定义') + '</div>';
    return;
  }
  if(r.total){
    html += '<div class="mck-row"><div><div class="mck-t">引用了但没定义 · ' + r.total + ' 个</div>'
      + '<div class="mck-d">游戏里会显示成空白方块或报错</div></div></div>';
    html += (r.missing || []).map(x=>
      '<div class="mck-row"><div><div class="mck-t" style="font-family:monospace">' + escapeHtml(x.name) + '</div>'
      + '<div class="mck-d">' + escapeHtml(x.where) + '　' + escapeHtml(x.file || '') + '</div></div></div>'
    ).join('');
  }
  if(bad){
    html += '<div class="mck-row"><div><div class="mck-t">定义了但贴图文件不存在 · ' + bad + ' 个</div>'
      + '<div class="mck-d">sprite 存在但 dds 缺失，加载时会报找不到文件</div></div></div>';
    html += (r.bad_texture || []).map(x=>
      '<div class="mck-row"><div><div class="mck-t" style="font-family:monospace">' + escapeHtml(x.name) + '</div>'
      + '<div class="mck-d">' + escapeHtml(x.texture) + '</div></div></div>'
    ).join('');
  }
  list.innerHTML = html;
}

// v1.4.0 国策树预览（参考 HOI4 Mod Utilities 的 Focus tree preview）
(function(){
  const CELL = 96;            // HOI4 的国策格边长
  const PAD = 60;
  let ftData = null, ftSel = null;

  function ftOpen(){
    document.getElementById('ftModal').classList.add('show');
    ftLoadList();
  }
  function ftClose(){ document.getElementById('ftModal').classList.remove('show'); }

  async function ftLoadList(){
    const sel = document.getElementById('ftPick');
    if(sel.dataset.loaded){
      if(sel.value) ftDraw(sel.value);
      return;
    }
    const r = await (await fetch('/api/focus_trees')).json();
    if(!r.ok){ document.getElementById('ftInfo').textContent = '读取失败'; return; }
    sel.innerHTML = (r.trees || []).map(t=>
      '<option value="' + t.id + '">' + t.id + '（' + t.count + ' 节点）</option>').join('');
    sel.dataset.loaded = '1';
    sel.onchange = ()=> ftDraw(sel.value);
    if(sel.value) ftDraw(sel.value);
  }

  async function ftDraw(tid){
    const svg = document.getElementById('ftSvg');
    const info = document.getElementById('ftInfo');
    info.textContent = '读取中…';
    const g = await (await fetch('/api/focus_graph?tree=' + encodeURIComponent(tid))).json();
    if(!g.ok){ info.textContent = g.msg || '读取失败'; svg.innerHTML = ''; return; }
    ftData = g;
    info.textContent = g.msg + '　' + (g.file || '');

    const nodes = g.nodes || [];
    if(!nodes.length){ svg.innerHTML = ''; return; }
    const minX = Math.min(...nodes.map(n=>n.x));
    const minY = Math.min(...nodes.map(n=>n.y));
    const maxX = Math.max(...nodes.map(n=>n.x));
    const maxY = Math.max(...nodes.map(n=>n.y));
    const W = (maxX - minX + 1) * CELL + PAD * 2;
    const H = (maxY - minY + 1) * CELL + PAD * 2;
    // 内容尺寸存 data-*；SVG 元素本身填满容器，视野完全由 viewBox 控制
    svg.setAttribute('data-w', W);
    svg.setAttribute('data-h', H);
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    if(!svg._pan){ svg._pan = makePannable(svg, document.getElementById('ftBody')); }
    setTimeout(()=>{ if(svg._pan) svg._pan(); }, 30);

    const px = n => (n.x - minX) * CELL + PAD;
    const py = n => (n.y - minY) * CELL + PAD;
    const idx = {};
    nodes.forEach(n=>{ idx[n.id] = n; });

    let out = '<defs><marker id="ftArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
      + '<path d="M0,0 L6,3 L0,6 z" fill="#5a656b"/></marker></defs>';
    // 连线
    for(const e of (g.edges || [])){
      const a = idx[e.from], b = idx[e.to];
      if(!a || !b) continue;
      const x1 = px(a) + CELL/2, y1 = py(a) + CELL/2;
      const x2 = px(b) + CELL/2, y2 = py(b) + CELL/2;
      const cls = e.kind === 'mutex' ? 'ft-edge mutex' : 'ft-edge';
      const mk = e.kind === 'mutex' ? '' : ' marker-end="url(#ftArrow)"';
      out += '<line class="' + cls + '" x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '"' + mk + '/>';
    }
    // 节点
    for(const n of nodes){
      const x = px(n), y = py(n);
      out += '<g class="ft-node" data-id="' + n.id + '" transform="translate(' + x + ',' + y + ')">'
        + '<rect width="' + (CELL-8) + '" height="' + (CELL-8) + '" rx="8"/>';
      if(n.icon){
        out += '<image href="/api/icon?gfx=' + encodeURIComponent(n.icon) + '" x="6" y="6"'
          + ' width="' + (CELL-20) + '" height="' + (CELL-20) + '" preserveAspectRatio="xMidYMid meet"/>';
      }
      const label = (n.name || n.id).slice(0, 16);
      out += '<text x="' + (CELL-8)/2 + '" y="' + (CELL-11) + '">' + label.replace(/[<>&]/g, '') + '</text>'
        + '</g>';
    }
    svg.innerHTML = out;

    svg.querySelectorAll('.ft-node').forEach(el=>{
      el.ondblclick = ()=>{
        el.dispatchEvent(new MouseEvent('click', {bubbles:true}));
        const eb = document.getElementById('ftEdit');
        if(eb && !eb.disabled) eb.click();
      };
      el.onclick = ()=>{
        svg.querySelectorAll('.ft-node').forEach(o=>o.classList.remove('sel'));
        el.classList.add('sel');
        const n = idx[el.dataset.id];
        ftSel = n;
        const eb = document.getElementById('ftEdit');
        if(eb) eb.disabled = false;
        info.textContent = (n.name || n.id) + '　[' + n.id + ']　(' + n.x + ',' + n.y + ')'
          + (n.cost ? '　成本 ' + n.cost : '')
          + (n.prereq.length ? '　前置 ' + n.prereq.map(g=>g.join('|')).join(' + ') : '')
          + (n.mutex.length ? '　互斥 ' + n.mutex.join(',') : '');
      };
    });
  }

  function ftBind(){
    const btn = document.getElementById('ftOpen');
    if(!btn || btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.onclick = ftOpen;
    document.getElementById('ftClose').onclick = ftClose;
    document.getElementById('ftEdit').onclick = ()=>{
      if(!ftSel || !ftData) return;
      const tid = ftData.tree, fid = ftSel.id;
      ftClose();
      if(typeof openTreeById === 'function') openTreeById(tid);
      setTimeout(()=>{
        const el = document.querySelector('#viewport .node[data-id="' + fid + '"]');
        if(el){
          el.dispatchEvent(new MouseEvent('click', {bubbles:true}));
          el.scrollIntoView({block:'center', inline:'center', behavior:'smooth'});
          status('已定位到 ' + fid);
        } else {
          status('编辑器里没找到 ' + fid, true);
        }
      }, 260);
    };
    document.getElementById('ftFit').onclick = ()=>{
      const svg = document.getElementById('ftSvg');
      if(svg._pan) svg._pan();
    };
  }
  window.mapBindFocusTree = ftBind;
  // ftBind 只在 DOM 就绪时绑一次；侧栏若被重渲染，按钮会换新节点导致点击失效。
  // 挂到 window 上，HTML 里用内联 onclick 兜底。
  window.__ftOpen = ftOpen;
  // 这个按钮在国策树面板里，初始化函数可能早于本段执行，所以自己再绑一次
  if(document.readyState !== 'loading') ftBind();
  else document.addEventListener('DOMContentLoaded', ftBind);
})();


// v1.5.0 事件树预览（参考 HOI4 Mod Utilities 的 Event tree preview）
(function(){
  const NW = 130, NH = 34, GX = 26, GY = 26;
  let evData = null, evSel = null, evOnlyDown = false;

  function evClose(){ document.getElementById('evModal').classList.remove('show'); }

  async function evLoadList(){
    const sel = document.getElementById('evPick');
    if(sel.dataset.loaded){ if(sel.value) evDraw(sel.value); return; }
    const r = await (await fetch('/api/event_spaces')).json();
    if(!r.ok){ document.getElementById('evInfo').textContent = '读取失败'; return; }
    sel.innerHTML = (r.spaces || []).map(x=>
      '<option value="' + x.id + '">' + x.id + '（' + x.count + ' 事件）</option>').join('');
    sel.dataset.loaded = '1';
    sel.onchange = ()=>{ evOnlyDown = false; evSel = null; evDraw(sel.value); };
    if(sel.value) evDraw(sel.value);
  }

  async function evDraw(ns){
    const svg = document.getElementById('evSvg');
    const info = document.getElementById('evInfo');
    info.textContent = '读取中…';
    const g = await (await fetch('/api/event_graph?ns=' + encodeURIComponent(ns))).json();
    if(!g.ok){ info.textContent = g.msg || '读取失败'; svg.innerHTML = ''; return; }
    evData = g;
    info.textContent = g.msg;

    let nodes = g.nodes || [], edges = g.edges || [];
    if(!nodes.length){ svg.innerHTML = ''; return; }
    // 只看下游：从选中事件出发做可达性，消掉无关分支（第一层太长时的主要痛点）
    if(evOnlyDown && evSel && nodes.some(x=>x.id === evSel)){
      const adj2 = {};
      edges.forEach(e=>{ (adj2[e.from] = adj2[e.from] || []).push(e.to); });
      const keep = new Set([evSel]);
      const q2 = [evSel];
      let guard2 = 0;
      while(q2.length && guard2++ < 20000){
        const cur = q2.shift();
        for(const nx of (adj2[cur] || [])){
          if(!keep.has(nx)){ keep.add(nx); q2.push(nx); }
        }
      }
      nodes = nodes.filter(n=>keep.has(n.id));
      edges = edges.filter(e=>keep.has(e.from) && keep.has(e.to));
    }

    // 分层：按「触发的深度」排；根 = 没有入边的事件
    const indeg = {}, adj = {};
    nodes.forEach(n=>{ indeg[n.id] = 0; adj[n.id] = []; });
    edges.forEach(e=>{ if(adj[e.from]) adj[e.from].push(e.to); if(indeg[e.to] !== undefined) indeg[e.to]++; });
    const depth = {};
    const roots = nodes.filter(n=>indeg[n.id] === 0).map(n=>n.id);
    const q = roots.slice();
    roots.forEach(r=>{ depth[r] = 0; });
    let guard = 0;
    while(q.length && guard++ < 5000){
      const cur = q.shift();
      for(const nx of (adj[cur] || [])){
        if(depth[nx] === undefined){ depth[nx] = depth[cur] + 1; q.push(nx); }
      }
    }
    nodes.forEach(n=>{ if(depth[n.id] === undefined) depth[n.id] = 0; });

    // 按层分组，层内按 id 排序
    const layers = {};
    nodes.forEach(n=>{ (layers[depth[n.id]] = layers[depth[n.id]] || []).push(n); });
    Object.keys(layers).forEach(k=> layers[k].sort((a,b)=>a.id.localeCompare(b.id, 'en', {numeric:true})));

    // 同层节点太多时换行：否则 12 层横排会拍成 15:1 的细条，全览时看不清
    const MAX_PER_ROW = 7;
    const pos = {};
    let maxW = 0, rowCursor = 0;
    Object.keys(layers).map(Number).sort((a,b)=>a-b).forEach(d=>{
      const items = layers[d];
      const rows = Math.ceil(items.length / MAX_PER_ROW) || 1;
      items.forEach((n, i)=>{
        const rr = Math.floor(i / MAX_PER_ROW), cc = i % MAX_PER_ROW;
        pos[n.id] = { x: cc * (NW + GX) + 10, y: (rowCursor + rr) * (NH + GY) + 10 };
      });
      maxW = Math.max(maxW, Math.min(items.length, MAX_PER_ROW) * (NW + GX));
      rowCursor += rows;
    });
    // 层与层之间多留一点空隙，读起来像一层一层的
    let extra = 0;
    Object.keys(layers).map(Number).sort((a,b)=>a-b).forEach(d=>{
      const rows = Math.ceil(layers[d].length / MAX_PER_ROW) || 1;
      layers[d].forEach((n)=>{ pos[n.id].y += extra * (NH + GY); });
      extra += 0.7;      // 每层之间的额外间隙（按行高比例）
      rowCursor;
    });
    const W = maxW + 20, H = rowCursor * (NH + GY) + extra * (NH + GY) + 20;
    // 内容尺寸存 data-*；SVG 元素本身填满容器，视野完全由 viewBox 控制
    svg.setAttribute('data-w', W);
    svg.setAttribute('data-h', H);
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    if(!svg._pan){ svg._pan = makePannable(svg, document.getElementById('evBody')); }
    setTimeout(()=>{ if(svg._pan) svg._pan(); }, 30);

    let out = '<defs><marker id="evArrow" markerWidth="7" markerHeight="7" refX="6" refY="2.5" orient="auto">'
      + '<path d="M0,0 L6,2.5 L0,5 z" fill="#5a656b"/></marker></defs>';
    for(const e of edges){
      const a = pos[e.from], b = pos[e.to];
      if(!a || !b) continue;
      const x1 = a.x + NW / 2, y1 = a.y + NH;
      const x2 = b.x + NW / 2, y2 = b.y;
      let cls = 'ev-edge';
      if(e.external) cls += ' external';
      else if(e.where === 'after') cls += ' after';
      else if(e.where === 'immediate') cls += ' immediate';
      const path = 'M' + x1 + ',' + y1 + ' C' + x1 + ',' + (y1 + 24) + ' ' + x2 + ',' + (y2 - 24) + ' ' + x2 + ',' + y2;
      out += '<path class="' + cls + '" d="' + path + '" marker-end="url(#evArrow)"/>';
    }
    for(const n of nodes){
      const p = pos[n.id];
      if(!p) continue;
      const ext = n.kind === 'external';
      out += '<g class="ev-node' + (ext ? ' ext' : '') + '" data-id="' + n.id + '"'
        + ' transform="translate(' + p.x + ',' + p.y + ')">'
        + '<rect width="' + NW + '" height="' + NH + '" rx="6"/>'
        + '<text x="8" y="14" style="font-size:10px;font-weight:600">' + n.id.replace(/[<>&]/g, '') + '</text>'
        + '<text x="8" y="27" style="font-size:9px;fill:#8a969c">'
        + ((n.name || (ext ? '（外部引用）' : n.kind)) + '').slice(0, 20).replace(/[<>&]/g, '') + '</text>'
        + '</g>';
    }
    svg.innerHTML = out;

    svg.querySelectorAll('.ev-node').forEach(el=>{
      el.onclick = ()=>{
        const n = nodes.find(x=>x.id === el.dataset.id);
        if(!n) return;
        evSel = n.id;
        const fb = document.getElementById('evFocus');
        if(fb) fb.disabled = false;
        if(n.kind !== 'external' && window.evLoadToEditor) window.evLoadToEditor(n.id);
        info.textContent = n.id + '　' + (n.name || '（无标题）')
          + (n.file ? '　' + n.file : '　（不在本 mod 里）')
          + '　深度 ' + depth[n.id];
      };
      el.ondblclick = ()=>{ if(typeof openEventById === 'function') openEventById(el.dataset.id); };
    });
  }

  function evBind(){
    const btn = document.getElementById('evEntryTree');
    if(!btn || btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.onclick = ()=>{
      document.getElementById('evModal').classList.add('show');
      evLoadList();
    };
    const listBtn = document.getElementById('evEntryList');
    if(listBtn && !listBtn.dataset.bound){
      listBtn.dataset.bound = '1';
      listBtn.onclick = ()=>{
        if(typeof openEvents === 'function') openEvents();
      };
    }
    document.getElementById('evClose').onclick = evClose;
    document.getElementById('evNew').onclick = async ()=>{
      const ns = prompt('新命名空间的名称（字母开头，只用字母数字下划线）：', 'my_events');
      if(!ns) return;
      const r = await (await fetch('/api/event_space_create?ns=' + encodeURIComponent(ns))).json();
      status(r.msg || (r.ok ? '已创建' : '创建失败'), !r.ok);
      if(r.ok){
        const sel = document.getElementById('evPick');
        sel.dataset.loaded = '';
        sel.innerHTML = '';
        await evLoadList();
        sel.value = r.ns;
        evDraw(r.ns);
      }
    };
    document.getElementById('evDel').onclick = async ()=>{
      const sel = document.getElementById('evPick');
      const ns = sel.value;
      if(!ns){ status('先选一个命名空间', true); return; }
      if(!confirm('删除命名空间 ' + ns + ' 的所有事件？会改动 events/ 下的文件（有备份）。')) return;
      const r = await (await fetch('/api/event_space_delete?ns=' + encodeURIComponent(ns))).json();
      status(r.msg || (r.ok ? '已删除' : '删除失败'), !r.ok);
      if(r.ok){
        sel.dataset.loaded = '';
        sel.innerHTML = '';
        await evLoadList();
      }
    };
    document.getElementById('evFocus').onclick = ()=>{
      if(!evSel){ return; }
      evOnlyDown = true;
      evDraw(document.getElementById('evPick').value);
    };
    document.getElementById('evAll').onclick = ()=>{
      evOnlyDown = false;
      evDraw(document.getElementById('evPick').value);
    };
    document.getElementById('evFit').onclick = ()=>{
      const svg = document.getElementById('evSvg');
      if(svg._pan) svg._pan();
    };
  }
  // 双击节点 → 打开事件编辑器并选中（复用已有的 openEvents / selectEvent）
  window.openEventById = function(eid){
    const e = ((window.DATA && DATA.events) || []).find(x=>x.id === eid);
    if(!e){ status('找不到事件 ' + eid, true); return; }
    evClose();
    if(typeof openEvents === 'function'){
      openEvents();
      if(typeof selectEvent === 'function') selectEvent(e);
      status('已打开事件 ' + eid);
    }
  };
  window.mapBindEventTree = evBind;
  if(document.readyState !== 'loading') evBind();
  else document.addEventListener('DOMContentLoaded', evBind);
})();


// v1.6.0 通用：SVG 预览的滚轮缩放 + 左键拖动（只操作 viewBox）
// v1.6.1 关键：viewBox 的宽高比必须锁定成容器的比例。
// 否则 preserveAspectRatio 会按「较小的一边」重新缩放内容，拖动时画面会突然缩成一条。
function makePannable(svg, body){
  let vb = null;

  function containerAR(){
    const r = svg.getBoundingClientRect();
    return (r.width > 1 && r.height > 1) ? (r.width / r.height) : (16 / 9);
  }
  function readVB(){
    const v = (svg.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number);
    if(v.length === 4 && v.every(n=>isFinite(n))) vb = {x:v[0], y:v[1], w:v[2], h:v[3]};
  }
  function writeVB(){ if(vb) svg.setAttribute('viewBox', vb.x + ' ' + vb.y + ' ' + vb.w + ' ' + vb.h); }
  // 把 viewBox 的高锁成与容器一致（宽度为准）
  function lockAR(){
    const ar = containerAR();
    vb.h = vb.w / ar;
  }

  readVB();
  if(vb){ lockAR(); writeVB(); }

  // 滚轮缩放：以鼠标位置为中心，宽高一起变（比例锁死）
  body.addEventListener('wheel', e=>{
    readVB();
    if(!vb) return;
    e.preventDefault();
    const r = svg.getBoundingClientRect();
    if(r.width < 1 || r.height < 1) return;
    const mx = (e.clientX - r.left) / r.width;
    const my = (e.clientY - r.top) / r.height;
    const k = e.deltaY > 0 ? 1.12 : (1 / 1.12);
    const nw = Math.max(60, Math.min(vb.w * 14, vb.w * k));
    const nh = nw / containerAR();
    vb.x += (vb.w - nw) * mx;
    vb.y += (vb.h - nh) * my;
    vb.w = nw; vb.h = nh;
    writeVB();
  }, {passive: false});

  // 左键拖动平移（宽高不变，所以内容不会重新缩放）
  let dragging = false, lx = 0, ly = 0;
  body.addEventListener('mousedown', e=>{
    if(e.button !== 0) return;
    if(e.target.closest && e.target.closest('.ft-node, .ev-node')) return;
    readVB();
    if(!vb) return;
    dragging = true; lx = e.clientX; ly = e.clientY;
    body.classList.add('dragging');
    e.preventDefault();
  });
  window.addEventListener('mousemove', e=>{
    if(!dragging || !vb) return;
    const r = svg.getBoundingClientRect();
    if(r.width < 1) return;
    const dx = (e.clientX - lx) / r.width * vb.w;
    const dy = (e.clientY - ly) / r.height * vb.h;
    vb.x -= dx; vb.y -= dy;
    lx = e.clientX; ly = e.clientY;
    writeVB();      // 只改 x/y，宽高不动 → 画面不会跳
  });
  window.addEventListener('mouseup', ()=>{
    if(!dragging) return;
    dragging = false;
    body.classList.remove('dragging');
  });

  // 窗口尺寸变了要重新校正视野比例（否则 viewBox 还是旧比例，内容会偏）
  let resizeFitTimer = null;
  window.addEventListener('resize', ()=>{
    if(resizeFitTimer) clearTimeout(resizeFitTimer);
    resizeFitTimer = setTimeout(()=>{
      resizeFitTimer = null;
      const r = svg.getBoundingClientRect();
      if(r.width < 1 || r.height < 1) return;
      readVB();
      if(!vb) return;
      lockAR();
      writeVB();
    }, 180);
  });

  return function fit(){
    const srcW = Number(svg.getAttribute('data-w')) || 1000;
    const srcH = Number(svg.getAttribute('data-h')) || 1000;
    const ar = containerAR();
    // 取「能装下整块内容」的最小 viewBox（保持容器比例），再居中
    let w = Math.max(srcW, srcH * ar) * 1.04;
    let h = w / ar;
    vb = {x: (srcW - w) / 2, y: (srcH - h) / 2, w: w, h: h};
    writeVB();
  };
}


// v1.7.0 事件就地编辑
(function(){
  let curEv = null;

  function edMsg(t, bad){
    const el = document.getElementById('evEdMsg');
    if(el){ el.textContent = t; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function loadEvent(eid){
    const sv = document.getElementById('evEdSave');
    if(sv) sv.disabled = true;
    edMsg('读取中…');
    const r = await (await fetch('/api/event_detail?id=' + encodeURIComponent(eid))).json();
    if(!r.ok){ edMsg(r.msg || '读取失败', true); curEv = null; return; }
    curEv = r;
    document.querySelector('.ev-p-id').textContent = r.id + (r.file ? '　' + r.file : '');
    document.getElementById('evEdTitle').value = r.title || '';
    document.getElementById('evEdDesc').value = r.desc || '';
    document.getElementById('evEdTitleText').textContent = r.titleText || '（无翻译）';
    document.getElementById('evEdDescText').textContent = (r.descText || '（无翻译）').slice(0, 160);
    document.getElementById('evEdTitleCn').value = r.titleText || '';
    document.getElementById('evEdDescCn').value = r.descText || '';
    const box = document.getElementById('evEdOpts');
    box.innerHTML = (r.options || []).map((o, i)=>
      '<div class="o-row"><b>选项 ' + (i + 1) + '</b>' +
      '<label>name 键</label><input data-oi="' + i + '" data-k="name" value="' + (o.name || '') + '">' +
      '<label>触发事件</label><input data-oi="' + i + '" data-k="target" value="' + (o.target || '') + '">' +
      '</div>').join('') || '<div class="ev-p-hint">这个事件没有 option</div>';
    if(sv) sv.disabled = false;
    edMsg('改完点「保存到文件」');
  }

  async function saveEvent(){
    if(!curEv) return;
    const opts = [];
    document.querySelectorAll('#evEdOpts input').forEach(inp=>{
      const i = Number(inp.dataset.oi);
      opts[i] = opts[i] || {};
      opts[i][inp.dataset.k] = inp.value.trim();
    });
    const body = {
      id: curEv.id,
      title: document.getElementById('evEdTitle').value.trim(),
      desc: document.getElementById('evEdDesc').value.trim(),
      titleText: document.getElementById('evEdTitleCn').value.trim(),
      descText: document.getElementById('evEdDescCn').value.trim(),
      options: opts.filter(Boolean)
    };
    edMsg('写入中…');
    const r = await (await fetch('/api/event_edit', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)})).json();
    edMsg(r.msg || (r.ok ? '已保存' : '保存失败'), !r.ok);
    if(r.ok) status(r.msg);
  }

  function bindEd(){
    const sv = document.getElementById('evEdSave');
    if(!sv || sv.dataset.bound) return;
    sv.dataset.bound = '1';
    sv.onclick = saveEvent;
    document.getElementById('evEdOpen').onclick = ()=>{
      if(curEv && typeof window.openEventById === 'function') window.openEventById(curEv.id);
    };
  }
  window.evLoadToEditor = function(eid){ bindEd(); loadEvent(eid); };
  if(document.readyState !== 'loading') bindEd();
  else document.addEventListener('DOMContentLoaded', bindEd);
})();


// v1.9.0 矢量省界
// 位图边界放大 8 倍会变成 8px 粗的背景带；这里改用 canvas 按「屏幕像素」画 1px 线，
// 任何缩放级别下边界粗细都恒定，这是位图放大给不了的。
(function(){
  let pending = null, lastDraw = 0;

  function edgeCanvas(){
    const c = document.getElementById('mapEdgeCanvas');
    const wrap = document.getElementById('mapStageWrap');
    if(!c || !wrap) return null;
    const r = wrap.getBoundingClientRect();
    const z = uiZoom();
    const w = Math.max(1, Math.round(r.width / z));
    const h = Math.max(1, Math.round(r.height / z));
    if(c.width !== w || c.height !== h){ c.width = w; c.height = h; }
    return { c: c, ctx: c.getContext('2d'), w: w, h: h };
  }

  function draw(){
    const sc = edgeCanvas();
    if(!sc) return;
    const {ctx, w, h} = sc;
    ctx.clearRect(0, 0, w, h);
    if(!MAP.ready || !MAP.idCanvas) return;

    const k = MAP.k;
    const idc = MAP.idCanvas.getContext('2d');
    const x0 = Math.max(0, Math.floor(-MAP.x / k) - 1);
    const y0 = Math.max(0, Math.floor(-MAP.y / k) - 1);
    const x1 = Math.min(MAP.w, Math.ceil((w - MAP.x) / k) + 1);
    const y1 = Math.min(MAP.h, Math.ceil((h - MAP.y) / k) + 1);
    const cw = x1 - x0, ch = y1 - y0;
    if(cw <= 0 || ch <= 0) return;
    let data;
    try { data = idc.getImageData(x0, y0, cw, ch).data; } catch(e) { return; }

    const at = function (x, y) {
      if (x < 0 || y < 0 || x >= cw || y >= ch) return -1;
      const i = (y * cw + x) * 4;
      return (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
    };

    // 缩得太小时不画省界：13264 个省在 18% 下每省只有几像素，边界会挤成一整片白网。
    // 这时候只需要铁路/地块颜色，边界反而碍事。
    if(k < 0.42 && !window.MAP_SHOW_RAILS) return;
    if(k < 0.42 && window.MAP_SHOW_RAILS){
      // 只画铁路，边界跳过
      if(window.mapDrawRailsOn) window.mapDrawRailsOn(ctx);
      return;
    }

    // 先标出边界像素，再「连相邻的两个边界像素」成折线。
    // 只画孤立点的话，缩放越大点间距越大，看起来就是虚线。
    const isEdge = new Uint8Array(cw * ch);
    for(let y = 0; y < ch; y++){
      for(let x = 0; x < cw; x++){
        const v = at(x, y);
        if(v === -1) continue;
        if(at(x - 1, y) === v && at(x + 1, y) === v &&
           at(x, y - 1) === v && at(x, y + 1) === v) continue;
        isEdge[y * cw + x] = 1;
      }
    }

    // 线宽固定 1 屏幕像素：任何缩放级别下边界粗细都一样，这是位图给不了的
    ctx.strokeStyle = 'rgba(238,242,236,0.95)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    const sx = function(x){ return Math.round((x0 + x) * k + MAP.x) + 0.5; };
    const sy = function(y){ return Math.round((y0 + y) * k + MAP.y) + 0.5; };
    for(let y = 0; y < ch; y++){
      for(let x = 0; x < cw; x++){
        if(!isEdge[y * cw + x]) continue;
        if(x + 1 < cw && isEdge[y * cw + x + 1]){
          ctx.moveTo(sx(x), sy(y));
          ctx.lineTo(sx(x + 1), sy(y));
        }
        if(y + 1 < ch && isEdge[(y + 1) * cw + x]){
          ctx.moveTo(sx(x), sy(y));
          ctx.lineTo(sx(x), sy(y + 1));
        }
      }
    }
    ctx.stroke();

    // 铁路画在边界之后（同一个 canvas，同一次绘制）
    if(window.MAP_SHOW_RAILS && window.mapDrawRailsOn){
      window.mapDrawRailsOn(ctx);
    }
  }

  window.mapRedrawEdges = function(){ draw(); };

  // 拖动时先清掉（避免错位），停手后再重算
  window.mapDrawVectorEdges = function(immediate){
    const now = Date.now();
    if(pending) clearTimeout(pending);
    if(immediate || now - lastDraw > 120){
      lastDraw = now;
      draw();
      return;
    }
    pending = setTimeout(()=>{ pending = null; lastDraw = Date.now(); draw(); }, 90);
  };

  // 每帧 mapApply 后跟随；缩放时立即，平移时节流
  const orig = window.mapApply;
  if(typeof orig === 'function'){
    window.mapApply = function(){
      orig.apply(this, arguments);
      window.mapDrawVectorEdges(false);
    };
  }
  window.addEventListener('resize', ()=> window.mapDrawVectorEdges(true));
})();


// v1.9.2 图层预设
// 图层组合自己试很难试对（比如州视图必须关掉底图才看得清），给几个一键预设。
(function(){
  // unit = 这个视图下左键点选的对象。看什么就选什么，不用先切回省再查。
  const PRESETS = {
    terrain: { unit: 'prov',    on: ['terrain'], off: ['prov','polit','state','region','continent','base'] },
    state:   { unit: 'state',   on: ['state'],   off: ['prov','polit','terrain','region','continent','base'] },
    prov:    { unit: 'prov',    on: ['prov'],    off: ['polit','terrain','state','region','continent','base'] },
    polit:   { unit: 'country', on: ['polit'],   off: ['prov','terrain','state','region','continent','base'] },
    region:  { unit: 'region',  on: ['region'],  off: ['prov','polit','terrain','state','continent','base'] },
    raw:     { unit: 'prov',    on: ['base'],    off: ['prov','polit','terrain','state','region','continent'] },
    rail:    { unit: 'prov',    on: ['terrain'], off: ['prov','polit','state','region','continent','base'],
               rails: true },
    river:   { unit: 'prov',    on: ['terrain','rivers'], off: ['prov','polit','state','region','continent','base'] },
  };
  const ID = { prov:'mapLProv', polit:'mapLPolit', terrain:'mapLTerrain', state:'mapLState',
               region:'mapLRegion', continent:'mapLContinent', base:'mapLBase',
               rivers:'mapLRivers' };
  const OP = { prov:'prov', polit:'polit', terrain:'terrain', state:'state',
               region:'region', continent:'continent', base:'base' };

  function applyPreset(name){
    const p = PRESETS[name];
    if(!p) return;
    (p.on || []).forEach(k=>{
      const el = document.getElementById(ID[k]);
      if(el) el.checked = true;
      const op = document.querySelector('.lt-op[data-op="' + OP[k] + '"]');
      if(op) op.value = 100;
    });
    (p.off || []).forEach(k=>{
      const el = document.getElementById(ID[k]);
      if(el) el.checked = false;
    });
    // 省界始终开（矢量描边，不影响别的图层）
    const e = document.getElementById('mapLEdges');
    if(e && name !== 'raw') e.checked = false;
    window.MAP_PICK_UNIT = p.unit || 'prov';
    window.MAP_SHOW_RAILS = !!p.rails;
    if(window.mapDrawRails) window.mapDrawRails();
    if(typeof mapApplyLayers === 'function') mapApplyLayers();
    document.querySelectorAll('.lt-preset').forEach(b=>{
      b.classList.toggle('on', b.dataset.preset === name);
    });
    try{ localStorage.setItem('xuerong_layer_preset', name); }catch(err){}
  }
  window.mapApplyPreset = applyPreset;

  function bindPresets(){
    const row = document.getElementById('ltPresets');
    if(!row || row.dataset.bound) return;
    row.dataset.bound = '1';
    row.querySelectorAll('.lt-preset').forEach(b=>{
      b.onclick = ()=> applyPreset(b.dataset.preset);
    });
    // 手动改任何图层就取消预设高亮
    document.querySelectorAll('.lt-group label input[type=checkbox]').forEach(cb=>{
      cb.addEventListener('change', ()=>{
        document.querySelectorAll('.lt-preset').forEach(b=>b.classList.remove('on'));
      });
    });
  }
  window.mapBindPresets = bindPresets;
  if(document.readyState !== 'loading') bindPresets();
  else document.addEventListener('DOMContentLoaded', bindPresets);
})();


// v1.9.3 按预设决定点选对象
(function(){
  const UNIT_LABEL = { prov:'省', state:'州', country:'国家', region:'战略区' };
  let editBlock = '';

  function cur() { return window.MAP_PICK_UNIT || 'prov'; }

  // 前端没有全局 STATES（州数据是按需拉的），这里懒加载一次并缓存
  let STATE_CACHE = null;
  async function ensureStates(){
    if(STATE_CACHE) return STATE_CACHE;
    try{
      const r = await (await fetch('/api/states')).json();
      const list = Array.isArray(r) ? r : (r.states || r.list || []);
      STATE_CACHE = list;
    }catch(e){ STATE_CACHE = []; }
    return STATE_CACHE;
  }

  function stateOf(pid){
    const rec = (MAP.idx && MAP.idx[String(pid)]) || {};
    const sid = rec.state || 0;
    if(!sid) return null;
    const all = STATE_CACHE || [];
    for(const s of all){
      if(Number(s.id) === Number(sid)) return s;
    }
    return { id: sid };
  }

  function regionOf(pid){
    const rec = (MAP.idx && MAP.idx[String(pid)]) || {};
    const rid = rec.region || 0;
    if(!rid) return null;
    const list = (window.MAP && MAP.regions) || [];
    for(const r of list){ if(Number(r.id) === Number(rid)) return r; }
    return { id: rid };
  }

  function countryOf(pid){
    const st = stateOf(pid);
    if(!st) return null;
    const tag = st.owner || st.owner_tag || '';
    if(!tag) return null;
    let c = null;
    if(window.COUNTRIES){
      c = Array.isArray(COUNTRIES) ? COUNTRIES.find(x=>x.tag === tag) : COUNTRIES[tag];
    }
    return { tag: tag, raw: c || st };
  }

  // 返回要显示的信息卡 HTML；prov 模式返回 null 走原有面板
  window.mapPickUnit = async function(pid){
    await ensureStates();
    const unit = cur();
    if(unit === 'prov') return null;
    const rec = (MAP.idx && MAP.idx[String(pid)]) || {};
    let title = '', rows = [], key = '';

    if(unit === 'state'){
      const st = stateOf(pid);
      if(!st){
        const rc = (MAP.idx && MAP.idx[String(pid)]) || {};
        const typ = String(rc.type || rc.terrain || '').toLowerCase();
        const isSea = typ === 'sea' || typ === 'ocean' || typ === 'lake';
        return { unit: 'state', empty: true,
                 html: '<div class="mp-empty-card">'
                     + '<div class="mp-k">' + (isSea ? '这是海洋（不属于任何国家/州）' : '这块地不属于任何州')
                     + '</div><div class="mp-k" style="color:var(--t3);margin-top:4px">省 ' + pid
                     + '　点陆地上的省份查看详情</div></div>' };
      }
      key = 'S' + st.id;
      title = '州 ' + st.id + (st.name && st.name !== ('STATE_' + st.id) ? '　' + st.name : '');
      // /api/states 的 provinces 字段有时是数量、有时是数组，两种都要认
      const pv = st.provinces;
      const nProv = Array.isArray(pv) ? pv.length : (typeof pv === 'number' ? pv : (st.province_count || 0));
      rows.push(['省数', nProv]);
      rows.push(['归属国', st.owner || st.owner_tag || '无']);
      const vps = st.victory_points || [];
      if(vps.length) rows.push(['胜利点', vps.map(v=>v.province + '(' + v.points + ')').join(', ')]);
      if(st.category) rows.push(['类别', st.category]);
      // v1.17.0 州视图直接编辑
      window.__curStateId = st.id;
      editBlock = ''
        + '<div class="mp-k" style="margin-top:10px">改归属国</div>'
        + '<div class="mp-acts">'
        + '<input id="stOwner" placeholder="TAG" value="' + (st.owner || st.owner_tag || '') + '"'
        + ' style="height:26px;width:80px;text-transform:uppercase">'
        + '<button class="btn" id="stOwnerSave">保存</button>'
        + '</div>'
        + '<div class="mp-k" id="stOwnerMsg" style="min-height:16px"></div>'
        + '<div class="mp-k" style="margin-top:8px">开局部队</div>'
        + '<div id="provUnitsBox" style="max-height:140px;overflow:auto"></div>'
        + '<div class="mp-acts" style="margin-top:4px" id="unitActBar">'
        + '<select id="unitTpl" style="height:26px;max-width:150px;background:var(--input);border:1px solid var(--line);color:var(--text);border-radius:5px;font-size:11px">'
        + '<option value="">（选模板）</option>'
        + '</select>'
        + '<input id="unitCount" value="1" style="height:26px;width:44px" title="数量">'
        + '<button class="btn" id="unitAddBtn">加部队</button>'
        + '</div>'
        + '<div class="mp-k" id="unitMsg" style="min-height:16px"></div>'
        + '<div class="mp-k" style="margin-top:10px">类别与人力</div>'
        + '<div class="mp-acts">'
        + '<select id="mvCat" style="height:26px;background:var(--input);border:1px solid var(--line);color:var(--text);border-radius:5px">'
        + ['wasteland','enclave','tiny_island','small_island','pastoral','rural','town','large_town','city','large_city','metropolis','megalopolis'].map(function(c){
            return '<option value="' + c + '">' + c + '</option>';
          }).join('')
        + '</select>'
        + '<input id="mvManpower" placeholder="人力" style="height:26px;width:90px">'
        + '<button class="btn" id="mvCatSave">保存</button>'
        + '</div>'
        + '<div class="mp-k" id="mvCatMsg" style="min-height:16px"></div>'
        + '<div class="mp-k" style="margin-top:10px">核心领土</div>'
        + '<input id="mvCores" placeholder="TAG 空格分隔，如 GER POL" style="width:100%;box-sizing:border-box;height:26px;background:var(--input);border:1px solid var(--line);color:var(--text);border-radius:5px;padding:0 6px">'
        + '<div class="mp-acts" style="margin-top:4px"><button class="btn" id="mvCoresSave">保存核心</button></div>'
        + '<div class="mp-k" id="mvCoresMsg" style="min-height:16px"></div>'
        + '<div class="mp-k" style="margin-top:10px">建筑位</div>'
        + '<div id="mvBuildings" style="max-height:200px;overflow:auto"></div>'
        + '<div class="mp-acts" style="margin-top:4px"><button class="btn" id="mvBldSave">保存建筑</button></div>'
        + '<div class="mp-k" id="mvBldMsg" style="min-height:16px"></div>'
        + '<div class="mp-k" style="margin-top:10px">资源</div>'
        + '<div id="resBox" style="display:grid;grid-template-columns:1fr 1fr;gap:3px"></div>'
        + '<div class="mp-acts" style="margin-top:4px"><button class="btn" id="resSave">保存资源</button></div>'
        + '<div class="mp-k" id="resMsg" style="min-height:16px"></div>'
        + '<div class="mp-k" style="margin-top:10px">批量增减省</div>'
        + '<div class="mp-k" id="stProvInfo" style="color:var(--t3)">（用地图框选省后操作）</div>'
        + '<div class="mp-acts">'
        + '<button class="btn" id="stProvAdd">并入此州</button>'
        + '<button class="btn" id="stProvDel">移出此州</button>'
        + '</div>'
        + '<div class="mp-k" id="stProvMsg" style="min-height:16px"></div>'
        + '<div class="mp-k" style="margin-top:10px">拆分这个州</div>'
        + '<div class="mp-acts">'
        + '<span class="mp-k">份数</span>'
        + '<select id="stRefineK" style="height:26px;background:var(--input);border:1px solid var(--line);color:var(--text);border-radius:5px">'
        + [2,3,4,5,6].map(function(n){ return '<option value="' + n + '"' + (n===3?' selected':'') + '>' + n + '</option>'; }).join('')
        + '</select>'
        + '<button class="btn" id="stRefinePreview">预览</button>'
        + '<button class="btn" id="stRefineApply">应用</button>'
        + '</div>'
        + '<div class="mp-k" id="stRefineMsg" style="min-height:16px;line-height:1.6"></div>';
    } else if(unit === 'country'){
      const c = countryOf(pid);
      if(!c){
        const rc = (MAP.idx && MAP.idx[String(pid)]) || {};
        const typ = String(rc.type || rc.terrain || '').toLowerCase();
        const isSea = typ === 'sea' || typ === 'ocean' || typ === 'lake';
        return { unit: 'country', empty: true,
                 html: '<div class="mp-empty-card">'
                     + '<div class="mp-k">' + (isSea ? '这是海洋，没有归属国' : '这块地没有归属国')
                     + '</div><div class="mp-k" style="color:var(--t3);margin-top:4px">省 ' + pid
                     + '　点陆地省份查看国家</div></div>' };
      }
      key = 'C' + c.tag;
      title = c.tag + (c.raw && c.raw.name ? '　' + c.raw.name : '');
      if(c.raw && c.raw.capital) rows.push(['首都', c.raw.capital]);
      if(c.raw && c.raw.political_power) rows.push(['政治点', c.raw.political_power]);
    } else if(unit === 'region'){
      const r = regionOf(pid);
      if(!r){ return { unit: 'region', empty: true, html: '<div class="mp-k">这块地不属于任何战略区</div>' }; }
      key = 'R' + r.id;
      title = '战略区 ' + r.id + (r.name ? '　' + r.name : '');
    }

    const html = '<div class="mp-k" style="margin-bottom:6px">当前视图按「' + (UNIT_LABEL[unit] || unit) + '」点选</div>'
      + '<div style="font-size:13px;font-weight:600;margin-bottom:8px">' + title + '</div>'
      + rows.map(([k, v]) => '<div class="mp-row"><label>' + k + '</label><span class="mp-v">' + v + '</span></div>').join('')
      + (editBlock || '')
      + '<div class="mp-k" style="margin-top:8px">点地图上的其它位置可切换</div>';
    editBlock = '';
    return { unit: unit, key: key, html: html };
  };

  // 挂到选中流程：prov 之外的模式直接替换右侧内容
  const orig = window.mapShowOps;
  if(typeof orig === 'function'){
    window.mapShowOps = function(pid, sid){
      // 省模式完全走原逻辑，不拦（拦截会让其它预设的旧内容残留）
      if((window.MAP_PICK_UNIT || 'prov') === 'prov'){
        return orig.apply(this, arguments);
      }
      const self = this, args = arguments;
      const maybe = window.mapPickUnit(pid);
      if(!maybe || typeof maybe.then !== 'function'){
        return orig.apply(self, args);
      }
      maybe.then(function(r){
        renderPick(r, pid, sid, orig, self, args);
      });
    };

    function renderPick(r, pid, sid, origFn, self, args){
      if(!r){ return origFn.apply(self, args); }
      const side = document.getElementById('mapSide');
      if(side) side.classList.remove('empty');
      if(window.mapSideTab) window.mapSideTab('edit');
      const box = document.getElementById('selBox');
      if(box) box.innerHTML = r.html;
      status(r.empty ? '这里是空的' : ('已选中 ' + (UNIT_LABEL[r.unit] || '') + '：' + (r.key || '')));
      if(window.mapRenderSelection) window.mapRenderSelection();
    }
  }
})();


// v1.10.0 铁路可视化
(function(){
  let RAIL_DATA = null;

  async function loadRails(){
    if(RAIL_DATA) return RAIL_DATA;
    const r = await (await fetch('/api/railways')).json();
    RAIL_DATA = r.ok ? r : { items: [] };
    window.RAIL_DATA_PRE = RAIL_DATA;
    return RAIL_DATA;
  }

  // 铁路必须和矢量边界画在同一次里：两者共用 mapEdgeCanvas，
  // 边界那一步会 clearRect，单独画会被擦掉。
  window.mapDrawRailsOn = function(ctx){
    if(!window.MAP_SHOW_RAILS || !RAIL_DATA || !MAP.centers) return;
    const items = RAIL_DATA.items || [];
    if(!items.length) return;
    const k = MAP.k;
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    items.forEach(function(it){
      const baseW = (it.level || 1) * 0.7;
      // 低缩放下线宽按缩放比例压细，避免全图糊成一片
      const scaleW = k < 1 ? Math.max(0.5, baseW * k * 1.6) : baseW;
      ctx.lineWidth = Math.max(0.5, Math.min(4, scaleW));
      ctx.strokeStyle = (it.broken && it.broken.length)
        ? 'rgba(230,90,90,.95)'
        : 'rgba(240,206,120,.92)';
      ctx.beginPath();
      let started = false;
      (it.provs || []).forEach(function(pid){
        const c = MAP.centers[String(pid)];
        if(!c){ started = false; return; }
        const x = c[0] * k + MAP.x, y = c[1] * k + MAP.y;
        if(!started){ ctx.moveTo(x, y); started = true; }
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });
    ctx.restore();
  };

  // 预加载后触发一次重画
  window.mapDrawRails = async function(){
    window.RAIL_DATA_PRE = await loadRails();
    if(window.mapRedrawEdges) window.mapRedrawEdges();
  };

  // 视图变化时跟着重画（铁路跟着地图走）
  const orig = window.mapApply;
  if(typeof orig === 'function'){
    window.mapApply = function(){
      orig.apply(this, arguments);
      if(window.MAP_SHOW_RAILS && window.mapDrawRails) window.mapDrawRails();
    };
  }
})();


// v1.11.0 铁路编辑 + 补给区
(function(){
  let RAILS = null, curIdx = -1;

  function msg(t, bad){
    const el = document.getElementById('railMsg');
    if(el){ el.textContent = t; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function loadRails(){
    const stat = document.getElementById('railStat');
    if(stat) stat.textContent = '读取中（首次要建全图邻接，约 4 秒）…';
    const r = await (await fetch('/api/railways')).json();
    RAILS = r;
    if(!r.ok){ if(stat) stat.textContent = r.msg || '读取失败'; return; }
    if(stat) stat.innerHTML = '共 <b>' + r.count + '</b> 条，断连 <b style="color:var(--danger)">'
      + r.broken + '</b> 条，等级超 5 <b>' + r.over + '</b> 条';
    const box = document.getElementById('railList');
    box.innerHTML = (r.items || []).map(function(it){
      const bad = (it.broken || []).length;
      return '<div class="rail-row" data-i="' + it.i + '" style="padding:3px 6px;border-radius:4px;cursor:pointer;'
        + 'font-size:11.5px;font-family:Consolas,monospace;' + (bad ? 'color:var(--danger)' : '') + '">'
        + '#' + it.i + '  Lv' + it.level + '  ' + it.len + '省  '
        + (it.provs || []).slice(0, 4).join('-') + (it.len > 4 ? '…' : '')
        + (bad ? '  ⚠断连' + bad : '') + '</div>';
    }).join('');
    box.querySelectorAll('.rail-row').forEach(function(el){
      el.onclick = function(){ selectRail(Number(el.dataset.i)); };
    });
  }

  function selectRail(i){
    if(!RAILS || !RAILS.items) return;
    const it = RAILS.items.find(function(x){ return x.i === i; });
    if(!it) return;
    curIdx = i;
    document.querySelectorAll('#railList .rail-row').forEach(function(el){
      el.style.background = (Number(el.dataset.i) === i) ? 'var(--panel2)' : '';
    });
    document.getElementById('railEdit').style.display = 'block';
    document.getElementById('railLv').value = it.level;
    document.getElementById('railProvs').value = (it.provs || []).join(' ');
    msg('#' + i + '　' + it.len + ' 个省' + ((it.broken || []).length ? ('，断连 ' + it.broken.length + ' 段') : ''));
  }

  async function saveRail(){
    if(curIdx < 0) return;
    const lv = Number(document.getElementById('railLv').value || 1);
    const provs = document.getElementById('railProvs').value.trim().split(/\s+/).map(Number).filter(function(x){ return x > 0; });
    msg('保存中…');
    const r = await (await fetch('/api/railway_edit', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({index: curIdx, level: lv, provs: provs})})).json();
    msg(r.msg || (r.ok ? '已保存' : '保存失败'), !r.ok);
    if(r.ok){
      status(r.msg);
      if(window.RAIL_DATA_PRE) window.RAIL_DATA_PRE = null;
      if(window.mapDrawRails) window.mapDrawRails();
      await loadRails();
    }
  }

  async function delRail(){
    if(curIdx < 0) return;
    if(!confirm('删除第 ' + curIdx + ' 条铁路？会改写 railways.txt（有备份）。')) return;
    const r = await (await fetch('/api/railway_delete', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({index: curIdx})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      curIdx = -1;
      document.getElementById('railEdit').style.display = 'none';
      if(window.RAIL_DATA_PRE) window.RAIL_DATA_PRE = null;
      if(window.mapDrawRails) window.mapDrawRails();
      await loadRails();
    }
  }

  async function loadSupply(){
    const stat = document.getElementById('supStat');
    if(stat) stat.textContent = '读取中…';
    const r = await (await fetch('/api/supply_areas')).json();
    if(!r.ok){ if(stat) stat.textContent = r.msg || '读取失败'; return; }
    if(stat) stat.textContent = r.msg;
    const box = document.getElementById('supList');
    box.innerHTML = (r.items || []).map(function(a){
      return '<div style="padding:3px 6px;font-size:11.5px;font-family:Consolas,monospace">'
        + '区 ' + a.id + '　价值 ' + a.value + '　' + a.count + ' 州　'
        + '<span style="color:var(--t3)">' + (a.states || []).slice(0, 6).join(',') + '</span></div>';
    }).join('');
  }

  function bind(){
    ['railRefresh','railSave','railDel','supRefresh'].forEach(function(id){
      const el = document.getElementById(id);
      if(!el || el.dataset.bound) return;
      el.dataset.bound = '1';
      if(id === 'railRefresh') el.onclick = loadRails;
      if(id === 'railSave') el.onclick = saveRail;
      if(id === 'railDel') el.onclick = delRail;
      if(id === 'supRefresh') el.onclick = loadSupply;
    });
  }
  window.mapBindRail = bind;
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.12.0 地形编辑
(function(){
  let TYPES = null, curPid = 0;

  async function loadTypes(){
    if(TYPES) return TYPES;
    try{
      const r = await (await fetch('/api/terrain_types')).json();
      TYPES = (r.items || []).filter(function(x){ return x.writable; });
    }catch(e){ TYPES = []; }
    const sel = document.getElementById('msTerrainSel');
    if(sel){
      sel.innerHTML = TYPES.map(function(x){
        return '<option value="' + x.type + '">' + x.type +
               (x.count ? ' (' + x.count + ')' : '') + '</option>';
      }).join('');
    }
    return TYPES;
  }

  function tmsg(t, bad){
    const el = document.getElementById('msTerrainMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  // 选中省变化时同步显示
  const origShow = window.mapShowOps;
  if(typeof origShow === 'function'){
    window.mapShowOps = function(pid, sid){
      const r = origShow.apply(this, arguments);
      curPid = pid;
      loadTypes().then(function(){
        const rec = (MAP.idx && MAP.idx[String(pid)]) || {};
        const el = document.getElementById('msTerrain');
        if(el) el.textContent = rec.terrain || '未知';
        const sel = document.getElementById('msTerrainSel');
        if(sel && rec.terrain){
          for(const op of sel.options){ if(op.value === rec.terrain){ sel.value = rec.terrain; break; } }
        }
        tmsg('');
      });
      return r;
    };
  }

  async function apply(){
    const sel = document.getElementById('msTerrainSel');
    if(!sel || !curPid){ tmsg('先在地图上选一个省', true); return; }
    const want = sel.value;
    tmsg('写入中…');
    const r = await (await fetch('/api/terrain_set', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({pid: curPid, terrain: want})})).json();
    tmsg(r.msg || (r.ok ? '已应用' : '失败'), !r.ok);
    if(r.ok){
      status(r.msg);
      const el = document.getElementById('msTerrain');
      if(el) el.textContent = want;
      if(MAP.idx && MAP.idx[String(curPid)]) MAP.idx[String(curPid)].terrain = want;
      // 地形图变了，自动重建地形层（否则地图上还是旧颜色）
      tmsg(r.msg + '　正在重建地形图层…');
      try{
        const br = await (await fetch('/api/map_build', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({force:true})})).json();
        tmsg(r.msg + (br.ok ? '　图层已重建' : '　图层重建失败'), !br.ok);
        if(br.ok && window.mapReloadLayers) window.mapReloadLayers();
      }catch(e){ tmsg(r.msg + '　图层重建失败：' + e.message, true); }
    }
  }

  function bind(){
    const b = document.getElementById('msTerrainApply');
    if(!b || b.dataset.bound) return;
    b.dataset.bound = '1';
    b.onclick = apply;
    loadTypes();
  }
  window.mapBindTerrain = bind;
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.12.1 场地形批量 / 按类型 / 画笔
(function(){
  let BRUSH_ON = false, BRUSH_PTS = [], BRUSH_DOWN = false;

  function bmsg(t, bad){
    const el = document.getElementById('msBatchMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function fillTwoSel(retry){
    const sel = document.getElementById('msTerrainSel');
    if(!sel) return;
    // 地形类型是异步拉的，可能比这里晚；没填满就再等一轮
    if(sel.options.length === 0 && (retry || 0) < 20){
      setTimeout(function(){ fillTwoSel((retry || 0) + 1); }, 300);
      return;
    }
    ['msFromType','msToType'].forEach(function(id){
      const el = document.getElementById(id);
      if(!el || el.options.length) return;
      el.innerHTML = Array.from(sel.options).map(function(o){
        return '<option value="' + o.value + '">' + o.textContent + '</option>';
      }).join('');
    });
  }

  function selectedPids(){
    const sel = Array.isArray(MAP.sel) ? MAP.sel : (MAP.sel ? [MAP.sel] : []);
    if(sel.length) return sel.slice();
    return [];
  }

  async function batchApply(){
    const pids = selectedPids();
    const sel = document.getElementById('msTerrainSel');
    if(!pids.length){ bmsg('先在地图上选中省（拖框可多选）', true); return; }
    if(!sel || !sel.value){ bmsg('先选一种地形', true); return; }
    bmsg('写入中（' + pids.length + ' 个省）…');
    const r = await (await fetch('/api/terrain_batch', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({pids: pids, terrain: sel.value})})).json();
    bmsg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      pids.forEach(function(p){ if(MAP.idx && MAP.idx[String(p)]) MAP.idx[String(p)].terrain = sel.value; });
      await rebuildMap();
    }
  }

  async function typeApply(){
    const from = document.getElementById('msFromType');
    const to = document.getElementById('msToType');
    if(!from || !to || !from.value || !to.value){ bmsg('选源类型和目标类型', true); return; }
    if(from.value === to.value){ bmsg('源和目标相同', true); return; }
    bmsg('转换中…');
    const r = await (await fetch('/api/terrain_by_type', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({from: from.value, to: to.value})})).json();
    bmsg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await rebuildMap(); }
  }

  async function rebuildMap(){
    try{
      const br = await (await fetch('/api/map_build', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({force:true})})).json();
      if(br.ok && window.mapReloadLayers) window.mapReloadLayers();
    }catch(e){}
  }

  async function flushBrush(){
    if(!BRUSH_PTS.length) return;
    const sel = document.getElementById('msTerrainSel');
    const size = Number(document.getElementById('msBrushSize').value || 5);
    const pts = BRUSH_PTS.slice();
    BRUSH_PTS = [];
    const r = await (await fetch('/api/terrain_paint', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({points: pts, terrain: sel ? sel.value : '', brush: size})})).json();
    bmsg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await rebuildMap(); }
  }

  function bind(){
    const b1 = document.getElementById('msBatchApply');
    if(b1 && !b1.dataset.bound){ b1.dataset.bound='1'; b1.onclick = batchApply; }
    const b2 = document.getElementById('msTypeApply');
    if(b2 && !b2.dataset.bound){ b2.dataset.bound='1'; b2.onclick = typeApply; }
    const b3 = document.getElementById('msBrushToggle');
    if(b3 && !b3.dataset.bound){
      b3.dataset.bound='1';
      b3.onclick = function(){
        BRUSH_ON = !BRUSH_ON;
        b3.textContent = BRUSH_ON ? '关闭笔刷' : '开启笔刷';
        b3.style.color = BRUSH_ON ? 'var(--accent)' : '';
        status(BRUSH_ON ? '笔刷已开启：按住左键拖动刷地形，松手保存' : '笔刷已关闭');
      };
    }
    const sr = document.getElementById('msBrushSize');
    if(sr && !sr.dataset.bound){
      sr.dataset.bound='1';
      sr.oninput = function(){
        const v = document.getElementById('msBrushSizeV');
        if(v) v.textContent = sr.value;
      };
    }
    fillTwoSel();
  }
  window.mapBindBatch = bind;
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);

  // 选中省数变化时更新提示
  const origSel = window.mapRenderSelection;
  if(typeof origSel === 'function'){
    window.mapRenderSelection = function(){
      const r = origSel.apply(this, arguments);
      const n = selectedPids().length;
      const el = document.getElementById('msBatchInfo');
      if(el) el.textContent = n ? ('已选 ' + n + ' 个省') : '未选中';
      return r;
    };
  }

  // 笔刷拦截地图拖动
  window.mapBrushActive = function(){ return BRUSH_ON; };
  window.mapBrushDown = function(x, y){
    if(!BRUSH_ON) return false;
    BRUSH_DOWN = true;
    BRUSH_PTS.push([Math.round(x), Math.round(y)]);
    return true;
  };
  window.mapBrushMove = function(x, y){
    if(!BRUSH_ON || !BRUSH_DOWN) return false;
    BRUSH_PTS.push([Math.round(x), Math.round(y)]);
    return true;
  };
  window.mapBrushUp = function(){
    if(!BRUSH_ON || !BRUSH_DOWN) return false;
    BRUSH_DOWN = false;
    flushBrush();
    return true;
  };
})();


// v1.12.1 地形笔刷的地图事件（和选择省互斥，笔刷开着就吃掉左键）
(function(){
  const BRUSH_EVENTS = true;
  const wrap = document.getElementById('mapStageWrap');
  if(!wrap) return;
  let down = false;

  wrap.addEventListener('pointerdown', e=>{
    if(!window.mapBrushActive || !window.mapBrushActive()) return;
    if(e.button !== 0) return;
    if(typeof mapEventOverUI === 'function' && mapEventOverUI(e)) return;
    const p = mapScreenToImage(e.clientX, e.clientY);
    if(window.mapBrushDown && window.mapBrushDown(p.x, p.y)){
      down = true;
      wrap.classList.add('dragging');
      e.stopPropagation();
      e.preventDefault();
    }
  }, true);

  wrap.addEventListener('pointermove', e=>{
    if(!down) return;
    const now = Date.now();
    if(!wrap._lastBrush || now - wrap._lastBrush < 35) return;
    wrap._lastBrush = now;
    const p = mapScreenToImage(e.clientX, e.clientY);
    if(window.mapBrushMove) window.mapBrushMove(p.x, p.y);
    e.stopPropagation();
  }, true);

  const up = function(e){
    if(!down) return;
    down = false;
    wrap.classList.remove('dragging');
    if(window.mapBrushUp) window.mapBrushUp();
    e.stopPropagation();
  };
  wrap.addEventListener('pointerup', up, true);
  window.addEventListener('pointerup', up, true);
})();


// v1.13.0 战略区
(function(){
  let SRS = null, curSR = -1;

  function smsg(t, bad){
    const el = document.getElementById('srMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function selPids(){
    const sel = Array.isArray(MAP.sel) ? MAP.sel : (MAP.sel ? [MAP.sel] : []);
    return sel.slice();
  }

  async function loadSR(){
    const stat = document.getElementById('srStat');
    if(stat) stat.textContent = '读取中…';
    const r = await (await fetch('/api/strategic_regions')).json();
    SRS = r;
    if(!r.ok){ if(stat) stat.textContent = r.msg || '读取失败'; return; }
    if(stat) stat.innerHTML = '共 <b>' + r.count + '</b> 个战略区';
    const box = document.getElementById('srList');
    box.innerHTML = (r.items || []).map(function(it){
      return '<div class="sr-row" data-i="' + it.id + '" style="padding:3px 6px;border-radius:4px;cursor:pointer;'
        + 'font-size:11.5px;font-family:Consolas,monospace;'
        + (it.fromMod ? '' : 'opacity:.55') + '">'
        + '#' + it.id + '　' + it.count + '省　'
        + '<span style="color:var(--t3)">' + it.name + '</span>'
        + (it.fromMod ? '' : ' <span style="color:var(--t3)">(原版)</span>') + '</div>';
    }).join('');
    box.querySelectorAll('.sr-row').forEach(function(el){
      el.onclick = function(){ pickSR(Number(el.dataset.i)); };
    });
  }

  function pickSR(id){
    if(!SRS || !SRS.items) return;
    const it = SRS.items.find(function(x){ return x.id === id; });
    if(!it) return;
    curSR = id;
    document.querySelectorAll('#srList .sr-row').forEach(function(el){
      el.style.background = (Number(el.dataset.i) === id) ? 'var(--panel2)' : '';
    });
    document.getElementById('srEdit').style.display = 'block';
    document.getElementById('srCur').textContent =
      '#' + id + '　' + it.name + '　' + it.count + ' 省' + (it.fromMod ? '' : '（原版只读）');
    document.getElementById('srDel').disabled = !it.fromMod;
    document.getElementById('srApplyProvs').disabled = !it.fromMod;
  }

  async function createSR(){
    const pids = selPids();
    if(!pids.length){ smsg('先在地图上选中省（拖框可多选）', true); return; }
    const idEl = document.getElementById('srNewId');
    const nameEl = document.getElementById('srNewName');
    smsg('创建中…');
    const r = await (await fetch('/api/sr_create', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: idEl.value.trim() || null,
                            name: nameEl.value.trim() || null,
                            provinces: pids})})).json();
    smsg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); idEl.value = ''; nameEl.value = ''; await loadSR(); }
  }

  async function applyProvs(){
    if(curSR < 0) return;
    const pids = selPids();
    if(!pids.length){ smsg('先在地图上选中省', true); return; }
    smsg('写入中…');
    const r = await (await fetch('/api/sr_set_provinces', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: curSR, provinces: pids})})).json();
    smsg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await loadSR(); }
  }

  async function delSR(){
    if(curSR < 0) return;
    if(!confirm('删除战略区 ' + curSR + '？（会摘掉整个块，文件里没有其它块就删文件）')) return;
    const r = await (await fetch('/api/sr_delete', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: curSR})})).json();
    smsg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      curSR = -1;
      document.getElementById('srEdit').style.display = 'none';
      await loadSR();
    }
  }

  function bind(){
    [['srRefresh', loadSR], ['srCreate', createSR],
     ['srApplyProvs', applyProvs], ['srDel', delSR]].forEach(function(pair){
      const el = document.getElementById(pair[0]);
      if(!el || el.dataset.bound) return;
      el.dataset.bound = '1';
      el.onclick = pair[1];
    });
  }
  window.mapBindSR = bind;
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.14.0 海峡 / 连接
(function(){
  let ADJS = null, curLine = -1;

  function amsg(t, bad){
    const el = document.getElementById('adjMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function loadAdj(){
    const stat = document.getElementById('adjStat');
    if(stat) stat.textContent = '读取中…';
    const r = await (await fetch('/api/adjacencies')).json();
    ADJS = r;
    if(!r.ok){ if(stat) stat.textContent = r.msg || '读取失败'; return; }
    if(stat) stat.textContent = r.msg + (r.fromMod ? '' : '（原版只读）');
    const box = document.getElementById('adjList');
    box.innerHTML = (r.items || []).map(function(it){
      const tn = it.type || '(空)';
      const col = tn === 'sea' ? 'var(--accent)' : (tn === 'impassable' ? 'var(--danger)' : 'var(--t3)');
      return '<div class="adj-row" data-l="' + it.line + '" style="padding:2px 6px;border-radius:4px;cursor:pointer;'
        + 'font-size:11.5px;font-family:Consolas,monospace">'
        + '行' + it.line + '　' + it.from + '↔' + it.to + '　'
        + '<span style="color:' + col + '">' + tn + '</span>'
        + (it.rule ? '　<span style="color:var(--t3)">' + it.rule + '</span>' : '')
        + (it.comment ? '　<span style="color:var(--t3)">' + it.comment + '</span>' : '')
        + '</div>';
    }).join('');
    box.querySelectorAll('.adj-row').forEach(function(el){
      el.onclick = function(){ pickAdj(Number(el.dataset.l)); };
    });
  }

  function pickAdj(line){
    if(!ADJS || !ADJS.items) return;
    const it = ADJS.items.find(function(x){ return x.line === line; });
    if(!it) return;
    curLine = line;
    document.querySelectorAll('#adjList .adj-row').forEach(function(el){
      el.style.background = (Number(el.dataset.l) === line) ? 'var(--panel2)' : '';
    });
    document.getElementById('adjEdit').style.display = 'block';
    document.getElementById('adjCur').textContent =
      '行 ' + line + '　' + it.from + ' ↔ ' + it.to + '　当前 ' + (it.type || '(空)');
    const sel = document.getElementById('adjTypeSel');
    if(sel && it.type){ sel.value = it.type; }
  }

  async function applyType(){
    if(curLine < 0) return;
    const sel = document.getElementById('adjTypeSel');
    amsg('写入中…');
    const r = await (await fetch('/api/adj_edit', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({line: curLine, type: sel.value})})).json();
    amsg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await loadAdj(); }
  }

  async function delAdj(){
    if(curLine < 0) return;
    if(!confirm('删除第 ' + curLine + ' 行连接？')) return;
    const r = await (await fetch('/api/adj_delete', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({line: curLine})})).json();
    amsg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      curLine = -1;
      document.getElementById('adjEdit').style.display = 'none';
      await loadAdj();
    }
  }

  async function addAdj(){
    const f = document.getElementById('adjFrom').value.trim();
    const t = document.getElementById('adjTo').value.trim();
    const ty = document.getElementById('adjNewType').value;
    if(!f || !t){ amsg('填两端省号', true); return; }
    amsg('新增中…');
    const r = await (await fetch('/api/adj_add', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({from: Number(f), to: Number(t), type: ty})})).json();
    amsg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      document.getElementById('adjFrom').value = '';
      document.getElementById('adjTo').value = '';
      await loadAdj();
    }
  }

  function bind(){
    [['adjRefresh', loadAdj], ['adjApplyType', applyType],
     ['adjDel', delAdj], ['adjAdd', addAdj]].forEach(function(pair){
      const el = document.getElementById(pair[0]);
      if(!el || el.dataset.bound) return;
      el.dataset.bound = '1';
      el.onclick = pair[1];
    });
  }
  window.mapBindAdj = bind;
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.15.0 装备变体编辑
(function(){
  let EQ = null, curId = '', pending = {};

  function emsg(t, bad){
    const el = document.getElementById('eqMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function loadList(){
    const stat = document.getElementById('eqStat');
    const q = (document.getElementById('eqSearch').value || '').trim();
    if(stat) stat.textContent = '读取中…';
    const r = await (await fetch('/api/equipment_list?q=' + encodeURIComponent(q))).json();
    EQ = r;
    if(!r.ok){ if(stat) stat.textContent = r.msg || '读取失败'; return; }
    if(stat) stat.textContent = r.msg + (r.total > 400 ? '（只显示前 400 个）' : '');
    const box = document.getElementById('eqList');
    box.innerHTML = (r.items || []).map(function(it){
      return '<div class="eq-row" data-id="' + it.id + '" style="padding:2px 6px;border-radius:4px;'
        + 'cursor:pointer;font-size:11.5px;font-family:Consolas,monospace">'
        + it.id + '　<span style="color:var(--t3)">' + (it.name || '') + '</span>'
        + (it.year ? '　' + it.year : '') + '</div>';
    }).join('');
    box.querySelectorAll('.eq-row').forEach(function(el){
      el.onclick = function(){ pickEq(el.dataset.id); };
    });
  }

  async function pickEq(id){
    curId = id;
    pending = {};
    document.querySelectorAll('#eqList .eq-row').forEach(function(el){
      el.style.background = (el.dataset.id === id) ? 'var(--panel2)' : '';
    });
    emsg('读取中…');
    const r = await (await fetch('/api/equipment_detail?id=' + encodeURIComponent(id))).json();
    if(!r.ok){ emsg(r.msg || '失败', true); return; }
    document.getElementById('eqEdit').style.display = 'block';
    document.getElementById('eqCur').innerHTML =
      '<b>' + r.id + '</b>　' + (r.name || '') +
      (r.archetype ? '　<span style="color:var(--t3)">底盘 ' + r.archetype + '</span>' : '') +
      (r.year ? '　' + r.year : '') +
      (r.readonly ? '　<span style="color:var(--danger)">原版只读</span>' : '');
    document.getElementById('eqFile').textContent = r.file || '';

    // 属性表
    const sc = r.scalars || {};
    const keys = Object.keys(sc).sort();
    document.getElementById('eqProps').innerHTML = keys.map(function(k){
      return '<div style="display:flex;gap:6px;align-items:center;padding:1px 0">'
        + '<span style="width:170px;font-size:11.5px;font-family:Consolas,monospace;color:var(--t2)">' + k + '</span>'
        + '<input class="eq-val" data-k="' + k + '" value="' + String(sc[k]).replace(/"/g,'&quot;') + '"'
        + ' style="flex:1;height:22px;font-size:11.5px;font-family:Consolas,monospace;'
        + 'background:var(--input);border:1px solid var(--line);color:var(--text);border-radius:4px;padding:0 5px"'
        + (r.readonly ? ' disabled' : '') + '></div>';
    }).join('');
    document.getElementById('eqProps').querySelectorAll('.eq-val').forEach(function(inp){
      inp.oninput = function(){ pending[inp.dataset.k] = inp.value; };
    });

    // 槽
    const slots = r.slots || [];
    document.getElementById('eqSlots').innerHTML = slots.length
      ? slots.map(function(s){
          return '· <b>' + s.slot + '</b>' + (s.required ? '　必装' : '　可选')
            + (s.categories.length ? '　[' + s.categories.join(', ') + ']' : '');
        }).join('<br>')
      : '（这个装备没有模块槽）';

    // 引用
    const refs = r.refs || [];
    document.getElementById('eqRefs').textContent = refs.length
      ? refs.join('\n') : '（没有其它文件引用）';

    emsg(r.msg || '');
    document.getElementById('eqSave').disabled = !!r.readonly;
    document.getElementById('eqDel').disabled = !!r.readonly;
    document.getElementById('eqAddProp').disabled = !!r.readonly;
  }

  async function save(){
    if(!curId) return;
    const props = Object.assign({}, pending);
    // 新属性
    const nk = document.getElementById('eqNewKey').value.trim();
    const nv = document.getElementById('eqNewVal').value.trim();
    if(nk && nv) props[nk] = nv;
    if(!Object.keys(props).length){ emsg('没有改动', true); return; }
    emsg('写入中…');
    const r = await (await fetch('/api/equipment_edit', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: curId, props: props})})).json();
    emsg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      pending = {};
      document.getElementById('eqNewKey').value = '';
      document.getElementById('eqNewVal').value = '';
      await pickEq(curId);
    }
  }

  async function del(){
    if(!curId) return;
    if(!confirm('删除装备 ' + curId + '？（有其它引用会被拒绝）')) return;
    const r = await (await fetch('/api/equipment_delete', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: curId})})).json();
    emsg(r.msg || '', !r.ok);
    if(r.ok){
      status(r.msg);
      curId = '';
      document.getElementById('eqEdit').style.display = 'none';
      await loadList();
    }
  }

  function bind(){
    [['eqRefresh', loadList], ['eqSave', save], ['eqDel', del],
     ['eqAddProp', function(){ save(); }]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(!el || el.dataset.bound) return;
      el.dataset.bound = '1';
      el.onclick = p[1];
    });
    const sb = document.getElementById('eqSearch');
    if(sb && !sb.dataset.bound){
      sb.dataset.bound = '1';
      sb.onkeydown = function(e){ if(e.key === 'Enter') loadList(); };
    }
  }
  window.mapBindEquip = bind;
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.17.0 州视图编辑：改归属国 + 批量增减省
(function(){
  function smsg(id, t, bad){
    const el = document.getElementById(id);
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  function selPids(){
    const s = Array.isArray(MAP.sel) ? MAP.sel : (MAP.sel ? [MAP.sel] : []);
    return s.slice();
  }

  async function saveOwner(){
    const el = document.getElementById('stOwner');
    const sid = window.__curStateId;
    if(!sid){ smsg('stOwnerMsg', '先选一个州', true); return; }
    const tag = (el && el.value || '').trim().toUpperCase();
    if(!tag){ smsg('stOwnerMsg', '填 TAG', true); return; }
    smsg('stOwnerMsg', '写入中…');
    const r = await (await fetch('/api/state_save', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: sid, fields: {owner: tag}})})).json();
    smsg('stOwnerMsg', r.msg || (r.ok ? '已保存' : '失败'), !r.ok);
    if(r.ok){ status(r.msg); }
  }

  async function moveProvs(detach){
    const sid = window.__curStateId;
    if(!sid){ smsg('stProvMsg', '先选一个州', true); return; }
    const pids = selPids();
    if(!pids.length){ smsg('stProvMsg', '先在地图上框选省（拖框可多选）', true); return; }
    smsg('stProvMsg', '写入中（' + pids.length + ' 个省）…');
    let okN = 0; const fail = [];
    for(const pid of pids){
      try{
        const r = await (await fetch('/api/state_province', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({pid: pid, target_sid: detach ? null : sid})})).json();
        if(r.ok) okN++; else fail.push(pid);
      }catch(e){ fail.push(pid); }
    }
    smsg('stProvMsg',
      (detach ? '移出 ' : '并入 ') + okN + ' 个省' +
      (fail.length ? '，失败 ' + fail.length + ' 个：' + fail.slice(0, 5).join(',') : ''),
      fail.length > 0);
    if(okN) status((detach ? '移出 ' : '并入 ') + okN + ' 个省');
  }

  function bindStateUI(){
    if((window.MAP_PICK_UNIT || 'prov') !== 'state') return;
    const b1 = document.getElementById('stOwnerSave');
    if(b1 && !b1.dataset.bound){ b1.dataset.bound = '1'; b1.onclick = saveOwner; }
    const b2 = document.getElementById('stProvAdd');
    if(b2 && !b2.dataset.bound){ b2.dataset.bound = '1'; b2.onclick = function(){ moveProvs(false); }; }
    const b3 = document.getElementById('stProvDel');
    if(b3 && !b3.dataset.bound){ b3.dataset.bound = '1'; b3.onclick = function(){ moveProvs(true); }; }
    const info = document.getElementById('stProvInfo');
    if(info){
      const n = selPids().length;
      info.textContent = n ? ('已选 ' + n + ' 个省') : '（用地图框选省后操作）';
    }
  }

  // 包一层 mapShowOps，渲染完成后绑按钮
  const origShow = window.mapShowOps;
  if(typeof origShow === 'function'){
    window.mapShowOps = function(){
      const r = origShow.apply(this, arguments);
      setTimeout(bindStateUI, 120);
      return r;
    };
  }
})();


// v1.18.0 州细化
(function(){
  function rmsg(t, bad){
    const el = document.getElementById('stRefineMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function preview(){
    const sid = window.__curStateId;
    if(!sid){ rmsg('先选一个州', true); return; }
    const k = Number((document.getElementById('stRefineK') || {}).value || 3);
    rmsg('计算中…');
    const r = await (await fetch('/api/state_refine_preview?sid=' + sid + '&k=' + k)).json();
    if(!r.ok){ rmsg(r.msg || '失败', true); return; }
    const lines = [r.msg];
    (r.warnings || []).forEach(function(w){ lines.push('⚠ ' + w); });
    (r.parts || []).forEach(function(p){
      lines.push('组 ' + (p.i + 1) + '：' + p.count + ' 省　' + p.provs.slice(0, 6).join(',') + (p.count > 6 ? '…' : ''));
    });
    rmsg(lines.join(String.fromCharCode(10)));
  }

  async function apply(){
    const sid = window.__curStateId;
    if(!sid){ rmsg('先选一个州', true); return; }
    const k = Number((document.getElementById('stRefineK') || {}).value || 3);
    if(!confirm('把州 ' + sid + ' 拆成 ' + k + ' 份？第 1 组留在原州，其余各建新州（有备份）。')) return;
    rmsg('拆分中…');
    const r = await (await fetch('/api/state_refine', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({sid: sid, k: k})})).json();
    rmsg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); }
  }

  // 绑到州视图的渲染流程
  const orig = window.mapShowOps;
  if(typeof orig === 'function'){
    window.mapShowOps = function(){
      const r = orig.apply(this, arguments);
      setTimeout(function(){
        if((window.MAP_PICK_UNIT || 'prov') !== 'state') return;
        const b1 = document.getElementById('stRefinePreview');
        if(b1 && !b1.dataset.bound){ b1.dataset.bound = '1'; b1.onclick = preview; }
        const b2 = document.getElementById('stRefineApply');
        if(b2 && !b2.dataset.bound){ b2.dataset.bound = '1'; b2.onclick = apply; }
      }, 160);
      return r;
    };
  }
})();


// v1.19.0 孤儿 tag 诊断 + 严格模式
(function(){
  async function checkOrphans(){
    const stat = document.getElementById('orphanStat');
    const box = document.getElementById('orphanList');
    if(stat) stat.textContent = '检查中…';
    const r = await (await fetch('/api/orphan_tags')).json();
    if(!r.ok){ if(stat) stat.textContent = r.msg || '失败'; return; }
    if(stat){
      stat.innerHTML = '<b>' + r.count + '</b> 个孤儿 tag　涉及 <b>' + r.total_states
        + '</b>/' + r.states_all + ' 州　<b>' + r.total_provinces + '</b> 省<br>'
        + '<span style="color:var(--t3)">国家表 ' + r.countries_all + ' 个，其中 '
        + r.unused_count + ' 个没有任何州</span>';
    }
    if(!box) return;
    if(!r.count){
      box.innerHTML = '<div class="mp-k" style="color:var(--t3)">州引用的 owner 都在国家表里</div>';
      return;
    }
    box.innerHTML = (r.items || []).map(function(it){
      return '<div style="padding:3px 6px;border-bottom:1px solid var(--line);font-size:11.5px;'
        + 'font-family:Consolas,monospace">'
        + '<b style="color:var(--danger)">' + it.tag + '</b>　'
        + it.states + ' 州 / ' + it.provinces + ' 省<br>'
        + '<span style="color:var(--t3)">州 ' + (it.sample_states || []).join(',') + '</span>'
        + '</div>';
    }).join('');
  }

  function bind(){
    const b = document.getElementById('orphanBtn');
    if(b && !b.dataset.bound){ b.dataset.bound = '1'; b.onclick = checkOrphans; }
    const st = document.getElementById('mapLStrict');
    if(st && !st.dataset.bound){
      st.dataset.bound = '1';
      st.onchange = function(){ if(typeof mapApplyLayers === 'function') mapApplyLayers(); };
    }
  }
  window.mapBindOrphan = bind;
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.0 州视图编辑补全：类别 / 人力 / cores / 建筑位
(function(){
  let SD = null;
  const BUILDINGS = ['infrastructure','arms_factory','industrial_complex','air_base',
    'anti_air_building','synthetic_refinery','dockyard','naval_base','rocket_site',
    'radar_station','nuclear_reactor','supply_hub'];

  function m(t, id, bad){
    const el = document.getElementById(id);
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function loadSD(){
    const sid = window.__curStateId;
    if(!sid) return;
    try{
      SD = await (await fetch('/api/state?id=' + sid + '&full=1')).json();
    }catch(e){ SD = null; }
    if(!SD) return;
    const cat = document.getElementById('mvCat');
    if(cat && SD.category){
      for(const op of cat.options){ if(op.value === SD.category){ cat.value = SD.category; break; } }
    }
    const mp = document.getElementById('mvManpower');
    if(mp && SD.manpower != null) mp.value = SD.manpower;
    const co = document.getElementById('mvCores');
    if(co) co.value = (SD.cores || []).join(' ');
    const box = document.getElementById('mvBuildings');
    if(box){
      const cur = SD.buildings || {};
      box.innerHTML = BUILDINGS.map(function(b){
        const v = (cur[b] != null ? cur[b] : '');
        return '<div style="display:flex;gap:6px;align-items:center;padding:1px 0">'
          + '<span style="width:148px;font-size:11.5px;font-family:Consolas,monospace;color:var(--t2)">' + b + '</span>'
          + '<input class="mv-bld" data-b="' + b + '" value="' + v + '" placeholder="0"'
          + ' style="flex:1;height:22px;font-size:11.5px;font-family:Consolas,monospace;'
          + 'background:var(--input);border:1px solid var(--line);color:var(--text);border-radius:4px;padding:0 5px">'
          + '</div>';
      }).join('');
    }
  }

  async function save(kind){
    const sid = window.__curStateId;
    if(!sid) return;
    const fields = {};
    let mid = 'mvCatMsg';
    if(kind === 'cat'){
      const cat = document.getElementById('mvCat');
      const mp = document.getElementById('mvManpower');
      if(cat) fields.category = cat.value;
      if(mp && mp.value.trim()) fields.manpower = mp.value.trim();
    } else if(kind === 'cores'){
      mid = 'mvCoresMsg';
      const co = document.getElementById('mvCores');
      fields.cores = ((co && co.value) || '').trim().split(/\s+/).filter(Boolean)
        .map(function(x){ return x.toUpperCase(); });
    } else {
      mid = 'mvBldMsg';
      const b = {};
      document.querySelectorAll('#mvBuildings .mv-bld').forEach(function(inp){
        const v = inp.value.trim();
        if(v !== '' && !isNaN(Number(v))) b[inp.dataset.b] = Number(v);
      });
      fields.buildings = b;
    }
    m('写入中…', mid);
    const r = await (await fetch('/api/state_save', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: sid, fields: fields})})).json();
    m(r.msg || (r.ok ? '已保存' : '失败'), mid, !r.ok);
    if(r.ok) status(r.msg);
  }

  function bindSD(){
    if((window.MAP_PICK_UNIT || 'prov') !== 'state') return;
    [['mvCatSave', function(){ save('cat'); }],
     ['mvCoresSave', function(){ save('cores'); }],
     ['mvBldSave', function(){ save('bld'); }]].forEach(function(p){
      const el = document.getElementById(p[0]);
      if(el && !el.dataset.bound){ el.dataset.bound = '1'; el.onclick = p[1]; }
    });
    if(document.getElementById('mvCat')) loadSD();
  }

  const orig = window.mapShowOps;
  if(typeof orig === 'function'){
    window.mapShowOps = function(){
      const r = orig.apply(this, arguments);
      setTimeout(bindSD, 180);
      return r;
    };
  }
})();


// v1.22.0 补给区增删改
(function(){
  function msg(t, bad){
    const el = document.getElementById('supMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function loadSup(){
    const stat = document.getElementById('supStat');
    const box = document.getElementById('supList');
    if(stat) stat.textContent = '读取中…';
    const r = await (await fetch('/api/supply_areas')).json();
    if(!r.ok){ if(stat) stat.textContent = r.msg || '失败'; return; }
    if(stat) stat.textContent = r.msg;
    if(!box) return;
    box.innerHTML = (r.items || []).map(function(a){
      return '<div style="display:flex;align-items:center;gap:6px;padding:2px 6px;'
        + 'font-size:11.5px;font-family:Consolas,monospace">'
        + '<span style="flex:1">区 ' + a.id + '　价值 ' + a.value + '　' + a.count + ' 州</span>'
        + '<button class="btn sup-del" data-id="' + a.id + '" style="height:20px;font-size:10px;padding:0 6px">删</button>'
        + '<button class="btn sup-edit" data-id="' + a.id + '" data-v="' + a.value + '"'
        + ' data-s="' + (a.states || []).join(' ') + '" style="height:20px;font-size:10px;padding:0 6px">改</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.sup-del').forEach(function(b){
      b.onclick = async function(){
        if(!confirm('删除补给区 ' + b.dataset.id + '？')) return;
        const r2 = await (await fetch('/api/supply_delete', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({id: Number(b.dataset.id)})})).json();
        msg(r2.msg || '', !r2.ok);
        if(r2.ok){ status(r2.msg); await loadSup(); }
      };
    });
    box.querySelectorAll('.sup-edit').forEach(function(b){
      b.onclick = function(){
        document.getElementById('supId').value = b.dataset.id;
        document.getElementById('supValue').value = b.dataset.v;
        document.getElementById('supStates').value = b.dataset.s;
        msg('已填入表单，改完点保存');
      };
    });
  }

  async function saveSup(){
    const id = Number(document.getElementById('supId').value || 0);
    const val = document.getElementById('supValue').value.trim();
    const st = document.getElementById('supStates').value.trim();
    if(!id){ msg('填 id', true); return; }
    const states = st ? st.split(/\s+/).map(Number).filter(function(x){ return x > 0; }) : null;
    msg('写入中…');
    const r = await (await fetch('/api/supply_save', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: id, value: val || null, states: states})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await loadSup(); }
  }

  function bind(){
    const b = document.getElementById('supNewBtn');
    if(b && !b.dataset.bound){ b.dataset.bound = '1'; b.onclick = saveSup; }
    const rf = document.getElementById('supRefresh');
    if(rf && !rf.dataset.bound2){ rf.dataset.bound2 = '1'; rf.addEventListener('click', loadSup); }
  }
  window.mapBindSupply = bind;
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.21.1 开局部队图层面板
(function(){
  function bindUnitsLayer(){
    const cb = document.getElementById('mapLUnits');
    if(!cb || cb.dataset.bound) return;
    cb.dataset.bound = '1';
    cb.addEventListener('change', function(){
      const img = document.getElementById('mapUnits');
      if(img) img.style.display = cb.checked ? '' : 'none';
    });
  }
  if(document.readyState !== 'loading') bindUnitsLayer();
  else document.addEventListener('DOMContentLoaded', bindUnitsLayer);

  // 省面板里显示该省的部队
  async function loadProvUnits(){
    const box = document.getElementById('provUnitsBox');
    if(!box) return;
    const pid = window.__curProvId;
    if(!pid){ box.innerHTML = ''; return; }
    box.innerHTML = '<div style="font-size:11px;color:var(--t3)">读取中…</div>';
    let r = null;
    try{
      r = await (await fetch('/api/units', {method:'POST',
        headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    }catch(e){ r = null; }
    if(!r || !r.ok){ box.innerHTML = '<div style="font-size:11px;color:var(--danger)">读取失败</div>'; return; }
    const lst = (r.by_prov || {})[String(pid)] || [];
    if(!lst.length){
      box.innerHTML = '<div style="font-size:11px;color:var(--t3)">这一省没有开局部队</div>';
      return;
    }
    box.innerHTML = lst.map(function(d, i){
      return '<div style="display:flex;gap:6px;align-items:center;font-size:11px;'
        + 'font-family:Consolas,monospace;padding:1px 0">'
        + '<span style="flex:1">' + (d.name || '(未命名)') + '</span>'
        + '<span style="color:var(--t3);font-size:10px">' + (d.template || '') + '</span>'
        + '</div>';
    }).join('');
  }
  window.__loadProvUnits = loadProvUnits;
  // 省切换时刷新（挂在 mapShowOps 上）
  const orig = window.mapShowOps;
  if(typeof orig === 'function'){
    window.mapShowOps = function(){
      const r = orig.apply(this, arguments);
      setTimeout(function(){
        if((window.MAP_PICK_UNIT || 'prov') === 'prov') loadProvUnits();
      }, 260);
      return r;
    };
  }
})();


// v1.21.2 省面板部队增删改
(function(){
  let TPL_CACHE = null;

  function msg(t, bad){
    const el = document.getElementById('unitMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function loadTplOptions(){
    const sel = document.getElementById('unitTpl');
    if(!sel) return;
    if(TPL_CACHE){ fill(sel, TPL_CACHE); return; }
    let r = null;
    try{
      r = await (await fetch('/api/units', {method:'POST',
        headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    }catch(e){ r = null; }
    if(!r || !r.ok){ msg('模板读取失败', true); return; }
    TPL_CACHE = (r.templates || []).map(function(t){ return t.name; });
    fill(sel, TPL_CACHE);
  }

  function fill(sel, names){
    const cur = sel.value;
    sel.innerHTML = '<option value="">（选模板）</option>' + names.map(function(n){
      return '<option value="' + n.replace(/"/g, '&quot;') + '">' + n + '</option>';
    }).join('');
    if(cur) sel.value = cur;
  }

  async function refresh(){
    if(window.__loadProvUnits) await window.__loadProvUnits();
  }

  async function addUnits(){
    const pid = window.__curProvId;
    const sel = document.getElementById('unitTpl');
    const cnt = Number((document.getElementById('unitCount')||{}).value || 1);
    if(!pid){ msg('先选一个省', true); return; }
    if(!sel || !sel.value){ msg('先选模板', true); return; }
    msg('写入中…');
    let ok = 0, err = '';
    for(let i=0;i<Math.max(1, cnt);i++){
      const r = await (await fetch('/api/unit_add', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({location: pid, template: sel.value,
                              tag: (st && (st.owner || st.owner_tag)) || null})})).json();
      if(r.ok) ok++; else { err = r.msg || '失败'; break; }
    }
    if(ok){ msg('已在省 ' + pid + ' 加 ' + ok + ' 支', false); status('加 ' + ok + ' 支部队'); await refresh(); }
    else msg(err, true);
  }

  async function delUnit(pid, idx){
    if(!confirm('删除这一支部队？')) return;
    msg('删除中…');
    const r = await (await fetch('/api/unit_delete', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({location: pid, index: idx})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await refresh(); }
  }

  async function moveUnit(pid, idx){
    const to = prompt('移到哪个省？（填省号）', '');
    if(!to) return;
    const n = Number(to);
    if(!n || n <= 0){ msg('省号不合法', true); return; }
    msg('移动中…');
    const r = await (await fetch('/api/unit_move', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({location: pid, index: idx, to: n})})).json();
    msg(r.msg || '', !r.ok);
    if(r.ok){ status(r.msg); await refresh(); }
  }

  // 重写省部队渲染：带按钮
  async function renderProvUnits(){
    const box = document.getElementById('provUnitsBox');
    if(!box) return;
    const pid = window.__curProvId;
    if(!pid){ box.innerHTML = ''; return; }
    let r = null;
    try{
      r = await (await fetch('/api/units', {method:'POST',
        headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    }catch(e){ r = null; }
    if(!r || !r.ok){ box.innerHTML = '<div style="font-size:11px;color:var(--danger)">读取失败</div>'; return; }
    TPL_CACHE = (r.templates || []).map(function(t){ return t.name; });
    const lst = (r.by_prov || {})[String(pid)] || [];
    if(!lst.length){
      box.innerHTML = '<div style="font-size:11px;color:var(--t3)">这一省没有开局部队</div>';
      return;
    }
    box.innerHTML = lst.map(function(d, i){
      return '<div style="display:flex;gap:4px;align-items:center;font-size:11px;'
        + 'font-family:Consolas,monospace;padding:1px 0">'
        + '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + (d.template||'') + '">'
        + (d.name || d.template || '(未命名)') + '</span>'
        + '<button class="btn up-mv" data-i="' + i + '" style="height:18px;font-size:9px;padding:0 4px">移</button>'
        + '<button class="btn up-del" data-i="' + i + '" style="height:18px;font-size:9px;padding:0 4px">删</button>'
        + '</div>';
    }).join('');
    box.querySelectorAll('.up-del').forEach(function(b){
      b.onclick = function(){ delUnit(pid, Number(b.dataset.i)); };
    });
    box.querySelectorAll('.up-mv').forEach(function(b){
      b.onclick = function(){ moveUnit(pid, Number(b.dataset.i)); };
    });
  }
  window.__renderProvUnits = renderProvUnits;

  function bind(){
    const add = document.getElementById('unitAddBtn');
    if(add && !add.dataset.bound){ add.dataset.bound = '1'; add.onclick = addUnits; }
    loadTplOptions();
  }

  // 省切换时用带按钮的渲染
  const orig = window.mapShowOps;
  if(typeof orig === 'function' && !orig.__unitsWrapped){
    const wrapped = function(){
      const r = orig.apply(this, arguments);
      setTimeout(function(){
        if((window.MAP_PICK_UNIT || 'prov') === 'prov'){ bind(); renderProvUnits(); }
      }, 280);
      return r;
    };
    wrapped.__unitsWrapped = 1;
    window.mapShowOps = wrapped;
  }

  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.22.0 地图生成
(function(){
  function msg(t, bad){
    const el = document.getElementById('mgMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }
  function log(lines){
    const box = document.getElementById('mgLog');
    if(!box) return;
    box.innerHTML = (lines || []).map(function(x){ return '<div>' + x + '</div>'; }).join('');
  }

  async function go(){
    const src = (document.getElementById('mgSource')||{}).value || 'procedural';
    const srcPath = ((document.getElementById('mgSrc')||{}).value || '').trim();
    const w = Number((document.getElementById('mgW')||{}).value || 600);
    const h = Number((document.getElementById('mgH')||{}).value || 240);
    const n = Number((document.getElementById('mgN')||{}).value || 60);
    const seed = Number((document.getElementById('mgSeed')||{}).value || 7);
    const out = ((document.getElementById('mgOut')||{}).value || '').trim();
    const bal = !!(document.getElementById('mgBal')||{}).checked;
    const minPx = Number((document.getElementById('mgMinPx')||{}).value || 800);
    const nr = (document.getElementById('mgRegions')||{}).value;
    const ns = (document.getElementById('mgSupply')||{}).value;
    const rivPath = ((document.getElementById('mgRiv')||{}).value || '').trim();
    const cityPath = ((document.getElementById('mgCity')||{}).value || '').trim();
    if(src !== 'procedural' && !srcPath){ msg('这个来源要填文件路径', true); return; }
    msg('生成中…（大尺寸可能要几十秒）');
    log([]);
    try{
      const r = await (await fetch('/api/map_generate', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({source: src, out: out || null, width: w, height: h,
                              n_provinces: n, seed: seed,
                              src_path: srcPath || null,
                              balance: bal, min_province_px: minPx,
                              n_regions: nr || null, n_supply: ns || null,
                              rivers_path: rivPath || null,
                              cities_path: cityPath || null})})).json();
      msg(r.msg || '', !r.ok);
      log(r.log || []);
      if(r.ok) status(r.msg);
    }catch(e){
      msg('请求失败：' + e, true);
    }
  }

  function bind(){
    const b = document.getElementById('mgGo');
    if(b && !b.dataset.bound){ b.dataset.bound = '1'; b.onclick = go; }
  }
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();


// v1.23.9 高程笔刷
(function(){
  let ON = false;

  function msg(t, bad){
    const el = document.getElementById('hpMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }

  async function paint(points){
    const hv = Number((document.getElementById('hpVal')||{}).value || 140);
    const br = Number((document.getElementById('hpBrush')||{}).value || 8);
    const fe = !!(document.getElementById('hpFeather')||{}).checked;
    try{
      const r = await (await fetch('/api/height_paint', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({points: points, height: hv, brush: br, feather: fe})})).json();
      if(r.ok){
        msg(r.msg);
        // 刷完清缓存重载高度图
        const clr = document.getElementById('mapClear');
        if(clr) clr.click();
      } else msg(r.msg || '失败', true);
    }catch(e){ msg('请求失败：' + e, true); }
  }

  function bind(){
    const btn = document.getElementById('hpToggle');
    if(!btn || btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.onclick = function(){
      ON = !ON;
      btn.textContent = ON ? '停止刷' : '开始刷';
      btn.style.background = ON ? 'var(--accent)' : '';
      msg(ON ? '左键拖拽刷高度（像素坐标）' : '已停止');
      window.__heightBrush = ON;
    };
  }

  // 在地图画布上接管拖拽
  function attach(){
    const cv = document.getElementById('mapSelCanvas') || document.querySelector('#mapStageWrap canvas');
    if(!cv || cv.dataset.hpBound) return;
    cv.dataset.hpBound = '1';
    let drawing = false;
    const toMap = function(ev){
      const r = cv.getBoundingClientRect();
      const x = (ev.clientX - r.left - (typeof MAP !== 'undefined' ? MAP.x : 0)) / (typeof MAP !== 'undefined' ? MAP.k : 1);
      const y = (ev.clientY - r.top - (typeof MAP !== 'undefined' ? MAP.y : 0)) / (typeof MAP !== 'undefined' ? MAP.k : 1);
      return [Math.round(x), Math.round(y)];
    };
    cv.addEventListener('mousedown', function(ev){
      if(!window.__heightBrush || ev.button !== 0) return;
      ev.stopPropagation(); ev.preventDefault();
      drawing = true;
      paint([toMap(ev)]);
    }, true);
    cv.addEventListener('mousemove', function(ev){
      if(!drawing) return;
      ev.stopPropagation(); ev.preventDefault();
      paint([toMap(ev)]);
    }, true);
    cv.addEventListener('mouseup', function(ev){
      if(drawing){ drawing = false; ev.stopPropagation(); }
    }, true);
    cv.addEventListener('mouseleave', function(){ drawing = false; });
  }

  if(document.readyState !== 'loading'){
    setTimeout(function(){ bind(); attach(); }, 800);
  } else {
    document.addEventListener('DOMContentLoaded', function(){
      setTimeout(function(){ bind(); attach(); }, 800);
    });
  }
})();


/* ---------- v1.23.48 河流笔刷 ---------- */
(function(){
  let ON = false, drawing = false, erasing = false, strokeNew = false;
  let pending = [], sending = false, lastSent = 0;

  const KIND_COLOR = {main:'rgba(0,210,255,.85)', tributary:'rgba(40,120,255,.85)',
                      stream:'rgba(130,220,255,.85)', deep:'rgba(0,70,200,.9)'};

  function msg(t, bad){
    const el = document.getElementById('rvMsg');
    if(el){ el.textContent = t || ''; el.style.color = bad ? 'var(--danger)' : ''; }
  }
  function kind(){ return ((document.getElementById('rvKind')||{}).value || 'main'); }
  function brush(){ return Number((document.getElementById('rvBrush')||{}).value || 2); }

  function ensureCanvas(){
    const stack = document.getElementById('mapStack');
    // MAP 是顶层 const（不是 window 属性），别写成 window.MAP
    if(!stack || typeof MAP === 'undefined') return null;
    let cv = document.getElementById('mapRiverCanvas');
    if(!cv){
      cv = document.createElement('canvas');
      cv.id = 'mapRiverCanvas';
      cv.style.cssText = 'position:absolute;left:0;top:0;pointer-events:none;z-index:4;image-rendering:pixelated';
      stack.appendChild(cv);
    }
    if(cv.width !== MAP.w || cv.height !== MAP.h){
      cv.width = MAP.w; cv.height = MAP.h;
      cv.style.width = MAP.w + 'px';
      cv.style.height = MAP.h + 'px';
      reloadPreview();
    }
    return cv;
  }
  window.__riverSync = function(){ ensureCanvas(); };

  function reloadPreview(){
    const cv = document.getElementById('mapRiverCanvas');
    if(!cv) return;
    const c = cv.getContext('2d');
    const img = new Image();
    img.onload = function(){
      c.clearRect(0, 0, cv.width, cv.height);
      c.drawImage(img, 0, 0);
    };
    img.src = '/api/river_preview.png?t=' + Date.now();
  }

  let localLast = null;

  function paintLocal(x, y){
    const cv = document.getElementById('mapRiverCanvas');
    if(!cv) return;
    const c = cv.getContext('2d');
    const r = Math.max(1, brush());
    c.strokeStyle = erasing ? 'rgba(255,90,90,.5)' : (KIND_COLOR[kind()] || KIND_COLOR.main);
    c.lineWidth = r * 2;
    c.lineCap = 'round';
    c.lineJoin = 'round';
    c.beginPath();
    if(localLast){
      c.moveTo(localLast[0], localLast[1]);
      c.lineTo(x, y);
    } else {
      c.moveTo(x, y);
      c.lineTo(x + 0.01, y);
    }
    c.stroke();
    localLast = [x, y];
  }

  function sendPoint(pt){
    pending.push([Math.round(pt.x), Math.round(pt.y)]);
    if(sending) return;
    const now = Date.now();
    if(now - lastSent < 35){
      if(!window.__rvTimer){
        window.__rvTimer = setTimeout(function(){
          window.__rvTimer = null; flush();
        }, 40);
      }
      return;
    }
    flush();
  }

  async function flush(){
    if(!pending.length || sending) return;
    sending = true;
    const pts = pending;
    pending = [];
    lastSent = Date.now();
    const body = {points: pts, kind: kind(), brush: brush(),
                  erase: erasing, new_stroke: strokeNew};
    strokeNew = false;
    try{
      const r = await (await fetch('/api/river_paint', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(body)})).json();
      if(r.ok) msg(r.msg);
      else msg(r.msg || '写入失败', true);
    }catch(e){ msg('请求失败：' + e.message, true); }
    sending = false;
    if(pending.length) flush();
  }

  function onDown(ev){
    if(!ON) return;
    if(window.mapEventOverUI && window.mapEventOverUI(ev)) return;
    if(typeof mapScreenToImage !== 'function') return;
    const pt = mapScreenToImage(ev.clientX, ev.clientY);
    if(!pt || pt.x < 0 || pt.y < 0 || pt.x >= MAP.w || pt.y >= MAP.h) return;
    ev.stopPropagation(); ev.preventDefault();
    drawing = true;
    erasing = (ev.button === 2);
    strokeNew = true;
    sendPoint(pt);
    paintLocal(pt.x, pt.y);
  }

  function onMove(ev){
    if(!ON || !drawing) return;
    if(typeof mapScreenToImage !== 'function') return;
    const pt = mapScreenToImage(ev.clientX, ev.clientY);
    if(!pt || pt.x < 0 || pt.y < 0 || pt.x >= MAP.w || pt.y >= MAP.h) return;
    ev.stopPropagation();
    sendPoint(pt);
    paintLocal(pt.x, pt.y);
  }

  function onUp(){
    if(!drawing) return;
    drawing = false;
    localLast = null;
    flush();
    // 抬手后从 rivers.bmp 重新生成预览：本地画笔只是「随手画」，以文件为准
    setTimeout(reloadPreview, 260);
  }

  function bind(){
    const wrap = document.getElementById('mapStageWrap');
    if(!wrap || wrap.dataset.rvBound) return;
    wrap.dataset.rvBound = '1';
    wrap.addEventListener('mousedown', onDown, true);
    wrap.addEventListener('mousemove', onMove, true);
    window.addEventListener('mouseup', onUp, true);
    wrap.addEventListener('contextmenu', function(e){ if(ON) e.preventDefault(); }, true);
    const t = document.getElementById('rvToggle');
    if(t && !t.dataset.bound){
      t.dataset.bound = '1';
      t.onclick = function(){
        ON = !ON;
        ensureCanvas();
        t.textContent = ON ? '停止画' : '开始画';
        t.style.background = ON ? 'var(--accent)' : '';
        msg(ON ? '左键画、右键擦（底图请先开「地形」或「省色块」）' : '已停止');
        if(ON) reloadPreview();
      };
    }
    const u = document.getElementById('rvUndo');
    if(u && !u.dataset.bound){
      u.dataset.bound = '1';
      u.onclick = async function(){
        try{
          const r = await (await fetch('/api/river_undo', {method:'POST',
            headers:{'Content-Type':'application/json'}, body: '{}'})).json();
          msg(r.msg || '', !r.ok);
          if(r.ok) reloadPreview();
        }catch(e){ msg('撤销失败：' + e.message, true); }
      };
    }
    const ck = document.getElementById('rvCheck');
    if(ck && !ck.dataset.bound){
      ck.dataset.bound = '1';
      ck.onclick = async function(){
        msg('检查中…');
        try{
          const r = await (await fetch('/api/river_stats')).json();
          if(!r.ok){ msg(r.msg || '检查失败', true); return; }
          msg((r.lines || [r.msg]).join('；'));
        }catch(e){ msg('检查失败：' + e.message, true); }
      };
    }
  }

  if(document.readyState !== 'loading'){
    setTimeout(bind, 900);
  } else {
    document.addEventListener('DOMContentLoaded', function(){ setTimeout(bind, 900); });
  }
})();


/* ---------- v0.81 地图界面 ---------- */
MAP.mode = 'view';

MAP.lastPid = null;

MAP.lastState = null;


function mapSetMode(mode){
  if(mode === 'pick'){ status('吸管还在开发中'); return; }
  if(mode === 'paint'){
    MAP.mode = 'paint';
    document.querySelectorAll('#mapRail .map-tool').forEach(b=>{
      b.classList.toggle('on', b.dataset.mode === 'paint');
    });
    const el = document.getElementById('msMode');
    if(el) el.textContent = '涂色';
    const hint = document.getElementById('msHint');
    if(hint) hint.textContent = '填目标省号 → 在地图上按住拖动涂抹 → 应用';
    const side = document.getElementById('mapSide');
    if(side) side.classList.remove('empty');
    document.getElementById('paintBox').style.display = '';
    document.getElementById('selBox').style.display = 'none';
    return;
  }
  MAP.mode = mode;
  document.querySelectorAll('#mapRail .map-tool').forEach(b=>{
    b.classList.toggle('on', b.dataset.mode === mode);
  });
  const el = document.getElementById('msMode');
  if(el) el.textContent = MAP_MODE_TEXT[mode] || mode;
  const hint = document.getElementById('msHint');
  if(hint){
    hint.textContent = mode === 'state'
      ? '单击省份后在右侧改归属'
      : '滚轮缩放 · 拖动平移 · 单击选省';
  }
  const pb = document.getElementById('paintBox');
  if(pb) pb.style.display = 'none';
  const sb2 = document.getElementById('selBox');
  if(sb2) sb2.style.display = '';
  // 浏览模式下，未选省时属性面板保持收起
  if(mode === 'view' && !MAP.lastPid){
    const side = document.getElementById('mapSide');
  }
}


function mapStatusPos(clientX, clientY){
  const p = mapScreenToImage(clientX, clientY);
  const el = document.getElementById('msPos');
  if(el) el.textContent = Math.round(p.x) + ', ' + Math.round(p.y);
}


function mapSelectProvince(pid){
  MAP.lastPid = pid;
  const rec = (MAP.idx && MAP.idx[String(pid)]) || {};
  if(window.mapSideTab) window.mapSideTab('edit');
  const set = (id, v)=>{ const e = document.getElementById(id); if(e) e.textContent = v; };
  set('msId', '省 ' + pid);
  set('msType', rec.type || '');
  set('msState', rec.state ? String(rec.state) : '无');
  set('msRegion', rec.region ? String(rec.region) : '无');
  set('msPx', rec.px ? rec.px.toLocaleString() : '—');
  const inp = document.getElementById('msTarget');
  if(inp) inp.value = rec.state ? String(rec.state) : '';
  const det = document.getElementById('msDetachProv');
  if(det) det.disabled = !rec.state;
  MAP.lastState = rec.state || null;
  if(window.mapRenderSelection) window.mapRenderSelection();
  const info = document.getElementById('msInfo');
  if(info) info.textContent = '省 ' + pid + ' · 州 ' + (rec.state || '无') + ' · 地区 ' + (rec.region || '无');
  mapUpdateStatus();
}


function mapBindV081(){
  const card = document.getElementById('mapCard');
  if(card && card.dataset.v081) return;
  if(card) card.dataset.v081 = '1';
  document.querySelectorAll('#mapRail .map-tool').forEach(btn=>{
    btn.addEventListener('click', ()=>mapSetMode(btn.dataset.mode));
  });
  const toggle = document.getElementById('mapLayerToggle');
  if(toggle){
    toggle.addEventListener('click', ()=>{
      const box = document.getElementById('mapTools');
      box.classList.toggle('min');
      toggle.textContent = box.classList.contains('min') ? '+' : '−';
    });
  }
  const mv = document.getElementById('msMoveProv');
  if(mv) mv.onclick = ()=>{
    const t = (document.getElementById('msTarget').value || '').trim();
    if(!/^\d+$/.test(t)){ status('填一个目标州号', true); return; }
    if(window.MAP_LAST) MAP_LAST_PID = MAP_LAST_PID || null;
    const src = document.getElementById('msTarget');
    if(src) src.value = t;
    mapMoveProv(false);
  };
  const det = document.getElementById('msDetachProv');
  if(det) det.onclick = ()=>mapMoveProv(true);
  const open = document.getElementById('msOpenState');
  if(open) open.onclick = ()=>{
    if(!MAP.lastState){ status('这个省不属于任何州'); return; }
    const sid = MAP.lastState;
    document.getElementById('mapModal').classList.remove('show');
    if(typeof openStates === 'function') openStates(sid);
  };
  if(window.mapBindPaint) window.mapBindPaint();
  if(window.mapBindMerge) window.mapBindMerge();
  if(window.mapBindNewState) window.mapBindNewState();
  if(window.mapBindHotkeys) window.mapBindHotkeys();
  if(window.mapBindPlayset) window.mapBindPlayset();
  if(window.mapBindSideTabs) window.mapBindSideTabs();
  if(window.mapBindOutput) window.mapBindOutput();
  if(window.mapBindRefine) window.mapBindRefine();
  if(window.mapBindFocusTree) window.mapBindFocusTree();
  mapSetMode('view');
}


function mapAssetUrl(name){
  return '/api/map_asset?name=' + encodeURIComponent(name) +
    (MAP.root ? '&root=' + encodeURIComponent(MAP.root) : '');
}


function mapFillSources(list, picked){
  const sel = document.getElementById('mapSource');
  if(!sel) return;
  sel.innerHTML = list.map(s=>'<option value="' + escapeHtml(s.path) + '"' +
    (s.path === picked ? ' selected' : '') + (s.has_map ? '' : ' disabled') + '>' +
    escapeHtml(s.name + (s.has_map ? (s.map_from ? '（地图来自 ' + s.map_from + '）' : '') : '（无地图）')) + '</option>').join('');
}


function mapSwitchSource(path){
  MAP.ready = false;
  MAP.idCanvas = null;
  MAP.idx = null;
  MAP.centers = null;
  MAP.regions = null;
  mapHideOps();
  document.getElementById('mapMeta').textContent = '切换来源…';
  mapLoadMeta(path);
}


async function openMap(){
  document.getElementById('mapModal').classList.add('show');
  mapBindV081();
  if(MAP.ready){ mapApply(); return; }
  await mapLoadMeta();
}


async function mapLoadMeta(root){
  const metaEl = document.getElementById('mapMeta');
  try{
    const q = root ? ('?root=' + encodeURIComponent(root)) : '';
    const d = await (await fetch('/api/map_meta' + q)).json();
    MAP.root = d.picked || root || MAP.root || '';
    if(d.sources) mapFillSources(d.sources, MAP.root);
    mapRenderLayers(d);
    if(!d.ok){ metaEl.textContent = d.msg || '没有地图数据'; return; }
    if(!d.built){
      const bb = document.getElementById('mapBuild');
      if(bb) bb.classList.add('primary');
      if(d.stale){
        metaEl.textContent = '图层缓存已过期（' + (d.prev_built || '上次构建') + ' 的数据或版本有变），点「构建图层」重建';
        metaEl.style.color = 'var(--accent)';
      } else {
        metaEl.textContent = '图层未构建（首次约 20 秒）';
      }
      return;
    }
    metaEl.style.color = '';
    MAP.meta = d.meta || {};
    // 省特别多时（1 万以上），「省色块」缩略看就是一片噪点，默认改用地形视图
    if(!MAP._viewInited){
      MAP._viewInited = true;
      let saved = '';
      try{ saved = localStorage.getItem('xuerong_layer_preset') || ''; }catch(e){}
      const want = saved || ((MAP.meta.provinces || 0) > 8000 ? 'terrain' : 'prov');
      if(window.mapApplyPreset) setTimeout(()=> window.mapApplyPreset(want), 60);
    }
    if(!MAP._viewInited) MAP._viewInited = true;
    MAP.w = MAP.meta.w || MAP.w;
    MAP.h = MAP.meta.h || MAP.h;
    await mapLoadAssets();
    metaEl.textContent = (MAP.w + '×' + MAP.h) + ' · ' + (MAP.meta.provinces || 0) + ' 块 · 构建于 ' + (MAP.meta.built || '');
    const bb = document.getElementById('mapBuild');
    if(bb) bb.classList.remove('primary');
    // submod：地图可能来自父 mod
    if(Array.isArray(d.layers) && d.layers.length > 2){
      const parent = d.layers[d.layers.length - 2];
      const provider = (d.source || '').replace(/[\/]+$/, '');
      if(parent && provider && provider.indexOf(parent.name) < 0){
        metaEl.textContent += ' · 地图来自 ' + parent.name;
      }
    }
    mapFit();
    mapReadyHint();
  }catch(e){ metaEl.textContent = '读取失败：' + e.message; }
}


// 图层文件重建后强制重载（src 相同浏览器会用缓存，必须先清空）
window.mapReloadLayers = function(){
  ['mapBase','mapPolit','mapRegion','mapTerrain','mapContinent','mapProv','mapUnits'].forEach(function(id){
    const el = document.getElementById(id);
    if(el) el.setAttribute('src', '');
  });
  if(typeof mapLoadAssets === 'function') mapLoadAssets();
};


async function mapLoadAssets(){
  const set = (id, name, opacity)=>{
    const el = document.getElementById(id);
    el.style.width = MAP.w + 'px';
    el.style.height = MAP.h + 'px';
    if(el.getAttribute('src') !== mapAssetUrl(name)){
      el.setAttribute('src', mapAssetUrl(name));
    }
    el.style.opacity = opacity;
  };
  set('mapBase', 'base.png', 1);
  set('mapPolit', 'political.png', 0.9);
  set('mapUnits', 'units.png', 1);
  set('mapRegion', 'region.png', 0.72);
  set('mapTerrain', 'terrain.png', 0.8);
  set('mapContinent', 'continent.png', 0.8);
  set('mapProv', 'province.png', 0.85);
  set('mapState', 'state.png', 0.62);
  set('mapEdges', 'edges.png', 0.7);
  document.getElementById('mapBase').style.width = (MAP.w / 2) + 'px';
  document.getElementById('mapBase').style.height = (MAP.h / 2) + 'px';
  document.getElementById('mapBase').style.transformOrigin = '0 0';
  document.getElementById('mapBase').style.transform = 'scale(2)';
  if(!MAP.idx){
    try{ MAP.idx = await (await fetch(mapAssetUrl('prov_index.json'))).json(); }catch(e){ MAP.idx = {}; }
  }
  if(!MAP.centers){
    try{ MAP.centers = await (await fetch(mapAssetUrl('centers.json'))).json(); }catch(e){ MAP.centers = {}; }
  }
  if(!MAP.regions){
    try{ MAP.regions = await (await fetch(mapAssetUrl('regions.json'))).json(); }catch(e){ MAP.regions = []; }
  }
  MAP.ready = true;
  mapApplyLayers();
}


function mapApplyLayers(){
  // v1.19.0 严格模式：换成只含真实国家的政治图
  try{
    const strict = document.getElementById('mapLStrict');
    const polit = document.getElementById('mapPolit');
    if(polit && strict){
      const want = strict.checked ? 'political_strict.png' : 'political.png';
      const url = mapAssetUrl(want);
      if(polit.getAttribute('src') !== url) polit.setAttribute('src', url);
    }
  }catch(e){}
  const rv = document.getElementById('mapLRivers');
  const rvImg = document.getElementById('mapRivers');
  if(rvImg){
    const on = rv && rv.checked;
    rvImg.style.display = on ? 'block' : 'none';
    if(on){
      rvImg.style.width = MAP.w + 'px';
      rvImg.style.height = MAP.h + 'px';
      const url = mapAssetUrl('rivers.png');
      if(rvImg.getAttribute('src') !== url) rvImg.setAttribute('src', url);
      const op = document.querySelector('.lt-op[data-op="rivers"]');
      rvImg.style.opacity = op ? (Number(op.value) / 100) : 1;
    }
  }
  const onPolit = document.getElementById('mapLPolit').checked;
  const onRegion = document.getElementById('mapLRegion').checked;
  const onTerrain = document.getElementById('mapLTerrain').checked;
  const onContinent = document.getElementById('mapLContinent').checked;
  const onProv = document.getElementById('mapLProv').checked;
  const onState = document.getElementById('mapLState').checked;
  const onEdges = document.getElementById('mapLEdges').checked;
  const onBase = document.getElementById('mapLBase').checked;
  const opAll = Number(document.getElementById('mapOpacity').value || 85) / 100;
  const lop = (window.mapLayerOp ? window.mapLayerOp() : {});
  const op = (k)=> (lop[k] != null ? lop[k] : opAll);
  const polit = document.getElementById('mapPolit');
  const region = document.getElementById('mapRegion');
  const terrain = document.getElementById('mapTerrain');
  const continent = document.getElementById('mapContinent');
  const prov = document.getElementById('mapProv');
  const state = document.getElementById('mapState');
  const edges = document.getElementById('mapEdges');
  const base = document.getElementById('mapBase');
  terrain.style.display = onTerrain ? '' : 'none';
  terrain.style.opacity = op('terrain');
  continent.style.display = onContinent ? '' : 'none';
  continent.style.opacity = op('continent');
  // 地形/大洲与省色块互斥，避免叠三层
  if(onTerrain || onContinent){ prov.style.opacity = 0; }
  region.style.display = onRegion ? '' : 'none';
  region.style.opacity = onRegion ? Math.min(0.85, op('region')) : 0;
  polit.style.display = onPolit ? '' : 'none';
  polit.style.opacity = op('polit');
  prov.style.display = (onProv && !onPolit) ? '' : 'none';
  [['mapLProv', onProv], ['mapLPolit', onPolit], ['mapLRegion', onRegion],
   ['mapLState', onState], ['mapLEdges', onEdges], ['mapLBase', onBase]].forEach(([id, on])=>{
    const el = document.getElementById(id);
    if(el && el.parentElement) el.parentElement.classList.toggle('on', !!on);
  });
  state.style.display = onState ? '' : 'none';
  edges.style.display = onEdges ? '' : 'none';
  base.style.display = onBase ? '' : 'none';
  base.style.opacity = op('base');
  prov.style.opacity = onState ? Math.min(0.35, op('prov')) : op('prov');
  if(onPolit) prov.style.opacity = 0;
  if(onRegion && !onPolit) prov.style.opacity = Math.min(prov.style.opacity || op('prov'), 0.3);
  state.style.opacity = op('state');
  edges.style.opacity = Math.max(0.15, op('edges'));
}


function mapApply(){
  const stack = document.getElementById('mapStack');
  stack.style.transform = 'translate(' + MAP.x + 'px,' + MAP.y + 'px) scale(' + MAP.k + ')';
  // 只有缩得很小（<0.35）时才用插值抗摩尔纹；
  // 放大时一律 pixelated —— 插值会把边界糊成一团，高倍下反而比锯齿更难看。
  stack.classList.toggle('smooth', MAP.k < 0.35);
  mapUpdateStatus();
  // 河流覆盖层的尺寸跟着地图走（地图尺寸在建图层时才确定）
  if(typeof window.__riverSync === 'function') window.__riverSync();
}


function mapFit(){
  const wrap = document.getElementById('mapStageWrap');
  if(!wrap) return;
  const r = wrap.getBoundingClientRect();
  MAP.k = Math.min(r.width / MAP.w, r.height / MAP.h) * 0.98;
  MAP.x = (r.width - MAP.w * MAP.k) / 2;
  MAP.y = (r.height - MAP.h * MAP.k) / 2;
  mapApply();
}


function mapEventOverUI(e){
  // 图层面板是绝对定位在画布内的浮层，其余面板与回放层同理；
  // 只要指针落在这些元素上，就不该触发地图的取省/涂色/拖动
  const t = e && e.target;
  if(!t || !t.closest) return false;
  return !!t.closest('#mapTools, #mapSide, #mapRail, #mapHead, #mapStatus, '
                    + '#mapCheckModal, #updModal, #mckCard, #updCard');
}


function mapScreenToImage(clientX, clientY){
  // getBoundingClientRect 返回的是「视觉像素」，而 MAP.x/MAP.k 用的是 CSS 像素。
  // 界面字号档位用的是 body{zoom}，缩放过时必须先除掉 uiZoom，否则点击会整体偏移
  // （表现就是：点在陆地上，右边显示的是旁边海洋的省）。
  const z = uiZoom();
  const r = document.getElementById('mapStageWrap').getBoundingClientRect();
  return {x: ((clientX - r.left) / z - MAP.x) / MAP.k,
          y: ((clientY - r.top) / z - MAP.y) / MAP.k};
}


function mapProvAt(imgX, imgY){
  if(!MAP.ready || !MAP.idCanvas) return null;
  const x = Math.floor(imgX), y = Math.floor(imgY);
  if(x < 0 || y < 0 || x >= MAP.w || y >= MAP.h) return null;
  const ctx = MAP.idCanvas.getContext('2d');
  const d = ctx.getImageData(x, y, 1, 1).data;
  const pid = (d[0] << 16) | (d[1] << 8) | d[2];
  return pid || null;
}


function mapBuildIdCanvas(){
  if(MAP.idCanvas || !MAP.ready) return;
  const c = document.createElement('canvas');
  c.width = MAP.w; c.height = MAP.h;
  const ctx = c.getContext('2d');
  const img = document.getElementById('mapProv');
  if(!img || !img.naturalWidth) return;
  const idImg = new Image();
  idImg.onload = ()=>{ ctx.drawImage(idImg, 0, 0); MAP.idCanvas = c; };
  idImg.src = mapAssetUrl('prov_id.png');
}


function mapShowOps(pid, sid){
  MAP_LAST_PID = pid;
  MAP_LAST_STATE = sid || null;
  if(typeof mapSelectProvince === 'function') mapSelectProvince(pid);
  const inp = document.getElementById('msTarget');
  if(inp) inp.value = sid ? String(sid) : '';
  const det = document.getElementById('msDetachProv');
  if(det) det.disabled = !sid;
}


function mapHideOps(){
  // 侧栏现在是常显的 Tab 容器（图层面板在里面），不能再靠 empty 类隐藏
  if(window.mapSideTab) window.mapSideTab('layers');
}


async function mapMoveProv(detach){
  if(!MAP_LAST_PID) return;
  const src = document.getElementById('msTarget');
  const target = detach ? null : ((src && src.value) || '').trim();
  if(!detach && !/^\d+$/.test(target)){ status('填一个目标州号', true); return; }
  const pided = MAP_LAST_PID;
  const verb = detach ? '移出州' : ('移入州 ' + target);
  if(!confirm('把省 ' + pided + ' ' + verb + '？会直接改 history/states 的 provinces 列表，可用备份回滚。')) return;
  try{
    const r = await (await fetch('/api/state_province', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({pid: pided, target: detach ? null : Number(target)})})).json();
    if(!r.ok){ status(r.msg || '失败', true); return; }
    status(r.msg + '（州色块需要重新构建图层才会更新）');
    const rec = (MAP.idx && MAP.idx[String(pided)]) || {};
    const newSid = detach ? 0 : Number(target);
    if(MAP.idx && MAP.idx[String(pided)]) MAP.idx[String(pided)].state = newSid;
    mapShowOps(pided, newSid);
    const info = document.getElementById('msInfo');
    if(info) info.textContent = '省 ' + pided + ' · 州 ' + (newSid || '无');
    const stEl = document.getElementById('msState');
    if(stEl) stEl.textContent = newSid ? String(newSid) : '无';
  }catch(e){ status('失败：' + e.message, true); }
}


function _stateById(sid){
  if(!sid || typeof STATES === 'undefined') return null;
  return Object.values(STATES || {}).find(x=>Number(x.id) === Number(sid)) || null;
}


function _regionName(rid){
  if(!rid || !MAP.regions) return '';
  const r = MAP.regions.find(x=>Number(x.id) === Number(rid));
  if(!r) return '';
  // regions.json 的 name 是本地化键（STRATEGICREGION_12），有翻译就用翻译
  const key = r.name || '';
  const loc = (typeof LOC !== 'undefined' && LOC[key]) ? LOC[key] : '';
  return loc || ('地区 ' + rid);
}


function mapUpdateStatus(){
  const pct = document.getElementById('msPct');
  if(pct) pct.textContent = Math.round((MAP.k || 1) * 100) + '%';
  const sel = document.getElementById('msSel');
  if(sel) sel.textContent = (MAP.sel && MAP.sel.length) ? ('已选 ' + MAP.sel.length) : '';
}


function mapInfo(pid){
  if(!pid) return '空白（海域或未定义）';
  const rec = (MAP.idx && MAP.idx[String(pid)]) || {};
  const sid = rec.state || 0;
  const parts = [];
  parts.push('省 ' + pid);
  // 省自己的 RGB（definition.csv 的原色）
  if(rec.rgb && rec.rgb.length === 3){
    const c = rec.rgb;
    parts.push('#' + ((1 << 24) + (c[0] << 16) + (c[1] << 8) + c[2]).toString(16).slice(1));
  }
  const t = rec.type || '';
  parts.push(t === 'ocean' ? '海洋' : (t === 'lake' ? '湖泊' : (t === 'land' ? '陆地' : (t || '未知'))));
  const st = _stateById(sid);
  parts.push('州 ' + (sid || '无') + (st && st.name && st.name !== ('STATE_' + sid) ? ' ' + st.name : ''));
  const rn = _regionName(rec.region);
  if(rn) parts.push(rn);
  if(rec.terrain) parts.push(rec.terrain);
  if(rec.continent) parts.push('洲 ' + rec.continent);
  return parts.join(' · ');
}


function mapReadyHint(){
  if(MAP.ready){
    document.getElementById('mapHud').textContent = '滚轮缩放 · 拖动平移 · 单击查省';
    mapBuildIdCanvas();
  }
}


function mapGoto(x, y, k){
  const wrap = document.getElementById('mapStageWrap').getBoundingClientRect();
  MAP.k = k || 1.0;
  MAP.x = wrap.width / 2 - x * MAP.k;
  MAP.y = wrap.height / 2 - y * MAP.k;
  mapApply();
}


function mapSearchGo(){
  const q = (document.getElementById('mapSearch').value || '').trim();
  if(!q || !MAP.ready) return;
  const hud = document.getElementById('mapHud');
  if(!/^\d+$/.test(q)){ hud.textContent = '输入数字：省号或州号'; return; }
  if(MAP.centers && MAP.centers[q]){
    const c = MAP.centers[q];
    mapGoto(c[0], c[1], 1.1);
    hud.textContent = '定位到省 ' + q + ' · ' + mapInfo(Number(q));
    return;
  }
  const sid = Number(q);
  // 战略区号
  if(MAP.regions && MAP.regions.some(r=>Number(r.id) === sid)){
    const provs2 = Object.keys(MAP.idx || {}).filter(pid=>Number((MAP.idx[pid] || {}).region) === sid);
    let sx2 = 0, sy2 = 0, n2 = 0;
    provs2.forEach(pid=>{ const c = MAP.centers && MAP.centers[pid]; if(c){ sx2 += c[0]; sy2 += c[1]; n2++; } });
    if(n2){ mapGoto(sx2 / n2, sy2 / n2, 0.85); hud.textContent = '定位到战略区 ' + sid + ' · ' + provs2.length + ' 块'; return; }
  }
  const provs = Object.keys(MAP.idx || {}).filter(pid=>Number((MAP.idx[pid] || {}).state) === sid);
  if(!provs.length){ hud.textContent = '没找到省或州：' + q; return; }
  let sx = 0, sy = 0, n = 0;
  provs.forEach(pid=>{
    const c = MAP.centers && MAP.centers[pid];
    if(c){ sx += c[0]; sy += c[1]; n++; }
  });
  if(!n){ hud.textContent = '州 ' + sid + ' 有 ' + provs.length + ' 块但没中心点'; return; }
  mapGoto(sx / n, sy / n, 0.9);
  hud.textContent = '定位到州 ' + sid + ' · ' + provs.length + ' 块';
}


function mapBindEvents(){
  const wrap = document.getElementById('mapStageWrap');
  if(!wrap || wrap.dataset.bound) return;
  wrap.dataset.bound = '1';
  let drag = null;
  wrap.addEventListener('pointerdown', e=>{
    if(mapEventOverUI(e)) return;
    e.preventDefault();
    drag = {x: e.clientX, y: e.clientY, ox: MAP.x, oy: MAP.y, moved: false};
    wrap.classList.add('dragging');
    try{ wrap.setPointerCapture(e.pointerId); }catch(err){}
  });
  wrap.addEventListener('pointermove', e=>{
    const hud = document.getElementById('mapHud');
    if(drag){
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if(Math.abs(dx) > 3 || Math.abs(dy) > 3) drag.moved = true;
      MAP.x = drag.ox + dx;
      MAP.y = drag.oy + dy;
      mapApply();
      return;
    }
    if(!MAP.ready || mapEventOverUI(e)) return;
    const p = mapScreenToImage(e.clientX, e.clientY);
    const pid = mapProvAt(p.x, p.y);
    hud.textContent = mapInfo(pid);
  });
  wrap.addEventListener('pointerup', e=>{
    wrap.classList.remove('dragging');
    const moved = drag && drag.moved;
    drag = null;
    if(mapEventOverUI(e)) return;           // 抬起在 UI 上：不算点选
    if(moved || !MAP.ready) return;
    const p = mapScreenToImage(e.clientX, e.clientY);
    const pid = mapProvAt(p.x, p.y);
    if(!pid) return;
    const rec = (MAP.idx && MAP.idx[String(pid)]) || {};
    mapShowOps(pid, rec.state || 0);
    if(rec.state){
      status('省 ' + pid + ' → 州 ' + rec.state + '，双击可打开州面板');
      MAP.lastState = rec.state;
    } else {
      status('省 ' + pid + ' 不属于任何州');
    }
  });
  wrap.addEventListener('dblclick', e=>{
    // 非省视图里双击 = 下钻到省（单击选的是州/国家/战略区）
    const unit = window.MAP_PICK_UNIT || 'prov';
    if(unit !== 'prov' && MAP.ready){
      const p = mapScreenToImage(e.clientX, e.clientY);
      const pid = mapProvAt(p.x, p.y);
      if(pid){
        window.MAP_PICK_UNIT = 'prov';
        const box = document.getElementById('selBox');
        if(box) box.innerHTML = '';
        mapShowOps(pid, ((MAP.idx && MAP.idx[String(pid)]) || {}).state || 0);
        const cb = document.getElementById('mapLProv');
        if(cb && !cb.checked){ cb.checked = true; mapApplyLayers(); }
        status('已下钻到省 ' + pid + '（双击州视图可回到整州）');
        if(window.mapRenderSelection) window.mapRenderSelection();
        return;
      }
    }
    if(!MAP.lastState) return;
    document.getElementById('mapModal').classList.remove('show');
    if(typeof openStates === 'function') openStates(MAP.lastState);
  });
  wrap.addEventListener('wheel', e=>{
    if(!MAP.ready) return;
    e.preventDefault();
    const r = wrap.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const k2 = Math.max(0.06, Math.min(32, MAP.k * (e.deltaY < 0 ? 1.16 : 0.86)));
    MAP.x = mx - (mx - MAP.x) * (k2 / MAP.k);
    MAP.y = my - (my - MAP.y) * (k2 / MAP.k);
    MAP.k = k2;
    mapApply();
  }, {passive: false});
}


async function mapClearCache(){
  if(!confirm('清理已生成的地图图层缓存？源文件不会动，下次打开需要重新构建约 13 秒。')) return;
  try{
    const r = await (await fetch('/api/map_cache_clear', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'})).json();
    MAP.ready = false;
    MAP.idCanvas = null;
    MAP.idx = null;
    MAP.centers = null;
    document.getElementById('mapMeta').textContent = '缓存已清理（点「构建图层」重建）';
    status(r.msg || '已清理地图缓存');
  }catch(e){ status('清理失败：' + e.message, true); }
}


async function mapBuild(){
  const metaEl = document.getElementById('mapMeta');
  metaEl.textContent = '构建中…（约 15 秒）';
  startLoading('正在构建地图图层…');
  try{
    const r = await (await fetch('/api/map_build', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({force: true, root: MAP.root || ''})})).json();
    stopLoading(r.ok ? '地图图层构建完成' : (r.msg || '构建失败'), !r.ok);
    if(r.ok){
      MAP.ready = false; MAP.idCanvas = null;
      await mapLoadMeta();
    } else {
      metaEl.textContent = r.msg || '构建失败';
    }
  }catch(e){
    stopLoading('构建失败：' + e.message, true);
    metaEl.textContent = '构建失败：' + e.message;
  }
}
