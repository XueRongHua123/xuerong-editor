# -*- coding: utf-8 -*-
"""读展示与保存：列表 / 详情 payload、`state_save` 落盘、批量建筑应用。"""
import io
import os
import re

from xuerong import state
from xuerong.core.paths import (_read_bom_text, _write_bom_text,
                                effective_layer_files, is_under_game,
                                write_base)
from xuerong.core.text import brace_match, strip_comments
from xuerong.model.history import snapshot
from xuerong.model.state._inj import (ensure_file_writable, link_countries,
                                      refresh_start_date, reload_data)
from xuerong.model.state.edit import (_drop_in_scope, _insert_pos, _set_building,
                                      _set_in_scope, _set_owner_all,
                                      _set_prov_building, _set_resource,
                                      _set_victory_points, _state_history_range)
from xuerong.model.state.index import _state_locate, state_is_coastal
from xuerong.state import (PROV_BUILDING_META, RESOURCE_META, STATE_BUILDINGS,
                           STATE_BUILDING_META, STATE_CATEGORIES,
                           STATE_RESOURCES)


def _building_caps(root=None):
    """从叠加链 common/buildings/*.txt 动态读取 state_max / province_max 上限。"""
    s_caps = {k: cap for k, _l, cap, _sea in STATE_BUILDING_META}
    p_caps = {k: cap for k, _l, cap in PROV_BUILDING_META}
    base = root or (state.roots()[-1] if state.roots() else state.game())
    if not base or not os.path.isdir(base):
        return s_caps, p_caps
    try:
        files = effective_layer_files("common/buildings", base)
    except Exception:
        files = []
    for _ab, d, fn in files:
        fp = os.path.join(d, fn)
        try:
            text = strip_comments(io.open(fp, encoding="utf-8-sig", errors="replace").read())
        except Exception:
            continue
        bm = re.search(r'(?m)^\s*buildings\s*=\s*\{', text)
        if not bm:
            continue
        bb = text.find("{", bm.end() - 1)
        be = brace_match(text, bb)
        if be <= bb:
            continue
        inner = text[bb + 1:be - 1]
        for m in re.finditer(r'(?m)^[ \t]*([a-z_][a-z0-9_]*)[ \t]*=\s*\{', inner):
            bkey = m.group(1)
            if bkey not in s_caps and bkey not in p_caps:
                continue
            sb = inner.find("{", m.end() - 1)
            se = brace_match(inner, sb)
            if se <= sb:
                continue
            body = inner[sb + 1:se - 1]
            sm = re.search(r'(?m)^\s*state_max\s*=\s*(\d+)', body)
            pm = re.search(r'(?m)^\s*province_max\s*=\s*(\d+)', body)
            if sm and bkey in s_caps:
                s_caps[bkey] = int(sm.group(1))
            if pm and bkey in p_caps:
                p_caps[bkey] = int(pm.group(1))
    return s_caps, p_caps


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
    s_caps, p_caps = _building_caps(state.roots()[-1] if state.roots() else root)
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
        "building_meta": [{"key": k, "label": l, "max": s_caps.get(k, m), "coastal": bool(c)}
                          for k, l, m, c in STATE_BUILDING_META],
        "prov_building_meta": [{"key": k, "label": l, "max": p_caps.get(k, m)}
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
    # 上限 / 沿海校验：优先读叠加链 common/buildings 真实 state_max/province_max，
    # 防止写出超限数值进游戏报 Malformed token（如 S14 infrastructure=77）
    s_caps, p_caps = _building_caps(state.roots()[-1] if state.roots() else root)
    _bmeta = {k: (l, s_caps.get(k, cap), sea) for k, l, cap, sea in STATE_BUILDING_META}
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
    _pmeta = {k: (l, p_caps.get(k, cap)) for k, l, cap in PROV_BUILDING_META}
    for _pid, _pvals in (fields.get("province_buildings") or {}).items():
        for k, v in (_pvals or {}).items():
            if k not in _pmeta:
                continue
            try:
                iv = int(v)
            except Exception:
                continue
            _plabel, _pcap = _pmeta[k]
            if iv > _pcap:
                return {"ok": False, "msg": "省份 %s 的 %s 最多 %d 级，你填了 %d" % (_pid, _plabel, _pcap, iv)}
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

    # 州文件在只读层时，只把「这一个州文件」复制到自己的 mod，不加 replace_path。
    # 这样原版/父 mod 其余州照常生效——整目录接管会复制数百个文件，
    # 而且一旦 replace_path 生效，漏掉任何一个州它就从游戏里消失了。
    _single, _why2 = ensure_file_writable(state.roots()[-1] if state.roots() else root,
                                          "history/states", os.path.basename(rel))
    if _single:
        root = os.path.dirname(_single)
        rel = os.path.basename(_single)
        state.layer_hint()["states"] = _why2
    else:
        # 目录被更高层 mod 独占，或者链里找不到源文件——这时只能要求先接管
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

def _state_fields_from(sid):
    """从原州提取要继承的字段"""
    s = state.states().get(sid) or {}
    return {
        "owner": s.get("owner") or s.get("owner_tag") or "",
        "cores": list(s.get("cores") or s.get("states_core") or []),
        "category": s.get("category") or "rural",
        "manpower": str(s.get("manpower") or ""),
    }
