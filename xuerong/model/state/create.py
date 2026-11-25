# -*- coding: utf-8 -*-
"""新建州：目标目录、空闲 ID、`state_create` 的整块生成与本地化写入。"""
import io
import os
import re

from xuerong import state
from xuerong.core.paths import (_read_bom_text, _write_bom_text, is_under_game,
                                mod_layers)
from xuerong.model.history import snapshot
from xuerong.model.map import _ensure_prov_rgb, _map_pick
from xuerong.model.state._inj import _parse_state_provinces, _set_state_provinces
from xuerong.model.state.index import (_prov_to_state_map, _state_file_for,
                                       _state_locate)


def _states_dir_for_write(root):
    """新建州文件应该写到的目录：链顶 mod（跳过原版）；原版只读"""
    layers = mod_layers(root)
    for lay in reversed(layers or []):
        if lay and not is_under_game(lay):
            d = os.path.join(lay, "history", "states")
            return lay, d
    return None, None

def _free_state_id(root=None):
    used = set()
    for sid in (state.states() or {}).keys():
        try:
            used.add(int(sid))
        except Exception:
            pass
    targets = [root] if root else (list(state.roots() or []) or [_map_pick(None)])
    seen_dirs = set()
    for t in targets:
        if not t:
            continue
        for lay in (mod_layers(t) or [t]):
            if not lay:
                continue
            d = os.path.join(lay, "history", "states")
            ab = os.path.abspath(d)
            if ab in seen_dirs or not os.path.isdir(d):
                continue
            seen_dirs.add(ab)
            try:
                names = os.listdir(d)
            except Exception:
                continue
            for fn in names:
                if not fn.lower().endswith(".txt"):
                    continue
                m = re.match(r'^\s*(\d+)', fn)
                if m:
                    try:
                        used.add(int(m.group(1)))
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
        new_id = _free_state_id(root)
    else:
        try:
            new_id = int(sid)
        except Exception:
            return {"ok": False, "msg": "州 id 不合法"}
        if str(new_id) in state.states() or new_id in state.states():
            return {"ok": False, "msg": "州 %d 已经存在" % new_id}

    # 从原州移出
    moved_from = []
    # 建一次「省 → 州」表，循环里只查字典。原来每个 pid 都调一次
    # _find_state_of_prov（每次重读并解析全部 818 个 state 文件，84 ms/次），
    # 移 50 个省是 4.2 秒；建表一次约 90 ms，之后每省 O(1)。
    _prov_map = _prov_to_state_map()
    for pid in pids:
        cur = _prov_map.get(pid)
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
        with io.open(fpath, "w", encoding="utf-8", newline="") as _f:
            _f.write(content)
    except Exception as e:
        return {"ok": False, "msg": "写文件失败：%s" % e}

    # 内存里也建一条，界面立刻能用
    state.states()[new_id] = {
        "id": new_id, "name": st_name, "manpower": str(mp), "category": cat,
        "provinces": pids, "province_count": len(pids),
        "owner": (owner or "").strip().upper(),
        "cores": [(owner or "").strip().upper()] if owner else [],
        "victory_points": [],
        "buildings": {}, "resources": {}, "province_buildings": {},
        "path": fpath, "file": fpath, "source": os.path.basename(top),
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
                with io.open(loc_path, encoding="utf-8-sig", errors="replace") as _f:
                    old_txt = _f.read()
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
