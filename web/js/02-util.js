// 02-util：status / escapeHtml / ERR_TEXT / showError / showMutex / applyView / resetView（只被调用，不调业务）
function status(msg, isErr){ msg = locMsg(msg); statusEl.textContent = msg; statusEl.className = 'show' + (isErr?' warn':'');
  clearTimeout(statusEl._t); statusEl._t = setTimeout(()=>statusEl.classList.remove('show'), 6000); }
function escapeHtml(s){ return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

async function downloadSupportBundle(){
  status('正在打包脱敏诊断信息…');
  try{
    const r = await fetch('/api/support_bundle?download=1', {cache: 'no-store'});
    if(!r.ok){
      let msg = '导出诊断包失败（HTTP ' + r.status + '）';
      try{
        const j = await r.json();
        if(j && j.msg) msg = j.msg;
      }catch(_e){}
      status(msg, true);
      return false;
    }
    const ct = (r.headers.get('content-type') || '').toLowerCase();
    if(ct.includes('application/json')){
      const j = await r.json();
      status((j && j.msg) || '导出诊断包失败', true);
      return false;
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'xuerong-diag.zip';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(function(){
      a.remove();
      URL.revokeObjectURL(url);
    }, 1000);
    status('已导出脱敏诊断包：xuerong-diag.zip');
    return true;
  }catch(e){
    status('导出诊断包失败：' + (e && e.message ? e.message : e), true);
    return false;
  }
}
window.downloadSupportBundle = downloadSupportBundle;

/* ---------- v1.24.0 错误说人话 ----------
   后端在 _send 出口给每个 ok:false 补了 code；这里查表渲染成三行：
   第一行「发生了什么」，第二行「为什么」，第三行「怎么办（按钮）」。 */
const ERR_TEXT = {
  GAME_DIR_MISSING: {title:'未找到《钢铁雄心 IV》游戏目录',
    why:'当前未设置有效的游戏安装目录（缺少 hoi4.exe）。加载原版参考、补充底座与一键进游戏检查都需要先指定它。',
    actions:[
      ['📁 设置游戏目录', function(){ if(typeof openGameDirPicker === 'function') openGameDirPicker(); }],
      ['📦 导出诊断包', function(){ downloadSupportBundle(); }]
    ]},
  TREE_NOT_FOUND: {title:'找不到这棵国策树',
    why:'当前加载的 mod 里没有这个 id 的树。可能它来自没加载的 mod，或者 id 拼错了。',
    actions:[['重新加载数据', function(){ loadData(); }]]},
  SAVE_VERIFY_FAILED: {title:'这个节点没能保存',
    why:'文件里没找到刚写进去的内容，可能是文件格式特殊（用了 macro 或非标准写法）。',
    actions:[['再试一次', function(){ saveAll(); }]]},
  NO_WRITABLE_MOD: {title:'没有可写的地方',
    why:'现在只加载了原版 / 创意工坊目录（只读）。要改东西得先有一个属于你自己的 mod。',
    actions:[['新建一个 mod', function(){ if(typeof openNewMod === 'function') openNewMod(); }]]},
  READONLY: {title:'这里是只读的',
    why:'原版和创意工坊目录不能改。编辑器会把要改的文件复制到你自己的 mod，前提是那个 mod 已经存在。',
    actions:[['新建一个 mod', function(){ if(typeof openNewMod === 'function') openNewMod(); }]]},
  FILE_NOT_FOUND: {title:'找不到对应的文件',
    why:'这个条目记的来源文件不在磁盘上，可能被删了或者换了路径。',
    actions:[['重新加载数据', function(){ loadData(); }]]},
  STATE_NOT_FOUND: {title:'找不到这个州',
    why:'州 id 不在当前地图的 definition 里。可能是别的 mod 的州，或者州被换过了。',
    actions:[['重新加载数据', function(){ loadData(); }]]},
  COUNTRY_NOT_FOUND: {title:'找不到这个国家',
    why:'tag 不在当前加载链的国家列表里。检查拼写，或确认它属于哪个 mod。',
    actions:[
      ['打开国家中心', function(){ if(typeof openCountry === 'function') openCountry(); }],
      ['📚 查看叠加链', function(){ if(typeof openLayerChain === 'function') openLayerChain(); }],
      ['重新加载数据', function(){ if(typeof loadData === 'function') loadData(); }]
    ]},
  BAD_PARAM: {title:'填的内容不合法',
    why:'有字段为空、类型不对或者超出允许范围。下面括号里是后端原话。',
    actions:[
      ['重新加载数据', function(){ if(typeof loadData === 'function') loadData(); }],
      ['🩺 打开诊断', function(){ if(typeof openDiag === 'function') openDiag(); else { const d = document.getElementById('diagEntry'); if(d) d.click(); } }]
    ]},
  READ_FAILED: {title:'读不出来',
    why:'文件在，但解析失败。常见原因是编码不是 UTF-8，或者文件正被别的程序占用。',
    actions:[
      ['🩺 打开诊断', function(){ if(typeof openDiag === 'function') openDiag(); else { const d = document.getElementById('diagEntry'); if(d) d.click(); } }],
      ['📚 查看叠加链', function(){ if(typeof openLayerChain === 'function') openLayerChain(); }],
      ['重新加载数据', function(){ if(typeof loadData === 'function') loadData(); }]
    ]},
  WRITE_FAILED: {title:'写不进去',
    why:'文件被占用、目录只读，或者磁盘满了。',
    actions:[
      ['📚 查看叠加链', function(){ if(typeof openLayerChain === 'function') openLayerChain(); }],
      ['📦 导出诊断包', function(){ downloadSupportBundle(); }],
      ['重新加载数据', function(){ if(typeof loadData === 'function') loadData(); }]
    ]},
  INTERNAL: {title:'服务器内部出错',
    why:'这是编辑器的 bug，不是你填错了。操作的参数可能不完整，或者这个文件用了编辑器没预料到的写法。服务端日志里有完整调用栈（stderr 里搜 [do_POST]）。',
    actions:[
      ['📦 导出诊断包', function(){ downloadSupportBundle(); }],
      ['🩺 打开诊断', function(){ if(typeof openDiag === 'function') openDiag(); else { const d = document.getElementById('diagEntry'); if(d) d.click(); } }],
      ['重新加载数据', function(){ if(typeof loadData === 'function') loadData(); }]
    ]},
  UNKNOWN: {title:'操作没成功',
    why:'没有更具体的原因，下面是后端原话。',
    actions:[
      ['🩺 打开诊断', function(){ if(typeof openDiag === 'function') openDiag(); else { const d = document.getElementById('diagEntry'); if(d) d.click(); } }],
      ['📦 导出诊断包', function(){ downloadSupportBundle(); }],
      ['重新加载数据', function(){ if(typeof loadData === 'function') loadData(); }]
    ]}
};

function showError(j){
  const code = (j && j.code) || 'UNKNOWN';
  const e = ERR_TEXT[code] || ERR_TEXT.UNKNOWN;
  let el = document.getElementById('errBar');
  if(!el){
    el = document.createElement('div');
    el.id = 'errBar';
    document.body.appendChild(el);
  }
  const detail = (j && (j.detail || j.msg)) || '';
  el.innerHTML = '<b>' + escapeHtml(e.title) + '</b>' +
    '<span class="err-why">' + escapeHtml(e.why) +
      (detail ? '<br><em>后端原话：' + escapeHtml(detail) + '</em>' : '') + '</span>' +
    '<div class="err-acts">' +
      e.actions.map(function(a, i){
        return '<button class="btn" data-ea="' + i + '">' + escapeHtml(a[0]) + '</button>';
      }).join('') +
      '<button class="btn" data-ea="close">关闭</button></div>';
  el.querySelectorAll('[data-ea]').forEach(function(b){
    b.onclick = function(){
      const k = b.dataset.ea;
      if(k === 'close'){ el.classList.remove('show'); return; }
      const a = e.actions[Number(k)];
      el.classList.remove('show');
      if(a && typeof a[1] === 'function') a[1]();
    };
  });
  el.classList.add('show');
  clearTimeout(el._t);
  // 保存校验失败与关键排查类多留一会儿，其余 12 秒自动收
  const longCodes = (code === 'INTERNAL' || code === 'UNKNOWN' || code === 'GAME_DIR_MISSING');
  const timeoutMs = code === 'SAVE_VERIFY_FAILED' ? 20000 : (longCodes ? 18000 : 12000);
  el._t = setTimeout(function(){ el.classList.remove('show'); }, timeoutMs);
}
function showMutex(){ return document.getElementById('showMutex').checked; }
function applyView(){ vp.setAttribute('transform', `translate(${view.x},${view.y}) scale(${view.k})`); }
function resetView(){ view = {x:0,y:0,k:1}; applyView(); (typeof updateZoomLabel === 'function') && updateZoomLabel(); }

