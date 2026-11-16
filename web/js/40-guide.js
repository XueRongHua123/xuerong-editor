// 40-guide：引导条（P4）
// 三条流程（FLOWS）各走各的，stepState 判断「这一步做完没有」，renderGuide 找第一个没做完的。
// 含引导条拖拽 IIFE（window.guideApplyPos / guideResetPos）。

/* ---------- 引导面板：三条流程各走各的 ---------- */
/* 每个步骤的 ok(st) 判断「这一步做完了没有」，renderGuide 找第一个没做完的显示。 */

function gbStep(n, title, desc, actionHtml, cls){
  return '<div class="gb-step' + (cls ? ' ' + cls : '') + '">' +
         '<span class="gb-num">' + n + '</span>' +
         '<span class="gb-txt"><b>' + escapeHtml(title) + '</b>' +
         escapeHtml(desc) + (actionHtml || '') + '</span></div>';
}


function gbState(){
  const roots = (DATA && DATA.roots) || [];
  const trees = (DATA && DATA.trees) || [];
  const cur = (trees.length && typeof current === 'number' && trees[current]) ? trees[current] : null;
  return {
    roots: roots,
    trees: trees,
    tree: cur,
    selId: (typeof selId !== 'undefined' && selId) ? selId : '',
    last: roots.length ? String(roots[roots.length - 1]) : '',
    dirty: (typeof dirty !== 'undefined' && dirty) ? dirty.size : 0,
    nFocus: (cur && cur.focuses) ? cur.focuses.length : 0
  };
}

   // ④ 成功保存过一次

function stepState(){
  const s = gbState();
  return {
    s: s,
    done: [
      s.roots.length > 0,
      treePicked || !!s.selId,
      nodePicked || !!s.selId,
      savedOnce && s.dirty === 0
    ]
  };
}


function renderStepBar(){
  const bar = document.getElementById('stepBar');
  if(!bar) return;
  const dot = document.getElementById('sbDot');
  if(localStorage.getItem('stepBarHidden') === '1'){
    bar.style.display = 'none';
    if(dot) dot.style.display = 'grid';
    return;
  }
  bar.style.display = '';
  if(dot) dot.style.display = 'none';
  // 工具栏会随窗口宽度换行（1080 下是两行），写死 top:56 会被按钮盖住。
  // 这里按工具栏实际底边算位置，贴着它下面放。
  try{
    const tb = document.querySelector('#main .toolbar');
    const main = document.getElementById('main');
    if(tb && main){
      const mr = main.getBoundingClientRect(), tr = tb.getBoundingClientRect();
      bar.style.top = Math.round(tr.bottom - mr.top + 6) + 'px';
      if(dot) dot.style.top = bar.style.top;
    }
  }catch(e){}

  const {s, done} = stepState();
  const row = document.getElementById('sbRow');
  const desc = document.getElementById('sbDesc');
  const allDone = done.every(Boolean);
  let cur = done.indexOf(false);

  let html = '';
  STEP_LABELS.forEach(function(lb, i){
    const cls = done[i] ? 'done' : (i === cur ? 'cur' : '');
    html += '<span class="sb-step ' + cls + '"><i>' + (done[i] ? '✓' : (i + 1)) + '</i>' + lb + '</span>';
    if(i < STEP_LABELS.length - 1) html += '<span class="sb-arw">›</span>';
  });
  row.innerHTML = html;

  let text;
  if(allDone){
    text = '✓ 都做完了。这条可以关掉（×），左下角「下一步」还在，需要时能翻明细。';
  } else if(cur === 0){
    text = STEP_DESCS[0];
  } else if(cur === 1){
    text = STEP_DESCS[1];
  } else if(cur === 2){
    text = STEP_DESCS[2];
  } else {
    text = s.dirty ? ('还有 ' + s.dirty + ' 处改动没保存：点顶部「💾 保存」或按 Ctrl+S。') : STEP_DESCS[3];
  }
  desc.textContent = text;
  bar.classList.toggle('all', allDone);
}


/* v1.24.2 侧栏的两个引导开关（状态式勾选框，因为引导条默认显示） */
function bindGuideToggles(){
  const ckS = document.getElementById('ckStepBar');
  const ckG = document.getElementById('ckGuide');
  if(ckS && !ckS.__b){
    ckS.__b = 1;
    ckS.checked = localStorage.getItem('stepBarHidden') !== '1';
    ckS.onchange = function(){
      if(this.checked) localStorage.removeItem('stepBarHidden');
      else localStorage.setItem('stepBarHidden', '1');
      if(typeof renderStepBar === 'function') renderStepBar();
    };
  }
  if(ckG && !ckG.__b){
    ckG.__b = 1;
    ckG.checked = localStorage.getItem('guideHidden') !== '1';
    ckG.onchange = function(){
      if(this.checked){ localStorage.removeItem('guideHidden'); renderGuide(); }
      else {
        localStorage.setItem('guideHidden', '1');
        const bx = document.getElementById('guideBox');
        if(bx) bx.classList.remove('show');
      }
    };
  }
}

function syncGuideToggle(){
  const ck = document.getElementById('ckGuide');
  if(ck) ck.checked = localStorage.getItem('guideHidden') !== '1';
  const ck2 = document.getElementById('ckStepBar');
  if(ck2) ck2.checked = localStorage.getItem('stepBarHidden') !== '1';
}


