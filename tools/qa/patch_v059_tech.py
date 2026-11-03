# -*- coding: utf-8 -*-
"""v0.59 注入：科技坐标写回（后端 + 前端）。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, '..', 'focus_editor.py')
HTML = os.path.join(HERE, '..', 'focus_editor_index.html')
BLOCK = os.path.join(HERE, '_v059_tech_move.py')

DOM = """    <div id="ttTools" style="display:flex;gap:6px;align-items:center;padding:0 0 6px">
      <button class="btn" id="ttEditToggle" title="打开后可以拖动科技节点改它在树上的位置">✏️ 拖动改位置</button>
      <button class="btn" id="ttSavePos" title="把拖动后的 folder.position 写回文件">💾 保存位置</button>
      <span id="ttPosHint" style="font-size:11px;color:var(--muted)"></span>
    </div>
"""

JS = """/* ---------- v0.59 科技树位置编辑 ---------- */
let ttEdit = false, ttOrigin = null, ttDirty = new Map(), ttDragNode = null;

function ttUpdateHint(){
  const btn = document.getElementById('ttSavePos');
  const hint = document.getElementById('ttPosHint');
  if(!btn || !hint) return;
  const n = ttDirty.size;
  btn.textContent = n ? ('💾 保存位置（' + n + '）') : '💾 保存位置';
  btn.classList.toggle('primary', n > 0);
  if(!ttOrigin){
    hint.textContent = '这个 folder 里的科技还没有 position，先在文件里设置后再拖';
  } else if(ttEdit){
    hint.textContent = n ? ('已改 ' + n + ' 个，点保存写回 folder.position') : '拖动节点改位置，松手后点保存';
  } else {
    hint.textContent = '写回的是 folder.position 的 x / y，和游戏读的是同一处';
  }
}

function ttToggleEdit(){
  ttEdit = !ttEdit;
  document.getElementById('ttEditToggle').classList.toggle('on', ttEdit);
  updateTechTreeShell();
  status(ttEdit ? '科技树位置编辑已开启：拖动节点，然后点「保存位置」' : '科技树位置编辑已关闭');
}

function updateTechTreeShell(){
  const svg = document.getElementById('techSvg');
  if(svg) svg.style.cursor = ttEdit ? 'default' : '';
  if(ttFolder) drawTechTree(ttFolder);
  ttUpdateHint();
}

function ttStartDrag(ev, node){
  if(!ttEdit || !ttOrigin) return;
  ev.stopPropagation(); ev.preventDefault();
  const t = ((DATA && DATA.techs) || []).find(x=>x.id === node.dataset.id);
  if(!t) return;
  const m = /translate\\(([-\\d.]+),([-\\d.]+)\\)/.exec(node.getAttribute('transform')) || [0, 0, 0];
  ttDragNode = { node, t, ox: parseFloat(m[1]), oy: parseFloat(m[2]), sx: ev.clientX, sy: ev.clientY };
  window.addEventListener('mousemove', ttOnDrag);
  window.addEventListener('mouseup', ttEndDrag, { once: true });
}

function ttScale(){
  const svg = document.getElementById('techSvg');
  const r = svg.getBoundingClientRect();
  const vb = svg.viewBox && svg.viewBox.baseVal;
  const base = (vb && vb.width) ? (vb.width / r.width) : 1;
  return base / (ttView.k || 1);
}

function ttOnDrag(ev){
  if(!ttDragNode) return;
  const s = ttScale();
  const nx = ttDragNode.ox + (ev.clientX - ttDragNode.sx) * s;
  const ny = ttDragNode.oy + (ev.clientY - ttDragNode.sy) * s;
  ttDragNode.nx = nx; ttDragNode.ny = ny;
  ttDragNode.node.setAttribute('transform', 'translate(' + nx + ',' + ny + ')');
}

function ttEndDrag(){
  window.removeEventListener('mousemove', ttOnDrag);
  if(!ttDragNode) return;
  const d = ttDragNode; ttDragNode = null;
  if(d.nx == null) return;
  const fx = Math.round((d.nx - 120) / 300 + ttOrigin.minx);
  const fy = Math.round((d.ny - 70) / 110 + ttOrigin.miny);
  const snappedX = 120 + (fx - ttOrigin.minx) * 300;
  const snappedY = 70 + (fy - ttOrigin.miny) * 110;
  d.node.setAttribute('transform', 'translate(' + snappedX + ',' + snappedY + ')');
  d.t.fx = fx; d.t.fy = fy;
  ttDirty.set(d.t.id, { id: d.t.id, x: fx, y: fy, file: d.t.file, source: d.t.source });
  ttUpdateHint();
  status(d.t.id + '：x=' + fx + ' y=' + fy + '（未保存）');
}

