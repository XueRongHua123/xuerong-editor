# -*- coding: utf-8 -*-
"""州 / 省份域：列表、详情、保存、新建、拆分、建筑与资源（P2-state 从 focus_editor.py 迁入）。

27 个函数：任务书列的 23 个 + 反向闭包吸收的 4 个
（_coastal_provinces / _free_state_id / _insert_pos / _set_resource）。

依赖边界：
  · 五个全局容器走 xuerong.state 的访问器（states/roots/loc/changed/countries）
  · 开局日期与写盘提示也走访问器（refresh_start_date 会改 START_DATE）
  · 六个州常量从 xuerong.state import（一处定义）
  · BMP 三个助手 / _map_pick / _ensure_prov_rgb / _refine_load_ids 来自 xuerong.model.map
  · 其余横切动作用 bind() 回注（见 _INJ）
"""
import io
import os
import re

from xuerong import state
from xuerong.core.paths import (_layers_find, _read_bom_text, _write_bom_text,
                                is_under_game, mod_layers, write_base)
from xuerong.core.text import _read_text, brace_match
from xuerong.model.history import snapshot
from xuerong.model.map import (_ensure_prov_rgb, _map_pick, _refine_load_ids,
                               bmp_read_rect, bmp_write_rect)
from xuerong.state import (PROV_BUILDING_META, RESOURCE_META, STATE_BUILDINGS,
                           STATE_BUILDING_META, STATE_CATEGORIES, STATE_RESOURCES)

# _coastal_provinces 的缓存：只在这里用，不跨模块
_COASTAL_CACHE = {"key": None, "set": set()}

# ---------------------------------------------------------------- 门面回注
_INJ = {}


def bind(**kw):
    _INJ.update(kw)


def _all_prov_neighbors(*a, **k):
    return _INJ["_all_prov_neighbors"](*a, **k)


def _hist_depths(*a, **k):
    return _INJ["_hist_depths"](*a, **k)


def _hist_find_top(*a, **k):
    return _INJ["_hist_find_top"](*a, **k)


def _refine_grow_units(*a, **k):
    return _INJ["_refine_grow_units"](*a, **k)


def _parse_state_provinces(*a, **k):
    return _INJ["_parse_state_provinces"](*a, **k)


def _set_state_provinces(*a, **k):
    return _INJ["_set_state_provinces"](*a, **k)


def ensure_file_writable(*a, **k):
    return _INJ["ensure_file_writable"](*a, **k)


def link_countries(*a, **k):
    return _INJ["link_countries"](*a, **k)


def refresh_start_date(*a, **k):
    return _INJ["refresh_start_date"](*a, **k)


def reload_data(*a, **k):
    return _INJ["reload_data"](*a, **k)


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

def _coastal_provinces():
    """definition.csv 第 6 列 = coastal（true/false）。按 mtime 缓存。

    注意要走 `_layers_find` 拿源文件；`_map_dir` 给的是缓存目录，里面只有 png。
    """
    root = _map_pick(None)
    layers = mod_layers(root) if root else []
    p, _base = (_layers_find("map/definition.csv", layers) if layers else (None, None))
    if not p and state.game():
        p = os.path.join(state.game(), "map", "definition.csv")
    if not p or not os.path.exists(p):
        return set()
    try:
        stamp = (p, int(os.path.getmtime(p)), os.path.getsize(p))
    except Exception:
        stamp = (p, 0, 0)
    if _COASTAL_CACHE.get("key") == stamp:
        return _COASTAL_CACHE["set"]
    out = set()
    try:
        for ln in io.open(p, encoding="utf-8", errors="replace"):
            f = ln.strip().split(";")
            if len(f) >= 6 and f[5].strip().lower() == "true":
                try:
                    out.add(int(f[0]))
                except Exception:
                    pass
    except Exception:
        pass
    _COASTAL_CACHE["key"] = stamp
    _COASTAL_CACHE["set"] = out
    return out

def state_is_coastal(s):
    """州里只要有一个沿海省，就能造海军基地/船坞。"""
    coastal = _coastal_provinces()
    if not coastal:
        return None                      # 拿不到定义，不做限制
    return any(int(p) in coastal for p in (s.get("provinces") or []))

