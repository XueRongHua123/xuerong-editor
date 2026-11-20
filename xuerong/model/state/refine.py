# -*- coding: utf-8 -*-
"""精细调整：省份逐个指派、预览与落盘。"""
from xuerong import state
from xuerong.core.paths import _read_bom_text, _write_bom_text, is_under_game
from xuerong.model.history import snapshot
from xuerong.model.map import _map_pick, _refine_load_ids
from xuerong.model.state._inj import (_all_prov_neighbors, _parse_state_provinces,
                                      _refine_grow_units, _set_state_provinces,
                                      link_countries, reload_data)
from xuerong.model.state.create import state_create
from xuerong.model.state.index import (_find_state_of_prov, _state_file_for,
                                       _state_locate)
from xuerong.model.state.io import _state_fields_from, _state_prov_list, state_save


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