async function ttSavePositions(){
  if(!ttDirty.size){ status('没有改过位置'); return; }
  const items = [...ttDirty.values()];
  let ok = 0, fail = [];
  for(const it of items){
    try{
      const r = await (await fetch('/api/tech_move', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({root: rootByName(it.source), rel: it.file, tid: it.id, x: it.x, y: it.y})})).json();
      if(r.ok) ok++; else fail.push(it.id + '：' + (r.msg || '失败'));
    }catch(e){ fail.push(it.id + '：' + e.message); }
  }
  ttDirty.clear();
  if(ok) await loadData();
  updateTechTreeShell();
  if(fail.length) status('保存 ' + ok + ' 个，失败 ' + fail.length + '：' + fail[0], true);
  else status('已保存 ' + ok + ' 个科技的位置（写回 folder.position）');
}

"""


def main():
    s = io.open(PY, encoding='utf-8').read()
    h = io.open(HTML, encoding='utf-8').read()
    if 'tech_move' in s and 'ttSavePositions' in h:
        print('已注入，跳过')
        return 0

    if 'def tech_move(' not in s:
        block = io.open(BLOCK, encoding='utf-8').read()
        anchor = "def state_detail(sid):"
        assert s.count(anchor) == 1
        s = s.replace(anchor, block + anchor, 1)

        old_post = '''        elif self.path == "/api/state_save":'''
        new_post = '''        elif self.path == "/api/tech_move":
            self._send(tech_move(body.get("root", ""), body.get("rel", ""),
                                 body.get("tid", ""), body.get("x", 0), body.get("y", 0)))
        elif self.path == "/api/state_save":'''
        assert s.count(old_post) == 1
        s = s.replace(old_post, new_post, 1)
        io.open(PY, 'w', encoding='utf-8', newline='').write(s)
        print('后端 tech_move 注入完成')

    if 'ttSavePositions' not in h:
        anchor_dom = '    <div id="techFolderTabs" class="tt-tabs"></div>'
        assert h.count(anchor_dom) == 1
        h = h.replace(anchor_dom, anchor_dom + "\n" + DOM, 1)

        anchor_js = "let ttView = {x:0, y:0, k:1}, ttFolder = '', ttDrag = null;"
        assert h.count(anchor_js) == 1
        h = h.replace(anchor_js, anchor_js + "\n\n" + JS, 1)

        # drawTechTree 里记录原点
        old_origin = """    list.forEach(t=>{
      const x = typeof t.fx === 'number' ? t.fx : 0;
      const y = typeof t.fy === 'number' ? t.fy : 0;
      pos[t.id] = {x: 120 + (x - minx) * 300, y: 70 + (y - miny) * 110, t};
      maxRow = Math.max(maxRow, y - miny);
    });"""
        new_origin = """    ttOrigin = {minx: minx, miny: miny};
    list.forEach(t=>{
      const x = typeof t.fx === 'number' ? t.fx : 0;
      const y = typeof t.fy === 'number' ? t.fy : 0;
      pos[t.id] = {x: 120 + (x - minx) * 300, y: 70 + (y - miny) * 110, t};
      maxRow = Math.max(maxRow, y - miny);
    });"""
        assert h.count(old_origin) == 1, 'drawTechTree 坐标段不符'
        h = h.replace(old_origin, new_origin, 1)

        old_else = """  } else {
    const byYear = {};"""
        new_else = """  } else {
    ttOrigin = null;
    const byYear = {};"""
        assert h.count(old_else) == 1
        h = h.replace(old_else, new_else, 1)

        # 节点加拖动
        old_click = """  view.querySelectorAll('.tt-node').forEach(n=>{
    n.addEventListener('click', e=>{"""
        new_click = """  view.querySelectorAll('.tt-node').forEach(n=>{
    n.addEventListener('mousedown', e=>ttStartDrag(e, n));
    n.addEventListener('click', e=>{"""
        assert h.count(old_click) == 1
        h = h.replace(old_click, new_click, 1)

        # 画完刷新提示
        old_tail = """  view.querySelectorAll('.tt-link').forEach(h=>{"""
        new_tail = """  ttUpdateHint();
  view.querySelectorAll('.tt-link').forEach(h=>{"""
        assert h.count(old_tail) == 1
        h = h.replace(old_tail, new_tail, 1)

        # 绑定按钮
        anchor_b = "document.getElementById('ttFit').onclick = fitTT;"
        bind = (anchor_b +
                "\ndocument.getElementById('ttEditToggle').onclick = ttToggleEdit;"
                "\ndocument.getElementById('ttSavePos').onclick = ttSavePositions;")
        assert h.count(anchor_b) == 1
        h = h.replace(anchor_b, bind, 1)

        io.open(HTML, 'w', encoding='utf-8', newline='').write(h)
        print('前端科技树位置编辑注入完成')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
