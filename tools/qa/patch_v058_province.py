# -*- coding: utf-8 -*-
"""v0.58 省份编辑：省建筑 + 胜利点写回。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor.py')
MARK = "# v0.58 省份编辑"

HELPERS = '''def _set_prov_building(body, pid, values):
    """省份建筑：values 为 {key: int}，全 0 表示删掉这个省块"""
    positive = {k: v for k, v in values.items() if v and int(v) > 0}
    m = re.search(r'(?m)^[ \\t]*buildings\\s*=\\s*\\{', body)
    if not m:
        if not positive:
            return body
        block = "buildings = {\\n\\t\\t%s = {\\n" % pid
        block += "".join("\\t\\t\\t%s = %d\\n" % (k, v) for k, v in sorted(positive.items()))
        block += "\\t\\t}\\n\\t}"
        hist = _state_history_range(body)
        if hist:
            pos = _insert_pos(body, hist[0], hist[1])
            return body[:pos] + "\\n" + block + body[pos:]
        return body.rstrip() + "\\n" + block + "\\n"
    b = body.find('{', m.end() - 1)
    e = brace_match(body, b)
    inner = body[b + 1:e - 1]
    pm = re.search(r'(?m)^[ \\t]*%s\\s*=\\s*\\{' % re.escape(str(pid)), inner)
    if pm:
        pb = inner.find('{', pm.end() - 1)
        pe = brace_match(inner, pb)
        line_start = inner.rfind("\\n", 0, pm.start()) + 1
        if positive:
            blk = "%s = {\\n" % pid
            blk += "".join("\\t\\t\\t\\t%s = %d\\n" % (k, v) for k, v in sorted(positive.items()))
            blk += "\\t\\t\\t}"
            inner = inner[:line_start] + "\\t\\t\\t" + blk + inner[pe:]
        else:
            inner = inner[:line_start] + inner[pe:]
    elif positive:
        blk = "\\t\\t\\t%s = {\\n" % pid
        blk += "".join("\\t\\t\\t\\t%s = %d\\n" % (k, v) for k, v in sorted(positive.items()))
        blk += "\\t\\t\\t}\\n"
        inner = blk + inner.lstrip("\\r\\n")
    return body[:b + 1] + inner + body[e - 1:]


def _set_victory_points(body, vps):
    """胜利点：vps 为 [[prov, value], ...]，空列表表示删除整块"""
    pairs = [(int(p), int(v)) for p, v in vps if str(p).strip() and str(v).strip()]
    m = re.search(r'(?m)^[ \\t]*victory_points\\s*=\\s*\\{', body)
    if m:
        b = body.find('{', m.end() - 1)
        e = brace_match(body, b)
        line_start = body.rfind("\\n", 0, m.start()) + 1
        if not pairs:
            return body[:line_start] + body[e:]
        inner = "".join("\\n\\t\\t\\t\\t%d %d" % (p, v) for p, v in pairs)
        return body[:b + 1] + inner + "\\n\\t\\t\\t" + body[e - 1:]
    if not pairs:
        return body
    block = "victory_points = {\\n"
    block += "".join("\\t\\t\\t\\t%d %d\\n" % (p, v) for p, v in pairs)
    block += "\\t\\t\\t}"
    hist = _state_history_range(body)
    if hist:
        pos = _insert_pos(body, hist[0], hist[1])
        return body[:pos] + "\\n" + block + body[pos:]
    return body.rstrip() + "\\n" + block + "\\n"


def state_detail(sid):'''


def main():
    s = io.open(P, encoding='utf-8').read()
    if MARK in s:
        print('已注入，跳过')
        return 0

    anchor = "def state_detail(sid):"
    assert s.count(anchor) == 1
    s = s.replace(anchor, HELPERS, 1)

    old = '''    for k in sorted(blds):
        v = blds[k]
        if old_blds.get(k, None) == v:
            continue
        body = _set_building(body, k, v)
        diff.append({"key": "b_" + k, "label": "建筑 " + k,
                     "old": str(old_blds.get(k, "")), "new": str(v)})
'''
    new = old + '''
    # v0.58 省份编辑
    pb = fields.get("province_buildings")
    if pb:
        old_pb = s.get("province_buildings", {}) or {}
        for pid, vals in pb.items():
            vals = vals or {}
            want = {}
            for k, v in vals.items():
                try:
                    iv = int(v)
                except Exception:
                    continue
                if iv >= 0:
                    want[k] = iv
            before = old_pb.get(str(pid), {}) or {}
            if want == before:
                continue
            body = _set_prov_building(body, str(pid), want)
            diff.append({"key": "pb_" + str(pid), "label": "省份 %s 建筑" % pid,
                         "old": ", ".join("%s=%d" % (k, v) for k, v in sorted(before.items())) or "无",
                         "new": ", ".join("%s=%d" % (k, v) for k, v in sorted(want.items())) or "无"})

    if fields.get("victory_points") is not None:
        want_vp = [[int(p), int(v)] for p, v in (fields.get("victory_points") or [])
                   if str(p).strip() and str(v).strip()]
        old_vp = [[int(p), int(v)] for p, v in s.get("victory_points", [])]
        if sorted(want_vp) != sorted(old_vp):
            body = _set_victory_points(body, want_vp)
            diff.append({"key": "vp", "label": "胜利点",
                         "old": ", ".join("%d:%d" % (p, v) for p, v in old_vp) or "无",
                         "new": ", ".join("%d:%d" % (p, v) for p, v in want_vp) or "无"})
'''
    assert s.count(old) == 1, '州保存锚点不符'
    s = s.replace(old, new, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(s)
    print('v0.58 省份编辑后端注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