def states_payload():
    items = []
    for sid in sorted(state.states()):
        s = state.states()[sid]
        ow = s.get("owner", "") or ""
        items.append({
            "id": sid,
            "name": state.loc().get(s.get("name", ""), s.get("name", "")),
            "raw_name": s.get("name", ""),
            "owner": ow,
            "owner_name": state.loc().get(ow, ""),
            "cores": len(s.get("cores", [])),
            "manpower": s.get("manpower", ""),
            "category": s.get("category", ""),
            "provinces": s.get("province_count", 0),
            "buildings": sum(s.get("buildings", {}).values()),
            # v1.24.2：州列表标来源用。source 是「这个州文件在哪一层」
            # （load_states 里按实际路径反推的），file 用来 hover 提示。
            "source": s.get("source", ""),
            "file": s.get("file", ""),
        })
    return {"count": len(items), "list": items}

def _state_locate(text):
    m = _hist_find_top(text, re.compile(r'(?m)^[ \t]*state\s*=\s*\{'))
    if not m:
        return None
    b = text.find('{', m.end() - 1)
    return b, brace_match(text, b)

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

def state_detail(sid, full=False):
    try:
        sid = int(sid)
    except Exception:
        return {"ok": False, "msg": "州 id 必须是数字"}
    s = state.states().get(sid)
    if not s:
        return {"ok": False, "msg": "没有这个州"}
    root = s.get("root") or ""
    owner = s.get("owner", "") or ""
    return {
        "ok": True, "id": sid,
        "name": state.loc().get(s.get("name", ""), s.get("name", "")),
        "raw_name": s.get("name", ""),
        "file": s.get("file", ""), "root": root,
        # v1.24.2：州面板的来源提示用（entry_source 拿它定位层，找不到再按文件猜）
        "source": s.get("source", ""),
        "writable": bool(root) and not is_under_game(root),
        "owner": owner,
        "owner_name": state.loc().get(owner, ""),
        "cores": s.get("cores", []),
        "core_names": {c: state.loc().get(c, c) for c in s.get("cores", [])},
        "manpower": s.get("manpower", ""),
        "category": s.get("category", ""),
        "history_date": s.get("history_date", ""),
        "provinces": s.get("provinces", []) if full else s.get("provinces", [])[:300],
        "province_count": s.get("province_count", 0),
        "buildings": s.get("buildings", {}),
        "resources": s.get("resources", {}),
        "province_buildings": s.get("province_buildings", {}),
        "victory_points": (s.get("victory_points") or [])[:20],
        "categories": list(STATE_CATEGORIES),
        "building_keys": [k for k in STATE_BUILDINGS],
        "building_meta": [{"key": k, "label": l, "max": m, "coastal": bool(c)}
                          for k, l, m, c in STATE_BUILDING_META],
        "prov_building_meta": [{"key": k, "label": l, "max": m}
                               for k, l, m in PROV_BUILDING_META],
        "resource_meta": [{"key": k, "label": l, "hint": h} for k, l, h in RESOURCE_META],
        "coastal": state_is_coastal(s),
        "owners": sorted(state.countries().keys()),
    }

