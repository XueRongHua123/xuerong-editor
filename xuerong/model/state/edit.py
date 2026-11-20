# -*- coding: utf-8 -*-
"""写侧改属性：owner / 建筑 / 资源 / 胜利点 / scope 的文本层改写。

只操作已读进内存的文本与历史块，不碰磁盘。
"""
import re

from xuerong import state
from xuerong.core.text import brace_match
from xuerong.model.state._inj import _hist_depths


def _state_owner_effective(body, hb, he, dep, start=None):
    """按游戏语义取生效的 owner：日期块（<= 开局，最晚者）优先，否则 history 里的直接子级"""
    owner = ""
    if hb > 0:
        dated = []
        for m in re.finditer(r'(?m)^[ \t]*(\d{4})\.(\d{1,2})\.(\d{1,2})\s*=\s*\{', body[hb:he]):
            bpos = body.find('{', hb + m.end() - 1)
            epos = brace_match(body, bpos)
            if epos <= bpos:
                continue
            dm = re.search(r'(?m)^[ \t]*owner\s*=\s*([A-Z0-9_]{2,8})', body[bpos + 1:epos - 1])
            if dm:
                dated.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), dm.group(1).strip()))
        dated.sort()
        _sd = start or state.start_date()
        eff = [d for d in dated if (d[0], d[1], d[2]) <= _sd]
        if eff:
            owner = eff[-1][3]
        if not owner:
            for m in re.finditer(r'(?m)^[ \t]*owner\s*=\s*([A-Z0-9_]{2,8})', body[hb:he]):
                pos = hb + m.start()
                if pos < len(dep) and dep[pos] == 1:
                    owner = m.group(1).strip()
                    break
    if not owner:
        for m in re.finditer(r'(?m)^[ \t]*owner\s*=\s*([A-Z0-9_]{2,8})', body):
            pos = m.start()
            if pos < len(dep) and dep[pos] == 0:
                owner = m.group(1).strip()
                break
    return owner

def _state_history_range(body):
    m = re.search(r'(?m)^[ \t]*history\s*=\s*\{', body)
    if not m:
        return None
    b = body.find('{', m.end() - 1)
    return b, brace_match(body, b)

def _insert_pos(body, lo, hi):
    """在块内末尾插入：跳过 `}` 本身与尾部空白"""
    pos = hi - 1 if hi - 1 > lo and body[hi - 1] == '}' else hi
    while pos > lo and body[pos - 1] in " \t\r\n":
        pos -= 1
    return pos

def _set_owner_all(body, owner, hb, he):
    """改所有 owner：history 直接子级 + 所有日期块内的。

    HOI4 的语义是「日期块覆盖直接子级」：state 里写
        history = { 1999.1.1 = { owner = EUR }  owner = SOV }
    开局若在 1999 之后，生效的是 EUR 而不是 SOV。
    只改直接子级的话，游戏里看到的还是日期块里的旧值。
    """
    # 先改所有日期块内的（depth == 2）
    dep = _hist_depths(body)
    pat = re.compile(r'(?m)^([ \t]*)owner\s*=\s*[^\s#\r\n]+')
    out, last, hit = [], 0, False
    for m in pat.finditer(body, hb if hb > 0 else 0, he if hb > 0 else len(body)):
        if m.start() < len(dep) and dep[m.start()] == 2:
            out.append(body[last:m.start()])
            out.append((m.group(1) or "") + "owner = " + owner)
            last = m.end()
            hit = True
    if hit:
        out.append(body[last:])
        body = "".join(out)
    # 再改直接子级（没有就插入）
    if hb > 0:
        before = body
        body = _set_in_scope(body, "owner", owner, 1, hb, he)
        if body == before:
            body = _set_in_scope(body, "owner", owner, 1, hb, he, insert=True)
    else:
        body = _set_in_scope(body, "owner", owner, 0, 0, len(body), insert=True)
    return body

