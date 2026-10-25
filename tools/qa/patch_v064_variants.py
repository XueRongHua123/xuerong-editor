# -*- coding: utf-8 -*-
"""v0.64：历史编辑器展示开局装备变体（create_equipment_variant，只读）。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, '..', 'focus_editor.py')
HTML = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "# v0.64 开局装备变体"

HELPERS = '''# v0.64 开局装备变体
def _hist_variants(text):
    """读取 create_equipment_variant 块（只读展示用）"""
    out = []
    for m in re.finditer(r'(?m)^[ \\t]*create_equipment_variant\\s*=\\s*\\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        nm = _first(body, r'(?m)^[ \\t]*name\\s*=\\s*"?([^"\\r\\n]+)"?')
        ty = _first(body, r'(?m)^[ \\t]*type\\s*=\\s*"?([^\\s"\\r\\n]+)"?')
        ic = _first(body, r'(?m)^[ \\t]*icon\\s*=\\s*"?([^\\s"\\r\\n]+)"?')
        mods = 0
        mm = re.search(r'(?m)^[ \\t]*modules\\s*=\\s*\\{', body)
        if mm:
            mb = body.find('{', mm.end() - 1)
            me = brace_match(body, mb)
            if me > mb:
                mods = len([1 for k, v, hb in top_items(body[mb + 1:me - 1]) if not hb])
        out.append({"name": nm or "(未命名)", "type": ty, "icon": ic, "modules": mods})
    return out


def country_history_raw(tag):'''


def main():
    s = io.open(PY, encoding='utf-8').read()
    h = io.open(HTML, encoding='utf-8').read()
    if MARK in s:
        print('已注入，跳过')
        return 0

    anchor = "def country_history_raw(tag):"
    assert s.count(anchor) == 1
    s = s.replace(anchor, HELPERS, 1)

    old = '''        "opinions": _hist_opinions(body),
    }'''
    new = '''        "opinions": _hist_opinions(body),
        "variants": _hist_variants(body),
    }'''
    assert s.count(old) == 1
    s = s.replace(old, new, 1)
    io.open(PY, 'w', encoding='utf-8', newline='').write(s)
    print('后端注入完成')

    # 前端：只读区块
    old_dom = '''          <div class="k">初始外交 add_opinion（每行「TAG 数值」，如 <code>EUR 50</code>；清空 = 不写）</div>'''
    new_dom = '''          <div class="k">开局装备变体 create_equipment_variant（只读；要改请用装备设计器的「插入」或直接编辑文件）</div>
          <div id="histVariants"></div>
''' + old_dom
    assert h.count(old_dom) == 1
    h = h.replace(old_dom, new_dom, 1)

    old_read = """  document.getElementById('histOpinions').value ="""
    new_read = """  renderHistVariants(f.variants || []);
  document.getElementById('histOpinions').value ="""
    assert h.count(old_read) == 1
    h = h.replace(old_read, new_read, 1)

    anchor_js = "async function loadHistoryIntoForm(){"
    fn = """function renderHistVariants(list){
  const box = document.getElementById('histVariants');
  if(!box) return;
  if(!list.length){ box.innerHTML = '<div class="k" style="margin:2px 0 6px">这个国家没有开局变体</div>'; return; }
  box.innerHTML = '<div class="hist-diff" style="margin:2px 0 8px">' + list.map(v=>
    '<div class="row"><i>' + escapeHtml(v.name) + '</i><span>' + escapeHtml(v.type || '?') +
    '</span><span class="new">' + (v.modules || 0) + ' 个模块</span></div>').join('') + '</div>';
}

"""
    assert h.count(anchor_js) == 1
    h = h.replace(anchor_js, fn + anchor_js, 1)

    io.open(HTML, 'w', encoding='utf-8', newline='').write(h)
    print('前端注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
