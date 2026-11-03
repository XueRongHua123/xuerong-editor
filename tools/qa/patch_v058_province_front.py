# -*- coding: utf-8 -*-
"""v0.58 前端：州面板里的省份建筑与胜利点可编辑。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "v0.58 省份编辑"

CSS = """  /* v0.58 省份编辑 */
  .st-tablewrap{max-height:230px;overflow:auto;border:1px solid var(--line);border-radius:8px;margin:4px 0 8px}
  .st-table{width:100%;border-collapse:collapse;font-size:11.5px}
  .st-table th{position:sticky;top:0;background:var(--panel2);color:var(--muted);font-weight:500;
    text-align:left;padding:5px 8px;border-bottom:1px solid var(--line)}
  .st-table td{padding:3px 8px;border-bottom:1px solid var(--line);color:var(--text)}
  .st-table input{width:74px;height:26px!important}
"""

TABLE_JS = """  const vpMap = {};
  (d.victory_points || []).forEach(v=>{ vpMap[v[0]] = v[1]; });
  const pbMap = d.province_buildings || {};
  if(d.provinces.length){
    html += '<div class="cm-sec">省份 · 建筑 · 胜利点<span>建筑留空=不改，0=删掉；胜利点留空=不写</span></div>' +
      '<div class="st-tablewrap"><table class="st-table"><thead><tr>' +
      '<th>省</th><th>naval_base</th><th>coastal_bunker</th><th>胜利点</th></tr></thead><tbody>' +
      d.provinces.map(p=>{
        const b = pbMap[p] || pbMap[String(p)] || {};
        const vv = vpMap[p] != null ? vpMap[p] : '';
        return '<tr><td>' + p + '</td>' +
          '<td><input type="number" min="0" data-pb="' + p + '" data-k="naval_base" value="' +
            (b.naval_base != null ? b.naval_base : '') + '"></td>' +
          '<td><input type="number" min="0" data-pb="' + p + '" data-k="coastal_bunker" value="' +
            (b.coastal_bunker != null ? b.coastal_bunker : '') + '"></td>' +
          '<td><input type="number" min="0" data-vp="' + p + '" value="' + vv + '"></td></tr>';
      }).join('') +
      '</tbody></table></div>' +
      (d.province_count > d.provinces.length ?
        '<div class="k">只列出前 ' + d.provinces.length + ' 个省，其余未显示</div>' : '');
  }
"""

SAVE_JS = """    province_buildings: (function(){
      const pb = {};
      document.querySelectorAll('#stateBody [data-pb]').forEach(inp=>{
        const v = inp.value.trim();
        if(v === '') return;
        (pb[inp.dataset.pb] = pb[inp.dataset.pb] || {})[inp.dataset.k] = Number(v);
      });
      return pb;
    })(),
    victory_points: [...document.querySelectorAll('#stateBody [data-vp]')]
      .filter(inp=>inp.value.trim() !== '')
      .map(inp=>[Number(inp.dataset.vp), Number(inp.value)])
  };"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    # CSS
    anchor_css = "  .st-vp{font-size:11.5px;color:var(--text);margin:2px 0}"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, anchor_css + "\n" + CSS, 1)

    # 省份/胜利点区块 → 可编辑表格
    old_block = """  if(d.provinces.length){
    html += '<div class="cm-sec">省份<span>' + d.province_count + ' 个</span></div>' +
      '<div class="st-prov">' + d.provinces.map(p=>'<span>' + p + '</span>').join('') +
      (d.province_count > d.provinces.length ? '<span>…</span>' : '') + '</div>';
  }
  if(d.victory_points.length){
    html += '<div class="cm-sec">胜利点<span>' + d.victory_points.length + ' 处</span></div>' +
      d.victory_points.map(vp=>'<div class="st-vp">省份 ' + vp[0] + ' → ' + vp[1] + ' 点</div>').join('');
  }
  const pbs = Object.entries(d.province_buildings || {});
  if(pbs.length){
    html += '<div class="cm-sec">省份建筑<span>只读</span></div>' +
      pbs.map(([pid, b])=>'<div class="st-vp">省 ' + escapeHtml(pid) + '：' +
        Object.entries(b).map(([k, v])=>k + ' ' + v).join('，') + '</div>').join('');
  }
"""
    assert h.count(old_block) == 1, '省份区块结构不符'
    h = h.replace(old_block, TABLE_JS, 1)

    # 保存时组装
    old_save = """    category: document.getElementById('stCategory').value,
    buildings: buildings
  };"""
    new_save = """    category: document.getElementById('stCategory').value,
    buildings: buildings,
""" + SAVE_JS
    assert h.count(old_save) == 1, '保存结构不符'
    h = h.replace(old_save, new_save, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.58 省份编辑前端注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
