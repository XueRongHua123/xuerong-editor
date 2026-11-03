# -*- coding: utf-8 -*-
"""v0.59：历史编辑器加初始外交（add_opinion）。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, '..', 'focus_editor.py')
HTML = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "# v0.59 初始外交"

HELPERS = '''# v0.59 初始外交
def _hist_opinions(text):
    """读取 add_opinion 块，返回 [[tag, value], ...]"""
    out = []
    for m in re.finditer(r'(?m)^[ \\t]*add_opinion\\s*=\\s*\\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        t = _first(body, r'(?m)^[ \\t]*target\\s*=\\s*([A-Z0-9]{2,4})')
        v = _first(body, r'(?m)^[ \\t]*(?:value|opinion)\\s*=\\s*(-?\\d+)')
        if t:
            out.append([t, int(v or 0)])
    return out


def _hist_set_opinions(text, pairs):
    """删掉所有 add_opinion 块再按 pairs 重建（顶层）"""
    for _ in range(40):
        m = _hist_find_top(text, re.compile(r'(?m)^[ \\t]*add_opinion\\s*=\\s*\\{'))
        if not m:
            break
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        line_start = text.rfind("\\n", 0, m.start()) + 1
        text = text[:line_start] + text[e:]
    for tag, val in pairs:
        text = text.rstrip() + "\\nadd_opinion = {\\n\\ttarget = %s\\n\\tvalue = %d\\n}\\n" % (tag, val)
    return text


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

    old = '''        "popularities": _hist_popularities(body),
    }'''
    new = '''        "popularities": _hist_popularities(body),
        "opinions": _hist_opinions(body),
    }'''
    assert s.count(old) == 1
    s = s.replace(old, new, 1)

    old2 = '''        if fields.get("popularities") is not None:'''
    new2 = '''        if fields.get("opinions") is not None:
            pairs = []
            for p in fields.get("opinions") or []:
                try:
                    tag2, val2 = p[0], int(p[1])
                except Exception:
                    continue
                if tag2 in COUNTRIES:
                    pairs.append((tag2, val2))
            old_pairs = _hist_opinions(before)
            if pairs != old_pairs:
                text = _hist_set_opinions(text, pairs)
                new["opinions"] = ",".join("%s:%d" % (t3, v3) for t3, v3 in pairs)
        if fields.get("popularities") is not None:'''
    assert s.count(old2) == 1
    s = s.replace(old2, new2, 1)

    old3 = '''            "popularities": ",".join("%s=%d" % (k, v) for k, v in
                                     sorted(_hist_popularities(before).items())),'''
    new3 = old3 + '''
            "opinions": ",".join("%s:%d" % (t4, v4) for t4, v4 in _hist_opinions(before)),'''
    assert s.count(old3) == 1
    s = s.replace(old3, new3, 1)

    old4 = '''                 "popularities": "政党支持度"}'''
    new4 = '''                 "popularities": "政党支持度", "opinions": "初始外交"}'''
    assert s.count(old4) == 1
    s = s.replace(old4, new4, 1)
    io.open(PY, 'w', encoding='utf-8', newline='').write(s)
    print('后端 add_opinion 注入完成')

    # 前端：文本域 + 读取/保存
    if 'histOpinions' not in h:
        old_dom = '''          <div class="k">开局精神（每行一个 idea id；清空 = 不写这一项）</div>'''
        new_dom = '''          <div class="k">初始外交 add_opinion（每行「TAG 数值」，如 <code>EUR 50</code>；清空 = 不写）</div>
          <textarea id="histOpinions" style="height:64px" placeholder="EUR 50"></textarea>
''' + old_dom
        assert h.count(old_dom) == 1
        h = h.replace(old_dom, new_dom, 1)

        old_read = """  document.getElementById('histTechs').value = (f.techs || []).join('\\n');"""
        new_read = old_read + """
  document.getElementById('histOpinions').value =
    (f.opinions || []).map(p=>p[0] + ' ' + p[1]).join('\\n');"""
        assert h.count(old_read) == 1
        h = h.replace(old_read, new_read, 1)

        old_save = """    techs: document.getElementById('histTechs').value.split(/\\r?\\n/).map(s=>s.trim()).filter(Boolean),"""
        new_save = old_save + """
    opinions: document.getElementById('histOpinions').value.split(/\\r?\\n/)
      .map(s=>s.trim()).filter(Boolean)
      .map(s=>{ const p = s.split(/[,，\\s]+/); return [p[0], Number(p[1] || 0)]; }),"""
        assert h.count(old_save) == 1
        h = h.replace(old_save, new_save, 1)

        io.open(HTML, 'w', encoding='utf-8', newline='').write(h)
        print('前端 add_opinion 注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