def _set_in_scope(body, key, value, want_depth, lo, hi, insert=False):
    pat = re.compile(r'(?m)^([ \t]*)%s\s*=\s*[^\s#\r\n]+' % re.escape(key))
    dep = _hist_depths(body)
    for m in pat.finditer(body, lo, hi):
        if m.start() < len(dep) and dep[m.start()] == want_depth:
            return body[:m.start()] + (m.group(1) or "") + "%s = %s" % (key, value) + body[m.end():]
    if not insert:
        return body
    indent = "\t" * want_depth
    pos = _insert_pos(body, lo, hi)
    return body[:pos] + "\n" + indent + "%s = %s" % (key, value) + "\n" + body[pos:]

def _drop_in_scope(body, key, depths, lo, hi):
    pat = re.compile(r'(?m)^[ \t]*%s\s*=\s*[^\s#\r\n]*[ \t]*\r?\n?' % re.escape(key))
    dep = _hist_depths(body)
    out, last = [], 0
    hit = False
    for m in pat.finditer(body, lo, hi):
        if m.start() < len(dep) and dep[m.start()] in depths:
            out.append(body[last:m.start()])
            last = m.end()
            hit = True
    if not hit:
        return body
    out.append(body[last:])
    return "".join(out)

def _set_resource(body, key, value):
    """改/建 state 顶层的 resources = { key = value }。"""
    if value <= 0:
        # 归零就删掉这一行
        m = re.search(r'(?m)^[ \t]*resources\s*=\s*\{', body)
        if not m:
            return body
        b = body.find("{", m.end() - 1)
        e = brace_match(body, b)
        if e <= b:
            return body
        inner = body[b + 1:e - 1]
        pat = re.compile(r'(?m)^[ \t]*' + re.escape(key) + r'[ \t]*=[ \t]*\d+[ \t]*\r?\n?')
        inner2 = pat.sub('', inner)
        if inner2 == inner:
            return body
        # 块空了就整段删
        if not inner2.strip():
            st = m.start()
            while st > 0 and body[st - 1] in " \t":
                st -= 1
            if st > 0 and body[st - 1] == "\n":
                st -= 1
            en = e
            while en < len(body) and body[en] in "\r\n":
                en += 1
            return body[:st] + "\n" + body[en:]
        return body[:b + 1] + inner2 + body[e - 1:]

    m = re.search(r'(?m)^[ \t]*resources\s*=\s*\{', body)
    if not m:
        return body.rstrip() + "\n\tresources = {\n\t\t%s = %d\n\t}\n" % (key, value)
    b = body.find("{", m.end() - 1)
    e = brace_match(body, b)
    if e <= b:
        return body
    inner = body[b + 1:e - 1]
    pat = re.compile(r'(?m)^([ \t]*)' + re.escape(key) + r'\s*=\s*\d+')
    if pat.search(inner):
        inner2 = pat.sub(lambda mm: (mm.group(1) or "\t\t") + "%s = %d" % (key, value), inner, count=1)
    else:
        # 追加到已有内容后面（顺序跟原版一致：先写先出）
        inner2 = inner.rstrip() + "\n\t\t%s = %d\n\t" % (key, value)
    return body[:b + 1] + inner2 + body[e - 1:]

