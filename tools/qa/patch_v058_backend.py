# -*- coding: utf-8 -*-
"""v0.58 补全历史编辑器：set_technology / oob / set_popularities。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor.py')
MARK = "# v0.58 历史编辑器补全"


def main():
    s = io.open(P, encoding='utf-8').read()
    if MARK in s:
        print('已注入，跳过')
        return 0

    # 1) 读取端：多给 oob / 科技 / 政党支持度
    old = '''        "focus_tree": ((COUNTRIES.get(tag) or {}).get("focus_trees") or [""])[0],
    }
    return {"ok": True, "exists": True, "writable": writable, "file": c.get("history_file", ""),'''
    new = '''        "focus_tree": ((COUNTRIES.get(tag) or {}).get("focus_trees") or [""])[0],
        "oob": top_val(r'(?m)^[ \\t]*oob\\s*=\\s*"([^"]+)"'),
        "techs": [k for k, v, hb in top_items(_hist_block_body(body, "set_technology")) if not hb],
        "popularities": _hist_popularities(body),
    }
    return {"ok": True, "exists": True, "writable": writable, "file": c.get("history_file", ""),'''
    assert s.count(old) == 1, '读取端锚点不符'
    s = s.replace(old, new, 1)

    # 2) 两个辅助函数
    anchor = "def _hist_party_of(text):"
    helpers = '''def _hist_block_body(text, key):
    """取顶层 key = { ... } 的块内文本，没有返回空串"""
    m = _hist_find_top(text, re.compile(r'(?m)^[ \\t]*%s\\s*=\\s*\\{' % re.escape(key)))
    if not m:
        return ""
    b = text.find('{', m.end() - 1)
    return text[b + 1:brace_match(text, b) - 1]


def _hist_popularities(text):
    out = {}
    for k, v, hb in top_items(_hist_block_body(text, "set_popularities")):
        if hb:
            continue
        try:
            out[k] = int(float(v.strip()))
        except Exception:
            pass
    return out


def _hist_party_of(text):'''
    assert s.count(anchor) == 1
    s = s.replace(anchor, helpers, 1)

    # 3) 写回端
    old2 = '''        if fields.get("focus_tree") is not None:
            text = _hist_put_block(text, "load_focus_tree", ["tree = " + tree] if tree else [])
            new["focus_tree"] = tree'''
    new2 = '''        if fields.get("focus_tree") is not None:
            text = _hist_put_block(text, "load_focus_tree", ["tree = " + tree] if tree else [])
            new["focus_tree"] = tree
        # v0.58 历史编辑器补全
        if fields.get("techs") is not None:
            techs = [x.strip() for x in fields.get("techs") or [] if x and x.strip()]
            text = _hist_put_block(text, "set_technology", ["%s = 1" % t for t in techs])
            new["techs"] = ",".join(techs)
        if fields.get("oob") is not None:
            oob = (fields.get("oob") or "").strip()
            if oob:
                text = _hist_set_scalar(text, "oob", '"%s"' % oob)
            new["oob"] = oob
        if fields.get("popularities") is not None:
            pops = {}
            for k, v in (fields.get("popularities") or {}).items():
                if k in PARTIES and str(v).strip():
                    try:
                        pops[k] = int(float(v))
                    except Exception:
                        pass
            if pops:
                text = _hist_put_block(text, "set_popularities",
                                       ["%s = %d" % (k, pops[k]) for k in PARTIES if k in pops])
                new["popularities"] = ",".join("%s=%d" % (k, pops[k]) for k in PARTIES if k in pops)'''
    assert s.count(old2) == 1, '写回端锚点不符'
    s = s.replace(old2, new2, 1)

    # 4) 旧值也读一读，供 diff 用
    old3 = '''            "focus_tree": (c.get("focus_trees") or [""])[0],
        }'''
    new3 = '''            "focus_tree": (c.get("focus_trees") or [""])[0],
            "techs": ",".join(c.get("techs", [])),
            "oob": c.get("oob", ""),
            "popularities": ",".join("%s=%d" % (k, v) for k, v in
                                     sorted(_hist_popularities(before).items())),
        }'''
    assert s.count(old3) == 1
    s = s.replace(old3, new3, 1)

    # 5) diff 标签
    old4 = '''        shown = {"capital": "首都", "ruling_party": "执政党", "political_power": "政治点",
                 "stability": "稳定度修正", "war_support": "战争支持修正", "ideas": "开局精神", "focus_tree": "国策树"}'''
    new4 = '''        shown = {"capital": "首都", "ruling_party": "执政党", "political_power": "政治点",
                 "stability": "稳定度修正", "war_support": "战争支持修正", "ideas": "开局精神",
                 "focus_tree": "国策树", "techs": "开局科技", "oob": "部队编成 oob",
                 "popularities": "政党支持度"}'''
    assert s.count(old4) == 1
    s = s.replace(old4, new4, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(s)
    print('v0.58 后端注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
