# -*- coding: utf-8 -*-
"""v0.71 前端：地图面板（叠图 + 缩放 + 点查省 + 联动州）。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.71 地图面板 ---------- */"

CSS = """  /* ---------- v0.71 地图面板 ---------- */
  #mapModal{position:fixed;inset:0;z-index:97;display:none;place-items:center;background:rgba(8,10,9,.72);
    backdrop-filter:blur(3px)}
  #mapModal.show{display:grid}
  #mapCard{width:min(1340px,calc(100% - 32px));height:min(880px,calc(100% - 32px));display:flex;
    flex-direction:column;background:var(--panel);border:1px solid var(--line);border-radius:16px;overflow:hidden}
  #mapStageWrap{flex:1;position:relative;overflow:hidden;background:#12150f;cursor:grab}
  #mapStageWrap.dragging{cursor:grabbing}
  #mapStack{position:absolute;left:0;top:0;transform-origin:0 0;will-change:transform}
  #mapStack img{position:absolute;left:0;top:0;image-rendering:pixelated;pointer-events:none}
  #mapHud{position:absolute;left:10px;top:10px;z-index:3;background:rgba(12,14,12,.82);border:1px solid var(--line);
    border-radius:8px;padding:6px 10px;font-size:11.5px;color:var(--text);line-height:1.6;pointer-events:none;
    min-width:150px}
  #mapTools{position:absolute;right:10px;top:10px;z-index:3;display:flex;flex-direction:column;gap:6px;
    background:rgba(12,14,12,.82);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:11.5px}
  #mapTools label{display:flex;gap:6px;align-items:center;color:var(--text);cursor:pointer}
  #mapTools input[type=range]{width:80px}
  #mapSearchWrap{display:flex;gap:6px;align-items:center;margin-left:auto}
  #mapSearch{width:170px;height:28px}
"""

DOM = """    <div id="mapModal">
      <div id="mapCard">
        <div class="cm-head">
          <b>地图</b>
          <span class="k" id="mapMeta">未构建</span>
          <div id="mapSearchWrap">
            <input id="mapSearch" placeholder="省号 / 州号，回车定位">
            <button class="btn" id="mapFit">适应</button>
            <button class="btn" id="mapBuild">构建图层</button>
            <button class="btn" id="mapClose">关闭</button>
          </div>
        </div>
        <div id="mapStageWrap">
          <div id="mapStack">
            <img id="mapBase" alt="">
            <img id="mapProv" alt="">
            <img id="mapState" alt="">
            <img id="mapEdges" alt="">
          </div>
          <div id="mapHud">把鼠标移到地图上看看</div>
          <div id="mapTools">
            <label><input type="checkbox" id="mapLProv" checked>省色块</label>
            <label><input type="checkbox" id="mapLState">州</label>
            <label><input type="checkbox" id="mapLEdges" checked>省界</label>
            <label><input type="checkbox" id="mapLBase" checked>底图</label>
            <label>透明度<input type="range" id="mapOpacity" min="20" max="100" value="85"></label>
          </div>
        </div>
      </div>
    </div>
"""

JS = """/* ---------- v0.71 地图面板 ---------- */
const MAP = {x: 0, y: 0, k: 0.24, w: 5632, h: 2048, meta: null, ready: false, idCanvas: null, idx: null, centers: null};

function mapAssetUrl(name){ return '/api/map_asset?name=' + encodeURIComponent(name); }

async function openMap(){
  document.getElementById('mapModal').classList.add('show');
  if(MAP.ready){ mapApply(); return; }
  await mapLoadMeta();
}

async function mapLoadMeta(){
  const metaEl = document.getElementById('mapMeta');
  try{
    const d = await (await fetch('/api/map_meta')).json();
    if(!d.ok){ metaEl.textContent = d.msg || '没有地图数据'; return; }
    if(!d.built){
      metaEl.textContent = '图层未构建（点右上角「构建图层」，约 15 秒）';
      return;
    }
    MAP.meta = d.meta || {};
    MAP.w = MAP.meta.w || MAP.w;
    MAP.h = MAP.meta.h || MAP.h;
    await mapLoadAssets();
    metaEl.textContent = (MAP.w + '×' + MAP.h) + ' · ' + (MAP.meta.provinces || 0) + ' 块 · 构建于 ' + (MAP.meta.built || '');
    mapFit();
    mapReadyHint();
  }catch(e){ metaEl.textContent = '读取失败：' + e.message; }
}

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
  set('mapProv', 'province.png', 0.85);
  set('mapState', 'state.png', 0.62);
  set('mapEdges', 'edges.png', 0.35);
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
  MAP.ready = true;
  mapApplyLayers();
}

function mapApplyLayers(){
  const onProv = document.getElementById('mapLProv').checked;
  const onState = document.getElementById('mapLState').checked;
  const onEdges = document.getElementById('mapLEdges').checked;
  const onBase = document.getElementById('mapLBase').checked;
  const op = Number(document.getElementById('mapOpacity').value) / 100;
  const prov = document.getElementById('mapProv');
  const state = document.getElementById('mapState');
  const edges = document.getElementById('mapEdges');
  const base = document.getElementById('mapBase');
  prov.style.display = onProv ? '' : 'none';
  state.style.display = onState ? '' : 'none';
  edges.style.display = onEdges ? '' : 'none';
  base.style.display = onBase ? '' : 'none';
  prov.style.opacity = onState ? Math.min(0.35, op) : op;
  state.style.opacity = op;
  edges.style.opacity = Math.max(0.2, op * 0.5);
}