def state_save(sid, fields, reload=True):
    try:
        sid = int(sid)
    except Exception:
        return {"ok": False, "msg": "州 id 必须是数字"}
    s = state.states().get(sid)
    if not s:
        return {"ok": False, "msg": "没有这个州"}
    root = s.get("root") or ""
    rel = s.get("file") or ""
    if not rel:
        return {"ok": False, "msg": "这个州没有来源文件"}
    # 州文件在只读层时，只把「这一个州文件」复制到自己的 mod，不加 replace_path。
    # 这样原版其余 820 个州照常生效——整目录接管会复制 821 个文件，
    # 而且一旦 replace_path 生效，漏掉任何一个州它就从游戏里消失了。
    _single, _why2 = ensure_file_writable(state.roots()[-1] if state.roots() else root,
                                          "history/states", os.path.basename(rel))
    if _single:
        root = os.path.dirname(_single)
        rel = os.path.basename(_single)
        state.layer_hint()["states"] = _why2
    else:
        # 目录被别的 mod 独占，或者链里找不到源文件——这时只能要求先接管
        _target, _why = write_base(state.roots()[-1] if state.roots() else root, "history/states")
        if _target and os.path.abspath(_target) != os.path.abspath(root):
            _src = os.path.join(root, rel)
            root = _target
            _dst = os.path.join(root, rel)
            os.makedirs(os.path.dirname(_dst) or root, exist_ok=True)
            if not os.path.exists(_dst) and os.path.exists(_src):
                try:
                    import shutil as _sh
                    _sh.copyfile(_src, _dst)
                except Exception:
                    pass
            state.layer_hint()["states"] = _why
        else:
            return {"ok": False, "msg": _why2 or "写不进去"}

    # 目标层还没有这个文件时，从原位置复制一份，保留未改动的字段
    if not os.path.exists(os.path.join(root, rel)):
        _src = os.path.join(s.get("root") or "", s.get("file") or "")
        if os.path.exists(_src):
            try:
                import shutil as _sh2
                _sh2.copyfile(_src, os.path.join(root, rel))
            except Exception:
                pass
    p = os.path.join(root, rel)
    if not os.path.exists(p):
        return {"ok": False, "msg": "州文件不存在：" + rel}

    owner = (fields.get("owner") or "").strip().upper()
    if owner and owner not in state.countries():
        return {"ok": False, "msg": "owner 不是有效 tag：" + owner}
    cores = [x.strip().upper() for x in (fields.get("cores") or []) if x and x.strip()]
    bad = [c for c in cores if c not in state.countries()]
    if bad:
        return {"ok": False, "msg": "核心不是有效 tag：" + ", ".join(bad[:3])}
    cat = (fields.get("category") or "").strip()
    if cat and cat not in STATE_CATEGORIES:
        return {"ok": False, "msg": "state_category 只能是 " + " / ".join(STATE_CATEGORIES)}
    man = (fields.get("manpower") or "").strip()
    if man and not man.isdigit():
        return {"ok": False, "msg": "人力必须是整数"}
    blds = {}
    for k, v in (fields.get("buildings") or {}).items():
        if k not in STATE_BUILDINGS:
            continue
        try:
            iv = int(v)
        except Exception:
            continue
        if iv >= 0:
            blds[k] = iv
    # 上限 / 沿海校验：写进游戏也会被截断或直接不生效，不如在这里说清楚
    _bmeta = {k: (l, cap, sea) for k, l, cap, sea in STATE_BUILDING_META}
    _coastal = state_is_coastal(s)
    for k, v in blds.items():
        if k not in _bmeta:
            continue
        _label, _cap, _need_sea = _bmeta[k]
        if v > _cap:
            return {"ok": False, "msg": "%s 最多 %d 级，你填了 %d" % (_label, _cap, v)}
        if _need_sea and v > 0 and _coastal is False:
            return {"ok": False,
                    "msg": "州 %d「%s」没有海岸线，%s 建不了（改填 0 或换个沿海州）"
                           % (sid, state.loc().get(s.get("name", ""), s.get("name", "")), _label)}
    res = {}
    for k, v in (fields.get("resources") or {}).items():
        if k not in STATE_RESOURCES:
            continue
        try:
            iv = int(v)
        except Exception:
            continue
        if iv >= 0:
            res[k] = iv

    text, has_bom = _read_bom_text(p)
    loc = _state_locate(text)
    if not loc:
        return {"ok": False, "msg": "文件里找不到 state = { } 块"}
    b, e = loc
    body = text[b + 1:e - 1]

    diff = []
    old_owner = s.get("owner", "")
    old_cores = list(s.get("cores", []))
    old_man = s.get("manpower", "")
    old_cat = s.get("category", "")
    old_blds = dict(s.get("buildings", {}))

    hist = _state_history_range(body)
    hb, he = hist if hist else (0, len(body))

    if owner and owner != old_owner:
        before = body
        # 日期块会覆盖直接子级，必须两处一起改，否则游戏里看到的还是旧值
        body = _set_owner_all(body, owner, hb if hist else 0, he if hist else 0)
        if body != before:
            diff.append({"key": "owner", "label": "所属国家", "old": old_owner, "new": owner})

    if fields.get("cores") is not None and cores != old_cores:
        if hist:
            body = _drop_in_scope(body, "add_core_of", (1, 2), hb, he)
            if cores:
                # 删过行后原来的 hb/he 已失效，重新定位 history 块再插
                hist2 = _state_history_range(body)
                ins = "\n".join("\t\tadd_core_of = %s" % c for c in cores)
                if hist2:
                    hb2, he2 = hist2
                    pos = _insert_pos(body, hb2, he2)
                    body = body[:pos] + "\n" + ins + body[pos:]
                else:
                    body = body.rstrip() + "\n" + ins + "\n"
        else:
            body = _drop_in_scope(body, "add_core_of", (0,), 0, len(body))
            if cores:
                ins = "\n".join("\tadd_core_of = %s" % c for c in cores)
                body = body.rstrip() + "\n" + ins + "\n"
        diff.append({"key": "cores", "label": "核心", "old": ",".join(old_cores), "new": ",".join(cores)})

    if man and man != old_man:
        body = _set_in_scope(body, "manpower", man, 0, 0, len(body), insert=True)
        diff.append({"key": "manpower", "label": "人力", "old": old_man, "new": man})

    if cat and cat != old_cat:
        body = _set_in_scope(body, "state_category", cat, 0, 0, len(body), insert=True)
        diff.append({"key": "category", "label": "州类别", "old": old_cat, "new": cat})

    for k in sorted(blds):
        v = blds[k]
        if old_blds.get(k, None) == v:
            continue
        if v == 0 and not old_blds.get(k):
            continue          # 本来就没有这一项，写 0 没意义（预设会把未列出的都填 0）
        body = _set_building(body, k, v)
        diff.append({"key": "b_" + k, "label": "建筑 " + k,
                     "old": str(old_blds.get(k, "")), "new": str(v)})

    old_res = (s.get("resources") or {})
    # 只处理「显式给出的键」。以前用的是 res ∪ old_res 的并集，
    # 于是没传的键会被当成 0 删掉 —— 面板上只改建筑、资源留空时，
    # 保存一次就把这个州原有的资源全清空了。
    for k in sorted(res.keys()):
        v = res[k]
        if old_res.get(k, 0) == v:
            continue
        if v == 0 and not old_res.get(k):
            continue          # 本来没有，写 0 等于什么都没做
        body = _set_resource(body, k, v)
        diff.append({"key": "res_" + k, "label": "资源 " + k,
                     "old": str(old_res.get(k, "")), "new": str(v)})


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
        old_vp = [[int(p), int(v)] for p, v in (s.get("victory_points") or [])]
        if sorted(want_vp) != sorted(old_vp):
            body = _set_victory_points(body, want_vp)
            diff.append({"key": "vp", "label": "胜利点",
                         "old": ", ".join("%d:%d" % (p, v) for p, v in old_vp) or "无",
                         "new": ", ".join("%d:%d" % (p, v) for p, v in want_vp) or "无"})

    if not diff:
        return {"ok": True, "msg": "没有改动", "diff": []}
    new_text = text[:b + 1] + body + text[e - 1:]
    snapshot(p)
    _write_bom_text(p, new_text, has_bom)
    if not reload:
        return {"ok": True, "msg": "已写入 " + rel, "diff": diff}
    refresh_start_date(state.roots())
    reload_data()
    link_countries()
    return {"ok": True, "msg": "已写入 " + rel, "diff": diff}

