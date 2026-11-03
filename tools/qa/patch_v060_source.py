# -*- coding: utf-8 -*-
"""v0.60：把数据源操作从国策树里独立出来，放在上方并加加载进度。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.60 数据源 ---------- */"

CSS = """  /* ---------- v0.60 数据源 ---------- */
  #srcBox{margin:10px 10px 6px;padding:10px;border:1px solid color-mix(in srgb,var(--accent) 42%,var(--line));
    border-radius:var(--r-md);
    background:linear-gradient(180deg,color-mix(in srgb,var(--accent) 9%,var(--panel)),var(--panel))}
  .src-head{display:flex;justify-content:space-between;align-items:center;font-size:10.5px;letter-spacing:1.3px;
    color:var(--accent);text-transform:uppercase;margin-bottom:8px}
  .src-badge{font-size:10px;letter-spacing:0;padding:1px 7px;border-radius:20px;
    border:1px solid color-mix(in srgb,var(--accent) 45%,transparent);color:var(--accent)}
  .src-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
  .src-btn{display:flex;flex-direction:column;gap:2px;align-items:flex-start;padding:8px 9px;
    border-radius:var(--r-sm);border:1px solid var(--line);background:var(--panel2);color:var(--text);
    cursor:pointer;text-align:left;transition:border-color .16s,background .16s}
  .src-btn:hover{border-color:var(--accent);background:var(--input)}
  .src-btn b{font-size:12px;font-weight:600;line-height:1.3}
  .src-btn i{font-size:9.5px;color:var(--muted);font-style:normal;line-height:1.3}
  .src-btn.primary{border-color:color-mix(in srgb,var(--accent) 55%,transparent);
    background:color-mix(in srgb,var(--accent) 13%,var(--panel2))}
  .src-state{margin-top:8px;font-size:10.5px;color:var(--muted);min-height:15px;line-height:1.45}
  .src-state.busy{color:var(--accent)}
  .spin{display:inline-block;width:9px;height:9px;margin-right:6px;vertical-align:-1px;
    border:2px solid color-mix(in srgb,var(--accent) 30%,transparent);border-top-color:var(--accent);
    border-radius:50%;animation:spin .8s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  #loadBar{position:fixed;top:0;left:0;right:0;height:3px;z-index:999;display:none;overflow:hidden}
  #loadBar.show{display:block}
  #loadBar .lb-inner{height:100%;width:34%;
    background:linear-gradient(90deg,transparent,var(--accent),transparent);
    animation:lbslide 1.15s ease-in-out infinite}
  @keyframes lbslide{0%{transform:translateX(-110%)}100%{transform:translateX(330%)}}
"""

BOX = """    <div id="srcBox">
      <div class="src-head"><span>数据源</span><span id="srcBadge" class="src-badge">0</span></div>
      <div class="src-grid">
        <button class="src-btn primary" id="addModBtn"><b>＋ 添加 mod</b><i>选模组根目录</i></button>
        <button class="src-btn" id="unloadModBtn"><b>－ 卸载</b><i>移除已加载项</i></button>
        <button class="src-btn" id="vanillaBtn"><b>📖 加载原版参考</b><i>只读，可卸载</i></button>
        <button class="src-btn" id="newModBtn"><b>🆕 新建模组</b><i>生成能直接玩的空壳</i></button>
      </div>
      <div id="srcState" class="src-state">还没有加载 mod</div>
    </div>
"""

JS = """/* ---------- v0.60 数据源与加载进度 ---------- */
let loadTimer = null, loadStartedAt = 0;

function startLoading(text){
  loadStartedAt = Date.now();
  const bar = document.getElementById('loadBar');
  if(bar) bar.classList.add('show');
  const st = document.getElementById('srcState');
  if(st){
    st.classList.add('busy');
    st.innerHTML = '<span class="spin"></span>' + escapeHtml(text || '加载中…') + ' <b id="loadSec">0.0s</b>';
  }
  clearInterval(loadTimer);
  loadTimer = setInterval(()=>{
    const el = document.getElementById('loadSec');
    if(el) el.textContent = ((Date.now() - loadStartedAt) / 1000).toFixed(1) + 's';
  }, 100);
}

function updateLoading(text){
  const st = document.getElementById('srcState');
  if(!st) return;
  const sec = ((Date.now() - loadStartedAt) / 1000).toFixed(1) + 's';
  st.innerHTML = '<span class="spin"></span>' + escapeHtml(text) + ' <b>' + sec + '</b>';
}