function bindStepBar(){
  const close = document.getElementById('sbClose');
  if(close && !close.__b){
    close.__b = 1;
    close.onclick = function(){ localStorage.setItem('stepBarHidden', '1'); renderStepBar(); if(typeof syncGuideToggle === 'function') syncGuideToggle(); };
  }
  const dot = document.getElementById('sbDot');
  if(dot && !dot.__b){
    dot.__b = 1;
    dot.onclick = function(){ localStorage.removeItem('stepBarHidden'); renderStepBar(); if(typeof syncGuideToggle === 'function') syncGuideToggle(); };
  }
}


function renderGuide(){
  const box = document.getElementById('guideBox');
  const body = document.getElementById('gbBody');
  if(!box || !body) return;
  if(localStorage.getItem('guideHidden') === '1'){ box.classList.remove('show'); return; }
  const flow = FLOWS[localStorage.getItem('workflow') || 'edit'] || FLOWS.edit;
  const st = gbState();
  let idx = flow.steps.findIndex(s => !s.ok(st));
  if(idx < 0) idx = flow.steps.length - 1;

  let html = '<div class="gb-flow">' + escapeHtml(flow.label) + '</div>';
  // 当前这一步
  const cur = flow.steps[idx];
  let actHtml = '';
  if(cur.btns && cur.btns.length){
    actHtml = cur.btns.map(function(b){
      return '<button class="gb-btn" data-act="' + b.act + '">' + escapeHtml(b.txt) + '</button>';
    }).join(' ');
  } else if(cur.btn){
    actHtml = '<button class="gb-btn" data-act="' + cur.btn.act + '">' + escapeHtml(cur.btn.txt) + '</button>';
  }
  html += gbStep(idx + 1, cur.t, cur.d, actHtml, 'now');
  // 后面两步灰着预览
  for(let k = idx + 1; k < Math.min(idx + 3, flow.steps.length); k++){
    html += gbStep(k + 1, flow.steps[k].t, flow.steps[k].d, '', 'next');
  }
  body.innerHTML = html;

  box.classList.add('show');
  if(window.guideApplyPos) window.guideApplyPos();
}

function openGuide(){
  localStorage.removeItem('guideHidden');
  renderGuide();
}


// v1.23.40 引导清单可拖动：位置存 localStorage，双击标题栏或点「复位」回左下角
(function(){
  const K = 'fe_guide_pos';
  function apply(){
    const box = document.getElementById('guideBox');
    if(!box) return;
    let p = null;
    try{ p = JSON.parse(localStorage.getItem(K) || 'null'); }catch(e){}
    if(!p || typeof p.x !== 'number') return;
    const w = box.offsetWidth || 292, h = box.offsetHeight || 200;
    box.style.left = Math.max(2, Math.min(window.innerWidth - w - 2, p.x)) + 'px';
    box.style.top = Math.max(2, Math.min(window.innerHeight - h - 2, p.y)) + 'px';
    box.style.bottom = 'auto';
  }
  function reset(){
    const box = document.getElementById('guideBox');
    if(!box) return;
    box.style.left = '14px'; box.style.top = ''; box.style.bottom = '14px';
    try{ localStorage.removeItem(K); }catch(e){}
  }
  let dg = null;
  function bind(){
    const box = document.getElementById('guideBox');
    const head = document.getElementById('gbHead');
    if(!box || !head || head.dataset.dragBound) return;
    head.dataset.dragBound = '1';
    head.addEventListener('pointerdown', function(e){
      if(e.target.closest('button')) return;
      const r = box.getBoundingClientRect();
      dg = {sx: e.clientX, sy: e.clientY, ox: r.left, oy: r.top, moved: false};
      box.classList.add('dragging');
      try{ head.setPointerCapture(e.pointerId); }catch(err){}
    });
    head.addEventListener('pointermove', function(e){
      if(!dg) return;
      const dx = e.clientX - dg.sx, dy = e.clientY - dg.sy;
      if(Math.abs(dx) > 3 || Math.abs(dy) > 3) dg.moved = true;
      if(!dg.moved) return;
      const w = box.offsetWidth, h = box.offsetHeight;
      box.style.left = Math.max(2, Math.min(window.innerWidth - w - 2, dg.ox + dx)) + 'px';
      box.style.top = Math.max(2, Math.min(window.innerHeight - h - 2, dg.oy + dy)) + 'px';
      box.style.bottom = 'auto';
    });
    head.addEventListener('pointerup', function(){
      if(!dg) return;
      const moved = dg.moved; dg = null;
      box.classList.remove('dragging');
      if(moved){
        const r = box.getBoundingClientRect();
        try{ localStorage.setItem(K, JSON.stringify({x: Math.round(r.left), y: Math.round(r.top)})); }catch(err){}
      }
    });
    head.addEventListener('dblclick', function(e){
      if(e.target.closest('button')) return;
      reset();
    });
    const rb = document.getElementById('gbReset');
    if(rb) rb.onclick = reset;
  }
  window.guideApplyPos = apply;
  window.guideResetPos = reset;
  if(document.readyState !== 'loading') bind();
  else document.addEventListener('DOMContentLoaded', bind);
})();