def state_apply_buildings(sids, buildings=None, resources=None, only_empty=False):
    """把一整套建筑/资源套用到多个州。

    only_empty=True 时只填当前为 0 的项（不覆盖已有值），适合「给一片州铺基础设施」。
    每州写一次文件，最后统一 reload 一次（逐个 reload 会把几十秒全花在解析上）。
    """
    if not sids:
        return {"ok": False, "msg": "没有选中任何州"}
    buildings = dict(buildings or {})
    resources = dict(resources or {})
    if not buildings and not resources:
        return {"ok": False, "msg": "没有要套用的数值"}
    done, skipped, failed = [], [], []
    base_res = dict(resources)
    for raw in sids:
        try:
            sid = int(raw)
        except Exception:
            failed.append({"id": raw, "msg": "州 id 不是数字"})
            continue
        s = state.states().get(sid)
        if not s:
            failed.append({"id": sid, "msg": "没有这个州"})
            continue
        use_b = dict(buildings)
        use_r = dict(base_res)
        if only_empty:
            old = s.get("buildings") or {}
            oldr = s.get("resources") or {}
            use_b = {k: v for k, v in use_b.items() if int(old.get(k, 0) or 0) == 0}
            use_r = {k: v for k, v in use_r.items() if int(oldr.get(k, 0) or 0) == 0}
        if not use_b and not use_r:
            skipped.append(sid)
            continue
        r = state_save(sid, {"buildings": use_b, "resources": use_r}, reload=False)
        if r.get("ok"):
            done.append(sid)
        else:
            failed.append({"id": sid, "msg": r.get("msg", "写入失败")})
    if done:
        refresh_start_date(state.roots())
        reload_data()
        link_countries()
    parts = []
    if done:
        parts.append("已套用到 %d 个州" % len(done))
    if skipped:
        parts.append("%d 个州本来就有值，跳过" % len(skipped))
    if failed:
        parts.append("%d 个州失败（%s）" % (len(failed), failed[0]["msg"]))
    return {"ok": bool(done) or not failed, "done": done, "skipped": skipped,
            "failed": failed, "msg": "；".join(parts) or "没有改动"}