def _set_building(body, key, value):
    m = re.search(r'(?m)^[ \t]*buildings\s*=\s*\{', body)
    if not m:
        if value <= 0:
            return body
        # 没有 buildings 块时必须建在 history 里面。
        # 原版 100% 都是 history={ ... buildings={...} ... }；写在 state 顶层
        # 游戏读不到（不报错，就是当没有），表现为「保存成功但进游戏没建筑」。
        block = "buildings = {\n\t\t\t%s = %d\n\t\t}" % (key, value)
        hist = _state_history_range(body)
        if hist:
            pos = _insert_pos(body, hist[0], hist[1])
            return body[:pos] + "\n\t\t" + block + body[pos:]
        return body.rstrip() + "\n\thistory = {\n\t\t" + block + "\n\t}\n"
    b = body.find('{', m.end() - 1)
    e = brace_match(body, b)
    inner = body[b + 1:e - 1]
    pat = re.compile(r'(?m)^[ \t]*%s\s*=\s*\d+[ \t]*\r?\n?' % re.escape(key))
    if value <= 0:
        # 0 = 删掉这一行（原版不写 0；留着 0 只会把文件越改越脏）
        inner2 = pat.sub("", inner)
        if inner2 == inner:
            return body
        if not inner2.strip():
            st = m.start()
            while st > 0 and body[st - 1] in " \t":
                st -= 1
            if st > 0 and body[st - 1] == "\n":
                st -= 1
            en = e
            while en < len(body) and body[en] in "\r\n":
                en += 1
            return body[:st] + "\n" + body[en:]
        return body[:b + 1] + inner2 + body[e - 1:]
    pat2 = re.compile(r'(?m)^([ \t]*)%s\s*=\s*\d+' % re.escape(key))
    if pat2.search(inner):
        inner2 = pat2.sub(lambda mm: (mm.group(1) or "\t") + "%s = %d" % (key, value), inner, count=1)
    else:
        inner2 = "\n\t\t\t%s = %d\n" % (key, value) + inner.lstrip("\r\n")
    return body[:b + 1] + inner2 + body[e - 1:]

def _set_prov_building(body, pid, values):
    """省份建筑：values 为 {key: int}，全 0 表示删掉这个省块"""
    positive = {k: v for k, v in values.items() if v and int(v) > 0}
    m = re.search(r'(?m)^[ \t]*buildings\s*=\s*\{', body)
    if not m:
        if not positive:
            return body
        block = "buildings = {\n\t\t%s = {\n" % pid
        block += "".join("\t\t\t%s = %d\n" % (k, v) for k, v in sorted(positive.items()))
        block += "\t\t}\n\t}"
        hist = _state_history_range(body)
        if hist:
            pos = _insert_pos(body, hist[0], hist[1])
            return body[:pos] + "\n" + block + body[pos:]
        return body.rstrip() + "\n" + block + "\n"
    b = body.find('{', m.end() - 1)
    e = brace_match(body, b)
    inner = body[b + 1:e - 1]
    pm = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(str(pid)), inner)
    if pm:
        pb = inner.find('{', pm.end() - 1)
        pe = brace_match(inner, pb)
        line_start = inner.rfind("\n", 0, pm.start()) + 1
        if positive:
            blk = "%s = {\n" % pid
            blk += "".join("\t\t\t\t%s = %d\n" % (k, v) for k, v in sorted(positive.items()))
            blk += "\t\t\t}"
            inner = inner[:line_start] + "\t\t\t" + blk + inner[pe:]
        else:
            inner = inner[:line_start] + inner[pe:]
    elif positive:
        blk = "\t\t\t%s = {\n" % pid
        blk += "".join("\t\t\t\t%s = %d\n" % (k, v) for k, v in sorted(positive.items()))
        blk += "\t\t\t}\n"
        inner = blk + inner.lstrip("\r\n")
    return body[:b + 1] + inner + body[e - 1:]

def _set_victory_points(body, vps):
    """胜利点：vps 为 [[prov, value], ...]，空列表表示删除整块"""
    pairs = [(int(p), int(v)) for p, v in vps if str(p).strip() and str(v).strip()]
    m = re.search(r'(?m)^[ \t]*victory_points\s*=\s*\{', body)
    if m:
        b = body.find('{', m.end() - 1)
        e = brace_match(body, b)
        line_start = body.rfind("\n", 0, m.start()) + 1
        if not pairs:
            return body[:line_start] + body[e:]
        inner = "".join("\n\t\t\t\t%d %d" % (p, v) for p, v in pairs)
        return body[:b + 1] + inner + "\n\t\t\t" + body[e - 1:]
    if not pairs:
        return body
    block = "victory_points = {\n"
    block += "".join("\t\t\t\t%d %d\n" % (p, v) for p, v in pairs)
    block += "\t\t\t}"
    hist = _state_history_range(body)
    if hist:
        pos = _insert_pos(body, hist[0], hist[1])
        return body[:pos] + "\n" + block + body[pos:]
    return body.rstrip() + "\n" + block + "\n"
