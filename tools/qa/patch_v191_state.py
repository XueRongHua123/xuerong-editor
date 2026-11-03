# -*- coding: utf-8 -*-
"""v1.9.1 细化时的州归属处理 + 前置警告。"""
import io
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'focus_editor.py')

BLOCK = '''def _refine_state_warnings(pid, prov2state):
    """细化前的风险提示：VP / 首都 / 州归属"""
    warn = []
    sid = prov2state.get(pid, 0)
    if not sid:
        warn.append("省 %d 不属于任何州，细化出来的新省也不会有归属" % pid)
        return warn, 0

    st = None
    for s in (STATES.values() if isinstance(STATES, dict) else []):
        try:
            if int(s.get("id") or 0) == int(sid):
                st = s
                break
        except Exception:
            continue
    if not st:
        return warn, sid

    provs = st.get("provinces") or []
    if len(provs) <= 1:
        warn.append("州 %d 只有这一个省，细化后新省需要单独建州或并入邻州" % sid)
    else:
        warn.append("新省会加入州 %d（共 %d 省）" % (sid, len(provs)))

    for vp in (st.get("victory_points") or []):
        try:
            if int(vp.get("province") or -1) == int(pid):
                warn.append("省 %d 有 %s 点胜利点，细化后图标会随质心移到原省残留块" % (
                    pid, vp.get("points")))
        except Exception:
            pass

    # 首都：只查已加载的国家，命中就提示
    try:
        for c in (COUNTRIES.values() if isinstance(COUNTRIES, dict) else []):
            if str(c.get("capital") or "") == str(pid):
                warn.append("省 %d 是 %s 的首都，细化后首都位置会落在原省残留块" % (
                    pid, c.get("tag") or c.get("name") or "某国"))
    except Exception:
        pass
    return warn, sid


def _refine_attach_to_state(root, sid, new_ids, pid):
    """把细化出来的新省加进原州（改 history/states/*.txt 的 provinces 列表）"""
    if not sid or not new_ids:
        return ""
    _r, rel, path = _state_file_for(sid)
    if not path:
        return ""
    try:
        text = _read_text(path)
        m = re.search(r'(?m)^[ \\t]*provinces\\s*=\\s*\\{', text)
        cur = []
        if m:
            b = text.find("{", m.end() - 1)
            e = brace_match(text, b)
            if e > b:
                cur = [int(x) for x in re.findall(r'\\d+', text[b + 1:e - 1])]
        if not cur:
            cur = [pid]
        merged = sorted(set(cur) | set(int(x) for x in new_ids))
        if merged == sorted(set(cur)):
            return ""
        body = _set_state_provinces(text, merged)
        snapshot(path)
        _write_bom_text(path, body, text.startswith("\\ufeff") or True)
        return rel
    except Exception as e:
        print("写州归属失败:", e)
        return ""


'''


def main():
    s = io.open(P, encoding='utf-8').read()
    if '_refine_state_warnings' in s:
        print('已注入，跳过')
        return 0

    anchor = 'def event_detail(eid, root=None):'
    assert s.count(anchor) == 1
    s = s.replace(anchor, BLOCK + anchor, 1)

    # 1) preview 返回 warnings
    old = '''    return {"ok": True, "pid": pid, "k": len(cnt), "total": len(res["px"]),
            "parts": parts, "msg": "切成 %d 块，面积 %s" % (
                len(cnt), sorted(cnt.values(), reverse=True))}'''
    new = '''    # 细化前把风险讲清楚：VP 会移动、首都会偏、新省要不要进州
    _p2s = {}
    for _s in (STATES.values() if isinstance(STATES, dict) else []):
        try:
            for _p in (_s.get("provinces") or []):
                _p2s[int(_p)] = int(_s.get("id") or 0)
        except Exception:
            pass
    _warn, _sid = _refine_state_warnings(pid, _p2s)
    return {"ok": True, "pid": pid, "k": len(cnt), "total": len(res["px"]),
            "state": _sid, "warnings": _warn,
            "parts": parts, "msg": "切成 %d 块，面积 %s" % (
                len(cnt), sorted(cnt.values(), reverse=True))}'''
    assert s.count(old) == 1, 'preview 返回不符'
    s = s.replace(old, new, 1)

    # 2) apply 后自动加进州
    old2 = '''    bmp_write_rect(bmp, bx, by, bw, bh, after)
    _REFINE_IDS_CACHE.pop("cur", None)

    return {"ok": True, "pid": pid, "new_ids": [assign[kk] for kk in keys[1:]],
            "parts": len(keys), "pixels": len(owner), "rect": [bx, by, bw, bh],
            "msg": "已切成 %d 块，新增省号 %s" % (len(keys), [assign[kk] for kk in keys[1:]])}'''
    new2 = '''    bmp_write_rect(bmp, bx, by, bw, bh, after)
    _REFINE_IDS_CACHE.pop("cur", None)

    # 新省必须进州，否则是孤儿地块（没有 owner / 建筑槽 / 人口）
    _new_ids = [assign[kk] for kk in keys[1:]]
    _p2s2 = {}
    for _s in (STATES.values() if isinstance(STATES, dict) else []):
        try:
            for _p in (_s.get("provinces") or []):
                _p2s2[int(_p)] = int(_s.get("id") or 0)
        except Exception:
            pass
    _sid2 = _p2s2.get(pid, 0)
    _state_rel = _refine_attach_to_state(root, _sid2, _new_ids, pid)
    reload_data()

    _m = "已切成 %d 块，新增省号 %s" % (len(keys), _new_ids)
    if _state_rel:
        _m += "；已加入州 %d（%s）" % (_sid2, _state_rel)
    elif _sid2:
        _m += "；加入州 %d 失败，需手动处理" % _sid2
    else:
        _m += "；原省无州归属，新省也未归属"
    return {"ok": True, "pid": pid, "new_ids": _new_ids, "state": _sid2,
            "stateFile": _state_rel,
            "parts": len(keys), "pixels": len(owner), "rect": [bx, by, bw, bh],
            "msg": _m}'''
    assert s.count(old2) == 1, 'apply 返回不符'
    s = s.replace(old2, new2, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(s)
    print('细化归属与警告已注入')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