def _states_dir_for_write(root):
    """新建州文件应该写到的目录：链顶 mod（跳过原版）；原版只读"""
    layers = mod_layers(root)
    for lay in reversed(layers or []):
        if lay and not is_under_game(lay):
            d = os.path.join(lay, "history", "states")
            return lay, d
    return None, None

def _free_state_id():
    used = set()
    for sid in state.states().keys():
        try:
            used.add(int(sid))
        except Exception:
            pass
    n = 1
    while n in used:
        n += 1
    return n

def state_create(provinces, root=None, name=None, category="rural", manpower=100000,
                 sid=None, owner=None):
    """用给定省份新建一个州。

    - 这些省若已属于别的州，会从原州移出（HOI4 里一个省只能属于一个州）
    - 文件写到链顶 mod 的 history/states/，原版与父 mod 不写
    - 给了 owner 就同时写 history = { owner / add_core_of }，
      否则这个州是无主地，地图上不会属于任何国家
    """
    root = _map_pick(root)
    try:
        pids = sorted({int(p) for p in (provinces or [])})
    except Exception:
        return {"ok": False, "msg": "省份列表不合法"}
    if not pids:
        return {"ok": False, "msg": "至少要给一个省"}

    top, states_dir = _states_dir_for_write(root)
    if not top or not states_dir:
        return {"ok": False, "msg": "找不到可写的 mod 目录（原版只读）"}

    # 省份必须存在于地图上
    _ensure_prov_rgb(root)
    known = set(state.map_var("PROV_RGB"))
    missing = [p for p in pids if p not in known]
    if missing:
        return {"ok": False, "msg": "这些省在地图上不存在：%s" % ", ".join(map(str, missing[:8]))}

    # 目标州 id
    if sid in (None, "", 0):
        new_id = _free_state_id()
    else:
        try:
            new_id = int(sid)
        except Exception:
            return {"ok": False, "msg": "州 id 不合法"}
        if str(new_id) in state.states() or new_id in state.states():
            return {"ok": False, "msg": "州 %d 已经存在" % new_id}

    # 从原州移出
    moved_from = []
    for pid in pids:
        cur = _find_state_of_prov(pid)
        if cur is None:
            continue
        _r, _rel, fpath = _state_file_for(cur)
        if not fpath or is_under_game(_r or ""):
            continue
        try:
            text, has_bom = _read_bom_text(fpath)
            loc = _state_locate(text)
            if not loc:
                continue
            b, e = loc
            body = text[b + 1:e - 1]
            old = _parse_state_provinces(body)
            new = [p for p in old if p != pid]
            new_text = text[:b + 1] + _set_state_provinces(body, new) + text[e - 1:]
            snapshot(fpath)
            _write_bom_text(fpath, new_text, has_bom)
            state.changed()[fpath] = _rel or os.path.relpath(fpath, _r or root)
            if cur not in moved_from:
                moved_from.append(cur)
        except Exception as e2:
            print("移出原州失败:", pid, e2)

    # HOI4 里 state 的 name 是本地化键，不能直接写中文；显示名写进 loc 文件
    display_name = (name or "").strip()
    st_name = "STATE_%d" % new_id
    cat = (category or "rural").strip()
    try:
        mp = int(manpower)
    except Exception:
        mp = 100000
    body_lines = [
        "state = {",
        "\tid = %d" % new_id,
        '\tname = "%s"' % st_name,
        "\tmanpower = %d" % mp,
        "\tstate_category = %s" % cat,
        "\tprovinces = {",
    ]
    body_lines += ["\t\t%d" % p for p in pids]
    body_lines += ["\t}", "\tlocal_supplies = 0.0"]
    # history 块必须在 provinces 之后也能解析，但照原版顺序写在前面更稳。
    # 没有 owner 的州是无主地，新地图上建完州却不写 owner，国家就没有领土。
    own = (owner or "").strip().upper()
    if own:
        # 插在 state_category 之后、provinces 之前（原版州文件就是这个顺序）。
        # body_lines 前 5 行：state={ / id / name / manpower / state_category
        body_lines = body_lines[:5] + [
            "\thistory = {",
            "\t\towner = %s" % own,
            "\t\tadd_core_of = %s" % own,
            "\t}",
        ] + body_lines[5:]
    body_lines += ["}", ""]
    content = "\n".join(body_lines)

    os.makedirs(states_dir, exist_ok=True)
    _fname_base = re.sub(r'[^\w\u4e00-\u9fa5-]+', "_", (display_name or st_name))[:40]
    fname = "%d - %s.txt" % (new_id, _fname_base)
    fpath = os.path.join(states_dir, fname)
    if os.path.exists(fpath):
        return {"ok": False, "msg": "文件已存在：%s" % fname}
    try:
        io.open(fpath, "w", encoding="utf-8", newline="").write(content)
    except Exception as e:
        return {"ok": False, "msg": "写文件失败：%s" % e}

    # 内存里也建一条，界面立刻能用
    state.states()[new_id] = {
        "id": new_id, "name": st_name, "manpower": str(mp), "category": cat,
        "provinces": pids, "owner": (owner or "").strip().upper(),
        "cores": [(owner or "").strip().upper()] if owner else [],
        "victory_points": {},
        "buildings": {}, "path": fpath, "file": fpath, "source": os.path.basename(top),
        "root": top, "rel": os.path.relpath(fpath, top), "created": True,
    }
    state.changed()[fpath] = os.path.relpath(fpath, top)

    # 本地化：把显示名写进 loc（yml 必须带 BOM，否则游戏读不到）
    loc_written = ""
    if display_name:
        try:
            loc_dir = os.path.join(top, "localisation", "simp_chinese")
            os.makedirs(loc_dir, exist_ok=True)
            loc_path = os.path.join(loc_dir, "zz_xuerong_state_names_l_simp_chinese.yml")
            line = ' %s:0 "%s"' % (st_name, display_name.replace('"', "'"))
            if os.path.exists(loc_path):
                old_txt = io.open(loc_path, encoding="utf-8-sig", errors="replace").read()
                if st_name not in old_txt:
                    body = old_txt.rstrip()
                    if not body.endswith("}"):
                        body = body.rstrip() + chr(10)
                    new_txt = body + line + chr(10)
                else:
                    new_txt = None
            else:
                new_txt = "l_simp_chinese:" + chr(10) + line + chr(10)
            if new_txt:
                snapshot(loc_path) if os.path.exists(loc_path) else None
                with io.open(loc_path, "w", encoding="utf-8-sig", newline="") as f:
                    f.write(new_txt)
                loc_written = os.path.relpath(loc_path, top)
                state.changed()[loc_path] = loc_written
        except Exception as e3:
            print("写本地化失败:", e3)

    return {"ok": True, "id": new_id, "name": st_name, "display": display_name,
            "loc": loc_written, "provinces": pids,
            "file": os.path.relpath(fpath, top), "moved_from": moved_from,
            "note": ("已写入本地化 %s" % loc_written) if loc_written else ("未填显示名，游戏里会显示 %s" % st_name)}