function stopLoading(msg, isErr){
  clearInterval(loadTimer); loadTimer = null;
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

function updateSourceBox(){
  const roots = (DATA && DATA.roots) || [];
  const badge = document.getElementById('srcBadge');
  if(badge) badge.textContent = String(roots.length);
  const vb = document.getElementById('vanillaBtn');
  const game = roots.find(r=>r.readonly);
  if(vb){
    vb.innerHTML = game
      ? '<b>🚫 卸载原版参考</b><i>当前已加载（只读）</i>'
      : '<b>📖 加载原版参考</b><i>只读，可卸载</i>';
    vb.classList.toggle('primary', !!game ? false : false);
  }
  const st = document.getElementById('srcState');
  if(st && !loadTimer){
    if(!roots.length){
      st.textContent = '还没有加载 mod；先「添加 mod」或加载原版参考';
    } else {
      st.textContent = roots.map(r=>{
        const n = ((COUNTRY_DATA && COUNTRY_DATA.list) || []).length;
        return (r.name || r.path) + (r.readonly ? '（原版·只读）' : '');
      }).join(' ＋ ') + ' 已加载';
    }
  }
}

async function loadVanillaWithProgress(){
  const game = ((DATA && DATA.roots) || []).find(r=>r.readonly);
  if(game){
    if(!confirm('从编辑器卸载原版参考？\\n只影响当前会话，不会删除磁盘文件。')) return;
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

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    # CSS
    anchor_css = "  #status{background:color-mix(in srgb,var(--panel) 94%,transparent)!important;color:var(--text)!important;"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, CSS + anchor_css, 1)

    # 侧栏：数据源区块插在品牌区之后
    anchor_side = '''    <details open>
      <summary>国策树</summary>'''
    assert h.count(anchor_side) == 1
    h = h.replace(anchor_side, BOX + anchor_side, 1)

    # 移除国策树里的四个旧按钮
    old_btns = '''      <div id="addModBtn" class="tabbtn" style="margin-bottom:6px">＋ 添加 mod</div>
    <div id="unloadModBtn" class="tabbtn" style="margin-bottom:6px">－ 卸载 mod / 原版</div>
    <div id="vanillaBtn" class="tabbtn" style="margin-bottom:6px">📖 加载原版参考（只读）</div>
      <div id="newModBtn" class="tabbtn" style="margin-bottom:6px">🆕 新建模组</div>
'''
    assert h.count(old_btns) == 1, '旧按钮结构不符'
    h = h.replace(old_btns, '', 1)

    # 进度条
    anchor_body = '<div id="app">'
    assert h.count(anchor_body) == 1
    h = h.replace(anchor_body, '<div id="loadBar"><div class="lb-inner"></div></div>\n' + anchor_body, 1)

    # JS
    anchor_js = "/* ---------- v0.59 科技树位置编辑 ---------- */"
    assert h.count(anchor_js) == 1
    h = h.replace(anchor_js, JS + anchor_js, 1)

    # 绑定：原版按钮走新逻辑
    old_bind = "document.getElementById('vanillaBtn').onclick = loadVanilla;"
    new_bind = "document.getElementById('vanillaBtn').onclick = loadVanillaWithProgress;"
    assert h.count(old_bind) == 1
    h = h.replace(old_bind, new_bind, 1)

    # loadData 后刷新数据源状态
    old_ld = "if(!DATA.trees || current >= DATA.trees.length) current = 0; renderAll(); applySavedSkin(); updateWelcome(); }"
    new_ld = "if(!DATA.trees || current >= DATA.trees.length) current = 0; renderAll(); applySavedSkin(); updateWelcome(); if(typeof updateSourceBox === 'function') updateSourceBox(); }"
    assert h.count(old_ld) == 1
    h = h.replace(old_ld, new_ld, 1)

    # 添加 mod：带进度
    old_add = """async function loadModPath(){
  const p = prompt('输入 mod 根目录路径（含 descriptor.mod 的那一层）：');
  if(!p) return;
  const r = await fetch('/api/load_mod', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({path: p})});
  const j = await r.json();
  status(j.msg || '', !j.ok);
  if(j.ok) await loadData();
}"""
    new_add = """async function loadModPath(){
  const p = prompt('输入 mod 根目录路径（含 descriptor.mod 的那一层）：');
  if(!p) return;
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
    }
    status(j.msg || '', !j.ok);
  }catch(e){ stopLoading('加载失败：' + e.message, true); }
}"""
    assert h.count(old_add) == 1, 'loadModPath 结构不符'
    h = h.replace(old_add, new_add, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.60 数据源面板注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