function mapApply(){
  const stack = document.getElementById('mapStack');
  stack.style.transform = 'translate(' + MAP.x + 'px,' + MAP.y + 'px) scale(' + MAP.k + ')';
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

function mapScreenToImage(clientX, clientY){
  const r = document.getElementById('mapStageWrap').getBoundingClientRect();
  return {x: (clientX - r.left - MAP.x) / MAP.k, y: (clientY - r.top - MAP.y) / MAP.k};
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

function mapInfo(pid){
  if(!pid) return '空白（海域或未定义）';
  const rec = (MAP.idx && MAP.idx[String(pid)]) || {};
  const sid = rec.state || 0;
  let stName = '';
  if(sid && typeof STATES !== 'undefined'){
    const st = Object.values(STATES || {}).find(x=>Number(x.id) === sid);
    if(st) stName = ' · ' + (st.name || ('州 ' + sid));
  }
  return '省 ' + pid + ' · 州 ' + (sid || '无') + stName + ' · ' + (rec.type || '');
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
  if(!/^\\d+$/.test(q)){ hud.textContent = '输入数字：省号或州号'; return; }
  if(MAP.centers && MAP.centers[q]){
    const c = MAP.centers[q];
    mapGoto(c[0], c[1], 1.1);
    hud.textContent = '定位到省 ' + q + ' · ' + mapInfo(Number(q));
    return;
  }
  const sid = Number(q);
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
    if(e.target.closest('#mapTools')) return;
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
    if(!MAP.ready) return;
    const p = mapScreenToImage(e.clientX, e.clientY);
    const pid = mapProvAt(p.x, p.y);
    hud.textContent = mapInfo(pid);
  });
  wrap.addEventListener('pointerup', e=>{
    wrap.classList.remove('dragging');
    const moved = drag && drag.moved;
    drag = null;
    if(moved || !MAP.ready) return;
    const p = mapScreenToImage(e.clientX, e.clientY);
    const pid = mapProvAt(p.x, p.y);
    if(!pid) return;
    const rec = (MAP.idx && MAP.idx[String(pid)]) || {};
    if(rec.state){
      status('省 ' + pid + ' → 州 ' + rec.state + '，双击可打开州面板');
      MAP.lastState = rec.state;
    }
  });
  wrap.addEventListener('dblclick', e=>{
    if(!MAP.lastState) return;
    document.getElementById('mapModal').classList.remove('show');
    if(typeof openStates === 'function') openStates(MAP.lastState);
  });
  wrap.addEventListener('wheel', e=>{
    if(!MAP.ready) return;
    e.preventDefault();
    const r = wrap.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const k2 = Math.max(0.08, Math.min(4, MAP.k * (e.deltaY < 0 ? 1.16 : 0.86)));
    MAP.x = mx - (mx - MAP.x) * (k2 / MAP.k);
    MAP.y = my - (my - MAP.y) * (k2 / MAP.k);
    MAP.k = k2;
    mapApply();
  }, {passive: false});
}

async function mapBuild(){
  const metaEl = document.getElementById('mapMeta');
  metaEl.textContent = '构建中…（约 15 秒）';
  startLoading('正在构建地图图层…');
  try{
    const r = await (await fetch('/api/map_build', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({force: true})})).json();
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

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    anchor_css = "  /* ---------- v0.68 变体写入 ---------- */"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, CSS + anchor_css, 1)

    anchor_dom = '    <div id="unloadModal">'
    assert h.count(anchor_dom) == 1
    h = h.replace(anchor_dom, DOM + anchor_dom, 1)

    # 侧栏入口
    anchor_entry = '      <div id="scriptEntry" class="tabbtn">🔍 脚本检查</div>'
    assert h.count(anchor_entry) == 1
    h = h.replace(anchor_entry, anchor_entry + '\n      <div id="mapEntry" class="tabbtn">🗺 地图</div>', 1)

    # JS 插到最后一个 script 块结尾前
    anchor_js = "\n/* ---------- v0.70 命令面板最近使用 ---------- */"
    assert h.count(anchor_js) == 1
    h = h.replace(anchor_js, "\n" + JS + "/* ---------- v0.70 命令面板最近使用 ---------- */", 1)

    # 绑定
    anchor_bind = "document.getElementById('scriptEntry').onclick = ()=>openScriptCheck(true);"
    assert h.count(anchor_bind) == 1
    bind = (anchor_bind +
            "\ndocument.getElementById('mapEntry').onclick = ()=>{ openMap(); mapBindEvents(); };"
            "\ndocument.getElementById('mapClose').onclick = ()=>{ document.getElementById('mapModal').classList.remove('show'); };"
            "\ndocument.getElementById('mapFit').onclick = mapFit;"
            "\ndocument.getElementById('mapBuild').onclick = mapBuild;"
            "\ndocument.getElementById('mapSearch').addEventListener('keydown', e=>{ if(e.key === 'Enter') mapSearchGo(); });"
            "\n['mapLProv','mapLState','mapLEdges','mapLBase'].forEach(id=>{"
            "  const el = document.getElementById(id); if(el) el.addEventListener('change', mapApplyLayers); });"
            "\nconst mapOpEl = document.getElementById('mapOpacity'); if(mapOpEl) mapOpEl.addEventListener('input', mapApplyLayers);")
    h = h.replace(anchor_bind, bind, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.71 地图前端注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