def _find_state_of_prov(pid):
    """扫 state 文件，找出哪个州包含这个省"""
    for root in state.roots():
        d = os.path.join(root, "history", "states")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            p = os.path.join(d, fn)
            try:
                text = _read_text(p)
            except Exception:
                continue
            m = re.search(r'(?m)^[ \t]*id\s*=\s*(\d+)', text)
            if not m:
                continue
            loc = _state_locate(text)
            if not loc:
                continue
            b, e = loc
            if int(pid) in _parse_state_provinces(text[b + 1:e - 1]):
                return int(m.group(1))
    return None

def _state_file_for(sid):
    """按州 id 找文件路径：(root, rel, path)。

    优先用 state.states() 里已经定下来的那条记录 —— 同一个 id 在多个文件里出现时
    （比如原版有 1-France.txt、mod 又加了 1-Corsica.txt），
    按文件名遍历会挑到和 state.states() 不一致的那一个，后续写入就落到错误文件。"""
    try:
        _s = state.states().get(int(sid)) if isinstance(state.states(), dict) else None
    except Exception:
        _s = None
    if _s and _s.get("root") and _s.get("file"):
        _p = os.path.join(_s["root"], _s["file"])
        if os.path.exists(_p):
            return _s["root"], _s["file"], _p

    _bases = []
    for _r in (state.roots() or []):
        for _b in (mod_layers(_r) or [_r]):
            if _b and os.path.abspath(_b) not in [os.path.abspath(x) for x in _bases]:
                _bases.append(_b)
    for root in reversed(_bases):
        d = os.path.join(root, "history", "states")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            p = os.path.join(d, fn)
            try:
                text = _read_text(p)
            except Exception:
                continue
            m = re.search(r'(?m)^[ \t]*id\s*=\s*(\d+)', text)
            if m and int(m.group(1)) == int(sid):
                return root, os.path.join("history", "states", fn), p
    return None, None, None

