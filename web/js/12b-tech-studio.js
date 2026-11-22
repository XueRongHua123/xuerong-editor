// 12b-tech-studio：科技树工作台（Tech Tree Studio Milestone 2）
// 基于 /api/tech_studio 的全量 GUI + 坐标 + 连线 + 国家开局 + 导入贴图工作台。

(function(){
  const S = {
    data: null,
    folder: '',
    mode: 'select', // select | link | xor | unlink
    linkSrc: null,
    countryTag: '',
    brush: false,
    selEdge: null,
    catTokens: [],
    catDirty: false,
    loading: false,
    yearCrossHint: null,
  };

  function el(id){ return document.getElementById(id); }

  function activeRoot(){
    if(typeof _writableRoot === 'function'){
      const wr = _writableRoot();
      if(wr) return wr;
    }
    if(typeof _lastRoot === 'function') return _lastRoot();
    return '';
  }

  function techRootFor(t){
    if(t && t.source && typeof rootByName === 'function'){
      return rootByName(t.source) || activeRoot();
    }
    return activeRoot();
  }

  async function apiPost(url, body){
    const r = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {})
    });
    return await r.json();
  }

  // ---------------- 坐标换算（与后端 _gridbox_pixel_pos 对齐） ----------------

  function resolvePct(rawVal, total, defVal){
    const s = String(rawVal == null ? '' : rawVal).trim();
    if(!s) return defVal || 0;
    if(s.endsWith('%')){
      const p = parseFloat(s.slice(0, -1));
      return isFinite(p) ? Math.round(total * p / 100) : (defVal || 0);
    }
    const v = parseFloat(s);
    return isFinite(v) ? Math.round(v) : (defVal || 0);
  }

  function gbBaseX(gb, stripesW){
    if(!gb) return 0;
    const fmt = String(gb.format || 'LEFT').toUpperCase();
    let baseX = Number(gb.x || 0);
    const bwRaw = String(gb.size_w_raw || '').trim();
    if((fmt === 'UP' || fmt === 'DOWN') && bwRaw.endsWith('%')){
      baseX += Math.floor(resolvePct(bwRaw, stripesW || 1400, 0) / 2);
    }
    return baseX;
  }

  function gridToPixel(gb, fx, fy, stripesW){
    if(!gb) return {px: Math.round((fy || 0) * 180 + 80), py: Math.round((fx || 0) * 90 + 80)};
    const fmt = String(gb.format || 'LEFT').toUpperCase();
    const gx = Number(gb.x || 0);
    const gy = Number(gb.y || 0);
    const sw = Number(gb.slot_w || 70) || 70;
    const sh = Number(gb.slot_h || 70) || 70;
    const bx = gbBaseX(gb, stripesW);
    if(fmt === 'LEFT') return {px: Math.round(gx + fy * sw), py: Math.round(gy + fx * sh)};
    if(fmt === 'RIGHT') return {px: Math.round(gx - fy * sw), py: Math.round(gy + fx * sh)};
    if(fmt === 'DOWN') return {px: Math.round(bx + fx * sw), py: Math.round(gy - fy * sh)};
    return {px: Math.round(bx + fx * sw), py: Math.round(gy + fy * sh)};
  }

  function pixelToGrid(gb, px, py, stripesW){
    if(!gb) return {fx: Math.round((py - 80) / 90), fy: Math.round((px - 80) / 180)};
    const fmt = String(gb.format || 'LEFT').toUpperCase();
    const gx = Number(gb.x || 0);
    const gy = Number(gb.y || 0);
    const sw = Number(gb.slot_w || 70) || 70;
    const sh = Number(gb.slot_h || 70) || 70;
    const bx = gbBaseX(gb, stripesW);
    if(fmt === 'LEFT') return {fx: Math.round((py - gy) / sh), fy: Math.round((px - gx) / sw)};
    if(fmt === 'RIGHT') return {fx: Math.round((py - gy) / sh), fy: Math.round((gx - px) / sw)};
    if(fmt === 'DOWN') return {fx: Math.round((px - bx) / sw), fy: Math.round((gy - py) / sh)};
    return {fx: Math.round((px - bx) / sw), fy: Math.round((py - gy) / sh)};
  }

  function cardSize(){
    const gui = (S.data && S.data.gui) || {};
    const st = gui.item_style || {};
    const w = Math.max(120, Math.min(220, Number(st.width) || 168));
    const h = Math.max(54, Math.min(96, Number(st.height) || 68));
    return {w, h};
  }

  // ---------------- 载入与状态同步 ----------------

  async function techStudioLoad(opts){
    opts = opts || {};
    const folder = opts.folder !== undefined ? opts.folder : (ttFolder || S.folder || '');
    const tag = opts.tag !== undefined ? opts.tag : S.countryTag;
    if(S.loading && !opts.force) return;
    S.loading = true;
    try{
      const j = await apiPost('/api/tech_studio', {
        root: activeRoot() || null,
        folder: folder || null,
        tag: tag || null
      });
      if(!j || !j.ok){
        if(!opts.silent) status((j && j.msg) || '科技树工作台加载失败', true);
        return;
      }
      S.data = j;
      S.folder = j.folder || folder || '';
      ttFolder = S.folder;
      S.selEdge = null;
      S.linkSrc = null;

      renderFolderTabs();
      renderRootList();
      renderCountrySelectors();
      renderGuiPane();
      renderFootDiagnostics();
      renderStudioCanvas();
      updateHint();

      if(techSel){
        const curT = ((DATA && DATA.techs) || []).find(x=>x.id === techSel.id) || techSel;
        renderTechNodePanel(curT, null);
      }
      if(opts.fit !== false && typeof fitTT === 'function'){
        requestAnimationFrame(()=>fitTT());
      }
    }catch(e){
      if(!opts.silent) status('科技树工作台加载出错：' + e.message, true);
    }finally{
      S.loading = false;
    }
  }

  function renderFolderTabs(){
    const box = el('techFolderTabs');
    if(!box || !S.data) return;
    const folders = S.data.folders || [];
    const map = (DATA && DATA.techIconMap) || {};
    box.innerHTML = '';
    folders.forEach(f=>{
      const b = document.createElement('button');
      b.className = 'tt-tab' + (f.id === S.folder ? ' on' : '');
      b.dataset.folder = f.id;
      const spr = f.tab_sprite || ('GFX_' + f.id + '_tab');
      const icon = f.tab_icon_url || map[spr] || '';
      const warn = (!f.registered || !f.has_gui) ? ' <span style="color:var(--warn)">!</span>' : '';
      b.innerHTML = (icon ? '<img src="' + escapeHtml(icon) + '" onerror="this.style.display=\'none\'">' : '') +
        escapeHtml((f.name && f.name !== f.id) ? f.name : f.id.replace(/_folder$/, '')) +
        ' <span class="muted">(' + (f.tech_count || 0) + ')</span>' + warn;
      b.title = f.id + (f.registered ? '' : '（未在 00_technology.txt 注册）') + (f.has_gui ? '' : '（缺少 GUI 页面）');
      b.onclick = ()=>{
        if(ttDirty.size && !confirm('当前有 ' + ttDirty.size + ' 个未保存位置，切换页签将清空未保存拖动，继续吗？')) return;
        ttDirty.clear();
        S.folder = f.id;
        ttFolder = f.id;
        techStudioLoad({folder: f.id, fit: true});
      };
      box.appendChild(b);
    });
  }

  function renderRootList(){
    const box = el('ttRootList');
    if(!box || !S.data) return;
    const gbs = (S.data.gui && S.data.gui.gridboxes) || [];
    box.innerHTML = '';
    if(!gbs.length){
      box.innerHTML = '<div class="muted" style="font-size:11px;padding:4px">本页尚未注册 gridboxtype 根树</div>';
      return;
    }
    gbs.forEach(gb=>{
      const row = document.createElement('div');
      row.className = 'tt-root-item' + (techSel && techSel.id === gb.root_tech ? ' on' : '');
      row.innerHTML = '<span class="rn" title="' + escapeHtml(gb.name) + '">' + escapeHtml(gb.root_tech || gb.name) + '</span>' +
        '<span class="rm">' + escapeHtml(gb.format || 'LEFT') + ' (' + gb.x + ',' + gb.y + ')</span>' +
        '<button class="tt-root-del" title="编辑此 gridbox">✎</button>' +
        '<button class="tt-root-del" title="删除此 gridbox">×</button>';
      const btns = row.querySelectorAll('button');
      row.onclick = e=>{
        if(e.target.tagName === 'BUTTON') return;
        const t = ((DATA && DATA.techs) || []).find(x=>x.id === gb.root_tech);
        if(t && typeof selectTech === 'function') selectTech(t);
        focusCanvasPoint(gb.x + 80, gb.y + 40);
      };
      btns[0].onclick = e=>{ e.stopPropagation(); openGridboxDialog(gb); };
      btns[1].onclick = async e=>{
        e.stopPropagation();
        if(!confirm('从 GUI 中删除 gridbox ' + gb.name + ' ？')) return;
        const r = await apiPost('/api/tech_gridbox_save', {
          root: activeRoot(), folder: S.folder, op: 'delete', data: {name: gb.name}
        });
        status(r.msg || '', !r.ok);
        if(r.ok) techStudioLoad({silent: true, fit: false});
      };
      box.appendChild(row);
    });
  }

  function focusCanvasPoint(px, py){
    const svg = el('techSvg');
    if(!svg) return;
    const r = svg.getBoundingClientRect();
    if(!r.width || !r.height) return;
    ttView.x = r.width / 2 - px * ttView.k;
    ttView.y = r.height / 2 - py * ttView.k;
    if(typeof applyTT === 'function') applyTT();
  }

  // ---------------- SVG 画布渲染 ----------------

  function setMode(mode){
    S.mode = mode || 'select';
    S.linkSrc = null;
    [['select', 'ttModeSelect'], ['link', 'ttModeLink'], ['xor', 'ttModeXor'], ['unlink', 'ttModeUnlink']].forEach(([m, id])=>{
      const b = el(id);
      if(b) b.classList.toggle('on', S.mode === m);
    });
    const svg = el('techSvg');
    if(svg) svg.style.cursor = (S.mode === 'select') ? (ttEdit ? 'default' : 'grab') : 'crosshair';
    updateHint();
    renderStudioCanvas();
  }

  function renderStudioCanvas(){
    const view = el('ttView');
    const svg = el('techSvg');
    if(!view || !svg || !S.data) return;

    const gui = S.data.gui || {};
    const nodes = S.data.nodes || [];
    const edges = S.data.edges || [];
    const gbs = gui.gridboxes || [];
    const years = gui.years || [];
    const subtitles = gui.subtitles || [];
    const stripesW = Number(gui.stripes_w) || 1400;
    const stripesH = Number(gui.stripes_h) || 1275;
    const cs = cardSize();
    const showBg = !el('ttShowBg') || el('ttShowBg').checked;
    const showYears = !el('ttShowYears') || el('ttShowYears').checked;
    const showGb = !el('ttShowGridbox') || el('ttShowGridbox').checked;
    const snapGrid = !el('ttSnapGrid') || el('ttSnapGrid').checked;
    const unlockedSet = new Set(S.data.unlocked || []);

    const gbByName = {};
    gbs.forEach(gb=>{ gbByName[gb.name] = gb; });

    // 计算节点最终绘制坐标（包含待保存拖拽坐标与隐身区停放坐标）
    const pos = {};
    let invIdx = 0;
    nodes.forEach(n=>{
      const dirtyMove = ttDirty.get(n.id);
      const gb = gbByName[n.gridbox];
      if(dirtyMove){
        const p = gridToPixel(gb, dirtyMove.x, dirtyMove.y, stripesW);
        pos[n.id] = {x: p.px, y: p.py, fx: dirtyMove.x, fy: dirtyMove.y, n, gb, visible: !!gb};
      } else if(n.px != null && n.py != null){
        pos[n.id] = {x: n.px, y: n.py, fx: n.fx, fy: n.fy, n, gb, visible: n.visible_in_game};
      } else {
        const col = invIdx % 5;
        const row = Math.floor(invIdx / 5);
        invIdx++;
        pos[n.id] = {
          x: 40 + col * (cs.w + 26),
          y: stripesH + 56 + row * (cs.h + 24),
          fx: n.fx, fy: n.fy, n, gb, visible: false
        };
      }
    });

    ttOrigin = gbs.length ? {minx: 0, miny: 0} : (nodes.some(n=>n.fx != null) ? {minx: 0, miny: 0} : null);

    let out = '<defs>' +
      '<marker id="ttArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">' +
        '<path d="M0,1 L9,5 L0,9 z" fill="var(--muted)"/>' +
      '</marker>' +
      '<marker id="ttArrowSel" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">' +
        '<path d="M0,1 L9,5 L0,9 z" fill="var(--accent)"/>' +
      '</marker>' +
    '</defs>';

    // 1. 背景与吸附格网
    if(showBg){
      const bp = gui.bg_pos || {x: 0, y: 0};
      if(gui.bg_url){
        out += '<image href="' + escapeHtml(gui.bg_url) + '" x="' + (bp.x || 0) + '" y="' + (bp.y || 0) +
          '" width="' + stripesW + '" height="' + stripesH + '" preserveAspectRatio="none" opacity="0.82"/>';
      }
      out += '<rect class="tt-page-frame" x="0" y="0" width="' + stripesW + '" height="' + stripesH + '"/>';
    }
    if(snapGrid && gbs.length){
      const sw = Number(gbs[0].slot_w) || 70;
      const sh = Number(gbs[0].slot_h) || 70;
      const ox = ((Number(gbs[0].x) || 0) % sw + sw) % sw;
      const oy = ((Number(gbs[0].y) || 0) % sh + sh) % sh;
      for(let gx = ox; gx <= stripesW; gx += sw){
        out += '<line class="tt-grid-line" x1="' + gx + '" y1="0" x2="' + gx + '" y2="' + stripesH + '"/>';
      }
      for(let gy = oy; gy <= stripesH; gy += sh){
        out += '<line class="tt-grid-line" x1="0" y1="' + gy + '" x2="' + stripesW + '" y2="' + gy + '"/>';
      }
    }

    // 2. 分区标题
    if(showBg){
      subtitles.forEach((sub, idx)=>{
        const label = (sub.loc_text && sub.loc_text !== sub.text) ? sub.loc_text : (sub.text || sub.name);
        const w = Math.max(90, Math.min(360, label.length * 13 + 24));
        out += '<g class="tt-sub-handle" data-idx="' + idx + '" transform="translate(' + (sub.x || 0) + ',' + (sub.y || 0) + ')">' +
          '<rect x="0" y="-14" width="' + w + '" height="22"/>' +
          '<text x="8" y="1">' + escapeHtml(label) + '</text></g>';
      });
    }

    // 3. 年代标尺线
    if(showYears){
      const isHoriz = !gbs.length || ['LEFT', 'RIGHT'].includes(String(gbs[0].format || 'LEFT').toUpperCase());
      years.forEach((yr, idx)=>{
        const x = Number(yr.x) || 0;
        const y = Number(yr.y) || 0;
        if(isHoriz){
          out += '<line class="tt-year-line" x1="' + x + '" y1="0" x2="' + x + '" y2="' + stripesH + '"/>';
        } else {
          out += '<line class="tt-year-line" x1="0" y1="' + y + '" x2="' + stripesW + '" y2="' + y + '"/>';
        }
        out += '<g class="tt-year-handle" data-idx="' + idx + '" transform="translate(' + x + ',' + y + ')">' +
          '<rect x="-26" y="-12" width="52" height="22"/>' +
          '<text x="0" y="3" text-anchor="middle">' + escapeHtml(yr.text || '') + '</text></g>';
      });
    }

    // 4. gridboxtype 根树框
    if(showGb){
      gbs.forEach((gb, idx)=>{
        const members = Object.values(pos).filter(p=>p.gb && p.gb.name === gb.name);
        let minX = gb.x, minY = gb.y, maxX = gb.x + cs.w + 20, maxY = gb.y + cs.h + 20;
        if(members.length){
          minX = Math.min(gb.x, ...members.map(m=>m.x)) - 14;
          minY = Math.min(gb.y, ...members.map(m=>m.y)) - 14;
          maxX = Math.max(gb.x + cs.w, ...members.map(m=>m.x + cs.w)) + 14;
          maxY = Math.max(gb.y + cs.h, ...members.map(m=>m.y + cs.h)) + 14;
        }
        const bw = Math.max(120, maxX - minX);
        const bh = Math.max(60, maxY - minY);
        const label = gb.name + ' [' + (gb.format || 'LEFT') + ']';
        const hw = Math.max(120, label.length * 7 + 18);
        out += '<rect class="tt-gb-box" x="' + minX + '" y="' + minY + '" width="' + bw + '" height="' + bh + '" rx="8"/>' +
          '<g class="tt-gb-handle" data-idx="' + idx + '" transform="translate(' + minX + ',' + (minY - 20) + ')">' +
          '<rect width="' + hw + '" height="18"/>' +
          '<text x="7" y="13">' + escapeHtml(label) + '</text></g>';
      });
    }

    // 隐身区提示框
    if(invIdx > 0){
      const rows = Math.ceil(invIdx / 5);
      out += '<rect x="20" y="' + (stripesH + 22) + '" width="' + Math.max(stripesW - 40, 960) + '" height="' +
        (rows * (cs.h + 24) + 50) + '" rx="8" fill="none" stroke="var(--warn)" stroke-dasharray="6 4" opacity="0.65"/>' +
        '<text x="34" y="' + (stripesH + 44) + '" fill="var(--warn)" font-size="12" font-weight="600">' +
        '⚠ 未绑定根树 / 缺坐标停放区（共 ' + invIdx + ' 项，游戏内不可见；可点底栏「一键修复」）</text>';
    }

    // 5. 连线层（path + xor）
    edges.forEach((ed, idx)=>{
      const a = pos[ed.from], b = pos[ed.to];
      if(!a || !b) return;
      const dx = (b.x - a.x), dy = (b.y - a.y);
      let x1, y1, x2, y2, dStr;
      if(ed.type === 'xor'){
        x1 = a.x + cs.w / 2; y1 = a.y + cs.h / 2;
        x2 = b.x + cs.w / 2; y2 = b.y + cs.h / 2;
        dStr = 'M' + x1 + ',' + y1 + ' L' + x2 + ',' + y2;
      } else if(Math.abs(dx) >= Math.abs(dy)){
        x1 = dx >= 0 ? (a.x + cs.w) : a.x;
        y1 = a.y + cs.h / 2;
        x2 = dx >= 0 ? b.x : (b.x + cs.w);
        y2 = b.y + cs.h / 2;
        const mx = (x1 + x2) / 2;
        dStr = 'M' + x1 + ',' + y1 + ' C' + mx + ',' + y1 + ' ' + mx + ',' + y2 + ' ' + x2 + ',' + y2;
      } else {
        x1 = a.x + cs.w / 2;
        y1 = dy >= 0 ? (a.y + cs.h) : a.y;
        x2 = b.x + cs.w / 2;
        y2 = dy >= 0 ? b.y : (b.y + cs.h);
        const my = (y1 + y2) / 2;
        dStr = 'M' + x1 + ',' + y1 + ' C' + x1 + ',' + my + ' ' + x2 + ',' + my + ' ' + x2 + ',' + y2;
      }
      const isSel = S.selEdge && S.selEdge.type === ed.type && S.selEdge.from === ed.from && S.selEdge.to === ed.to;
      const cls = 'tt-edge' + (isSel ? ' sel' : '');
      const marker = ed.type === 'path' ? (' marker-end="url(#' + (isSel ? 'ttArrowSel' : 'ttArrow') + ')"') : '';
      out += '<g class="' + cls + '" data-eidx="' + idx + '">' +
        '<path class="' + (ed.type === 'xor' ? 'tt-edge-xor' : 'tt-edge-path') + '" d="' + dStr + '"' + marker + '/>' +
        '<path class="tt-edge-hit" d="' + dStr + '"/>';
      if(ed.type === 'path' && ed.coeff != null && Number(ed.coeff) !== 1){
        const bx = (x1 + x2) / 2, by = (y1 + y2) / 2;
        out += '<g class="tt-edge-badge" transform="translate(' + bx + ',' + by + ')">' +
          '<rect x="-16" y="-8" width="32" height="16"/><text x="0" y="3" text-anchor="middle">×' + escapeHtml(String(ed.coeff)) + '</text></g>';
      }
      out += '</g>';
    });

    // 6. 节点层
    let maxX = stripesW, maxY = stripesH;
    nodes.forEach(n=>{
      const p = pos[n.id];
      if(!p) return;
      maxX = Math.max(maxX, p.x + cs.w + 80);
      maxY = Math.max(maxY, p.y + cs.h + 80);
      const cls = ['tt-node'];
      if(unlockedSet.has(n.id)) cls.push('unlocked');
      if(!p.visible) cls.push('invisible');
      if(techSel && techSel.id === n.id) cls.push('selected');
      if(ttDirty.has(n.id)) cls.push('dirty');
      if(S.linkSrc === n.id) cls.push('link-src');

      const title = (n.name && n.name !== n.id) ? n.name : n.id;
      const shortTitle = title.length > 13 ? (title.slice(0, 12) + '…') : title;
      const iconHtml = n.icon_url
        ? '<image href="' + escapeHtml(n.icon_url) + '" x="8" y="' + Math.round((cs.h - 36) / 2) + '" width="36" height="36" preserveAspectRatio="xMidYMid meet"/>'
        : '';
      const tx = n.icon_url ? 50 : 10;
      const coordStr = (p.fx != null && p.fy != null) ? ('(' + p.fx + ',' + p.fy + ')') : '无坐标';
      const badge = !p.visible
        ? '<g class="tt-node-badge" transform="translate(' + (cs.w - 46) + ',-7)"><rect width="44" height="14"/><text x="22" y="10" text-anchor="middle">隐身</text></g>'
        : '';

      out += '<g class="' + cls.join(' ') + '" data-id="' + escapeHtml(n.id) + '" transform="translate(' + p.x + ',' + p.y + ')">' +
        '<rect class="tt-node-bg" width="' + cs.w + '" height="' + cs.h + '"/>' +
        iconHtml +
        '<text class="tt-node-title" x="' + tx + '" y="22">' + escapeHtml(shortTitle) + '</text>' +
        '<text class="meta" x="' + tx + '" y="39">' + escapeHtml(n.year || '-') + ' · c' + escapeHtml(String(n.cost || 1)) + '</text>' +
        '<text class="meta" x="' + tx + '" y="54">' + escapeHtml(coordStr) + '</text>' +
        badge +
        '<circle class="tt-link" data-id="' + escapeHtml(n.id) + '" cx="' + cs.w + '" cy="' + (cs.h / 2) + '" r="6"/>' +
        '<title>' + escapeHtml(title + ' (' + n.id + ')') + '\n年份: ' + escapeHtml(n.year || '-') +
        '  gridbox: ' + escapeHtml(n.gridbox || '无') + '</title></g>';
    });

    view.innerHTML = out;
    view.dataset.w = Math.max(800, maxX);
    view.dataset.h = Math.max(600, maxY);

    if(typeof applyTechHighlight === 'function') applyTechHighlight();
    bindCanvasInteractions(pos, stripesW, stripesH);
  }

  function svgPoint(ev){
    const svg = el('techSvg');
    const view = el('ttView');
    const p = svg.createSVGPoint();
    p.x = ev.clientX;
    p.y = ev.clientY;
    return p.matrixTransform(view.getScreenCTM().inverse());
  }

  function findNearestYearForPos(gb, px, py){
    const years = (S.data && S.data.gui && S.data.gui.years) || [];
    if(!years.length) return null;
    const fmt = String((gb && gb.format) || 'LEFT').toUpperCase();
    const isHoriz = fmt === 'LEFT' || fmt === 'RIGHT';
    const sorted = [...years].sort((a, b)=> isHoriz ? (a.x - b.x) : (a.y - b.y));
    let matched = null;
    sorted.forEach(yr=>{
      if(isHoriz){
        if(px >= (yr.x - 40)) matched = yr.text;
      } else {
        if(py >= (yr.y - 30)) matched = yr.text;
      }
    });
    return matched;
  }

  function bindCanvasInteractions(pos, stripesW, stripesH){
    const view = el('ttView');
    const svg = el('techSvg');
    if(!view || !svg) return;

    // 节点交互（选择 / 点选刷 / 连线 / 拖动）
    view.querySelectorAll('.tt-node').forEach(nodeEl=>{
      const tid = nodeEl.dataset.id;
      const nInfo = (S.data.nodes || []).find(x=>x.id === tid);
      const tObj = ((DATA && DATA.techs) || []).find(x=>x.id === tid);

      nodeEl.addEventListener('mousedown', ev=>{
        if(ev.button !== 0) return;
        if(ev.target.closest('.tt-link')) return;
        ev.stopPropagation();

        if(S.mode !== 'select' || !ttEdit) return;
        const p = pos[tid];
        if(!p) return;
        const s0 = svgPoint(ev);
        let moved = false;
        const mv = e2=>{
          const s1 = svgPoint(e2);
          const dx = s1.x - s0.x, dy = s1.y - s0.y;
          if(Math.abs(dx) > 3 || Math.abs(dy) > 3) moved = true;
          if(!moved) return;
          nodeEl.setAttribute('transform', 'translate(' + (p.x + dx) + ',' + (p.y + dy) + ')');
        };
        const up = e2=>{
          window.removeEventListener('mousemove', mv);
          if(!moved) return;
          nodeEl._skipClick = true;
          const s1 = svgPoint(e2);
          const nx = p.x + (s1.x - s0.x);
          const ny = p.y + (s1.y - s0.y);
          const gbs = (S.data.gui && S.data.gui.gridboxes) || [];
          const gb = p.gb || gbs[0] || null;
          const g = pixelToGrid(gb, nx, ny, stripesW);
          const snap = !el('ttSnapGrid') || el('ttSnapGrid').checked;
          const snapped = snap ? gridToPixel(gb, g.fx, g.fy, stripesW) : {px: Math.round(nx), py: Math.round(ny)};

          const yrSuggest = findNearestYearForPos(gb, snapped.px, snapped.py);
          let newYear = null;
          if(yrSuggest && nInfo && String(yrSuggest) !== String(nInfo.year || '')){
            S.yearCrossHint = {tid, from: nInfo.year || '', to: yrSuggest};
            newYear = yrSuggest;
          } else {
            S.yearCrossHint = null;
          }
          ttDirty.set(tid, {
            id: tid, tid, x: g.fx, y: g.fy,
            rel: (nInfo && nInfo.file) || (tObj && tObj.file) || '',
            source: (nInfo && nInfo.source) || (tObj && tObj.source) || '',
            year: newYear || undefined
          });
          if(tObj){ tObj.fx = g.fx; tObj.fy = g.fy; }
          if(nInfo){ nInfo.fx = g.fx; nInfo.fy = g.fy; nInfo.px = snapped.px; nInfo.py = snapped.py; }
          renderStudioCanvas();
          updateHint();
          status(tid + ' → (' + g.fx + ', ' + g.fy + ')' + (newYear ? ('，跨越年代线建议年份 ' + newYear) : '') + '（未保存）');
        };
        window.addEventListener('mousemove', mv);
        window.addEventListener('mouseup', up, {once: true});
      });

      nodeEl.addEventListener('click', async ev=>{
        ev.stopPropagation();
        if(nodeEl._skipClick){ nodeEl._skipClick = false; return; }

        if(S.mode === 'link' || S.mode === 'xor' || S.mode === 'unlink'){
          if(!S.linkSrc){
            S.linkSrc = tid;
            renderStudioCanvas();
            status((S.mode === 'link' ? '连前置' : (S.mode === 'xor' ? '加互斥' : '断线')) + '：已选起点 ' + tid + '，请点目标科技');
            return;
          }
          if(S.linkSrc === tid){
            S.linkSrc = null;
            renderStudioCanvas();
            return;
          }
          const srcId = S.linkSrc;
          S.linkSrc = null;
          const srcNode = (S.data.nodes || []).find(x=>x.id === srcId);
          const url = S.mode === 'unlink' ? '/api/tech_unlink' : '/api/tech_link';
          const modeParam = S.mode === 'xor' ? 'xor' : 'path';
          const res = await apiPost(url, {
            root: techRootFor(srcNode),
            file: srcNode ? srcNode.file : '',
            source: srcId,
            target: tid,
            mode: modeParam,
            coeff: 1
          });
          status(res.msg || '', !res.ok);
          if(res.ok) await techStudioLoad({silent: true, fit: false});
          else renderStudioCanvas();
          return;
        }

        // 国家点选刷模式
        if(S.brush && S.countryTag){
          const unlockedSet = new Set(S.data.unlocked || []);
          const nextOn = !unlockedSet.has(tid);
          const r = await apiPost('/api/country_tech_toggle', {
            root: activeRoot() || null, tag: S.countryTag, tech: tid, on: nextOn
          });
          status(r.msg || '', !r.ok);
          if(r.ok) await techStudioLoad({silent: true, fit: false});
          return;
        }

        if(tObj && typeof selectTech === 'function'){
          await selectTech(tObj);
        } else if(nInfo){
          renderTechNodePanel(nInfo, null);
        }
        renderStudioCanvas();
      });

      nodeEl.addEventListener('dblclick', ev=>{
        ev.stopPropagation();
        if(tObj && typeof showTechDetail === 'function') showTechDetail(tObj);
      });
    });

    // 右侧连线手柄拖线（path 或 xor）
    view.querySelectorAll('.tt-link').forEach(h=>{
      h.addEventListener('mousedown', ev=>{
        ev.stopPropagation(); ev.preventDefault();
        const srcId = h.dataset.id;
        const srcPos = pos[srcId];
        if(!srcPos) return;
        const cs = cardSize();
        const x0 = srcPos.x + cs.w, y0 = srcPos.y + cs.h / 2;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('class', 'tt-temp');
        line.setAttribute('x1', x0); line.setAttribute('y1', y0);
        line.setAttribute('x2', x0); line.setAttribute('y2', y0);
        view.appendChild(line);
        const mv = e2=>{ const p = svgPoint(e2); line.setAttribute('x2', p.x); line.setAttribute('y2', p.y); };
        const up = async e2=>{
          window.removeEventListener('mousemove', mv);
          line.remove();
          const hitEl = document.elementFromPoint(e2.clientX, e2.clientY);
          const target = hitEl && hitEl.closest ? hitEl.closest('.tt-node') : null;
          if(target && target.dataset.id !== srcId){
            const srcNode = (S.data.nodes || []).find(x=>x.id === srcId);
            const r = await apiPost('/api/tech_link', {
              root: techRootFor(srcNode),
              file: srcNode ? srcNode.file : '',
              source: srcId,
              target: target.dataset.id,
              mode: S.mode === 'xor' ? 'xor' : 'path',
              coeff: 1
            });
            status(r.msg || '', !r.ok);
            if(r.ok) await techStudioLoad({silent: true, fit: false});
          }
        };
        window.addEventListener('mousemove', mv);
        window.addEventListener('mouseup', up, {once: true});
      });
    });

    // 连线点击（断线或选中改 coeff）
    view.querySelectorAll('.tt-edge').forEach(eGrp=>{
      eGrp.addEventListener('click', async ev=>{
        ev.stopPropagation();
        const idx = Number(eGrp.dataset.eidx);
        const ed = (S.data.edges || [])[idx];
        if(!ed) return;
        const srcNode = (S.data.nodes || []).find(x=>x.id === ed.from);
        if(S.mode === 'unlink'){
          const r = await apiPost('/api/tech_unlink', {
            root: techRootFor(srcNode),
            file: srcNode ? srcNode.file : '',
            source: ed.from,
            target: ed.to,
            mode: ed.type
          });
          status(r.msg || '', !r.ok);
          if(r.ok) await techStudioLoad({silent: true, fit: false});
          return;
        }
        S.selEdge = ed;
        renderStudioCanvas();
        showEdgeDetail(ed, srcNode);
      });
    });

    // gridbox 头部拖动手柄
    view.querySelectorAll('.tt-gb-handle').forEach(hd=>{
      hd.addEventListener('mousedown', ev=>{
        if(ev.button !== 0) return;
        ev.stopPropagation(); ev.preventDefault();
        const idx = Number(hd.dataset.idx);
        const gb = (S.data.gui.gridboxes || [])[idx];
        if(!gb) return;
        const s0 = svgPoint(ev);
        const origX = Number(gb.x || 0), origY = Number(gb.y || 0);
        let nx = origX, ny = origY, moved = false;
        const mv = e2=>{
          const s1 = svgPoint(e2);
          const dx = Math.round(s1.x - s0.x), dy = Math.round(s1.y - s0.y);
          if(Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
          nx = origX + dx; ny = origY + dy;
          hd.setAttribute('transform', 'translate(' + (nx - 14) + ',' + (ny - 34) + ')');
        };
        const up = async ()=>{
          window.removeEventListener('mousemove', mv);
          if(!moved) return;
          const r = await apiPost('/api/tech_gridbox_save', {
            root: activeRoot(), folder: S.folder, op: 'update',
            data: {name: gb.name, x: nx, y: ny}
          });
          status(r.msg || '', !r.ok);
          if(r.ok) await techStudioLoad({silent: true, fit: false});
        };
        window.addEventListener('mousemove', mv);
        window.addEventListener('mouseup', up, {once: true});
      });
    });

    // 年代标尺拖动手柄
    view.querySelectorAll('.tt-year-handle').forEach(hd=>{
      hd.addEventListener('mousedown', ev=>{
        if(ev.button !== 0) return;
        ev.stopPropagation(); ev.preventDefault();
        const idx = Number(hd.dataset.idx);
        const yr = (S.data.gui.years || [])[idx];
        if(!yr) return;
        const s0 = svgPoint(ev);
        const origX = Number(yr.x || 0), origY = Number(yr.y || 0);
        let nx = origX, ny = origY, moved = false;
        const mv = e2=>{
          const s1 = svgPoint(e2);
          const dx = Math.round(s1.x - s0.x), dy = Math.round(s1.y - s0.y);
          if(Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
          nx = origX + dx; ny = origY + dy;
          hd.setAttribute('transform', 'translate(' + nx + ',' + ny + ')');
        };
        const up = async ()=>{
          window.removeEventListener('mousemove', mv);
          if(!moved) return;
          const r = await apiPost('/api/tech_year_save', {
            root: activeRoot(), folder: S.folder, op: 'update',
            data: {name: yr.name, x: nx, y: ny}
          });
          status(r.msg || '', !r.ok);
          if(r.ok) await techStudioLoad({silent: true, fit: false});
        };
        window.addEventListener('mousemove', mv);
        window.addEventListener('mouseup', up, {once: true});
      });
    });

    // 分区标题拖动手柄
    view.querySelectorAll('.tt-sub-handle').forEach(hd=>{
      hd.addEventListener('mousedown', ev=>{
        if(ev.button !== 0) return;
        ev.stopPropagation(); ev.preventDefault();
        const idx = Number(hd.dataset.idx);
        const sub = (S.data.gui.subtitles || [])[idx];
        if(!sub) return;
        const s0 = svgPoint(ev);
        const origX = Number(sub.x || 0), origY = Number(sub.y || 0);
        let nx = origX, ny = origY, moved = false;
        const mv = e2=>{
          const s1 = svgPoint(e2);
          const dx = Math.round(s1.x - s0.x), dy = Math.round(s1.y - s0.y);
          if(Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
          nx = origX + dx; ny = origY + dy;
          hd.setAttribute('transform', 'translate(' + nx + ',' + ny + ')');
        };
        const up = async ()=>{
          window.removeEventListener('mousemove', mv);
          if(!moved) return;
          const r = await apiPost('/api/tech_subtitle_save', {
            root: activeRoot(), folder: S.folder, op: 'update',
            data: {name: sub.name, x: nx, y: ny}
          });
          status(r.msg || '', !r.ok);
          if(r.ok) await techStudioLoad({silent: true, fit: false});
        };
        window.addEventListener('mousemove', mv);
        window.addEventListener('mouseup', up, {once: true});
      });
    });
  }

  function showEdgeDetail(ed, srcNode){
    const d = el('techDetail');
    if(!d) return;
    const isPath = ed.type === 'path';
    d.innerHTML = '<h4>' + (isPath ? '前置连线（path）' : '互斥关系（xor）') + '</h4>' +
      '<div class="row">' + escapeHtml(ed.from) + (isPath ? ' → ' : ' ↔ ') + escapeHtml(ed.to) + '</div>' +
      (isPath ? '<div class="row" style="display:flex;gap:6px;align-items:center"><span>research_cost_coeff:</span>' +
        '<input type="text" data-role="coeff" value="' + escapeHtml(String(ed.coeff != null ? ed.coeff : 1)) + '" style="width:72px;margin:0"></div>' : '') +
      '<div style="display:flex;gap:6px;margin-top:8px">' +
        (isPath ? '<button class="btn primary" data-act="save">更新倍率</button>' : '') +
        '<button class="btn" data-act="unlink" style="color:var(--warn)">断开此连线</button>' +
        '<button class="btn" data-act="close">关闭</button></div>';
    d.classList.add('show');
    const closeBtn = d.querySelector('[data-act="close"]');
    if(closeBtn) closeBtn.onclick = ()=>{ d.classList.remove('show'); S.selEdge = null; renderStudioCanvas(); };
    const unlinkBtn = d.querySelector('[data-act="unlink"]');
    if(unlinkBtn) unlinkBtn.onclick = async ()=>{
      d.classList.remove('show');
      const r = await apiPost('/api/tech_unlink', {
        root: techRootFor(srcNode), file: srcNode ? srcNode.file : '',
        source: ed.from, target: ed.to, mode: ed.type
      });
      status(r.msg || '', !r.ok);
      if(r.ok) await techStudioLoad({silent: true, fit: false});
    };
    const saveBtn = d.querySelector('[data-act="save"]');
    if(saveBtn) saveBtn.onclick = async ()=>{
      const coeff = parseFloat((d.querySelector('[data-role="coeff"]') || {}).value || '1');
      if(!isFinite(coeff) || coeff <= 0){ status('倍率必须是正数', true); return; }
      const r1 = await apiPost('/api/tech_unlink', {
        root: techRootFor(srcNode), file: srcNode ? srcNode.file : '',
        source: ed.from, target: ed.to, mode: 'path'
      });
      if(!r1.ok){ status(r1.msg || '更新失败', true); return; }
      const r2 = await apiPost('/api/tech_link', {
        root: techRootFor(srcNode), file: srcNode ? srcNode.file : '',
        source: ed.from, target: ed.to, mode: 'path', coeff
      });
      status(r2.msg || '', !r2.ok);
      d.classList.remove('show');
      if(r2.ok) await techStudioLoad({silent: true, fit: false});
    };
  }

  // ---------------- 保存批量移动 & 工具提示 ----------------

  function updateHint(){
    const btn = el('ttSavePos');
    const hint = el('ttPosHint');
    if(!btn || !hint) return;
    const n = ttDirty.size;
    btn.textContent = n ? ('💾 保存位置（' + n + '）') : '💾 保存位置';
    btn.classList.toggle('primary', n > 0);
    if(S.mode === 'link') hint.textContent = S.linkSrc ? ('已选起点 ' + S.linkSrc + '，点目标建 path') : '依次点两个节点建立 path 前置';
    else if(S.mode === 'xor') hint.textContent = S.linkSrc ? ('已选 ' + S.linkSrc + '，点目标建 xor 互斥') : '依次点两个节点建立 xor 互斥';
    else if(S.mode === 'unlink') hint.textContent = '点连线或依次点两个节点断开关系';
    else if(ttEdit) hint.textContent = n ? ('已改 ' + n + ' 项坐标，点「保存位置」写回') : '拖动节点自动吸附格子；拖根树/年代手柄实时保存';
    else hint.textContent = '空白右键/双击可向导新建；开「拖动改位置」可调节点';
  }

  async function techStudioSavePositions(){
    if(!ttDirty.size){ status('没有改过位置'); return; }
    const moves = [...ttDirty.values()].map(it=>({
      tid: it.id || it.tid,
      rel: it.rel || it.file || '',
      x: it.x,
      y: it.y,
      year: it.year
    }));
    const r = await apiPost('/api/tech_batch_move', {root: activeRoot() || null, moves});
    status(r.msg || '', !r.ok);
    if(r.ok){
      ttDirty.clear();
      S.yearCrossHint = null;
      await techStudioLoad({silent: true, fit: false});
    }
  }

  // ---------------- 右栏 1：科技属性增强 ----------------

  function parseTokenBlock(raw, key){
    if(typeof _extractBlockInner !== 'function') return [];
    const inner = _extractBlockInner(raw || '', key);
    return inner ? (inner.match(/[A-Za-z][A-Za-z0-9_.]*/g) || []) : [];
  }

  function syncBlockIntoRaw(key, tokens){
    const rawEl = el('techRaw');
    if(!rawEl || !rawEl.value) return;
    let text = rawEl.value;
    const re = new RegExp('(^|\\n)[ \\t]*' + key + '\\s*=\\s*\\{');
    const m = re.exec(text);
    const body = tokens.length ? ('\t\t' + key + ' = {\n' + tokens.map(x=>'\t\t\t' + x).join('\n') + '\n\t\t}') : '';
    if(m){
      const b = text.indexOf('{', m.index);
      let d = 0, e = -1;
      for(let j = b; j < text.length; j++){
        if(text[j] === '{') d++;
        else if(text[j] === '}'){ d--; if(d === 0){ e = j + 1; break; } }
      }
      if(e > b){
        const start = m.index + (m[1] ? m[1].length : 0);
        text = text.slice(0, start) + (body ? body : '') + text.slice(e);
        rawEl.value = text.replace(/\n{3,}/g, '\n\n');
        return;
      }
    }
    if(body){
      const rb = text.lastIndexOf('}');
      if(rb > 0) rawEl.value = text.slice(0, rb).replace(/\s*$/, '\n') + body + '\n' + text.slice(rb);
    }
  }

  function renderTechNodePanel(t, detail){
    if(!t) return;
    const view = el('ttView');
    if(view){
      view.querySelectorAll('.tt-node').forEach(gn=>{
        gn.classList.toggle('selected', gn.dataset.id === t.id);
      });
    }
    const rl = el('ttRootList');
    if(rl){
      rl.querySelectorAll('.tt-root-item').forEach(r=>{
        const rn = r.querySelector('.rn');
        r.classList.toggle('on', !!(rn && rn.textContent === t.id));
      });
    }
    const ep = el('techEditPane');
    if(ep && ep.style.display !== 'none' && !detail) techStudioSyncEditPane();
    const node = S.data && (S.data.nodes || []).find(x=>x.id === t.id);

    // 图标预览
    const img = el('techIconImg');
    if(img){
      const map = (DATA && DATA.techIconMap) || {};
      const spr = (node && node.icon_gfx) || t.icon || ('GFX_' + t.id + '_medium');
      const url = node ? (node.icon_url || '') : (map[spr] || '');
      if(url){
        img.src = url;
        img.style.opacity = '1';
      } else {
        img.removeAttribute('src');
        img.style.opacity = '0.25';
      }
      img.title = spr;
      img.onerror = ()=>{ img.style.opacity = '0.25'; };
      img.onload = ()=>{ img.style.opacity = '1'; };
    }

    // 所属根树与坐标信息
    const gi = el('techGridInfo');
    if(gi){
      if(node){
        const vis = node.visible_in_game ? '<span class="tt-diag-ok">可见</span>' : '<span class="tt-diag-warn">游戏内隐身</span>';
        const coord = (node.fx != null && node.fy != null) ? ('(' + node.fx + ',' + node.fy + ') → ' + (node.px || '?') + 'px,' + (node.py || '?') + 'px') : '无坐标';
        gi.innerHTML = '<span>根树：<b>' + escapeHtml(node.gridbox || '未绑定') + '</b> · ' + escapeHtml(coord) + ' · ' + vis + '</span>' +
          (!node.gridbox && (!node.prereq || !node.prereq.length)
            ? '<button class="btn tt-mini-btn" data-act="reg-gb">注册根树</button>' : '');
        const rb = gi.querySelector('[data-act="reg-gb"]');
        if(rb) rb.onclick = async ()=>{
          const r = await apiPost('/api/tech_gridbox_save', {
            root: activeRoot(), folder: S.folder || t.path, op: 'add',
            data: {root_tech: t.id, name: t.id + '_tree', x: 140, y: 210, slot_w: 70, slot_h: 70, format: 'LEFT'}
          });
          status(r.msg || '', !r.ok);
          if(r.ok) await techStudioLoad({silent: true, fit: false});
        };
      } else {
        gi.textContent = '坐标：(' + (t.fx != null ? t.fx : '-') + ',' + (t.fy != null ? t.fy : '-') + ')';
      }
    }

    // 分类芯片
    if(detail && detail.raw){
      S.catTokens = parseTokenBlock(detail.raw, 'categories');
      S.catDirty = false;
    } else if(Array.isArray(t.categories)){
      S.catTokens = [...t.categories];
      S.catDirty = false;
    }
    renderCatChips();

    // 互斥芯片
    renderXorChips();

    // 前置与后续连线芯片
    const lBox = el('techLinkChips');
    if(lBox){
      lBox.innerHTML = '';
      const pres = (node && node.prereq) || t.prereq || [];
      const leads = (node && node.leads) || t.leads || [];
      pres.forEach(pid=>{
        const c = document.createElement('span');
        c.className = 'ts-chip pre';
        c.innerHTML = '<span class="ts-chip-clk" title="选中前置 ' + escapeHtml(pid) + '">← ' + escapeHtml(pid) + '</span>' +
          '<button class="ts-chip-x" title="断开前置">×</button>';
        c.querySelector('.ts-chip-clk').onclick = ()=>jumpToTech(pid);
        c.querySelector('.ts-chip-x').onclick = async ()=>{
          const pObj = ((DATA && DATA.techs) || []).find(x=>x.id === pid);
          const r = await apiPost('/api/tech_unlink', {
            root: techRootFor(pObj), file: pObj ? pObj.file : '', source: pid, target: t.id, mode: 'path'
          });
          status(r.msg || '', !r.ok);
          if(r.ok) await techStudioLoad({silent: true, fit: false});
        };
        lBox.appendChild(c);
      });
      leads.forEach(lid=>{
        const c = document.createElement('span');
        c.className = 'ts-chip lead';
        c.innerHTML = '<span class="ts-chip-clk" title="选中后续 ' + escapeHtml(lid) + '">→ ' + escapeHtml(lid) + '</span>' +
          '<button class="ts-chip-x" title="断开后续">×</button>';
        c.querySelector('.ts-chip-clk').onclick = ()=>jumpToTech(lid);
        c.querySelector('.ts-chip-x').onclick = async ()=>{
          const r = await apiPost('/api/tech_unlink', {
            root: techRootFor(t), file: t.file, source: t.id, target: lid, mode: 'path'
          });
          status(r.msg || '', !r.ok);
          if(r.ok) await techStudioLoad({silent: true, fit: false});
        };
        lBox.appendChild(c);
      });
      if(!pres.length && !leads.length) lBox.innerHTML = '<span class="muted" style="font-size:11px">无前后置连线</span>';
    }
  }

  function renderCatChips(){
    const box = el('techCatChips');
    if(!box) return;
    box.innerHTML = '';
    const catMeta = {};
    ((S.data && S.data.categories) || []).forEach(c=>{ catMeta[c.id] = c.name; });
    if(!S.catTokens.length){
      box.innerHTML = '<span class="muted" style="font-size:11px">未设置分类</span>';
      return;
    }
    S.catTokens.forEach(cid=>{
      const chip = document.createElement('span');
      chip.className = 'ts-chip';
      const zh = catMeta[cid] && catMeta[cid] !== cid ? (' (' + catMeta[cid] + ')') : '';
      chip.innerHTML = '<span>' + escapeHtml(cid + zh) + '</span><button class="ts-chip-x" title="移除分类">×</button>';
      chip.querySelector('button').onclick = ()=>{
        S.catTokens = S.catTokens.filter(x=>x !== cid);
        S.catDirty = true;
        syncBlockIntoRaw('categories', S.catTokens);
        renderCatChips();
      };
      box.appendChild(chip);
    });
  }

  function renderXorChips(){
    const box = el('techXorChips');
    const rawInp = el('techXorRaw');
    if(!box || !rawInp) return;
    const tokens = (rawInp.value || '').match(/[A-Za-z][A-Za-z0-9_.]*/g) || [];
    box.innerHTML = '';
    if(!tokens.length){
      box.innerHTML = '<span class="muted" style="font-size:11px">无互斥科技</span>';
      return;
    }
    tokens.forEach(xid=>{
      const chip = document.createElement('span');
      chip.className = 'ts-chip xor';
      chip.innerHTML = '<span class="ts-chip-clk">⚔ ' + escapeHtml(xid) + '</span><button class="ts-chip-x" title="移除互斥">×</button>';
      chip.querySelector('.ts-chip-clk').onclick = ()=>jumpToTech(xid);
      chip.querySelector('button').onclick = ()=>{
        const next = tokens.filter(k=>k !== xid);
        rawInp.value = next.join('\n');
        syncBlockIntoRaw('xor', next);
        renderXorChips();
      };
      box.appendChild(chip);
    });
  }

  function jumpToTech(tid){
    const t = ((DATA && DATA.techs) || []).find(x=>x.id === tid);
    if(!t) return;
    if(typeof selectTech === 'function') selectTech(t);
    if(t.path && t.path !== S.folder){
      S.folder = t.path;
      ttFolder = t.path;
      techStudioLoad({folder: t.path, fit: true});
    } else {
      renderStudioCanvas();
    }
  }

  // ---------------- 右栏 2：页面与 GUI ----------------

  function renderGuiPane(){
    if(!S.data) return;
    const fObj = (S.data.folders || []).find(f=>f.id === S.folder) || {};
    const gui = S.data.gui || {};

    const ledEl = el('ttGuiLedger');
    if(ledEl){
      const lv = fObj.ledger || '';
      if(lv && !Array.from(ledEl.options).some(o=>o.value === lv)){
        const opt = document.createElement('option');
        opt.value = lv; opt.textContent = lv;
        ledEl.appendChild(opt);
      }
      ledEl.value = lv;
    }
    if(el('ttGuiDoctrine')) el('ttGuiDoctrine').checked = !!fObj.doctrine;
    if(el('ttGuiAvail')) el('ttGuiAvail').value = fObj.available_raw || '';
    if(el('ttGuiBgName')) el('ttGuiBgName').value = gui.bg_sprite || '';
    if(el('ttGuiW')) el('ttGuiW').value = gui.stripes_w || 1400;
    if(el('ttGuiH')) el('ttGuiH').value = gui.stripes_h || 1275;

    const st = gui.item_style || {};
    const gb0 = (gui.gridboxes || [])[0] || {};
    if(el('ttGuiItemW')) el('ttGuiItemW').value = st.width || '';
    if(el('ttGuiItemH')) el('ttGuiItemH').value = st.height || '';
    if(el('ttGuiSlotW')) el('ttGuiSlotW').value = gb0.slot_w || 70;
    if(el('ttGuiSlotH')) el('ttGuiSlotH').value = gb0.slot_h || 70;

    // 年代标尺列表
    const yBox = el('ttGuiYears');
    if(yBox){
      yBox.innerHTML = '';
      (gui.years || []).forEach(yr=>{
        const row = document.createElement('div');
        row.className = 'tt-gui-row';
        row.innerHTML = '<span title="' + escapeHtml(yr.name) + '"><b>' + escapeHtml(yr.text) + '</b> (' + yr.x + ', ' + yr.y + ')</span>' +
          '<button class="btn tt-mini-btn" data-act="del">×</button>';
        row.querySelector('[data-act="del"]').onclick = async ()=>{
          if(!confirm('删除年代标尺 ' + yr.text + ' ？')) return;
          const r = await apiPost('/api/tech_year_save', {
            root: activeRoot(), folder: S.folder, op: 'delete', data: {name: yr.name}
          });
          status(r.msg || '', !r.ok);
          if(r.ok) techStudioLoad({silent: true, fit: false});
        };
        yBox.appendChild(row);
      });
      if(!(gui.years || []).length) yBox.innerHTML = '<div class="muted" style="font-size:11px;padding:3px">暂无年代标尺</div>';
    }

    // 分区标题列表
    const sBox = el('ttGuiSubtitles');
    if(sBox){
      sBox.innerHTML = '';
      (gui.subtitles || []).forEach(sub=>{
        const row = document.createElement('div');
        row.className = 'tt-gui-row';
        const txt = sub.loc_text || sub.text || sub.name;
        row.innerHTML = '<span title="' + escapeHtml(sub.name) + '">' + escapeHtml(txt) + ' (' + sub.x + ', ' + sub.y + ')</span>' +
          '<button class="btn tt-mini-btn" data-act="del">×</button>';
        row.querySelector('[data-act="del"]').onclick = async ()=>{
          if(!confirm('删除分区标题 ' + txt + ' ？')) return;
          const r = await apiPost('/api/tech_subtitle_save', {
            root: activeRoot(), folder: S.folder, op: 'delete', data: {name: sub.name}
          });
          status(r.msg || '', !r.ok);
          if(r.ok) techStudioLoad({silent: true, fit: false});
        };
        sBox.appendChild(row);
      });
      if(!(gui.subtitles || []).length) sBox.innerHTML = '<div class="muted" style="font-size:11px;padding:3px">暂无分区标题</div>';
    }
  }

  // ---------------- 右栏 3 & 工具栏：国家开局叠加与点选刷 ----------------

  function renderCountrySelectors(){
    const sel = el('ttCountrySel');
    if(sel){
      const cur = S.countryTag || sel.value || '';
      const list = (DATA && DATA.countries) || [];
      let html = '<option value="">国家叠加（无）</option>';
      list.forEach(c=>{
        const tag = c.tag || c.id || '';
        if(!tag) return;
        const lbl = c.name && c.name !== tag ? (tag + ' - ' + c.name) : tag;
        html += '<option value="' + escapeHtml(tag) + '">' + escapeHtml(lbl) + '</option>';
      });
      if(cur && !list.some(c=>(c.tag || c.id) === cur)){
        html += '<option value="' + escapeHtml(cur) + '">' + escapeHtml(cur) + '</option>';
      }
      sel.innerHTML = html;
      sel.value = cur;
    }
    const inp = el('ttCountryTagInput');
    if(inp && S.countryTag) inp.value = S.countryTag;

    const st = el('ttCountryStats');
    if(st && S.data){
      if(!S.countryTag){
        st.textContent = '未载入国家（输入 TAG 或在画布工具栏选择）';
      } else {
        const allUnlocked = (S.data.unlocked || []).length;
        const onPage = (S.data.nodes || []).filter(n=>(S.data.unlocked || []).includes(n.id)).length;
        st.innerHTML = '当前国家：<b>' + escapeHtml(S.countryTag) + '</b><br>' +
          '全局已解锁：<b>' + allUnlocked + '</b> 项 · 本页已解锁：<b>' + onPage + '</b> / ' + (S.data.nodes || []).length;
      }
    }
    if(el('ttCountryBrush')) el('ttCountryBrush').classList.toggle('on', S.brush);
    if(el('ttCountryBrush2')) el('ttCountryBrush2').checked = S.brush;
  }

  // ---------------- 底栏实时诊断与一键修复 ----------------

  function renderFootDiagnostics(){
    if(!S.data) return;
    const diag = S.data.diagnostics || {};
    const inv = diag.invisible_roots || [];
    const ov = diag.overlaps || [];
    const mc = diag.missing_cats || [];
    const mg = diag.missing_gfx || [];

    const dv = el('techDiagVis');
    const fixBtn = el('ttFixInvisibleBtn');
    if(dv){
      if(inv.length){
        dv.className = 'tt-diag-warn';
        dv.textContent = '⚠ ' + inv.length + ' 个根科技游戏内不可见（' + inv.slice(0, 3).map(x=>x.tid).join(', ') + (inv.length > 3 ? '…' : '') + '）';
      } else {
        dv.className = 'tt-diag-ok';
        dv.textContent = '✓ 本页根科技游戏内全部可见';
      }
    }
    if(fixBtn) fixBtn.style.display = inv.length ? 'inline-flex' : 'none';

    const dov = el('techDiagOverlap');
    if(dov){
      dov.className = ov.length ? 'tt-diag-warn' : 'muted';
      dov.textContent = ov.length ? ('⚠ 坐标重叠 ' + ov.length + ' 处') : '重叠：0';
    }
    const dm = el('techDiagMeta');
    if(dm){
      dm.textContent = '缺分类：' + mc.length + ' · 缺图标：' + mg.length + ' · GUI：' + (S.data.gui_source || S.data.gui_file || '-');
    }
  }

  async function fixInvisibleRoots(){
    const diag = (S.data && S.data.diagnostics) || {};
    const inv = diag.invisible_roots || [];
    if(!inv.length) return;
    let fixed = 0;
    const moves = [];
    for(let i = 0; i < inv.length; i++){
      const item = inv[i];
      if(item.reason === 'no_gridbox'){
        const r = await apiPost('/api/tech_gridbox_save', {
          root: activeRoot(), folder: S.folder, op: 'add',
          data: {root_tech: item.tid, name: item.tid + '_tree', x: 140, y: 210 + i * 110, slot_w: 70, slot_h: 70, format: 'LEFT'}
        });
        if(r.ok) fixed++;
      } else if(item.reason === 'missing_coords'){
        const n = (S.data.nodes || []).find(x=>x.id === item.tid);
        if(n) moves.push({tid: item.tid, rel: n.file, x: 0, y: i});
      }
    }
    if(moves.length){
      const mr = await apiPost('/api/tech_batch_move', {root: activeRoot(), moves});
      if(mr.ok) fixed += (mr.moved || moves.length);
    }
    status('已修复 ' + fixed + ' 个隐身根科技');
    await techStudioLoad({silent: true, fit: false});
  }

  // ---------------- 弹窗向导（新建科技 / 新建科技页 / 页签排序 / 根树 / 选图） ----------------

  function openDlg(title, bodyHtml, onBuild){
    const dlg = el('ttStudioDlg');
    if(!dlg) return;
    dlg.innerHTML = '<div class="tt-dlg-card">' +
      '<div class="tt-dlg-head"><span>' + escapeHtml(title) + '</span><button class="btn tt-mini-btn" data-act="x">关闭</button></div>' +
      '<div class="tt-dlg-body">' + bodyHtml + '</div>' +
      '<div class="tt-dlg-foot" data-role="foot"></div></div>';
    dlg.style.display = 'flex';
    dlg.querySelector('[data-act="x"]').onclick = closeDlg;
    dlg.onclick = e=>{ if(e.target === dlg) closeDlg(); };
    if(typeof onBuild === 'function') onBuild(dlg);
  }

  function closeDlg(){
    const dlg = el('ttStudioDlg');
    if(dlg){ dlg.style.display = 'none'; dlg.innerHTML = ''; }
  }

  function openNewTechWizard(prefill){
    prefill = prefill || {};
    const folders = (S.data && S.data.folders) || [];
    const curNodes = (S.data && S.data.nodes) || [];
    const folderOpts = folders.map(f=>'<option value="' + escapeHtml(f.id) + '"' + (f.id === (prefill.folder || S.folder) ? ' selected' : '') + '>' + escapeHtml(f.id) + '</option>').join('');
    const parentOpts = '<option value="">（无父科技 · 独立根树并自动注册 gridbox）</option>' +
      curNodes.map(n=>'<option value="' + escapeHtml(n.id) + '">' + escapeHtml(n.id + (n.name && n.name !== n.id ? ' - ' + n.name : '')) + '</option>').join('');

    openDlg('✨ 向导新建科技',
      '<label>科技 ID（英文数字下划线）<input type="text" data-f="id" placeholder="my_new_tech"></label>' +
      '<div class="tt-form-row">' +
        '<label>中文名称<input type="text" data-f="name" placeholder="新科技名称"></label>' +
        '<label>年份 start_year<input type="text" data-f="year" value="' + escapeHtml(String(prefill.year || '1936')) + '"></label>' +
      '</div>' +
      '<label>中文描述<textarea data-f="desc" style="height:46px" placeholder="游戏内悬停描述"></textarea></label>' +
      '<div class="tt-form-row">' +
        '<label>所属科技页 folder<select data-f="folder">' + folderOpts + '</select></label>' +
        '<label>挂接方式 / 父科技<select data-f="parent">' + parentOpts + '</select></label>' +
      '</div>' +
      '<div class="tt-form-row">' +
        '<label>格坐标 X<input type="text" data-f="x" value="' + escapeHtml(String(prefill.x != null ? prefill.x : 0)) + '"></label>' +
        '<label>格坐标 Y<input type="text" data-f="y" value="' + escapeHtml(String(prefill.y != null ? prefill.y : 0)) + '"></label>' +
      '</div>',
      dlg=>{
        const foot = dlg.querySelector('[data-role="foot"]');
        foot.innerHTML = '<button class="btn" data-act="cancel">取消</button><button class="btn primary" data-act="ok">创建科技</button>';
        foot.querySelector('[data-act="cancel"]').onclick = closeDlg;
        foot.querySelector('[data-act="ok"]').onclick = async ()=>{
          const tid = dlg.querySelector('[data-f="id"]').value.trim();
          const folder = dlg.querySelector('[data-f="folder"]').value.trim() || S.folder || 'custom_folder';
          const parent = dlg.querySelector('[data-f="parent"]').value.trim();
          const root = activeRoot();
          if(!tid){ status('请填写科技 ID', true); return; }
          if(!root){ status('先加载或新建可写模组', true); return; }
          const r = await apiPost('/api/tech_add', {
            root, id: tid, folder,
            year: dlg.querySelector('[data-f="year"]').value.trim() || '1936',
            x: Number(dlg.querySelector('[data-f="x"]').value) || 0,
            y: Number(dlg.querySelector('[data-f="y"]').value) || 0,
            parent_tech: parent || null,
            as_root: !parent,
            name_zh: dlg.querySelector('[data-f="name"]').value.trim(),
            desc_zh: dlg.querySelector('[data-f="desc"]').value.trim()
          });
          status(r.msg || '', !r.ok);
          if(r.ok){
            closeDlg();
            let hit = null;
            if(r.item && typeof _upsertDataItem === 'function') hit = _upsertDataItem('techs', r.item);
            if(typeof renderTechList === 'function') renderTechList(el('techSearch')?.value || '');
            if(hit && typeof selectTech === 'function') await selectTech(hit);
            await techStudioLoad({folder, silent: true, fit: false});
          }
        };
      });
  }

  function openNewFolderDialog(){
    const folders = (S.data && S.data.folders) || [];
    const copyOpts = '<option value="">（空白默认模板）</option>' +
      folders.filter(f=>f.has_gui).map(f=>'<option value="' + escapeHtml(f.id) + '">' + escapeHtml(f.id) + '</option>').join('');
    openDlg('＋ 新建科技页（Folder）',
      '<label>科技页 ID（如 custom_tech_folder）<input type="text" data-f="id" placeholder="my_custom_folder"></label>' +
      '<label>中文显示名<input type="text" data-f="name" placeholder="特种科技"></label>' +
      '<div class="tt-form-row">' +
        '<label>分类 ledger<select data-f="ledger"><option value="army">army</option><option value="navy">navy</option><option value="air">air</option><option value="civilian">civilian</option></select></label>' +
        '<label>复制 GUI 模板<select data-f="copy">' + copyOpts + '</select></label>' +
      '</div>' +
      '<label class="tt-chk"><input type="checkbox" data-f="doc"> 设为学说页（doctrine = yes）</label>',
      dlg=>{
        const foot = dlg.querySelector('[data-role="foot"]');
        foot.innerHTML = '<button class="btn" data-act="cancel">取消</button><button class="btn primary" data-act="ok">创建科技页</button>';
        foot.querySelector('[data-act="cancel"]').onclick = closeDlg;
        foot.querySelector('[data-act="ok"]').onclick = async ()=>{
          const fid = dlg.querySelector('[data-f="id"]').value.trim();
          if(!fid){ status('请填写科技页 ID', true); return; }
          const r = await apiPost('/api/tech_folder_save', {
            root: activeRoot(), id: fid,
            fields: {
              ledger: dlg.querySelector('[data-f="ledger"]').value,
              doctrine: dlg.querySelector('[data-f="doc"]').checked,
              copy_from: dlg.querySelector('[data-f="copy"]').value,
              name_zh: dlg.querySelector('[data-f="name"]').value.trim(),
              sync_gui: true
            }
          });
          status(r.msg || '', !r.ok);
          if(r.ok){
            closeDlg();
            await techStudioLoad({folder: fid, fit: true});
          }
        };
      });
  }

  function openReorderFoldersDialog(){
    const list = ((S.data && S.data.folders) || []).filter(f=>f.registered).map(f=>f.id);
    if(!list.length){ status('没有已注册的科技页可排序', true); return; }
    openDlg('⇄ 页签排序（00_technology.txt + GUI）', '<div data-role="list" style="display:flex;flex-direction:column;gap:4px"></div>', dlg=>{
      const box = dlg.querySelector('[data-role="list"]');
      const draw = ()=>{
        box.innerHTML = '';
        list.forEach((fid, idx)=>{
          const row = document.createElement('div');
          row.className = 'tt-reorder-row';
          row.innerHTML = '<span>' + (idx + 1) + '. <b>' + escapeHtml(fid) + '</b></span>' +
            '<button class="btn tt-mini-btn" data-d="-1"' + (idx === 0 ? ' disabled' : '') + '>↑</button>' +
            '<button class="btn tt-mini-btn" data-d="1"' + (idx === list.length - 1 ? ' disabled' : '') + '>↓</button>';
          row.querySelectorAll('button').forEach(b=>{
            b.onclick = ()=>{
              const d = Number(b.dataset.d);
              const tmp = list[idx]; list[idx] = list[idx + d]; list[idx + d] = tmp;
              draw();
            };
          });
          box.appendChild(row);
        });
      };
      draw();
      const foot = dlg.querySelector('[data-role="foot"]');
      foot.innerHTML = '<button class="btn" data-act="cancel">取消</button><button class="btn primary" data-act="ok">保存排序</button>';
      foot.querySelector('[data-act="cancel"]').onclick = closeDlg;
      foot.querySelector('[data-act="ok"]').onclick = async ()=>{
        const r = await apiPost('/api/tech_folders_reorder', {root: activeRoot(), order: list});
        status(r.msg || '', !r.ok);
        if(r.ok){ closeDlg(); await techStudioLoad({silent: true, fit: false}); }
      };
    });
  }

  function openGridboxDialog(existingGb){
    const nodes = (S.data && S.data.nodes) || [];
    const rootOpts = nodes.map(n=>'<option value="' + escapeHtml(n.id) + '"' + (existingGb && existingGb.root_tech === n.id ? ' selected' : '') + '>' + escapeHtml(n.id) + '</option>').join('');
    openDlg(existingGb ? ('编辑根树：' + existingGb.name) : '＋ 注册根树（gridboxtype）',
      (existingGb ? '' : '<label>根科技 ID<select data-f="root">' + rootOpts + '</select></label>') +
      '<label>gridbox 名称<input type="text" data-f="name" value="' + escapeHtml(existingGb ? existingGb.name : (nodes[0] ? nodes[0].id + '_tree' : '')) + '"></label>' +
      '<div class="tt-form-row">' +
        '<label>原点 X<input type="text" data-f="x" value="' + (existingGb ? existingGb.x : 140) + '"></label>' +
        '<label>原点 Y<input type="text" data-f="y" value="' + (existingGb ? existingGb.y : 210) + '"></label>' +
        '<label>格宽 slot_w<input type="text" data-f="sw" value="' + (existingGb ? existingGb.slot_w : 70) + '"></label>' +
        '<label>格高 slot_h<input type="text" data-f="sh" value="' + (existingGb ? existingGb.slot_h : 70) + '"></label>' +
      '</div>' +
      '<label>方向 format<select data-f="fmt">' +
        ['LEFT', 'RIGHT', 'UP', 'DOWN'].map(f=>'<option value="' + f + '"' + ((existingGb && existingGb.format === f) ? ' selected' : '') + '>' + f + '</option>').join('') +
      '</select></label>',
      dlg=>{
        const rootSel = dlg.querySelector('[data-f="root"]');
        const nameInp = dlg.querySelector('[data-f="name"]');
        if(rootSel && nameInp){
          rootSel.onchange = ()=>{ nameInp.value = rootSel.value + '_tree'; };
        }
        const foot = dlg.querySelector('[data-role="foot"]');
        foot.innerHTML = '<button class="btn" data-act="cancel">取消</button><button class="btn primary" data-act="ok">保存</button>';
        foot.querySelector('[data-act="cancel"]').onclick = closeDlg;
        foot.querySelector('[data-act="ok"]').onclick = async ()=>{
          const r = await apiPost('/api/tech_gridbox_save', {
            root: activeRoot(), folder: S.folder, op: existingGb ? 'update' : 'add',
            data: {
              old_name: existingGb ? existingGb.name : undefined,
              name: nameInp.value.trim(),
              root_tech: rootSel ? rootSel.value : (existingGb ? existingGb.root_tech : ''),
              x: Number(dlg.querySelector('[data-f="x"]').value) || 0,
              y: Number(dlg.querySelector('[data-f="y"]').value) || 0,
              slot_w: Number(dlg.querySelector('[data-f="sw"]').value) || 70,
              slot_h: Number(dlg.querySelector('[data-f="sh"]').value) || 70,
              format: dlg.querySelector('[data-f="fmt"]').value
            }
          });
          status(r.msg || '', !r.ok);
          if(r.ok){ closeDlg(); await techStudioLoad({silent: true, fit: false}); }
        };
      });
  }

  async function openStudioIconPicker(kind, onPick){
    const res = await (await fetch('/api/icons?kind=' + encodeURIComponent(kind))).json();
    const list = res.list || [];
    const map = res.map || {};
    openDlg(kind === 'tech_bg' ? '选择背景贴图' : '选择科技/页签图标',
      '<input type="text" data-f="q" placeholder="搜索 GFX sprite 名称…">' +
      '<div class="tt-icon-grid" data-role="grid"></div>',
      dlg=>{
        const qInp = dlg.querySelector('[data-f="q"]');
        const grid = dlg.querySelector('[data-role="grid"]');
        const draw = ()=>{
          const q = qInp.value.trim().toLowerCase();
          const hits = list.filter(g=>!q || g.toLowerCase().includes(q)).slice(0, 120);
          grid.innerHTML = '';
          if(!hits.length){ grid.innerHTML = '<div class="muted">没有匹配的图标</div>'; return; }
          hits.forEach(g=>{
            const cell = document.createElement('div');
            cell.className = 'tt-icon-cell';
            const url = map[g] || ('/api/icon?gfx=' + encodeURIComponent(g));
            cell.innerHTML = '<img src="' + escapeHtml(url) + '" loading="lazy" alt=""><span>' + escapeHtml(g) + '</span>';
            cell.onclick = ()=>{ closeDlg(); onPick(g, url); };
            grid.appendChild(cell);
          });
        };
        qInp.oninput = draw;
        draw();
      });
  }

  function readAndImportImage(file, opts, onDone){
    if(!file) return;
    const reader = new FileReader();
    reader.onload = async ()=>{
      const dataUrl = String(reader.result || '');
      const idx = dataUrl.indexOf('base64,');
      const b64 = idx >= 0 ? dataUrl.slice(idx + 7) : dataUrl;
      const r = await apiPost('/api/gfx_import', {
        root: activeRoot() || null,
        kind: opts.kind,
        name: opts.name,
        sprite: opts.sprite,
        overwrite: true,
        data_b64: b64
      });
      status(r.msg || '', !r.ok);
      if(r.ok && typeof onDone === 'function') onDone(r);
    };
    reader.readAsDataURL(file);
  }

  function openCategoryDialog(){
    if(!techSel){ status('先选择一项科技', true); return; }
    const cats = (S.data && S.data.categories) || [];
    openDlg('＋ 添加科技分类（categories）',
      '<label>选择已有分类<select data-f="sel"><option value="">（新建自定义分类）</option>' +
        cats.map(c=>'<option value="' + escapeHtml(c.id) + '">' + escapeHtml(c.id + (c.name && c.name !== c.id ? ' (' + c.name + ')' : '')) + '</option>').join('') +
      '</select></label>' +
      '<div class="tt-form-row">' +
        '<label>新分类 ID<input type="text" data-f="cid" placeholder="例如 muvluv_tsa"></label>' +
        '<label>中文名称（可选）<input type="text" data-f="zh" placeholder="战术机"></label>' +
      '</div>',
      dlg=>{
        const foot = dlg.querySelector('[data-role="foot"]');
        foot.innerHTML = '<button class="btn" data-act="cancel">取消</button><button class="btn primary" data-act="ok">添加</button>';
        foot.querySelector('[data-act="cancel"]').onclick = closeDlg;
        foot.querySelector('[data-act="ok"]').onclick = async ()=>{
          const picked = dlg.querySelector('[data-f="sel"]').value.trim();
          const newId = dlg.querySelector('[data-f="cid"]').value.trim();
          const zh = dlg.querySelector('[data-f="zh"]').value.trim();
          const cid = picked || newId;
          if(!cid){ status('请选择或输入分类 ID', true); return; }
          if(!picked){
            const r = await apiPost('/api/tech_category_add', {root: activeRoot(), id: cid, name_zh: zh});
            if(!r.ok){ status(r.msg || '注册分类失败', true); return; }
            if(S.data && S.data.categories && !S.data.categories.some(x=>x.id === cid)){
              S.data.categories.push({id: cid, name: zh || cid});
            }
          }
          if(!S.catTokens.includes(cid)){
            S.catTokens.push(cid);
            S.catDirty = true;
            syncBlockIntoRaw('categories', S.catTokens);
            renderCatChips();
          }
          closeDlg();
          status('已添加分类 ' + cid + '（请点「保存科技」写回文件）');
        };
      });
  }

  // ---------------- 表单与原文辅助区（#techEditPane） ----------------

  function techStudioSyncEditPane(){
    const info = el('ttEditFileInfo');
    if(info){
      info.textContent = techSel
        ? (techSel.id + ' · ' + (techSel.file || '-') + ' · ' + (techSel.source || '-'))
        : '未选择科技';
    }
    const snipBox = el('ttEditSnippets');
    if(snipBox && !snipBox.dataset.built){
      snipBox.dataset.built = '1';
      const snips = [
        ['+ categories', '\tcategories = {\n\t\tinfantry_weapons\n\t}'],
        ['+ enable_equipments', '\tenable_equipments = {\n\t\tinfantry_equipment_1\n\t}'],
        ['+ enable_subunits', '\tenable_subunits = {\n\t\tinfantry\n\t}'],
        ['+ xor', '\txor = {\n\t\tother_tech_id\n\t}'],
        ['+ ai_will_do', '\tai_will_do = {\n\t\tfactor = 1\n\t}']
      ];
      snips.forEach(([label, code])=>{
        const b = document.createElement('button');
        b.className = 'btn tt-mini-btn';
        b.textContent = label;
        b.onclick = ()=>{
          const rawEl = el('techRaw');
          if(!rawEl || !rawEl.value) return;
          const rb = rawEl.value.lastIndexOf('}');
          if(rb > 0){
            rawEl.value = rawEl.value.slice(0, rb).replace(/\s*$/, '\n') + code + '\n' + rawEl.value.slice(rb);
            status('已插入 ' + label + ' 到脚本原文');
          }
        };
        snipBox.appendChild(b);
      });
    }
    const macBox = el('ttEditMacroList');
    if(macBox){
      const macros = (S.data && S.data.macros) || {};
      const keys = Object.keys(macros);
      macBox.innerHTML = keys.length
        ? keys.map(k=>'<span class="ts-chip">@' + escapeHtml(k) + ' = ' + escapeHtml(macros[k]) + '</span>').join('')
        : '<span class="muted">本页文件暂无 @macro 定义</span>';
    }
    const tbl = el('ttEditPageTable');
    if(tbl && S.data){
      tbl.innerHTML = '';
      (S.data.nodes || []).forEach(n=>{
        const row = document.createElement('div');
        row.className = 'tt-pt-row' + (techSel && techSel.id === n.id ? ' on' : '');
        row.innerHTML = '<span style="font-family:Consolas,monospace">' + escapeHtml(n.id) + '</span>' +
          '<span>' + escapeHtml(n.name || n.id) + '</span>' +
          '<span>' + escapeHtml(n.year || '-') + '</span>' +
          '<span>c' + escapeHtml(String(n.cost || 1)) + '</span>' +
          '<span>' + (n.fx != null ? ('(' + n.fx + ',' + n.fy + ')') : '无坐标') + '</span>';
        row.onclick = async ()=>{
          const t = ((DATA && DATA.techs) || []).find(x=>x.id === n.id);
          if(t && typeof selectTech === 'function') await selectTech(t);
          techStudioSyncEditPane();
        };
        tbl.appendChild(row);
      });
    }
  }

  // ---------------- 右栏子页签切换与事件绑定 ----------------

  function switchRightTab(tab){
    [['tech', 'ttRTabTech', 'ttRPaneTech'], ['gui', 'ttRTabGui', 'ttRPaneGui'], ['country', 'ttRTabCountry', 'ttRPaneCountry']].forEach(([k, tid, pid])=>{
      const tb = el(tid), pn = el(pid);
      if(tb) tb.classList.toggle('on', tab === k);
      if(pn) pn.style.display = (tab === k) ? 'flex' : 'none';
    });
  }

  function bindStudioEvents(){
    const on = (id, fn)=>{ const e = el(id); if(e && !e.dataset.tsBound){ e.dataset.tsBound = '1'; e.onclick = fn; } };

    on('ttStudioNewTech', ()=>openNewTechWizard());
    on('ttFolderNew', openNewFolderDialog);
    on('ttFolderReorder', openReorderFoldersDialog);
    on('ttAddRootBox', ()=>openGridboxDialog(null));
    on('ttFixInvisibleBtn', fixInvisibleRoots);

    on('ttModeSelect', ()=>setMode('select'));
    on('ttModeLink', ()=>setMode('link'));
    on('ttModeXor', ()=>setMode('xor'));
    on('ttModeUnlink', ()=>setMode('unlink'));

    on('ttRTabTech', ()=>switchRightTab('tech'));
    on('ttRTabGui', ()=>switchRightTab('gui'));
    on('ttRTabCountry', ()=>switchRightTab('country'));

    ['ttShowBg', 'ttShowYears', 'ttShowGridbox', 'ttSnapGrid'].forEach(id=>{
      const c = el(id);
      if(c && !c.dataset.tsBound){ c.dataset.tsBound = '1'; c.onchange = renderStudioCanvas; }
    });

    // 画布空白右键 / 双击新建
    const svg = el('techSvg');
    if(svg && !svg.dataset.tsBound){
      svg.dataset.tsBound = '1';
      const openAtEv = ev=>{
        if(ev.target.closest('.tt-node,.tt-gb-handle,.tt-year-handle,.tt-sub-handle,.tt-edge-hit')) return;
        const p = svgPoint(ev);
        const gui = (S.data && S.data.gui) || {};
        const gb = (gui.gridboxes || [])[0] || null;
        const g = pixelToGrid(gb, p.x, p.y, Number(gui.stripes_w) || 1400);
        const yr = findNearestYearForPos(gb, p.x, p.y);
        openNewTechWizard({folder: S.folder, x: g.fx, y: g.fy, year: yr || '1936'});
      };
      svg.addEventListener('dblclick', openAtEv);
      svg.addEventListener('contextmenu', ev=>{ ev.preventDefault(); openAtEv(ev); });
    }

    // 国家叠加与点选刷
    const cSel = el('ttCountrySel');
    if(cSel && !cSel.dataset.tsBound){
      cSel.dataset.tsBound = '1';
      cSel.onchange = ()=>{
        S.countryTag = cSel.value.trim().toUpperCase();
        techStudioLoad({tag: S.countryTag, silent: false, fit: false});
      };
    }
    on('ttCountryLoadBtn', ()=>{
      const tag = (el('ttCountryTagInput')?.value || '').trim().toUpperCase();
      S.countryTag = tag;
      techStudioLoad({tag, silent: false, fit: false});
    });
    const toggleBrush = val=>{
      S.brush = !!val;
      if(S.brush && !S.countryTag) status('请先选择或载入一个国家 TAG', true);
      renderCountrySelectors();
    };
    on('ttCountryBrush', ()=>toggleBrush(!S.brush));
    const b2 = el('ttCountryBrush2');
    if(b2 && !b2.dataset.tsBound){ b2.dataset.tsBound = '1'; b2.onchange = ()=>toggleBrush(b2.checked); }

    // 科技图标选择与导入
    on('techIconPick', ()=>{
      if(!techSel){ status('先选择一项科技', true); return; }
      openStudioIconPicker('tech', (gfx, url)=>{
        const img = el('techIconImg');
        if(img) img.src = url;
        status('选中图标 ' + gfx + '（如需写入科技脚本请点击下方或原文添加 icon / GFX）');
      });
    });
    on('techIconUploadBtn', ()=>{
      if(!techSel){ status('先选择一项科技', true); return; }
      el('techIconFile')?.click();
    });
    const tf = el('techIconFile');
    if(tf && !tf.dataset.tsBound){
      tf.dataset.tsBound = '1';
      tf.onchange = ()=>{
        const f = tf.files && tf.files[0];
        tf.value = '';
        if(!f || !techSel) return;
        readAndImportImage(f, {
          kind: 'tech',
          name: techSel.id + '_medium',
          sprite: 'GFX_' + techSel.id + '_medium'
        }, ()=>{
          const img = el('techIconImg');
          if(img) img.src = '/api/icon?gfx=' + encodeURIComponent('GFX_' + techSel.id + '_medium') + '&t=' + Date.now();
          techStudioLoad({silent: true, fit: false});
        });
      };
    }

    // 分类与互斥联动
    on('techCatAddBtn', openCategoryDialog);
    const xorInp = el('techXorRaw');
    if(xorInp && !xorInp.dataset.tsBound){
      xorInp.dataset.tsBound = '1';
      xorInp.addEventListener('input', renderXorChips);
    }
    const rawInp = el('techRaw');
    if(rawInp && !rawInp.dataset.tsBound){
      rawInp.dataset.tsBound = '1';
      rawInp.addEventListener('input', ()=>{
        S.catTokens = parseTokenBlock(rawInp.value, 'categories');
        S.catDirty = false;
        renderCatChips();
        if(xorInp && typeof _extractBlockInner === 'function'){
          xorInp.value = _extractBlockInner(rawInp.value, 'xor');
          renderXorChips();
        }
      });
    }

    // GUI 页签保存、贴图导入、年代/标题新增、皮肤保存
    on('ttGuiSaveMeta', async ()=>{
      const r = await apiPost('/api/tech_folder_save', {
        root: activeRoot(), id: S.folder,
        fields: {
          ledger: el('ttGuiLedger')?.value || '',
          doctrine: !!el('ttGuiDoctrine')?.checked,
          available_raw: el('ttGuiAvail')?.value || ''
        }
      });
      status(r.msg || '', !r.ok);
      if(r.ok) techStudioLoad({silent: true, fit: false});
    });
    on('ttGuiTabIconBtn', ()=>{
      openStudioIconPicker('tech', async gfx=>{
        const r = await apiPost('/api/tech_folder_save', {
          root: activeRoot(), id: S.folder, fields: {tab_sprite: gfx, sync_gui: true}
        });
        status(r.msg || '', !r.ok);
        if(r.ok) techStudioLoad({silent: true, fit: false});
      });
    });
    on('ttGuiTabUploadBtn', ()=>el('ttGuiTabFile')?.click());
    const tabFile = el('ttGuiTabFile');
    if(tabFile && !tabFile.dataset.tsBound){
      tabFile.dataset.tsBound = '1';
      tabFile.onchange = ()=>{
        const f = tabFile.files && tabFile.files[0];
        tabFile.value = '';
        if(!f || !S.folder) return;
        readAndImportImage(f, {
          kind: 'tech_tab', name: S.folder, sprite: 'GFX_' + S.folder + '_tab'
        }, async res=>{
          await apiPost('/api/tech_folder_save', {
            root: activeRoot(), id: S.folder, fields: {tab_sprite: res.sprite, sync_gui: true}
          });
          techStudioLoad({silent: true, fit: false});
        });
      };
    }

    on('ttGuiBgPickBtn', ()=>{
      openStudioIconPicker('tech_bg', gfx=>{
        if(el('ttGuiBgName')) el('ttGuiBgName').value = gfx;
      });
    });
    on('ttGuiBgUploadBtn', ()=>el('ttGuiBgFile')?.click());
    const bgFile = el('ttGuiBgFile');
    if(bgFile && !bgFile.dataset.tsBound){
      bgFile.dataset.tsBound = '1';
      bgFile.onchange = ()=>{
        const f = bgFile.files && bgFile.files[0];
        bgFile.value = '';
        if(!f || !S.folder) return;
        readAndImportImage(f, {
          kind: 'tech_bg', name: S.folder + '_bg', sprite: 'GFX_' + S.folder + '_bg'
        }, res=>{
          if(el('ttGuiBgName')) el('ttGuiBgName').value = res.sprite;
        });
      };
    }
    on('ttGuiSaveBg', async ()=>{
      const r = await apiPost('/api/tech_folder_save', {
        root: activeRoot(), id: S.folder,
        fields: {
          bg_sprite: el('ttGuiBgName')?.value.trim() || '',
          stripes_w: Number(el('ttGuiW')?.value) || 1400,
          stripes_h: Number(el('ttGuiH')?.value) || 1275,
          sync_gui: true
        }
      });
      status(r.msg || '', !r.ok);
      if(r.ok) techStudioLoad({silent: true, fit: false});
    });

    on('ttGuiAddYear', ()=>{
      openDlg('＋ 添加年代标尺',
        '<label>4 位年份<input type="text" data-f="yr" value="1945"></label>' +
        '<div class="tt-form-row"><label>X 坐标<input type="text" data-f="x" value="600"></label>' +
        '<label>Y 坐标<input type="text" data-f="y" value="50"></label></div>',
        dlg=>{
          const foot = dlg.querySelector('[data-role="foot"]');
          foot.innerHTML = '<button class="btn" data-act="cancel">取消</button><button class="btn primary" data-act="ok">添加</button>';
          foot.querySelector('[data-act="cancel"]').onclick = closeDlg;
          foot.querySelector('[data-act="ok"]').onclick = async ()=>{
            const r = await apiPost('/api/tech_year_save', {
              root: activeRoot(), folder: S.folder, op: 'add',
              data: {
                text: dlg.querySelector('[data-f="yr"]').value.trim(),
                x: Number(dlg.querySelector('[data-f="x"]').value) || 0,
                y: Number(dlg.querySelector('[data-f="y"]').value) || 0
              }
            });
            status(r.msg || '', !r.ok);
            if(r.ok){ closeDlg(); techStudioLoad({silent: true, fit: false}); }
          };
        });
    });

    on('ttGuiAddSub', ()=>{
      openDlg('＋ 添加分区标题',
        '<label>标题文本 / 本地化 Key<input type="text" data-f="txt" placeholder="NEW_SECTION"></label>' +
        '<label>中文显示文本（写入本地化）<input type="text" data-f="zh" placeholder="特种装备分支"></label>' +
        '<div class="tt-form-row"><label>X 坐标<input type="text" data-f="x" value="40"></label>' +
        '<label>Y 坐标<input type="text" data-f="y" value="100"></label></div>',
        dlg=>{
          const foot = dlg.querySelector('[data-role="foot"]');
          foot.innerHTML = '<button class="btn" data-act="cancel">取消</button><button class="btn primary" data-act="ok">添加</button>';
          foot.querySelector('[data-act="cancel"]').onclick = closeDlg;
          foot.querySelector('[data-act="ok"]').onclick = async ()=>{
            const r = await apiPost('/api/tech_subtitle_save', {
              root: activeRoot(), folder: S.folder, op: 'add',
              data: {
                text: dlg.querySelector('[data-f="txt"]').value.trim(),
                text_zh: dlg.querySelector('[data-f="zh"]').value.trim(),
                x: Number(dlg.querySelector('[data-f="x"]').value) || 0,
                y: Number(dlg.querySelector('[data-f="y"]').value) || 0
              }
            });
            status(r.msg || '', !r.ok);
            if(r.ok){ closeDlg(); techStudioLoad({silent: true, fit: false}); }
          };
        });
    });

    on('ttGuiSaveStyle', async ()=>{
      const fields = {};
      const iw = Number(el('ttGuiItemW')?.value);
      const ih = Number(el('ttGuiItemH')?.value);
      const sw = Number(el('ttGuiSlotW')?.value);
      const sh = Number(el('ttGuiSlotH')?.value);
      if(iw > 0) fields.width = iw;
      if(ih > 0) fields.height = ih;
      if(sw > 0) fields.slot_w = sw;
      if(sh > 0) fields.slot_h = sh;
      const r = await apiPost('/api/tech_item_style_save', {root: activeRoot(), folder: S.folder, fields});
      status(r.msg || '', !r.ok);
      if(r.ok) techStudioLoad({silent: true, fit: false});
    });

    on('ttEditCheckBtn', ()=>{
      const raw = el('techRaw')?.value || '';
      if(!raw.trim()){ status('脚本原文为空', true); return; }
      let d = 0, bad = false;
      for(const ch of raw){ if(ch === '{') d++; else if(ch === '}'){ d--; if(d < 0){ bad = true; break; } } }
      if(bad || d !== 0){ status('花括号不匹配（当前余量 ' + d + '）', true); return; }
      if(!/research_cost\s*=/.test(raw)){ status('缺少 research_cost 字段', true); return; }
      if(!/(start_year|year)\s*=/.test(raw)){ status('缺少 start_year / year 字段', true); return; }
      status('✓ 脚本基础结构校验通过');
    });
  }

  window.techStudioLoad = techStudioLoad;
  window.techStudioRender = renderStudioCanvas;
  window.techStudioSavePositions = techStudioSavePositions;
  window.techStudioUpdateHint = updateHint;
  window.techStudioOnSelectTech = renderTechNodePanel;
  window.techStudioGetCategoriesRaw = ()=>S.catDirty ? S.catTokens.join('\n') : null;
  window.techStudioSyncEditPane = techStudioSyncEditPane;

  if(document.readyState !== 'loading') bindStudioEvents();
  else document.addEventListener('DOMContentLoaded', bindStudioEvents);
})();