def state_province_edit(pid, target_sid=None):
    """把省 pid 移到 target_sid 州；target_sid 为空表示移出当前州"""
    try:
        pid = int(pid)
    except Exception:
        return {"ok": False, "msg": "省 id 不合法"}
    if pid <= 0:
        return {"ok": False, "msg": "省 id 不合法"}
    target = None
    if target_sid not in (None, "", 0, "0"):
        try:
            target = int(target_sid)
        except Exception:
            return {"ok": False, "msg": "目标州 id 不合法"}

    cur_sid = _find_state_of_prov(pid)
    if target is not None and cur_sid == target:
        return {"ok": True, "msg": "省 %d 已经在州 %d 里了" % (pid, target), "noop": True}

    diff = []
    if cur_sid is not None:
        root, rel, path = _state_file_for(cur_sid)
        if not path:
            return {"ok": False, "msg": "找不到州 %s 的文件" % cur_sid}
        if is_under_game(root):
            return {"ok": False, "msg": "州 %d 在原版目录里，只读" % cur_sid}
        text, has_bom = _read_bom_text(path)
        loc = _state_locate(text)
        if not loc:
            return {"ok": False, "msg": "州 %d 文件里找不到 state 块" % cur_sid}
        _b, _e = loc
        body = text[_b + 1:_e - 1]
        old = _parse_state_provinces(body)
        new = [p for p in old if p != pid]
        new_text = text[:_b + 1] + _set_state_provinces(body, new) + text[_e - 1:]
        snapshot(path)
        _write_bom_text(path, new_text, has_bom)
        diff.append({"key": "st_%d" % cur_sid, "label": "州 %d 省份" % cur_sid,
                     "old": "%d 个省" % len(old), "new": "%d 个省" % len(new)})
        state.changed()[path] = rel

    if target is not None:
        root, rel, path = _state_file_for(target)
        if not path:
            return {"ok": False, "msg": "找不到州 %d 的文件" % target}
        if is_under_game(root):
            return {"ok": False, "msg": "州 %d 在原版目录里，只读" % target}
        text, has_bom = _read_bom_text(path)
        loc = _state_locate(text)
        if not loc:
            return {"ok": False, "msg": "州 %d 文件里找不到 state 块" % target}
        _b, _e = loc
        body = text[_b + 1:_e - 1]
        old = _parse_state_provinces(body)
        new = sorted(set(old) | {pid})
        new_text = text[:_b + 1] + _set_state_provinces(body, new) + text[_e - 1:]
        snapshot(path)
        _write_bom_text(path, new_text, has_bom)
        diff.append({"key": "st_%d" % target, "label": "州 %d 省份" % target,
                     "old": "%d 个省" % len(old), "new": "%d 个省" % len(new)})
        state.changed()[path] = rel

    reload_data()
    link_countries()
    if target is None:
        msg = "省 %d 已从州 %s 移出" % (pid, cur_sid)
    elif cur_sid:
        msg = "省 %d：州 %s → 州 %d" % (pid, cur_sid, target)
    else:
        msg = "省 %d 已加入州 %d" % (pid, target)
    return {"ok": True, "msg": msg, "diff": diff, "from": cur_sid, "to": target}

def _state_prov_list(sid):
    """某个州的省列表"""
    s = state.states().get(int(sid)) if isinstance(state.states(), dict) else None
    if not s:
        for v in (state.states().values() if isinstance(state.states(), dict) else []):
            if int(v.get("id") or 0) == int(sid):
                s = v
                break
    if not s:
        return []
    return [int(x) for x in (s.get("provinces") or [])]

def state_refine_preview(sid, k=2, root=None):
    """预览：把州 sid 的省分成 k 组。

    用的是和省份细化同一套算法 _refine_grow_units：
    单元 = 省，邻居 = 省邻接图，坐标 = 省质心。
    """
    root = _map_pick(root)
    try:
        sid = int(sid)
        k = max(2, min(8, int(k or 2)))
    except Exception:
        return {"ok": False, "msg": "参数不合法"}
    provs = _state_prov_list(sid)
    if len(provs) < k:
        return {"ok": False,
                "msg": "州 %d 只有 %d 个省，拆不成 %d 份" % (sid, len(provs), k)}

    allnb = _all_prov_neighbors(root)
    pset = set(provs)
    nb = {p: [x for x in (allnb.get(p) or []) if x in pset] for p in provs}

    # 质心：从省号数组现算（前端才有 centers.json，后端用像素均值）
    ids, w, h = _refine_load_ids(root)
    sums = {}
    if ids:
        for i, pid in enumerate(ids):
            if pid in pset:
                acc = sums.get(pid)
                x, y = i % w, i // w
                if acc is None:
                    sums[pid] = [x, y, 1]
                else:
                    acc[0] += x
                    acc[1] += y
                    acc[2] += 1
    centers = {}
    for p in provs:
        a = sums.get(p)
        if a and a[2]:
            centers[p] = (a[0] / a[2], a[1] / a[2])
        else:
            centers[p] = (0.0, 0.0)

    groups = _refine_grow_units(provs, nb, k, centers)
    parts = []
    for gi in sorted(groups):
        mem = sorted(groups[gi])
        parts.append({"i": gi, "count": len(mem), "provs": mem})

    # 警告
    warn = []
    s = state.states().get(sid) or {}
    owner = s.get("owner") or s.get("owner_tag") or ""
    if owner:
        warn.append("新州会继承归属国 %s 与 cores" % owner)
    vps = s.get("victory_points") or []
    if vps:
        warn.append("原州有 %d 个胜利点，拆分后只留在第 1 组" % len(vps))
    if s.get("category"):
        warn.append("新州类别沿用 %s，人力沿用原值（不会按面积重算）" % s.get("category"))

    return {"ok": True, "sid": sid, "k": len(parts), "total": len(provs),
            "parts": parts, "warnings": warn,
            "msg": "州 %d 的 %d 个省拆成 %d 份：%s" % (
                sid, len(provs), len(parts),
                " / ".join(str(p["count"]) for p in parts))}

def _state_fields_from(sid):
    """从原州提取要继承的字段"""
    s = state.states().get(sid) or {}
    return {
        "owner": s.get("owner") or s.get("owner_tag") or "",
        "cores": list(s.get("cores") or s.get("states_core") or []),
        "category": s.get("category") or "rural",
        "manpower": str(s.get("manpower") or ""),
    }

def state_refine_apply(sid, k=2, root=None):
    """应用：第 1 组留在原州，其余各组建成新州（继承归属国/核心/类别/人力）。"""
    pv = state_refine_preview(sid, k, root)
    if not pv.get("ok"):
        return pv
    root = _map_pick(root)
    sid = pv["sid"]
    parts = pv["parts"]
    base = _state_fields_from(sid)

    # 1) 原州只留第一组
    first = parts[0]["provs"]
    _r, _rel, fpath = _state_file_for(sid)
    if not fpath:
        return {"ok": False, "msg": "找不到州 %d 的文件" % sid}
    if is_under_game(_r or ""):
        return {"ok": False, "msg": "州 %d 来自原版，只读" % sid}
    try:
        text, has_bom = _read_bom_text(fpath)
        loc = _state_locate(text)
        b, e = loc
        body = text[b + 1:e - 1]
        new_body = _set_state_provinces(body, first)
        snapshot(fpath)
        _write_bom_text(fpath, text[:b + 1] + new_body + text[e - 1:], has_bom)
    except Exception as ex:
        return {"ok": False, "msg": "改原州失败：%s" % ex}

    # 2) 其余组各建一个新州
    created = []
    failed = []
    for p in parts[1:]:
        r = state_create(p["provs"], root, None, base["category"],
                         int(base["manpower"]) if base["manpower"].isdigit() else 100000)
        if not r.get("ok"):
            failed.append({"provs": p["provs"][:3], "msg": r.get("msg")})
            continue
        nid = r.get("id") or r.get("sid")
        created.append({"id": nid, "count": p["count"]})
        # 继承字段
        if nid and base["owner"]:
            try:
                state_save(nid, {"owner": base["owner"], "cores": base["cores"]})
            except Exception:
                pass
    reload_data()
    msg = "州 %d 拆成 %d 份：原州留 %d 省" % (sid, len(parts), len(first))
    if created:
        msg += "，新建 " + "、".join("%s(%d省)" % (c["id"], c["count"]) for c in created)
    if failed:
        msg += "；%d 份失败：%s" % (len(failed), failed[0].get("msg"))
    return {"ok": True, "sid": sid, "kept": first, "created": created,
            "failed": failed, "parts": len(parts), "msg": msg}
