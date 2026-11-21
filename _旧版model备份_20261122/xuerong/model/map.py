# -*- coding: utf-8 -*-
"""地图：省界 / 地形 / 高程 / 河流的读取、渲染、编辑与校验（P2-map 从 focus_editor.py 迁入）。

这一域几乎自给自足：66+2 个函数里只有 6 个外部函数要靠门面回注，
其余依赖都在 core 与 model.history。

依赖边界：
  · 叠加链与路径 → xuerong.core.paths；文本工具 → xuerong.core.text
  · 全局容器（PROV_RGB / MAP_EDIT / 各种缓存）→ xuerong.state.map_var()
  · 写前快照 → xuerong.model.history.snapshot
  · 门面回注 6 个：_qa_dir / _dir_mtime / _first / load_units /
    _state_locate / _parse_state_provinces / _set_state_provinces
    （都是别的域或全局小工具，不能反向 import 门面）
"""
import hashlib
import io
import json
import os
import re
import shutil
import struct
import sys
import time
import traceback
import zlib

from PIL import Image, ImageDraw

from xuerong import state
from xuerong.core import paths
from xuerong.core.paths import (_layers_find, _mod_descriptor, _out_path, _out_read_path,
                          _read_bom_text, _write_bom_text, is_under_game, mod_layers)
from xuerong.core.text import _atomic_write, brace_match, strip_comments
from xuerong.model.history import snapshot

# ---------------------------------------------------------------- 门面回注
_INJ = {}


def bind(**kw):
    """门面启动时回注横切依赖（见模块 doc）。"""
    _INJ.update(kw)


def _qa_dir():
    return _INJ["_qa_dir"]()


def _dir_mtime(p):
    return _INJ["_dir_mtime"](p)


def _first(*a, **k):
    return _INJ["_first"](*a, **k)


def load_units(*a, **k):
    return _INJ["load_units"](*a, **k)


def _state_locate(*a, **k):
    return _INJ["_state_locate"](*a, **k)


def _parse_state_provinces(*a, **k):
    return _INJ["_parse_state_provinces"](*a, **k)


def _set_state_provinces(*a, **k):
    return _INJ["_set_state_provinces"](*a, **k)


def _map_files(root):
    """沿叠加链找地图（子 mod → 父 mod → 原版），返回 (bmp, csv, 提供者)"""
    if root:
        b, d, provider, _layers = _map_files_layered(root)
        if b and d:
            return b, d, (provider or root)
    if state.game():
        b = os.path.join(state.game(), "map", "provinces.bmp")
        d = os.path.join(state.game(), "map", "definition.csv")
        if os.path.exists(b) and os.path.exists(d):
            return b, d, state.game()
    return None, None, None

def _map_key(root):
    """缓存键必须覆盖所有会影响图层的输入：
    省位图、definition.csv、州 history、战略区定义。
    少一项就会出现"改了数据但地图没变"的错觉。"""
    b, d, base = _map_files(root)
    if not b:
        return None, None
    layers = mod_layers(root)
    layer_sig = "|".join("%s:%d:%d" % (os.path.abspath(x), _dir_mtime(os.path.join(x, "history", "states")),
                                       _dir_mtime(os.path.join(x, "map", "strategicregions")))
                         for x in layers)
    key = "%s|%d|%d|%d|%s" % (
        os.path.abspath(base), os.path.getmtime(b), os.path.getsize(b), os.path.getmtime(d), layer_sig)
    return key, base

def _map_dir(root):
    key, base = _map_key(root)
    if not key:
        return None, None, None
    return os.path.join(state.map_var("MAP_CACHE_DIR"), hashlib.md5(key.encode("utf-8")).hexdigest()[:12]), key, base

def _csv_path_for(root):
    layers = mod_layers(root)
    csvp, prov = _layers_find("map/definition.csv", layers)
    return csvp, prov

def _save_point_undo(bmp, changes):
    """把「像素索引 → 原 RGB」存成紧凑二进制（4 字节索引 + 3 字节 RGB）。

    散布型改动（十字交叉修复）用包围盒备份会长到几十 MB，实际只改了几百个像素。"""
    import struct
    os.makedirs(state.map_var("MAP_UNDO_DIR"), exist_ok=True)
    seq = int(time.time() * 1000)
    fn = os.path.join(state.map_var("MAP_UNDO_DIR"), "pt%d.bin" % seq)
    buf = bytearray()
    buf += struct.pack("<I", len(changes))
    for idx, rgb in changes:
        buf += struct.pack("<I", idx)
        buf += bytes((rgb[0], rgb[1], rgb[2]))
    _atomic_write(fn, bytes(buf))
    return fn

def _load_point_undo(fn):
    """读回点级备份 → [(idx, (r,g,b)), ...]"""
    import struct
    raw = io.open(fn, "rb").read()
    if len(raw) < 4:
        return []
    n = struct.unpack("<I", raw[:4])[0]
    out = []
    off = 4
    for _ in range(n):
        if off + 7 > len(raw):
            break
        idx = struct.unpack("<I", raw[off:off + 4])[0]
        r, g, b = raw[off + 4], raw[off + 5], raw[off + 6]
        out.append((idx, (r, g, b)))
        off += 7
    return out

def _apply_point_undo(entry):
    """把点级备份写回 bmp（按行分组批量写，减少 IO）"""
    bmp = entry.get("bmp")
    pts = _load_point_undo(entry.get("file") or "")
    if not bmp or not pts:
        return 0
    info = bmp_info(bmp)
    if not info:
        return 0
    w, h = info["w"], info["h"]
    # 按包围盒一次读、逐点改、一次写
    xs = [i % w for i, _ in pts]
    ys = [i // w for i, _ in pts]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx + 1, max(ys) - by + 1
    rect = bmp_read_rect(bmp, bx, by, bw, bh)
    if rect is None:
        return 0
    for idx, rgb in pts:
        o = (idx // w - by) * bw + (idx % w - bx)
        if 0 <= o < len(rect):
            rect[o] = rgb
    bmp_write_rect(bmp, bx, by, bw, bh, rect)
    return len(pts)

def _scan_cross(allpx, w, h):
    """找出所有 2x2 十字模式：左上==右下 且 右上==左下 且 A!=B。返回 [(x, y, A, B)]"""
    out = []
    for y in range(h - 1):
        base = y * w
        nxt = base + w
        for x in range(w - 1):
            a = allpx[base + x]
            b = allpx[base + x + 1]
            c = allpx[nxt + x]
            d = allpx[nxt + x + 1]
            if a == d and b == c and a != b:
                out.append((x, y, a, b))
    return out

def _refine_load_ids(root):
    """载入 省号数组（按 provinces.bmp + definition.csv 的 mtime 缓存）"""
    from PIL import Image, ImageDraw
    Image.MAX_IMAGE_PIXELS = None
    layers = mod_layers(root)
    bmp, _ = _layers_find("map/provinces.bmp", layers)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not bmp or not csvp:
        return None, 0, 0
    key = (bmp, os.path.getmtime(bmp), csvp, os.path.getmtime(csvp))
    hit = state.map_var("_REFINE_IDS_CACHE").get("cur")
    if hit and hit[0] == key:
        return hit[1], hit[2], hit[3]
    with Image.open(bmp) as im:
        w, h = im.size
        raw = im.convert("RGB").tobytes()
    rgb2pid = {}
    with io.open(csvp, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.strip().split(";")
            if len(p) >= 8 and p[0].isdigit():
                rgb2pid[(int(p[1]), int(p[2]), int(p[3]))] = int(p[0])
    ids = [0] * (w * h)
    for i in range(w * h):
        ids[i] = rgb2pid.get((raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]), 0)
    state.map_var("_REFINE_IDS_CACHE")["cur"] = (key, ids, w, h)
    return ids, w, h

def map_repair_cross(root=None, apply_fix=False, limit=2000):
    """修十字交叉像素：把 2x2 的 `A B / B A` 解成 `A A / B B` 或 `A B / A B`。
    选择依据：看 A 在上方还是左方的邻域更多，优先保持那个方向的连通。"""
    root = _map_pick(root)
    layers = mod_layers(root)
    bmp, prov = _layers_find("map/provinces.bmp", layers)
    if not bmp:
        return {"ok": False, "msg": "找不到 provinces.bmp"}
    if apply_fix and is_under_game(bmp):
        return {"ok": False, "msg": "provinces.bmp 来自原版，只读"}
    info = bmp_info(bmp)
    if not info or info["bpp"] != 24:
        return {"ok": False, "msg": "只支持 24 位 BMP"}
    w, h = info["w"], info["h"]
    allpx = bmp_read_rect(bmp, 0, 0, w, h)
    if allpx is None:
        return {"ok": False, "msg": "读图失败"}
    crosses = _scan_cross(allpx, w, h)
    if not crosses:
        return {"ok": True, "found": 0, "fixed": 0, "msg": "没有十字交叉"}

    # 决定每处怎么解
    changes = []      # [(x, y, new_rgb)]
    plan = {"h": 0, "v": 0, "tie": 0}
    for (x, y, a, b) in crosses[:limit]:
        up = allpx[(y - 1) * w + x] if y > 0 else None
        left = allpx[y * w + (x - 1)] if x > 0 else None
        a_up = (up == a)
        a_left = (left == a)
        if a_up and not a_left:
            # A 在上方更连贯 → 纵向切：把 (x, y+1) 的 B 改成 A
            changes.append((x, y + 1, a))
            plan["v"] += 1
        elif a_left and not a_up:
            # A 在左方更连贯 → 横向切：把 (x+1, y) 的 B 改成 A
            changes.append((x + 1, y, a))
            plan["h"] += 1
        else:
            # 无法判断：默认横向（改动更集中在上方）
            changes.append((x + 1, y, a))
            plan["tie"] += 1

    result = {"ok": True, "found": len(crosses), "planned": len(changes),
              "plan": plan, "applied": 0}
    if not apply_fix:
        result["msg"] = "发现 %d 处十字交叉（横向 %d / 纵向 %d / 默认 %d），未改动" % (
            len(crosses), plan["h"], plan["v"], plan["tie"])
        result["sample"] = [{"x": x, "y": y} for (x, y, _c) in changes[:20]]
        return result

    # 应用：点级备份（散布改动用包围盒会备份整幅图，30+ MB，实际只改几百个像素）
    # 多轮迭代只记「第一次遇到该像素时的原值」，最后统一存成一个 undo 条目，
    # 否则撤销只能退回到上一轮，而不是修复前的状态。
    xs = [c[0] for c in changes]
    ys = [c[1] for c in changes]
    x0, x1 = max(0, min(xs)), min(w - 1, max(xs))
    y0, y1 = max(0, min(ys)), min(h - 1, max(ys))
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    before = bmp_read_rect(bmp, x0, y0, bw, bh)
    if before is None:
        return {"ok": False, "msg": "读 bmp 区域失败"}
    after = list(before)
    orig_vals = {}
    for (cx, cy, rgb) in changes:
        o = (cy - y0) * bw + (cx - x0)
        if 0 <= o < len(after):
            gi = cy * w + cx
            if gi not in orig_vals:
                orig_vals[gi] = tuple(before[o])
            after[o] = rgb
    bmp_write_rect(bmp, x0, y0, bw, bh, after)
    result["applied"] = len(changes)

    # 改像素会产生新的交叉，迭代几轮直到不再减少
    rounds = 1
    prev = len(crosses)
    while rounds < 4:
        allpx2 = bmp_read_rect(bmp, 0, 0, w, h)
        cs2 = _scan_cross(allpx2, w, h) if allpx2 else []
        if not cs2 or len(cs2) >= prev:
            break
        prev = len(cs2)
        ch2 = []
        for (x, y, a, b) in cs2:
            up = allpx2[(y - 1) * w + x] if y > 0 else None
            left = allpx2[y * w + (x - 1)] if x > 0 else None
            ch2.append((x + 1 if (left == a or up != a) else x,
                        y if (left == a or up != a) else y + 1, a))
        xs2 = [c[0] for c in ch2]
        ys2 = [c[1] for c in ch2]
        ax0, ax1 = max(0, min(xs2)), min(w - 1, max(xs2))
        ay0, ay1 = max(0, min(ys2)), min(h - 1, max(ys2))
        aw, ah = ax1 - ax0 + 1, ay1 - ay0 + 1
        bef2 = bmp_read_rect(bmp, ax0, ay0, aw, ah)
        if bef2 is None:
            break
        aft2 = list(bef2)
        for (cx, cy, rgb) in ch2:
            _i = (cy - ay0) * aw + (cx - ax0)
            if 0 <= _i < len(aft2):
                gi2 = cy * w + cx
                if gi2 not in orig_vals:
                    orig_vals[gi2] = tuple(bef2[_i])
                aft2[_i] = rgb
        bmp_write_rect(bmp, ax0, ay0, aw, ah, aft2)
        result["applied"] += len(ch2)
        rounds += 1

    # 所有轮次合成一个 undo 条目
    _pts = [(gi, rgb) for gi, rgb in orig_vals.items()]
    _fn = _save_point_undo(bmp, _pts)
    state.map_var("MAP_EDIT")["undo"].append({"file": _fn, "bmp": bmp, "kind": "points",
                             "count": len(_pts), "rect": [x0, y0, bw, bh]})
    state.map_var("MAP_EDIT")["redo"] = []

    result["rounds"] = rounds
    result["remaining"] = prev
    result["msg"] = "已修复 %d 处十字交叉（%d 轮），剩余约 %d 处（图层需要重建）" % (
        result["applied"], rounds, prev)
    return result

def map_repair_preview(root=None):
    """列出能自动修的问题及其影响面（不改文件）"""
    root = _map_pick(root)
    dirp, key, base = _map_dir(root)
    idx_path = os.path.join(dirp or "", "prov_index.json")
    if not os.path.exists(idx_path):
        return {"ok": False, "msg": "请先构建图层"}
    try:
        idx = json.loads(io.open(idx_path, encoding="utf-8").read())
    except Exception as e:
        return {"ok": False, "msg": "读取索引失败：%s" % e}
    have = set()
    for k, v in idx.items():
        try:
            if int(v.get("px") or 0) > 0:
                have.add(int(k))
        except Exception:
            continue
    csvp, prov = _csv_path_for(root)
    if not csvp:
        return {"ok": False, "msg": "找不到 definition.csv"}
    ghost = []
    total = 0
    try:
        for line in io.open(csvp, encoding="utf-8", errors="replace"):
            parts = line.strip().split(";")
            if len(parts) < 4 or not parts[0].isdigit():
                continue
            total += 1
            pid = int(parts[0])
            if pid == 0:
                continue
            if pid not in have:
                ghost.append(pid)
    except Exception as e:
        return {"ok": False, "msg": "读 csv 失败：%s" % e}
    return {"ok": True, "csv": csvp, "csv_from": prov, "csv_rows": total,
            "ghost": sorted(ghost)[:500], "ghost_count": len(ghost),
            "repairable": {"ghost": len(ghost)}}

def map_repair_ghost(root=None):
    """删除 definition.csv 里在地图上没有像素的省（省 0 保留）。
    改的是链顶 mod 的 csv；原版只读时拒绝。"""
    pv = map_repair_preview(root)
    if not pv.get("ok"):
        return pv
    csvp = pv["csv"]
    if is_under_game(csvp):
        return {"ok": False, "msg": "definition.csv 来自原版，只读，不能修"}
    ghost = set(pv["ghost"])
    if not ghost:
        return {"ok": True, "removed": 0, "msg": "没有幽灵省，不需要修"}
    try:
        raw = io.open(csvp, "rb").read()
        has_bom = raw[:3] == bytes((0xEF, 0xBB, 0xBF))
        text = raw.decode("utf-8-sig", errors="replace")
    except Exception as e:
        return {"ok": False, "msg": "读 csv 失败：%s" % e}
    keep = []
    removed = []
    for line in text.splitlines():
        parts = line.strip().split(";")
        if len(parts) >= 4 and parts[0].isdigit():
            pid = int(parts[0])
            if pid in ghost:
                removed.append(pid)
                continue
        keep.append(line)
    new_text = chr(10).join(keep)
    if text.endswith(chr(10)):
        new_text += chr(10)
    snapshot(csvp)
    try:
        with io.open(csvp, "w", encoding="utf-8-sig" if has_bom else "utf-8", newline="") as f:
            f.write(new_text)
    except Exception as e:
        return {"ok": False, "msg": "写 csv 失败：%s" % e}
    state.changed()[csvp] = os.path.relpath(csvp, os.path.dirname(os.path.dirname(csvp)))
    state.map_var("PROV_RGB").clear()
    return {"ok": True, "removed": len(removed), "ids": removed[:30], "csv": csvp,
            "msg": "已删除 %d 个幽灵省，图层需要重建" % len(removed)}

def map_analysis(root=None, limit=60, min_px=800, only_land=True):


    """省份排名：按面积（像素数）列出大省，附州/战略区/地形。
    数据直接来自图层缓存的 prov_index.json，不重新扫像素。"""
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "还没有加载 mod"}
    dirp, key, base = _map_dir(root)
    idx_path = os.path.join(dirp or "", "prov_index.json")
    if not os.path.exists(idx_path):
        return {"ok": False, "msg": "请先构建图层（缺少 prov_index.json）"}
    try:
        idx = json.loads(io.open(idx_path, encoding="utf-8").read())
    except Exception as e:
        return {"ok": False, "msg": "读取索引失败：%s" % e}

    rows = []
    total_px = 0
    for pid_s, rec in idx.items():
        try:
            px = int(rec.get("px") or 0)
            pid = int(pid_s)
        except Exception:
            continue
        if pid <= 0 or px <= 0:
            continue
        _type = rec.get("type") or ""
        if only_land and _type and _type != "land":
            continue          # 海省湖省不需要细化，默认排除
        total_px += px
        rows.append({"pid": pid, "px": px, "state": rec.get("state") or 0,
                     "region": rec.get("region") or 0, "terrain": rec.get("terrain") or "",
                     "continent": rec.get("continent") or 0, "type": rec.get("type") or ""})
    if not rows:
        return {"ok": False, "msg": "索引里没有有效省份"}
    rows.sort(key=lambda r: -r["px"])
    px_all = sorted(r["px"] for r in rows)
    n = len(px_all)
    median = px_all[n // 2] if n else 0
    mean = total_px / n if n else 0
    big = [r for r in rows if r["px"] >= min_px]
    st_agg = {}
    for r in rows:
        sid = r["state"]
        a = st_agg.setdefault(sid, {"state": sid, "n": 0, "px": 0, "max": 0})
        a["n"] += 1
        a["px"] += r["px"]
        a["max"] = max(a["max"], r["px"])
    st_rows = sorted(st_agg.values(), key=lambda a: -(a["px"] / max(1, a["n"])))[:20]
    for a in st_rows:
        a["avg"] = round(a["px"] / max(1, a["n"]))
    return {"ok": True, "count": n, "total_px": total_px, "mean": round(mean),
            "median": median, "min_px": min_px, "big_count": len(big),
            "top": rows[:limit], "big": big[:limit], "states": st_rows, "source": base}

def map_sources():
    """列出所有可用于地图的来源：已加载的 mod（有无 map 都列出）+ 原版"""
    out = []
    seen = set()
    for r in state.roots():
        p = os.path.abspath(r)
        if p in seen:
            continue
        seen.add(p)
        # 用叠加链判断：submod 自己没有 bmp，但父 mod 有
        try:
            _b, _d, _prov, _layers = _map_files_layered(p)
        except Exception:
            _b = _d = _prov = None
        has = bool(_b and _d)
        prov_name = ""
        if _prov and os.path.abspath(_prov) != os.path.abspath(p):
            prov_name = os.path.basename(_prov.replace(chr(92), "/").rstrip("/"))
        out.append({"path": p, "name": os.path.basename(p.replace(chr(92), "/").rstrip("/")) or p,
                    "has_map": has, "map_from": prov_name,
                    "readonly": is_under_game(p), "is_game": False})
    if state.game():
        g = os.path.abspath(state.game())
        out.append({"path": g, "name": "原版（游戏本体）",
                    "has_map": os.path.exists(os.path.join(g, "map", "provinces.bmp")),
                    "readonly": True, "is_game": True})
    return out

def _map_pick(root=None):
    """指定 root 就用它；否则第一个在叠加链里能找到地图的 mod；最后原版。
    注意：submod 自己可能没有 provinces.bmp（由父 mod 提供），所以判断要走整条链。"""
    if root:
        return root
    for r in state.roots():
        try:
            b, d, _provider, _layers = _map_files_layered(r)
        except Exception:
            b = d = None
        if b and d:
            return r
    return state.game()

def map_generate(source="procedural", out_dir=None, width=1200, height=440,
                 n_provinces=180, min_size=300, seed=11, src_path=None,
                 sea_level=0.42, balance=True, min_province_px=800,
                 n_regions=None, n_supply=None, bbox=None, rivers_path=None,
                 cities_path=None, city_radius=4):
    """调用 qa/mapgen.py 生成完整 map/ 目录。"""
    try:
        import sys as _sys
        _qa = _qa_dir()
        if _qa not in _sys.path:
            _sys.path.insert(0, _qa)
        import mapgen
    except Exception as e:
        return {"ok": False, "msg": "地图生成器不可用：%s" % e}
    if not out_dir:
        out_dir = os.path.join(paths.app_dir(), "tmp",
                               "_gen_%d" % int(__import__("time").time()))
    try:
        r = mapgen.generate(source, out_dir, int(width), int(height),
                            int(n_provinces), int(min_size), int(seed),
                            src_path, float(sea_level),
                            template_map=os.path.join(state.game(), "map") if state.game() else None,
                            balance=bool(balance),
                            min_province_px=int(min_province_px),
                            n_regions=n_regions, n_supply=n_supply,
                            bbox=bbox, rivers_path=rivers_path,
                            cities_path=cities_path, city_radius=int(city_radius))
        return r
    except Exception as e:
        import traceback
        return {"ok": False, "msg": "生成失败：%s" % e,
                "trace": traceback.format_exc()[-800:]}

def _map_files_layered(root):
    """在叠加链里找 provinces.bmp / definition.csv，返回 (bmp, csv, 提供地图的 root, layers)"""
    layers = mod_layers(root)
    b, rb = _layers_find("map/provinces.bmp", layers)
    d, rd = _layers_find("map/definition.csv", layers)
    if b and d:
        return b, d, (rb or rd), layers
    return None, None, None, layers

def bmp_info(path):
    """读 BMP 头，返回 (width, height, bpp, data_offset, row_size, top_down)"""
    with open(path, "rb") as f:
        head = f.read(54)
        if len(head) < 54 or head[:2] != b"BM":
            return None
        data_off = struct.unpack("<I", head[10:14])[0]
        w = struct.unpack("<i", head[18:22])[0]
        h = struct.unpack("<i", head[22:26])[0]
        bpp = struct.unpack("<H", head[28:30])[0]
        top_down = h < 0
        h = abs(h)
        row_size = ((w * bpp // 8) + 3) // 4 * 4
        return {"w": w, "h": h, "bpp": bpp, "offset": data_off,
                "row": row_size, "top_down": top_down, "bytes_pp": bpp // 8}

def bmp_read_rect(path, x0, y0, w, h):
    path = _out_read_path(path)          # 输出模式下读改过的副本
    """读矩形区域的原始像素（RGB 三元组列表，行优先）。
    走 Pillow 的 C 实现；逐行手工解析在 1100 万像素时要 7 秒以上。"""
    info = bmp_info(path)
    if not info or info["bpp"] != 24:
        return None
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as im:
            box = im.convert("RGB").crop((x0, y0, x0 + w, y0 + h))
            raw = box.tobytes()
        return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
    except Exception:
        pass
    out = []
    with open(path, "rb") as f:
        for y in range(y0, y0 + h):
            row_idx = y if info["top_down"] else (info["h"] - 1 - y)
            f.seek(info["offset"] + row_idx * info["row"] + x0 * 3)
            data = f.read(w * 3)
            for i in range(0, len(data), 3):
                out.append((data[i + 2], data[i + 1], data[i]))
    return out

def bmp_write_rect(path, x0, y0, w, h, pixels):
    """把 RGB 像素列表原位写回 bmp（不重存文件，保持原有结构）。
    输出模式下：先把源 bmp 复制到 output/ 再改副本，源文件不动。"""
    if state.output_mode():
        _dst = _out_path(path)
        if os.path.abspath(_dst) != os.path.abspath(path):
            if not os.path.exists(_dst):
                os.makedirs(os.path.dirname(_dst) or ".", exist_ok=True)
                shutil.copyfile(path, _dst)
            path = _dst
    info = bmp_info(path)
    if not info or info["bpp"] != 24:
        return False
    buf = bytearray()
    if pixels and isinstance(pixels[0], (list, tuple)) and len(pixels[0]) == 3:
        for (r, g, b) in pixels:
            buf += bytes((b, g, r))
    else:
        buf = bytearray(pixels)
    with open(path, "r+b") as f:
        stride = w * 3
        for row in range(h):
            row_idx = (y0 + row) if info["top_down"] else (info["h"] - 1 - (y0 + row))
            f.seek(info["offset"] + row_idx * info["row"] + x0 * 3)
            f.write(bytes(buf[row * stride:(row + 1) * stride]))
    return True

def _ensure_prov_rgb(root=None):
    """按需从 definition.csv 加载省颜色，**按 mod 缓存**。

    原来用全局单例：第一个 mod 加载完就再也不更新，换 mod 后它的省号全部「不存在」。
    实测后果：跑回归时先测 CN 再测京都，京都的 17214/17217 被判为不存在，州细化失败。"""
    _root = _map_pick(root or None)
    key = os.path.abspath(_root or "")
    if key in state.map_var("_PROV_RGB_CACHE"):
        state.map_var("PROV_RGB").clear()
        state.map_var("PROV_RGB").update(state.map_var("_PROV_RGB_CACHE")[key])
        return state.map_var("PROV_RGB")
    state.map_var("PROV_RGB").clear()
    try:
        _layers = mod_layers(_root)
        csvp, _prov = _layers_find("map/definition.csv", _layers)
        if not csvp or not os.path.exists(csvp):
            return state.map_var("PROV_RGB")
        with io.open(csvp, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.strip().split(";")
                if len(parts) < 4:
                    continue
                try:
                    state.map_var("PROV_RGB")[int(parts[0])] = (int(parts[1]), int(parts[2]), int(parts[3]))
                except Exception:
                    continue
    except Exception as e:
        print("加载 definition.csv 颜色失败:", e)
    state.map_var("_PROV_RGB_CACHE")[key] = dict(state.map_var("PROV_RGB"))
    return state.map_var("PROV_RGB")

def map_edit_begin(bmp_path):
    """开始一次地图编辑事务：清空待提交队列"""
    state.map_var("MAP_EDIT")["pending"] = []
    state.map_var("MAP_EDIT")["file"] = bmp_path
    state.map_var("MAP_EDIT")["touched"] = set()
    return True

def map_edit_dab(bmp_path, x, y, radius, rgb):
    """在事务里画一笔（圆），记录待写像素；返回实际影响的像素数"""
    info = bmp_info(bmp_path)
    if not info:
        return 0
    w, h = info["w"], info["h"]
    n = 0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy > radius * radius:
                continue
            px, py = x + dx, y + dy
            if 0 <= px < w and 0 <= py < h:
                state.map_var("MAP_EDIT")["pending"].append((px, py, rgb))
                state.map_var("MAP_EDIT")["touched"].add((px, py))
                n += 1
    return n

def map_edit_commit(bmp_path=None):
    """提交事务：先保存受影响区域的原始像素（供撤销），再原位写入"""
    bmp_path = bmp_path or state.map_var("MAP_EDIT").get("file")
    pend = state.map_var("MAP_EDIT").get("pending") or []
    if not bmp_path or not pend:
        return {"ok": False, "msg": "没有待写入的像素"}
    info = bmp_info(bmp_path)
    if not info:
        return {"ok": False, "msg": "读不到 bmp 头"}
    xs = [p[0] for p in pend]
    ys = [p[1] for p in pend]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    before = bmp_read_rect(bmp_path, x0, y0, w, h)
    if before is None:
        return {"ok": False, "msg": "只支持 24 位 BMP"}
    # 组装新像素
    grid = {(px - x0, py - y0): rgb for (px, py, rgb) in pend}
    after = list(before)
    for (gx, gy), rgb in grid.items():
        after[gy * w + gx] = rgb
    bmp_write_rect(bmp_path, x0, y0, w, h, after)
    # 存撤销区块。
    # 包围盒备份的代价是 w*h*3 字节——一次改散布在图两头的几百个像素，
    # 包围盒能覆盖整张 5632x2048 的图，单次 33MB。密度低于 35% 时改存点级
    # （每点 7 字节），同样的改动只要几百字节。
    os.makedirs(state.map_var("MAP_UNDO_DIR"), exist_ok=True)
    seq = int(time.time() * 1000)
    area = w * h
    use_points = area > 0 and len(pend) < area * 0.35
    if use_points:
        W_full = info["w"]
        changes = []
        for (px, py, rgb) in pend:
            old_rgb = before[(py - y0) * w + (px - x0)]
            changes.append((py * W_full + px, old_rgb))
        fn = _save_point_undo(bmp_path, changes)
        state.map_var("MAP_EDIT")["undo"].append({"kind": "points", "file": fn, "bmp": bmp_path,
                                 "count": len(pend)})
    else:
        fn = os.path.join(state.map_var("MAP_UNDO_DIR"), "u%d_%d_%d_%d_%d.bin" % (seq, x0, y0, w, h))
        with open(fn, "wb") as f:
            for (r, g, b) in before:
                f.write(bytes((r, g, b)))
        state.map_var("MAP_EDIT")["undo"].append({"file": fn, "bmp": bmp_path, "x": x0, "y": y0,
                                 "w": w, "h": h, "count": len(pend)})
    state.map_var("MAP_EDIT")["redo"] = []
    state.map_var("MAP_EDIT")["pending"] = []
    state.map_var("MAP_EDIT")["touched"] = set()
    return {"ok": True, "pixels": len(pend), "rect": [x0, y0, w, h],
            "backup": "points" if use_points else "rect",
            "undo_depth": len(state.map_var("MAP_EDIT")["undo"])}

def map_edit_undo():
    if not state.map_var("MAP_EDIT")["undo"]:
        return {"ok": False, "msg": "没有可撤销的地图编辑"}
    u = state.map_var("MAP_EDIT")["undo"].pop()
    # 点级备份（十字交叉修复等散布型改动）：逐点写回，不记录 redo
    if u.get("kind") == "points":
        n = _apply_point_undo(u)
        state.map_var("MAP_EDIT")["redo"] = []
        return {"ok": True, "restored": n, "kind": "points",
                "msg": "已撤销 %d 个像素的改动（点级备份，不支持重做）" % n}
    cur = bmp_read_rect(u["bmp"], u["x"], u["y"], u["w"], u["h"])
    prev = []
    with open(u["file"], "rb") as f:
        data = f.read()
    for i in range(0, len(data), 3):
        prev.append((data[i], data[i + 1], data[i + 2]))
    bmp_write_rect(u["bmp"], u["x"], u["y"], u["w"], u["h"], prev)
    state.map_var("MAP_EDIT")["redo"].append({"file": u["file"], "bmp": u["bmp"], "x": u["x"], "y": u["y"],
                             "w": u["w"], "h": u["h"], "current": cur, "count": u["count"]})
    return {"ok": True, "restored": u["count"], "undo_depth": len(state.map_var("MAP_EDIT")["undo"])}

def map_edit_redo():
    if not state.map_var("MAP_EDIT")["redo"]:
        return {"ok": False, "msg": "没有可重做的地图编辑"}
    r = state.map_var("MAP_EDIT")["redo"].pop()
    # 用当前值回写，再压回 undo
    bmp_write_rect(r["bmp"], r["x"], r["y"], r["w"], r["h"], r["current"])
    state.map_var("MAP_EDIT")["undo"].append({"file": r["file"], "bmp": r["bmp"], "x": r["x"], "y": r["y"],
                             "w": r["w"], "h": r["h"], "count": r["count"]})
    return {"ok": True, "undo_depth": len(state.map_var("MAP_EDIT")["undo"])}

def map_merge_preview(src, dst, root=None):
    """预览合并：返回源省像素数、受影响的州/战略区，不写盘"""
    src, dst = int(src), int(dst)
    if src == dst:
        return {"ok": False, "msg": "源省和目标省相同"}
    root = _map_pick(root)
    _ensure_prov_rgb(root)
    if src not in state.map_var("PROV_RGB"):
        return {"ok": False, "msg": "省 %d 在 definition.csv 里没有定义" % src}
    if dst not in state.map_var("PROV_RGB"):
        return {"ok": False, "msg": "省 %d 在 definition.csv 里没有定义" % dst}
    layers = mod_layers(root)
    bmp, _prov = _layers_find("map/provinces.bmp", layers)
    if not bmp:
        return {"ok": False, "msg": "找不到 provinces.bmp"}
    info = bmp_info(bmp)
    if not info:
        return {"ok": False, "msg": "只支持 24 位 BMP"}
    src_rgb = state.map_var("PROV_RGB")[src]
    # 预览只需计数：优先读图层缓存里的 prov_index.json（构建时已算好每省像素数），零遍历成本
    _n = 0
    try:
        _d, _key, _b = _map_dir(root)
        _idx = os.path.join(_d or "", "prov_index.json")
        if os.path.exists(_idx):
            _j = json.loads(io.open(_idx, encoding="utf-8").read())
            _n = int((_j.get(str(src)) or {}).get("px") or 0)
    except Exception:
        _n = 0
    if not _n:
        try:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(bmp) as _im:
                _cols = _im.convert("RGB").getcolors(maxcolors=200000) or []
            _n = next((c for c, col in _cols if tuple(col) == tuple(src_rgb)), 0)
        except Exception:
            allpx = bmp_read_rect(bmp, 0, 0, info["w"], info["h"])
            _n = sum(1 for px in allpx if px == src_rgb)
    hit = [0] * _n
    states_hit = []
    for sid, st in state.states().items():
        if src in (st.get("provinces") or []):
            states_hit.append(sid)
    prov2region, _rl = _strategic_regions(root)
    region_hit = [prov2region.get(src)] if prov2region.get(src) else []
    # 合并后源省的州会不会变空
    empty_after = []
    for sid in states_hit:
        st = state.states().get(sid) or {}
        rest = [p for p in (st.get("provinces") or []) if p != src]
        if not rest:
            empty_after.append(sid)
    return {"ok": True, "src": src, "dst": dst, "pixels": len(hit),
            "src_rgb": list(src_rgb), "dst_rgb": list(state.map_var("PROV_RGB")[dst]),
            "states": states_hit, "states_empty_after": empty_after,
            "regions": region_hit, "bmp": bmp, "w": info["w"], "h": info["h"]}

def map_merge_apply(src, dst, root=None):
    """合并：把 src 的所有像素涂成 dst 的颜色，并把 src 从州列表里改成 dst"""
    pv = map_merge_preview(src, dst, root)
    if not pv.get("ok"):
        return pv
    src, dst = pv["src"], pv["dst"]
    root = _map_pick(root)
    layers = mod_layers(root)
    bmp = pv["bmp"]
    if is_under_game(bmp):
        return {"ok": False, "msg": "原版目录只读"}
    src_rgb = tuple(pv["src_rgb"])
    dst_rgb = tuple(pv["dst_rgb"])
    w, h = pv["w"], pv["h"]
    allpx = bmp_read_rect(bmp, 0, 0, w, h)
    changed = 0
    newpx = list(allpx)
    for i, px in enumerate(allpx):
        if px == src_rgb:
            newpx[i] = dst_rgb
            changed += 1
    if not changed:
        return {"ok": False, "msg": "省 %d 在地图上没有像素" % src}
    # 备份整幅原像素（合并影响面可能很大，用整幅更稳，33MB 一次性）
    os.makedirs(state.map_var("MAP_UNDO_DIR"), exist_ok=True)
    seq = int(time.time() * 1000)
    fn = os.path.join(state.map_var("MAP_UNDO_DIR"), "merge%d.bin" % seq)
    with open(fn, "wb") as f:
        for (r, g, b) in allpx:
            f.write(bytes((r, g, b)))
    bmp_write_rect(bmp, 0, 0, w, h, newpx)
    # 州：src → dst
    touched_states = []
    for sid in pv["states"]:
        st = state.states().get(sid) or {}
        fpath = st.get("path") or st.get("file")
        if not fpath or not os.path.exists(fpath):
            continue
        try:
            _text, _bom = _read_bom_text(fpath)
            _loc = _state_locate(_text)
            if not _loc:
                continue
            _b, _e = _loc
            _body = _text[_b + 1:_e - 1]
            _old = _parse_state_provinces(_body)
            _new = [p for p in _old if p != src]
            if dst not in _new:
                _new.append(dst)
            _new_text = _text[:_b + 1] + _set_state_provinces(_body, _new) + _text[_e - 1:]
            snapshot(fpath)
            _write_bom_text(fpath, _new_text, _bom)
            state.changed()[fpath] = os.path.relpath(fpath, root)
            touched_states.append(os.path.relpath(fpath, root))
        except Exception as _e2:
            print("合并时写州失败:", fpath, _e2)
    # 内存里的 state.states() 也更新
    for sid in pv["states"]:
        st = state.states().get(sid)
        if not st:
            continue
        lst = [p for p in (st.get("provinces") or []) if p != src]
        if dst not in lst:
            lst.append(dst)
        st["provinces"] = sorted(lst)
    state.map_var("MAP_EDIT")["undo"].append({"file": fn, "bmp": bmp, "x": 0, "y": 0, "w": w, "h": h,
                             "count": changed, "kind": "merge", "src": src, "dst": dst,
                             "states": touched_states})
    state.map_var("MAP_EDIT")["redo"] = []
    return {"ok": True, "src": src, "dst": dst, "pixels": changed,
            "states": touched_states, "undo_depth": len(state.map_var("MAP_EDIT")["undo"]),
            "note": "definition.csv 未改动（省 %d 仍保留定义，可后续手工清理或用「删除省」）" % src}

def map_prov_neighbors(pid, root=None):
    """返回某省的相邻省（按共享边像素数排序）。整幅扫描约 5 秒，按 bmp mtime 缓存结果。"""
    root = _map_pick(root)
    try:
        _layers0 = mod_layers(root)
        _b0, _p0 = _layers_find("map/provinces.bmp", _layers0)
        _sig = (os.path.abspath(_b0 or ""), int(os.path.getmtime(_b0)) if _b0 and os.path.exists(_b0) else 0, int(pid))
        if _sig in state.map_var("_NB_CACHE"):
            return dict(state.map_var("_NB_CACHE")[_sig])
    except Exception:
        _sig = None
    _ensure_prov_rgb(root)
    layers = mod_layers(root)
    bmp, _prov = _layers_find("map/provinces.bmp", layers)
    if not bmp:
        return {"ok": False, "msg": "找不到 provinces.bmp"}
    info = bmp_info(bmp)
    w, h = info["w"], info["h"]
    if pid not in state.map_var("PROV_RGB"):
        return {"ok": False, "msg": "省 %d 没有颜色定义" % pid}
    rgb = state.map_var("PROV_RGB")[pid]
    allpx = bmp_read_rect(bmp, 0, 0, w, h)
    idx = {v: k for k, v in state.map_var("PROV_RGB").items()}
    nb = {}
    for i, px in enumerate(allpx):
        if px != rgb:
            continue
        x, y = i % w, i // w
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                other = allpx[ny * w + nx]
                if other != rgb:
                    npid = idx.get(other)
                    if npid:
                        nb[npid] = nb.get(npid, 0) + 1
    out = sorted(nb.items(), key=lambda kv: -kv[1])[:12]
    res = {"ok": True, "pid": pid, "neighbors": [{"pid": p, "share": c} for p, c in out]}
    try:
        if _sig:
            state.map_var("_NB_CACHE")[_sig] = dict(res)
    except Exception:
        pass
    return res

def map_edit_state():

    return {"ok": True, "undo": len(state.map_var("MAP_EDIT")["undo"]), "redo": len(state.map_var("MAP_EDIT")["redo"]),
            "pending": len(state.map_var("MAP_EDIT").get("pending") or []), "file": state.map_var("MAP_EDIT").get("file") or ""}

def _map_files_strict(root):


    """严格模式：沿叠加链找地图（子 mod 没有地图时用父 mod 的），整条链都没有才返回 None。
    返回的地图 bmp 可能来自父 mod，但 base 仍报请求的 root，便于界面区分"数据来自哪里"。"""
    if not root:
        return None, None, None
    b, d, provider, layers = _map_files_layered(root)
    if not b or not d:
        return None, None, None
    return b, d, provider

def map_meta(root=None):
    root = _map_pick(root)
    b, d, base = _map_files_strict(root)
    if not b:
        return {"ok": False, "msg": "这个来源没有 map/provinces.bmp 或 definition.csv",
                "sources": map_sources(), "picked": root}
    dirp, key, base = _map_dir(root)
    built = bool(dirp and os.path.exists(os.path.join(dirp, "meta.json")))
    meta = {}
    if built:
        try:
            meta = json.loads(io.open(os.path.join(dirp, "meta.json"), encoding="utf-8").read())
        except Exception:
            meta = {}
    # 缓存过期：同一来源以前构建过，但缓存键变了（数据或版本改动）
    stale = False
    prev = {}
    lastp = os.path.join(state.map_var("MAP_CACHE_DIR"), "_last.json")
    if os.path.exists(lastp):
        try:
            prev = json.loads(io.open(lastp, encoding="utf-8").read())
        except Exception:
            prev = {}
    if not built and prev.get("root") and os.path.abspath(prev.get("root")) == os.path.abspath(base or ""):
        stale = prev.get("key") != key
    layers = mod_layers(root)
    return {"ok": True, "built": built, "stale": stale, "dir": dirp, "source": base, "stamp": key,
            "prev_built": prev.get("built"), "meta": meta, "picked": root,
            "layers": [{"path": x,
                        "name": os.path.basename(x.replace("\\", "/").rstrip("/")) or x,
                        "is_game": os.path.abspath(x) == os.path.abspath(state.game() or ""),
                        "descriptor_file": os.path.join(x, "descriptor.mod"),
                        "has_descriptor": os.path.exists(os.path.join(x, "descriptor.mod")),
                        "mod_name": _mod_descriptor(x)["name"],
                        "deps": _mod_descriptor(x)["deps"],
                        "replace_count": len(_mod_descriptor(x)["replace"])}
                       for x in layers],
            "sources": map_sources()}

def _hsv_hex(i, sat=0.52, val=0.88):
    """6 色循环 + 按 id 的轻微明度扰动：相邻省不撞色，整体也不花"""
    i = int(i)
    base = state.map_var("MAP_PALETTE")[i % len(state.map_var("MAP_PALETTE"))]
    d = ((i * 37) % 44) - 22
    return bytes(max(10, min(246, c + d)) for c in base)

def map_build(force=False, root=None):
    """生成地图图层（首次约 13 秒），返回 meta。可按 root 指定来源。"""
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "还没有加载任何 mod"}
    bmp, csv, base = _map_files_strict(root)
    if not bmp:
        return {"ok": False, "msg": "这个来源没有 map/provinces.bmp 或 definition.csv",
                "sources": map_sources(), "picked": root}
    dirp, key, base = _map_dir(root)
    if not dirp:
        return {"ok": False, "msg": "无法创建缓存目录"}
    os.makedirs(dirp, exist_ok=True)
    meta_path = os.path.join(dirp, "meta.json")
    try:
        os.makedirs(state.map_var("MAP_CACHE_DIR"), exist_ok=True)
        io.open(os.path.join(state.map_var("MAP_CACHE_DIR"), "_last.json"), "w", encoding="utf-8", newline="").write(
            json.dumps({"root": os.path.abspath(base or ""), "key": key,
                        "built": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False))
    except Exception:
        pass
    if not force and os.path.exists(meta_path):
        try:
            return {"ok": True, "cached": True,
                    "meta": json.loads(io.open(meta_path, encoding="utf-8").read())}
        except Exception:
            pass

    from PIL import Image, ImageDraw
    Image.MAX_IMAGE_PIXELS = None
    t_all = time.time()

    # 1) definition.csv：颜色 -> 省 id
    color2prov = {}
    prov2type = {}
    prov2terrain = {}
    prov2continent = {}
    with io.open(csv, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) < 5:
                continue
            try:
                pid = int(parts[0])
                rgb = (int(parts[1]), int(parts[2]), int(parts[3]))
            except Exception:
                continue
            color2prov[rgb] = pid
            prov2type[pid] = parts[4] or "land"
            if len(parts) > 6:
                prov2terrain[pid] = (parts[6] or "").strip()
            if len(parts) > 7:
                try:
                    prov2continent[pid] = int(parts[7])
                except Exception:
                    pass

    # 2) 读图
    im = Image.open(bmp).convert("RGB")
    w, h = im.size
    raw = im.tobytes()

    # 3) 省 -> 州
    prov2state = {}
    for sid, st in state.states().items():
        try:
            sid_int = int(st.get("id") or sid)
        except Exception:
            continue
        for p in (st.get("provinces") or []):
            try:
                prov2state[int(p)] = sid_int
            except Exception:
                pass

    # 3.5) 政治视图：省 -> owner -> 国家颜色
    prov2owner = {}
    for sid, st in state.states().items():
        ow = (st.get("owner") or "").strip()
        if not ow:
            continue
        for p in (st.get("provinces") or []):
            try:
                prov2owner[int(p)] = ow
            except Exception:
                pass
    tag_color = {}
    tag_color_real = {}
    for tag, c in state.countries().items():
        col = c.get("color") or []
        if len(col) >= 3:
            _c = bytes((max(0, min(255, int(col[0] * 255))),
                        max(0, min(255, int(col[1] * 255))),
                        max(0, min(255, int(col[2] * 255)))))
            tag_color[tag] = _c
            tag_color_real[tag] = _c
        else:
            tag_color[tag] = bytes((132, 132, 132))
    neutral = bytes((46, 50, 46))
    oceanc = bytes((26, 42, 74))          # 海色：比无主陆地明显的蓝
    ptypes = _prov_type_map(root)

    # 3.6) 战略区
    prov2region, region_list = _strategic_regions(root)

    # 3.7) 地形：用游戏自己的配色，再叠 terrain.bmp 的明暗做出纹理感
    _tcols = {}
    try:
        _tcols = _terrain_colors(root)
    except Exception as _e:
        print("读地形配色失败:", _e)
    # 旧的「terrain.bmp 灰度明暗」已弃用：现在统一用 heightmap 的真实山体阴影
    # （_apply_hillshade）。两套叠一起会把颜色压暗一倍。
    _shade = None

    # 4) 一遍像素：ids、质心累加
    n = w * h
    ids = [0] * n
    sumx = {}
    sumy = {}
    cnts = {}
    lookup = color2prov
    unset_px = 0          # 颜色在 definition.csv 里找不到的像素
    for i in range(n):
        o = i * 3
        pid = lookup.get((raw[o], raw[o + 1], raw[o + 2]))
        if pid is None:
            pid = 0
            unset_px += 1
        ids[i] = pid
        if pid:
            sumx[pid] = sumx.get(pid, 0) + (i % w)
            sumy[pid] = sumy.get(pid, 0) + (i // w)
            cnts[pid] = cnts.get(pid, 0) + 1

    # 4.5) 地图定义一致性（definition.csv ↔ provinces.bmp）
    try:
        state.map_var("PROV_RGB").clear()
        for _rgb, _pid in color2prov.items():
            state.map_var("PROV_RGB")[int(_pid)] = _rgb
    except Exception:
        pass
    csv_ids = set(color2prov.values())
    bmp_ids = set(cnts)
    ghost = sorted(csv_ids - bmp_ids)          # 定义了但地图上没有像素
    # 同色多个省（后写覆盖前写，前面的 id 永远不会出现）
    rgb_count = {}
    for _rgb, _pid in color2prov.items():
        rgb_count.setdefault(_rgb, []).append(_pid)
    dup_rgb = {k: v for k, v in rgb_count.items() if len(v) > 1}
    consistency = {
        "csv_ids": len(csv_ids),
        "bmp_ids": len(bmp_ids),
        "ghost": len(ghost),
        "ghost_sample": ghost[:20],
        "unset_pixels": unset_px,
        "unset_ratio": round(unset_px * 100.0 / max(1, n), 3),
        "dup_rgb": len(dup_rgb),
        "dup_rgb_sample": [{"rgb": list(k), "ids": v[:5]} for k, v in list(dup_rgb.items())[:10]],
    }

    # 5) 图层缓冲
    provbuf = bytearray(n * 3)
    statebuf = bytearray(n * 3)
    polbuf = bytearray(n * 3)
    regbuf = bytearray(n * 3)
    terrbuf = bytearray(n * 3)
    contbuf = bytearray(n * 3)
    edgebuf = bytearray(n * 3)
    idbuf = bytearray(n * 3)
    prov_color = {}
    state_color = {}
    reg_color = {}
    terr_color = {}
    cont_color = {}
    for i in range(n):
        pid = ids[i]
        c = prov_color.get(pid)
        if c is None:
            c = _hsv_hex(pid, 0.72, 0.96) if pid else bytes((24, 28, 26))
            prov_color[pid] = c
        sid = prov2state.get(pid, 0)
        sc = state_color.get(sid)
        if sc is None:
            sc = _hsv_hex(sid + 7, 0.62, 0.92) if sid else bytes((30, 34, 32))
            state_color[sid] = sc
        o = i * 3
        provbuf[o:o + 3] = c
        statebuf[o:o + 3] = sc
        ow = prov2owner.get(pid, "")
        if ow:
            pcb = tag_color.get(ow)
            if pcb is None:
                # 国家表里没有这个 tag（mod 改了国家但州还引用旧 tag），
                # 按 tag 生成稳定色，而不是画成无主灰
                pcb = _tag_fallback_color(ow)
                tag_color[ow] = pcb
        else:
            # 没有归属国的省分两种：海洋给海色，无主陆地给中性灰
            ptype = ptypes.get(pid, "")
            pcb = oceanc if ptype in ("sea", "ocean", "lake") else neutral
        polbuf[o:o + 3] = pcb
        # 地形：按 definition.csv 的 terrain 名字取稳定色
        tname = prov2terrain.get(pid, "")
        tc = terr_color.get(tname)
        if tc is None:
            _base = _tcols.get(tname)
            if _base:
                tc = bytes(_base)
            elif tname:
                tc = _hsv_hex(zlib.crc32(tname.encode("utf-8")) % 997, 0.35, 0.72)
            else:
                tc = bytes((26, 30, 28))
            terr_color[tname] = tc
        if _shade is not None:
            # 明暗系数 0.72~1.18，让同一种地形也有起伏感
            _f = 0.72 + (_shade[i] / 255.0) * 0.46
            terrbuf[o] = min(255, int(tc[0] * _f))
            terrbuf[o + 1] = min(255, int(tc[1] * _f))
            terrbuf[o + 2] = min(255, int(tc[2] * _f))
        else:
            terrbuf[o:o + 3] = tc
        # 大洲
        con = prov2continent.get(pid, 0)
        cc2 = cont_color.get(con)
        if cc2 is None:
            cc2 = _hsv_hex(con * 7 + 11, 0.40, 0.78) if con else bytes((30, 34, 32))
            cont_color[con] = cc2
        contbuf[o:o + 3] = cc2
        rid = prov2region.get(pid, 0)
        rc = reg_color.get(rid)
        if rc is None:
            rc = _hsv_hex(rid + 3, 0.38, 0.72) if rid else bytes((28, 32, 30))
            reg_color[rid] = rc
        regbuf[o:o + 3] = rc
        idbuf[o] = (pid >> 16) & 0xFF
        idbuf[o + 1] = (pid >> 8) & 0xFF
        idbuf[o + 2] = pid & 0xFF

    # 6) 省界（4 邻域不同即标白）
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            pid = ids[i]
            edge = False
            if x + 1 < w and ids[i + 1] != pid:
                edge = True
            elif y + 1 < h and ids[i + w] != pid:
                edge = True
            elif x > 0 and ids[i - 1] != pid:
                edge = True
            elif y > 0 and ids[i - w] != pid:
                edge = True
            if edge:
                o = i * 3
                # 淡灰而不是纯白：放大后边界线仍然可见但不会压过色块
                edgebuf[o] = 205
                edgebuf[o + 1] = 209
                edgebuf[o + 2] = 203

    # 6.5) 国家边界：相邻省属于不同 owner 的地方压深一档
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            pid = ids[i]
            ow = prov2owner.get(pid, "")
            border = False
            if x + 1 < w:
                ow2 = prov2owner.get(ids[i + 1], "")
                if ow2 != ow:
                    border = True
            elif y + 1 < h:
                ow3 = prov2owner.get(ids[i + w], "")
                if ow3 != ow:
                    border = True
            if border:
                o = i * 3
                polbuf[o] = min(255, int(polbuf[o] * 0.45))
                polbuf[o + 1] = min(255, int(polbuf[o + 1] * 0.45))
                polbuf[o + 2] = min(255, int(polbuf[o + 2] * 0.45))

    # 7) 写资产
    Image.frombytes("RGB", (w, h), bytes(provbuf)).save(os.path.join(dirp, "province.png"))
    Image.frombytes("RGB", (w, h), bytes(statebuf)).save(os.path.join(dirp, "state.png"))
    # 省界存成 RGBA：白线不透明、其余全透明。
    # 之前存 RGB（黑底白线），前端按 opacity 叠上去时黑色背景会把地形压暗一大截。
    _edge_img = Image.frombytes("RGB", (w, h), bytes(edgebuf)).convert("RGBA")
    _edge_img.putalpha(_edge_img.convert("L"))
    _edge_img.save(os.path.join(dirp, "edges.png"))
    Image.frombytes("RGB", (w, h), bytes(polbuf)).save(os.path.join(dirp, "political.png"))
    # 严格版：国家表里查不到的 tag 不参与着色，落到无主色（还原游戏里的真实政治图）
    try:
        stbuf = bytearray(polbuf)
        for i in range(n):
            pid = ids[i]
            ow = prov2owner.get(pid, "")
            if not ow or ow in tag_color_real:
                continue
            o = i * 3
            ptype = ptypes.get(pid, "")
            stbuf[o:o + 3] = oceanc if ptype in ("sea", "ocean", "lake") else neutral
        Image.frombytes("RGB", (w, h), bytes(stbuf)).save(
            os.path.join(dirp, "political_strict.png"))
    except Exception as _e:
        print("  严格版政治图跳过:", _e)
    # 开局部队图层：每省按部队数画一个标记（透明底，叠在任意图层上）
    try:
        _u = load_units(root)
        _by = _u.get("by_prov") or {}
        _img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        _dr = ImageDraw.Draw(_img)
        _cent = {}
        try:
            _cj = io.open(os.path.join(dirp, "centers.json"), encoding="utf-8").read()
            _cent = json.loads(_cj) or {}
        except Exception:
            _cent = {}
        for _pid_s, _lst in _by.items():
            _c = _cent.get(str(_pid_s))
            if not _c:
                continue
            try:
                _cx, _cy = int(_c[0]), int(_c[1])
            except Exception:
                continue
            _n = len(_lst)
            # 半径随数量增长，封顶
            _r = 6 if _n < 5 else (9 if _n < 20 else (12 if _n < 50 else 15))
            _dr.ellipse([_cx - _r, _cy - _r, _cx + _r, _cy + _r],
                        fill=(220, 60, 60, 200), outline=(255, 255, 255, 230), width=2)
            _txt = str(_n) if _n < 100 else "99+"
            try:
                _dr.text((_cx, _cy), _txt, fill=(255, 255, 255, 255), anchor="mm")
            except Exception:
                pass
        _img.save(os.path.join(dirp, "units.png"))
        print("  部队图层: %d 个有部队的省" % len(_by))
    except Exception as _e:
        print("  部队图层生成失败: %s" % _e)
    except Exception as _e:
        print("  严格版政治图跳过:", _e)
    Image.frombytes("RGB", (w, h), bytes(regbuf)).save(os.path.join(dirp, "region.png"))
    _terr_img = _render_terrain(root, w, h, prov2terrain)
    if _terr_img is None:
        # 省级地形色（来自 definition.csv，永远可信）+ 高度阴影
        _terr_img = Image.frombytes("RGB", (w, h), bytes(terrbuf))
        try:
            _terr_img = _apply_hillshade(_terr_img, root, w, h, None)
        except Exception as _e:
            print("  高度阴影失败，保留纯色:", _e)
    _terr_img.save(os.path.join(dirp, "terrain.png"))
    Image.frombytes("RGB", (w, h), bytes(contbuf)).save(os.path.join(dirp, "continent.png"))
    try:
        _build_rivers_png(root, w, h, dirp)
    except Exception as _e:
        print("  河流图层跳过:", _e)
    Image.frombytes("RGB", (w, h), bytes(idbuf)).save(os.path.join(dirp, "prov_id.png"))
    # 底图用全分辨率：缩进一半的话放大后是糊的（游戏地图本来就只有这个尺寸，没得再高）
    im.save(os.path.join(dirp, "base.png"))

    centers = {}
    counts = cnts
    for pid, cnt in counts.items():
        centers[str(pid)] = [round(sumx[pid] / cnt, 1), round(sumy[pid] / cnt, 1)]

    index = {}
    for pid, cnt in counts.items():
        _rgb = None
        try:
            _rgb = list(color2prov and next((k for k, v in color2prov.items() if v == pid), None) or ()) or None
        except Exception:
            _rgb = None
        index[str(pid)] = {"state": prov2state.get(pid, 0), "type": prov2type.get(pid, ""),
                           "region": prov2region.get(pid, 0), "terrain": prov2terrain.get(pid, ""),
                           "continent": prov2continent.get(pid, 0), "px": cnt,
                           "rgb": _rgb}

    io.open(os.path.join(dirp, "centers.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(centers, ensure_ascii=False))
    io.open(os.path.join(dirp, "prov_index.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(index, ensure_ascii=False))
    io.open(os.path.join(dirp, "regions.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(region_list, ensure_ascii=False))

    meta = {"w": w, "h": h, "provinces": len(counts), "source": base,
            "ms": int((time.time() - t_all) * 1000), "built": time.strftime("%Y-%m-%d %H:%M:%S"),
            "consistency": consistency,
            "assets": {a: os.path.getsize(os.path.join(dirp, a)) for a in state.map_var("MAP_ASSETS")
                       if os.path.exists(os.path.join(dirp, a))}}
    io.open(meta_path, "w", encoding="utf-8", newline="").write(json.dumps(meta, ensure_ascii=False))
    return {"ok": True, "cached": False, "meta": meta}

def map_cache_clear():
    """清空所有地图图层缓存（源文件不动，下次打开自动重建）"""
    total = 0
    n = 0
    if os.path.isdir(state.map_var("MAP_CACHE_DIR")):
        for name in sorted(os.listdir(state.map_var("MAP_CACHE_DIR"))):
            p = os.path.join(state.map_var("MAP_CACHE_DIR"), name)
            if not os.path.isdir(p):
                continue
            size = 0
            for dp, _, fs in os.walk(p):
                for f in fs:
                    try:
                        size += os.path.getsize(os.path.join(dp, f))
                    except Exception:
                        pass
            shutil.rmtree(p, ignore_errors=True)
            total += size
            n += 1
    return {"ok": True, "dirs": n, "bytes": total,
            "msg": "已清理 %d 个来源的缓存，释放 %.1f MB" % (n, total / 1e6)}

def _strategic_regions(root):
    """读 map/strategicregions/*.txt，返回 {province: region_id} 与 region 列表。
    带 mtime 缓存：合并预览/涂色都要用，不缓存每次白花 1.5 秒。"""
    try:
        _sig = None
        for _b in (root, state.game()):
            _d = os.path.join(_b or "", "map", "strategicregions")
            if os.path.isdir(_d):
                _mt = 0
                try:
                    for _fn in os.listdir(_d):
                        _mt = max(_mt, int(os.path.getmtime(os.path.join(_d, _fn))))
                except Exception:
                    pass
                _sig = (os.path.abspath(_b or ""), _mt)
                break
        _hit = state.map_var("_REGION_CACHE").get(_sig)
        if _hit:
            return dict(_hit[0]), list(_hit[1])
    except Exception:
        _sig = None
    _orig_note = None
    prov2region = {}
    regions = []
    for base in (root, state.game()):
        d = os.path.join(base or "", "map", "strategicregions")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'strategic_region\s*=\s*\{', text):
                b = text.find('{', m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                rid = _first(body, r'(?m)^[ \t]*id\s*=\s*(\d+)')
                if not rid:
                    continue
                rid = int(rid)
                nm = _first(body, r'(?m)^[ \t]*name\s*=\s*"?([^"\r\n]+)"?') or ("地区 %d" % rid)
                pm = re.search(r'(?m)^[ \t]*provinces\s*=\s*\{', body)
                pids = []
                if pm:
                    pb = body.find('{', pm.end() - 1)
                    pe = brace_match(body, pb)
                    if pe > pb:
                        pids = [int(x) for x in re.findall(r'\d+', body[pb + 1:pe - 1])]
                for p in pids:
                    prov2region[p] = rid
                regions.append({"id": rid, "name": nm, "count": len(pids)})
        if regions:
            break
    try:
        if _sig:
            state.map_var("_REGION_CACHE")[_sig] = (dict(prov2region), list(regions))
    except Exception:
        pass
    return prov2region, regions

def _terrain_index_map(root):
    """解析 common/terrain/*.txt：地形索引 → 类别名"""
    idx2type = {}
    for base in reversed(mod_layers(root)):
        d = os.path.join(base or "", "common", "terrain")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8-sig",
                                              errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'(?m)^\s*([A-Za-z_][\w]*)\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                typ = re.search(r'type\s*=\s*(\w+)', body)
                col = re.search(r'color\s*=\s*\{\s*(\d+)\s*\}', body)
                if typ and col:
                    idx2type[int(col.group(1))] = typ.group(1)
    return idx2type

def _hillshade_mask(root, w, h):
    """高度图 → 明暗 mask（L 模式，255=全亮）。没有高度图或尺寸不符返回 None。"""
    try:
        from PIL import Image, ImageChops
        Image.MAX_IMAGE_PIXELS = None
        hbmp, _ = _layers_find("map/heightmap.bmp", mod_layers(root))
        if not hbmp:
            return None
        with Image.open(hbmp) as him:
            if him.size != (w, h):
                return None
            hh = him.convert("L")
        gx = ImageChops.subtract(ImageChops.offset(hh, 1, 0),
                                 ImageChops.offset(hh, -1, 0), 1.0, 128)
        gy = ImageChops.subtract(ImageChops.offset(hh, 0, 1),
                                 ImageChops.offset(hh, 0, -1), 1.0, 128)

        def lit(v):
            # 西北光：东侧高、南侧高的地形变暗。系数小一点，避免山地整片压黑
            return max(0, min(255, int(128 - (v - 128) * 0.70)))
        shade = ImageChops.add(gx.point(lit), gy.point(lit), 1.0, -128)
        # 下限 108：最暗处也保留约 42% 亮度，当作环境光，不让背光坡变成黑块
        return shade.point(lambda v: max(108, min(255, int(v * 1.28))))
    except Exception:
        return None

def _apply_hillshade(img, root, w, h, ocean_mask=None):
    """给地形色图叠高度阴影。ocean_mask 为 L 模式，255 = 海洋（用弱阴影）。

    用乘法光照而不是 composite（后者会把背光面压到接近黑）：
      先把底色提亮 1.35 倍，再乘一个 0.72~1.27 的系数，
      最终亮度 = 底色 × (0.97 ~ 1.71)，中间值约 1.32 倍，暗部仍有 0.97 倍。"""
    from PIL import Image, ImageChops
    Image.MAX_IMAGE_PIXELS = None
    shade = _hillshade_mask(root, w, h)
    if shade is None:
        return img
    bright = img.point(lambda v: min(255, int(v * 1.35)))
    # m/255 = (0.72 + 0.55*s) / 1.35
    factor = shade.point(lambda v: max(1, min(255, int(189 * (0.72 + 0.55 * (v / 255.0))))))
    out = ImageChops.multiply(bright, factor.convert("RGB"))
    if ocean_mask is not None:
        # 海洋/湖泊只用很弱的起伏
        soft = ImageChops.multiply(img.point(lambda v: min(255, int(v * 1.06))),
                                   shade.point(lambda v: max(150, min(255, int(v * 1.6)))).convert("RGB"))
        out = Image.composite(soft, out, ocean_mask)
    return out

def _terrain_tex_map(root):
    """terrain.txt 的 terrain_N -> {color索引: (type, texture编号)}"""
    idx2type, idx2tex = {}, {}
    for base in reversed(mod_layers(root)):
        d = os.path.join(base or "", "common", "terrain")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8-sig",
                                              errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'(?m)^\s*([A-Za-z_][\w]*)\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                typ = re.search(r'type\s*=\s*(\w+)', body)
                col = re.search(r'color\s*=\s*\{\s*(\d+)\s*\}', body)
                tex = re.search(r'texture\s*=\s*(\d+)', body)
                if typ and col and tex:
                    k = int(col.group(1))
                    idx2type[k] = typ.group(1)
                    idx2tex[k] = int(tex.group(1))
    return idx2type, idx2tex

def _apply_terrain_texture(img, root, w, h, tmap, ids):
    """用 map/terrain/atlas0.dds 的贴图亮度调制地形色明暗。

    只调亮度不混色：贴图本身是灰色调细节层，直接 alpha 混合会把地形色洗掉。
    海洋/湖泊跳过——atlas 里没有水面贴图（借用 desert 的），会把海面弄成斑块。
    纹理起点按省号哈希偏移，相邻省的花纹不会对齐。"""
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        atlas_path, _ = _layers_find("map/terrain/atlas0.dds", mod_layers(root))
        if not atlas_path:
            _g = os.path.join(state.game() or "", "map", "terrain", "atlas0.dds")
            atlas_path = _g if os.path.exists(_g) else None
        if not atlas_path or not tmap:
            return img
        with Image.open(atlas_path) as aim:
            atlas = aim.convert("RGBA")
        TILE = atlas.width // 8
        if TILE <= 0:
            return img
        idx2type, idx2tex = _terrain_tex_map(root)
        if not idx2tex:
            return img
        apx = atlas.load()
        traw = tmap.tobytes()
        src = img.tobytes()
        out = bytearray(src)
        cache = {}
        water = ("ocean", "lakes")
        n = w * h
        for i in range(n):
            ti = traw[i]
            typ = idx2type.get(ti)
            m = idx2tex.get(ti)
            if m is None or m > 63 or typ in water:
                continue
            pid = ids[i] if ids else 0
            ax = (i % w + (pid * 37)) % TILE
            ay = (i // w + (pid * 71)) % TILE
            key = (m, ax, ay)
            tc = cache.get(key)
            if tc is None:
                tc = apx[(m % 8) * TILE + ax, (m // 8) * TILE + ay]
                if len(cache) < 300000:
                    cache[key] = tc
            luma = tc[0] * 0.30 + tc[1] * 0.59 + tc[2] * 0.11
            f = 0.74 + (luma / 255.0) * 0.56
            a = tc[3] / 255.0
            f = 1.0 + (f - 1.0) * (0.50 + a * 0.50)
            o = i * 3
            r = src[o] * f
            g = src[o + 1] * f
            b = src[o + 2] * f
            out[o] = 255 if r > 255 else int(r)
            out[o + 1] = 255 if g > 255 else int(g)
            out[o + 2] = 255 if b > 255 else int(b)
        return Image.frombytes("RGB", (w, h), bytes(out))
    except Exception as e:
        print("地形贴图失败，保留纯色:", e)
        return img

def _terrain_index_trusted(root, layers):
    """terrain.bmp 是否与 provinces.bmp 同源。
    不同源说明 mod 换了地图却没换地形索引图，用它着色会得到与地图无关的分布。"""
    try:
        _t, tbase = _layers_find("map/terrain.bmp", layers)
        _p, pbase = _layers_find("map/provinces.bmp", layers)
        if not _t or not _p:
            return False
        return os.path.abspath(tbase or "") == os.path.abspath(pbase or "")
    except Exception:
        return False

def _render_terrain(root, w, h, prov2terrain):
    """像素级地形图（terrain.bmp 可信时用）。返回 RGB Image，不可信或失败返回 None。"""
    try:
        from PIL import Image, ImageChops
        Image.MAX_IMAGE_PIXELS = None
        layers = mod_layers(root)
        if not _terrain_index_trusted(root, layers):
            print("  terrain.bmp 与 provinces.bmp 不同源，改用省级地形着色")
            return None
        tbmp, _ = _layers_find("map/terrain.bmp", layers)
        if not tbmp:
            return None
        cats = _terrain_colors(root)
        idx2type = _terrain_index_map(root)
        if not idx2type:
            return None
        with Image.open(tbmp) as tim:
            if tim.size != (w, h):
                return None
            tmap = tim.convert("P") if tim.mode != "P" else tim.copy()
        pal = [0] * (256 * 3)
        default = (60, 70, 60)
        for i in range(256):
            typ = idx2type.get(i)
            col = cats.get(typ, default) if typ else default
            pal[i * 3] = col[0]
            pal[i * 3 + 1] = col[1]
            pal[i * 3 + 2] = col[2]
        tmap.putpalette(pal)
        base_rgb = tmap.convert("RGB")

        ocean_mask = tmap.convert("L").point(
            lambda v: 255 if idx2type.get(v) in ("ocean", "lakes") else 0)
        base_rgb = _apply_terrain_texture(base_rgb, root, w, h, tmap, None)
        return _apply_hillshade(base_rgb, root, w, h, ocean_mask)
    except Exception as e:
        print("地形渲染失败，回退纯色:", e)
        return None

def _map_ids_from_cache(dirp):


    """从缓存的 prov_id.png 还原 ids 数组（省 id 按 RGB 编码）"""
    from array import array
    from PIL import Image
    p = os.path.join(dirp, "prov_id.png")
    if not os.path.exists(p):
        return None, 0, 0, None
    im = Image.open(p).convert("RGB")
    w, h = im.size
    raw = im.tobytes()
    n = w * h
    ids = array("I", bytes(4 * n))
    a = ids
    for i in range(n):
        o = i * 3
        a[i] = (raw[o] << 16) | (raw[o + 1] << 8) | raw[o + 2]
    return ids, w, h, raw

def _prov_state_map():
    """省 → 州 的映射。

    同一省被多个州声明时（原版和 mod 都有这个省，mod 的州覆盖原版的州），
    按 state.roots() 的加载顺序取优先级最高的那一层 —— 后面的 mod 覆盖前面的。
    只有在同一层内部冲突时才记为真实数据问题。"""
    layers = {}
    for i, r in enumerate(state.roots() or []):
        layers[os.path.abspath(r)] = i
    best = {}      # pid -> (priority, sid)
    dups = {}
    for _s in (state.states().values() if isinstance(state.states(), dict) else []):
        try:
            sid = int(_s.get("id") or 0)
        except Exception:
            continue
        pri = layers.get(os.path.abspath(_s.get("root") or ""), 0)
        for _p in (_s.get("provinces") or []):
            try:
                pid = int(_p)
            except Exception:
                continue
            cur = best.get(pid)
            if cur is None or pri > cur[0]:
                best[pid] = (pri, sid)
            elif pri == cur[0] and cur[1] != sid:
                # 同一层里两个州都声明了这个省 —— 这才是真冲突
                dups.setdefault(pid, [cur[1]]).append(sid)
    return {k: v[1] for k, v in best.items()}, dups

def bmp_write_rect_8(path, x0, y0, w, h, values):
    """8 位索引图（terrain.bmp 这类）的矩形写入，每像素 1 字节。

    bmp_write_rect 只处理 24 位；索引图必须单独写，否则会把 P 模式 bmp 改成 RGB，
    HOI4 就读不出来了。"""
    info = bmp_info(path)
    if not info or info.get("bpp") != 8:
        return False
    bpp_bytes = info.get("bytes_pp") or 1
    if bpp_bytes != 1:
        return False
    row_bytes = info["row"]
    W, H = info["w"], info["h"]
    if x0 < 0 or y0 < 0 or x0 + w > W or y0 + h > H:
        return False
    with open(path, "r+b") as f:
        for r in range(h):
            y = y0 + r
            fy = y if info.get("top_down") else (H - 1 - y)
            off = info["offset"] + fy * row_bytes + x0
            f.seek(off)
            f.write(bytes(values[r * w:(r + 1) * w]))
    return True

def _terrain_type_to_index(root):
    """类型名 → terrain.bmp 里的索引（同一类型有多个索引时取第一个）"""
    idx2type, _tex = _terrain_tex_map(root)
    out = {}
    for i in sorted(idx2type):
        t = idx2type[i]
        if t not in out:
            out[t] = i
    return out, idx2type

def terrain_types(root=None):
    """列出可用的地形类型（按 definition.csv 里实际出现的 + terrain.txt 定义的）"""
    root = _map_pick(root)
    t2i, idx2type = _terrain_type_to_index(root)
    # 统计每个类型有多少省
    cnt = {}
    csvp, _ = _layers_find("map/definition.csv", mod_layers(root))
    if csvp:
        try:
            with io.open(csvp, encoding="utf-8", errors="replace") as f:
                for line in f:
                    p = line.strip().split(";")
                    if len(p) >= 8 and p[0].isdigit():
                        cnt[p[6]] = cnt.get(p[6], 0) + 1
        except Exception:
            pass
    items = []
    for t in sorted(set(list(t2i.keys()) + list(cnt.keys()))):
        items.append({"type": t, "index": t2i.get(t), "count": cnt.get(t, 0),
                      "writable": t2i.get(t) is not None})
    return {"ok": True, "items": items, "count": len(items),
            "msg": "共 %d 种地形类型" % len(items)}

def prov_terrain_set(pid, terrain, root=None):
    """把某个省的地形改成指定类型。

    同时做两件事：
      1. definition.csv 第 7 列（地形名）
      2. terrain.bmp 里该省所有像素的索引改成该类型对应的索引
    只改 definition.csv 不改 bmp 的话，游戏读的是 bmp，改了等于没改。
    """
    pid = int(pid or 0)
    terrain = (terrain or "").strip()
    if pid <= 0 or not terrain:
        return {"ok": False, "msg": "参数不完整"}
    root = _map_pick(root)
    layers = mod_layers(root)
    csvp, csvbase = _layers_find("map/definition.csv", layers)
    tbmp, tbase = _layers_find("map/terrain.bmp", layers)
    if not csvp:
        return {"ok": False, "msg": "找不到 definition.csv"}
    if not tbmp:
        return {"ok": False, "msg": "找不到 terrain.bmp"}
    # terrain.bmp 与 provinces.bmp 必须同源，否则改 bmp 没有意义（会画出错误的地形）
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    if os.path.abspath(tbase or "") != os.path.abspath(pbase or ""):
        return {"ok": False,
                "msg": "terrain.bmp 与 provinces.bmp 不同源（mod 换了地图没换地形图），改地形会错位"}

    t2i, idx2type = _terrain_type_to_index(root)
    if terrain not in t2i:
        return {"ok": False, "msg": "terrain.txt 里没有类型 %s（可选：%s）" % (
            terrain, "、".join(sorted(t2i.keys())[:8]))}
    new_idx = t2i[terrain]

    # 1) 改 definition.csv
    raw = io.open(csvp, encoding="utf-8", errors="replace").read()
    lines = raw.splitlines(True)
    old_type = None
    hit = False
    for i, ln in enumerate(lines):
        p = ln.rstrip("\r\n").split(";")
        if len(p) >= 8 and p[0].isdigit() and int(p[0]) == pid:
            old_type = p[6]
            if old_type == terrain:
                return {"ok": True, "changed": False,
                        "msg": "省 %d 已经是 %s，无需改动" % (pid, terrain)}
            p[6] = terrain
            tail = chr(10) if ln.endswith(chr(10)) else ""
            lines[i] = ";".join(p) + tail
            hit = True
            break
    if not hit:
        return {"ok": False, "msg": "definition.csv 里没有省 %d" % pid}

    # 2) 改 terrain.bmp 里该省的像素
    ids, w, h = _refine_load_ids(root)
    if not ids:
        return {"ok": False, "msg": "读不到省号数组"}
    px = [i for i in range(len(ids)) if ids[i] == pid]
    if not px:
        return {"ok": False, "msg": "省 %d 在地图上没有像素" % pid}
    xs = [p % w for p in px]
    ys = [p // w for p in px]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx + 1, max(ys) - by + 1
    # 读原索引（用 Pillow 读整块更稳）
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(tbmp) as im:
        if im.size != (w, h):
            return {"ok": False, "msg": "terrain.bmp 尺寸与地图不符"}
        crop = im.crop((bx, by, bx + bw, by + bh))
        buf = list(crop.tobytes())
    for p in px:
        o = (p // w - by) * bw + (p % w - bx)
        if 0 <= o < len(buf):
            buf[o] = new_idx

    snapshot(csvp)
    snapshot(tbmp)
    _atomic_write(csvp, b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
    if not bmp_write_rect_8(tbmp, bx, by, bw, bh, buf):
        return {"ok": False, "msg": "terrain.bmp 写入失败（不是 8 位索引图）"}

    # 地形变了，缓存与图层都要失效
    try:
        state.map_var("_REFINE_IDS_CACHE").pop("cur", None)
    except Exception:
        pass
    return {"ok": True, "changed": True, "pid": pid,
            "from": old_type, "to": terrain, "index": new_idx,
            "pixels": len(px), "rect": [bx, by, bw, bh],
            "msg": "省 %d 地形 %s → %s（%d 像素，索引 %d），需重建图层" % (
                pid, old_type, terrain, len(px), new_idx)}

def _terrain_common(root, terrain):
    """批量改地形的公共准备：找文件、查索引、验同源。
    返回 (csvp, tbmp, new_idx, ids, w, h, err)"""
    root = _map_pick(root)
    layers = mod_layers(root)
    csvp, csvbase = _layers_find("map/definition.csv", layers)
    tbmp, tbase = _layers_find("map/terrain.bmp", layers)
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    if not csvp:
        return None, None, None, None, 0, 0, "找不到 definition.csv"
    if not tbmp:
        return None, None, None, None, 0, 0, "找不到 terrain.bmp"
    if os.path.abspath(tbase or "") != os.path.abspath(pbase or ""):
        return None, None, None, None, 0, 0, "terrain.bmp 与 provinces.bmp 不同源，改地形会错位"
    t2i, _idx2type = _terrain_type_to_index(root)
    if terrain not in t2i:
        return None, None, None, None, 0, 0, "terrain.txt 里没有类型 %s" % terrain
    ids, w, h = _refine_load_ids(root)
    if not ids:
        return None, None, None, None, 0, 0, "读不到省号数组"
    return csvp, tbmp, t2i[terrain], ids, w, h, None

def _terrain_apply(csvp, tbmp, ids, w, h, pid_set, new_idx, renumber_from=None):
    """把 pid_set 里所有省在 terrain.bmp 里改成 new_idx，同时改 definition.csv。
    一次读全图、一次写全图 —— 批量改几百个省也不会变成几百次磁盘 IO。
    返回 (改动省数, 像素数, 旧类型统计)"""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    raw = io.open(csvp, encoding="utf-8", errors="replace").read()
    lines = raw.splitlines(True)
    old_types = {}
    changed_pids = set()
    for i, ln in enumerate(lines):
        p = ln.rstrip("\r\n").split(";")
        if len(p) >= 8 and p[0].isdigit():
            pid = int(p[0])
            if pid in pid_set:
                old_types[p[6]] = old_types.get(p[6], 0) + 1
                if p[6] != renumber_from:
                    p[6] = renumber_from if renumber_from else p[6]
                changed_pids.add(pid)
    # 上面只是统计；真正写入在下面统一做
    if not changed_pids:
        return 0, 0, {}

    idset = changed_pids
    pxmap = [p for p in range(len(ids)) if ids[p] in idset]
    if not pxmap:
        return 0, 0, old_types

    xs = [p % w for p in pxmap]
    ys = [p // w for p in pxmap]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx + 1, max(ys) - by + 1

    with Image.open(tbmp) as im:
        if im.size != (w, h):
            return 0, 0, old_types
        crop = im.crop((bx, by, bx + bw, by + bh))
        buf = list(crop.tobytes())
    for p in pxmap:
        o = (p // w - by) * bw + (p % w - bx)
        if 0 <= o < len(buf):
            buf[o] = new_idx

    snapshot(csvp)
    snapshot(tbmp)
    _atomic_write(csvp, b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
    if not bmp_write_rect_8(tbmp, bx, by, bw, bh, buf):
        return 0, 0, old_types
    try:
        state.map_var("_REFINE_IDS_CACHE").pop("cur", None)
    except Exception:
        pass
    return len(changed_pids), len(pxmap), old_types

def prov_terrain_batch(pids, terrain, root=None):
    """批量改多个省的地形（一次读写）"""
    terrain = (terrain or "").strip()
    if not pids or not terrain:
        return {"ok": False, "msg": "参数不完整"}
    try:
        want = set(int(x) for x in pids if int(x) > 0)
    except Exception:
        return {"ok": False, "msg": "省号列表不合法"}
    if not want:
        return {"ok": False, "msg": "没有有效的省号"}

    csvp, tbmp, new_idx, ids, w, h, err = _terrain_common(root, terrain)
    if err:
        return {"ok": False, "msg": err}

    # 找出真正要改的（已经是指定类型的跳过）
    raw = io.open(csvp, encoding="utf-8", errors="replace").read()
    lines = raw.splitlines(True)
    todo = set()
    old_types = {}
    for ln in lines:
        p = ln.rstrip("\r\n").split(";")
        if len(p) >= 8 and p[0].isdigit() and int(p[0]) in want:
            if p[6] != terrain:
                todo.add(int(p[0]))
                old_types[p[6]] = old_types.get(p[6], 0) + 1
    if not todo:
        return {"ok": True, "changed": 0, "msg": "这 %d 个省已经是 %s" % (len(want), terrain)}

    n_pid, n_px, _ = _terrain_apply(csvp, tbmp, ids, w, h, todo, new_idx, terrain)
    return {"ok": True, "changed": n_pid, "pixels": n_px, "to": terrain,
            "from": old_types, "skipped": len(want) - n_pid,
            "msg": "%d 个省改成 %s（%d 像素），%d 个已是该类型跳过 · 需重建图层" % (
                n_pid, terrain, n_px, len(want) - n_pid)}

def prov_terrain_by_type(from_type, to_type, root=None):
    """把某一地形的所有省改成另一种（先从 csv 查，再批量改）"""
    from_type = (from_type or "").strip()
    to_type = (to_type or "").strip()
    if not from_type or not to_type or from_type == to_type:
        return {"ok": False, "msg": "参数不合法（源类型与目标类型不能相同）"}
    root = _map_pick(root)
    layers = mod_layers(root)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not csvp:
        return {"ok": False, "msg": "找不到 definition.csv"}
    pids = []
    for ln in io.open(csvp, encoding="utf-8", errors="replace"):
        p = ln.rstrip("\r\n").split(";")
        if len(p) >= 8 and p[0].isdigit() and p[6] == from_type:
            pids.append(int(p[0]))
    if not pids:
        return {"ok": False, "msg": "没有地形为 %s 的省" % from_type}
    r = prov_terrain_batch(pids, to_type, root)
    if r.get("ok"):
        r["msg"] = "把 %d 个 %s 改成了 %s · 需重建图层" % (
            r.get("changed", 0), from_type, to_type)
    return r

def height_paint(points, height, brush=8, feather=True, root=None):
    """画笔式刷高程：直接改 heightmap.bmp 的灰度。

    HOI4 的 heightmap.bmp 是 8 位灰度，0 = 海平面，值越大越高。
    points: [[x, y], ...]（地图坐标）
    height: 0-255
    brush:  笔刷半径（像素）
    feather: 边缘渐变，避免硬边
    """
    try:
        brush = max(1, min(60, int(brush or 1)))
    except Exception:
        brush = 1
    try:
        hv = int(height)
    except Exception:
        return {"ok": False, "msg": "高度必须是 0-255 的整数"}
    if hv < 0 or hv > 255:
        return {"ok": False, "msg": "高度必须是 0-255 的整数"}
    if not points:
        return {"ok": False, "msg": "没有落点"}
    root = _map_pick(root)
    layers = mod_layers(root)
    hbmp, hbase = _layers_find("map/heightmap.bmp", layers)
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    if not hbmp:
        return {"ok": False, "msg": "找不到 heightmap.bmp"}
    if os.path.abspath(hbase or "") != os.path.abspath(pbase or ""):
        return {"ok": False, "msg": "heightmap.bmp 与 provinces.bmp 不同源，刷高程会错位"}

    info = bmp_info(hbmp)
    if not info or info.get("bpp") != 8:
        return {"ok": False, "msg": "heightmap.bmp 不是 8 位图，无法按像素刷"}
    W, H = info["w"], info["h"]
    off0, rowb = info["offset"], info["row"]
    top_down = bool(info.get("top_down"))

    # 收集要刷的像素 + 目标值（羽化时按距离插值）
    hit = {}
    for pt in points:
        try:
            cx, cy = int(pt[0]), int(pt[1])
        except Exception:
            continue
        for dy in range(-brush, brush + 1):
            for dx in range(-brush, brush + 1):
                d2 = dx * dx + dy * dy
                if d2 > brush * brush:
                    continue
                x, y = cx + dx, cy + dy
                if not (0 <= x < W and 0 <= y < H):
                    continue
                if feather:
                    t = 1.0 - (d2 ** 0.5) / float(brush)   # 中心 1 → 边缘 0
                    t = max(0.0, min(1.0, t))
                    v = int(round(255 * t + hv * (1 - t))) if False else hv
                    # 羽化：新值和旧值按 t 混合，t 在中心接近 1
                    hit[(x, y)] = (hv, t)
                else:
                    hit[(x, y)] = (hv, 1.0)
    if not hit:
        return {"ok": False, "msg": "笔刷没落在图内"}

    snapshot(hbmp)
    n = 0
    with open(hbmp, "r+b") as f:
        for (x, y), (target, t) in hit.items():
            fy = y if top_down else (H - 1 - y)
            f.seek(off0 + fy * rowb + x)
            cur = f.read(1)
            old = cur[0] if cur else 0
            if feather and t < 1.0:
                new = int(round(old * (1 - t) + target * t))
            else:
                new = target
            new = max(0, min(255, new))
            f.seek(off0 + fy * rowb + x)
            f.write(bytes((new,)))
            n += 1
    try:
        state.map_var("_REFINE_IDS_CACHE").pop("cur", None)
    except Exception:
        pass
    return {"ok": True, "painted": n, "to": hv,
            "msg": "刷了 %d 个像素，高度 %d%s" % (n, hv, "（羽化）" if feather else "")}

def height_sample(points, radius=1, root=None):
    """读某几个点附近的高程，返回平均值（用来画等高线或显示）。"""
    if not points:
        return {"ok": True, "values": []}
    root = _map_pick(root)
    hbmp, _ = _layers_find("map/heightmap.bmp", mod_layers(root))
    if not hbmp:
        return {"ok": False, "msg": "找不到 heightmap.bmp", "values": []}
    info = bmp_info(hbmp)
    if not info or info.get("bpp") != 8:
        return {"ok": False, "msg": "heightmap.bmp 不是 8 位图", "values": []}
    W, H = info["w"], info["h"]
    off0, rowb = info["offset"], info["row"]
    top_down = bool(info.get("top_down"))
    r = max(0, min(8, int(radius or 0)))
    out = []
    with open(hbmp, "rb") as f:
        for pt in points:
            try:
                cx, cy = int(pt[0]), int(pt[1])
            except Exception:
                out.append(None)
                continue
            vals = []
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    x, y = cx + dx, cy + dy
                    if not (0 <= x < W and 0 <= y < H):
                        continue
                    fy = y if top_down else (H - 1 - y)
                    f.seek(off0 + fy * rowb + x)
                    b = f.read(1)
                    if b:
                        vals.append(b[0])
            out.append(int(sum(vals) / len(vals)) if vals else None)
    return {"ok": True, "values": out}

def terrain_paint(points, terrain, brush=3, root=None):
    """画笔式刷地形：直接改 terrain.bmp 的像素索引，不动 definition.csv。

    points: [[x, y], ...]（地图坐标），brush: 笔刷半径（像素）
    """
    terrain = (terrain or "").strip()
    try:
        brush = max(1, min(30, int(brush or 1)))
    except Exception:
        brush = 1
    if not points or not terrain:
        return {"ok": False, "msg": "参数不完整"}
    root = _map_pick(root)
    layers = mod_layers(root)
    tbmp, tbase = _layers_find("map/terrain.bmp", layers)
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    if not tbmp:
        return {"ok": False, "msg": "找不到 terrain.bmp"}
    if os.path.abspath(tbase or "") != os.path.abspath(pbase or ""):
        return {"ok": False, "msg": "terrain.bmp 与 provinces.bmp 不同源，刷地形会错位"}
    t2i, _ = _terrain_type_to_index(root)
    if terrain not in t2i:
        return {"ok": False, "msg": "terrain.txt 里没有类型 %s" % terrain}
    new_idx = t2i[terrain]

    info = bmp_info(tbmp)
    if not info or info.get("bpp") != 8:
        return {"ok": False, "msg": "terrain.bmp 不是 8 位索引图，无法按像素刷"}
    W, H = info["w"], info["h"]
    off0, rowb = info["offset"], info["row"]
    top_down = bool(info.get("top_down"))

    # 收集要刷的像素（去重）
    hit = set()
    for pt in points:
        try:
            cx, cy = int(pt[0]), int(pt[1])
        except Exception:
            continue
        for dy in range(-brush, brush + 1):
            for dx in range(-brush, brush + 1):
                if dx * dx + dy * dy > brush * brush:
                    continue
                x, y = cx + dx, cy + dy
                if 0 <= x < W and 0 <= y < H:
                    hit.add((x, y))
    if not hit:
        return {"ok": False, "msg": "笔刷没落在图内"}

    # 原地 seek 写单字节：Image.save 会用 "w+b" 重开文件，在某些路径上直接 EINVAL
    snapshot(tbmp)
    with open(tbmp, "r+b") as f:
        for (x, y) in hit:
            fy = y if top_down else (H - 1 - y)
            f.seek(off0 + fy * rowb + x)
            f.write(bytes((new_idx,)))
    n = len(hit)
    try:
        state.map_var("_REFINE_IDS_CACHE").pop("cur", None)
    except Exception:
        pass
    return {"ok": True, "painted": n, "to": terrain,
            "msg": "刷了 %d 个像素为 %s · 需重建图层" % (n, terrain)}

def _def_rgb_kind():
    """definition.csv 的 RGB → land/sea。擦除时用它决定还原成 255 还是 254。"""
    root = _map_pick(None)
    layers = mod_layers(root) if root else []
    csvp, _base = (_layers_find("map/definition.csv", layers) if layers else (None, None))
    if not csvp and state.game():
        csvp = os.path.join(state.game(), "map", "definition.csv")
    if not csvp or not os.path.exists(csvp):
        return {}
    try:
        key = (csvp, int(os.path.getmtime(csvp)), os.path.getsize(csvp))
    except Exception:
        key = (csvp, 0, 0)
    if state.map_var("_DEF_RGB_CACHE").get("key") == key:
        return state.map_var("_DEF_RGB_CACHE")["map"]
    m = {}
    try:
        for ln in io.open(csvp, encoding="utf-8", errors="replace"):
            p = ln.strip().split(";")
            if len(p) >= 5:
                try:
                    m[(int(p[1]), int(p[2]), int(p[3]))] = p[4]
                except Exception:
                    pass
    except Exception:
        pass
    state.map_var("_DEF_RGB_CACHE")["key"] = key
    state.map_var("_DEF_RGB_CACHE")["map"] = m
    return m

def _line_pts(p0, p1):
    """Bresenham：两点之间补齐像素，避免鼠标移动快了变成虚线"""
    (x0, y0), (x1, y1) = p0, p1
    pts = []
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = err * 2
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return pts

def river_paint(points, kind="main", brush=1, erase=False, new_stroke=False, root=None):
    """在地图上画河流（直接写 rivers.bmp 的索引）。

    points: [[x,y], ...] 地图像素坐标（和 /api/map_asset 的图同一坐标系）
    kind:   main / tributary / stream / deep
    brush:  笔刷半径 1-5
    erase:  True = 擦回陆地/海洋
    new_stroke: 一次拖拽的第一帧，用来把整笔合成一个撤销单元
    """
    if not points:
        return {"ok": False, "msg": "没有落点"}
    try:
        brush = max(1, min(5, int(brush or 1)))
    except Exception:
        brush = 1
    kind = (kind or "main").strip()
    if not erase and kind not in state.map_var("RIVER_KIND_IDX"):
        return {"ok": False, "msg": "河型只能是 " + " / ".join(k for k, _l, _i in state.map_var("RIVER_KINDS"))}
    root = _map_pick(root)
    layers = mod_layers(root)
    rbmp, rbase = _layers_find("map/rivers.bmp", layers)
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    if not rbmp:
        return {"ok": False, "msg": "找不到 map/rivers.bmp"}
    if not pbmp:
        return {"ok": False, "msg": "找不到 map/provinces.bmp"}
    if os.path.abspath(rbase or "") != os.path.abspath(pbase or ""):
        return {"ok": False, "msg": "rivers.bmp 与 provinces.bmp 不同源，画上去会错位"}
    if is_under_game(rbmp):
        return {"ok": False, "msg": "这张河流图来自原版目录（只读），不能直接改"}
    info = bmp_info(rbmp)
    if not info or info.get("bpp") != 8:
        return {"ok": False, "msg": "rivers.bmp 不是 8 位索引图，无法按像素画"}
    W, H = info["w"], info["h"]
    off0, rowb = info["offset"], info["row"]
    top_down = bool(info.get("top_down"))
    new_idx = state.map_var("RIVER_KIND_IDX").get(kind, 3)

    # 把这一批点连成线，并接上同一笔的上一个末点（跨请求不断线）
    seq = []
    for pt in points:
        try:
            seq.append((int(pt[0]), int(pt[1])))
        except Exception:
            continue
    if not seq:
        return {"ok": False, "msg": "坐标不合法"}
    pts = []
    if state.map_var("_RIVER_LAST").get("path") == rbmp and state.map_var("_RIVER_LAST").get("pt") and not new_stroke:
        pts.extend(_line_pts(state.map_var("_RIVER_LAST")["pt"], seq[0])[1:])
    pts.append(seq[0])
    for a, b in zip(seq, seq[1:]):
        pts.extend(_line_pts(a, b)[1:])
    state.map_var("_RIVER_LAST")["path"] = rbmp
    state.map_var("_RIVER_LAST")["pt"] = seq[-1]

    hit = set()
    for (cx, cy) in pts:
        for dy in range(-brush + 1, brush):
            for dx in range(-brush + 1, brush):
                if brush > 1 and dx * dx + dy * dy > (brush - 1) * (brush - 1) + 1:
                    continue
                x, y = cx + dx, cy + dy
                if 0 <= x < W and 0 <= y < H:
                    hit.add((x, y))
    if not hit:
        return {"ok": False, "msg": "笔刷落在图外了"}

    if new_stroke or not state.map_var("_RIVER_UNDO") or state.map_var("_RIVER_UNDO")[-1]["path"] != rbmp:
        state.map_var("_RIVER_UNDO").append({"path": rbmp, "px": {}})
        if len(state.map_var("_RIVER_UNDO")) > 30:
            state.map_var("_RIVER_UNDO").pop(0)
        # 备份一笔一次就够：每次 mousemove 都 snapshot 会把整个 bmp 复制几十份
        snapshot(rbmp)
    undo = state.map_var("_RIVER_UNDO")[-1]

    rgb2kind = _def_rgb_kind() if erase else {}
    pb = open(pbmp, "rb") if erase else None
    pinfo = bmp_info(pbmp) if erase else None
    n = 0
    try:
        with open(rbmp, "r+b") as f:
            for (x, y) in hit:
                fy = y if top_down else (H - 1 - y)
                f.seek(off0 + fy * rowb + x)
                old_b = f.read(1)
                old = old_b[0] if old_b else 0
                if erase:
                    # 还原成「原本的底色」：看 provinces.bmp 这个像素属于陆还是海
                    new = state.map_var("RIVER_LAND")
                    if rgb2kind and pb and pinfo:
                        pfy = y if pinfo.get("top_down") else (pinfo["h"] - 1 - y)
                        pb.seek(pinfo["offset"] + pfy * pinfo["row"] + x * 3)
                        b3 = pb.read(3)
                        if len(b3) == 3:
                            new = state.map_var("RIVER_LAND") if rgb2kind.get((b3[2], b3[1], b3[0])) == "land" else state.map_var("RIVER_SEA")
                else:
                    new = new_idx
                if old == new:
                    continue
                undo["px"][(x, y)] = old
                f.seek(off0 + fy * rowb + x)
                f.write(bytes((new,)))
                n += 1
    finally:
        if pb:
            pb.close()
    return {"ok": True, "painted": n, "to": ("擦除" if erase else kind),
            "msg": ("擦掉 %d 个像素" % n) if erase else ("画了 %d 个像素（%s）" % (n, dict((k, l) for k, l, _i in state.map_var("RIVER_KINDS")).get(kind, kind)))}

def river_undo(root=None):
    """撤销上一笔（一笔 = 一次按下到松开）"""
    if not state.map_var("_RIVER_UNDO"):
        return {"ok": False, "msg": "没有可撤销的笔画（只记录本次运行画过的）"}
    item = state.map_var("_RIVER_UNDO").pop()
    p = item["path"]
    if not os.path.exists(p):
        return {"ok": False, "msg": "文件不在了：" + p}
    info = bmp_info(p)
    if not info:
        return {"ok": False, "msg": "读不了 bmp 头"}
    W, H = info["w"], info["h"]
    off0, rowb = info["offset"], info["row"]
    top_down = bool(info.get("top_down"))
    with open(p, "r+b") as f:
        for (x, y), old in item["px"].items():
            fy = y if top_down else (H - 1 - y)
            f.seek(off0 + fy * rowb + x)
            f.write(bytes((old,)))
    state.map_var("_RIVER_LAST")["pt"] = None
    return {"ok": True, "restored": len(item["px"]),
            "msg": "撤销了上一笔（%d 个像素）" % len(item["px"])}

def river_stats(root=None):
    """读 rivers.bmp + provinces.bmp，算索引分布 / 落海的河 / 连通块"""
    root = _map_pick(root)
    layers = mod_layers(root)
    rbmp, _rb = _layers_find("map/rivers.bmp", layers)
    pbmp, _pb = _layers_find("map/provinces.bmp", layers)
    if not rbmp:
        return {"ok": False, "msg": "找不到 rivers.bmp"}
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(rbmp) as im:
            # 必须是索引值本身。convert("L") 会把索引按调色板折成灰度，
            # 254（RGB 122,122,122）就变成 122 —— 统计出来的「河」全是假的。
            if im.mode not in ("P", "L"):
                im = im.convert("P")
            W, H = im.size
            riv = im.tobytes()
        land = None
        if pbmp:
            with Image.open(pbmp) as im2:
                raw = im2.convert("RGB").tobytes()
            rgb2kind = _def_rgb_kind()
            land = bytearray(W * H)
            for i in range(0, len(raw), 3):
                k = rgb2kind.get((raw[i], raw[i + 1], raw[i + 2]))
                land[i // 3] = 1 if k == "land" else 0
    except Exception as e:
        return {"ok": False, "msg": "读图失败：%s" % str(e)[:80]}
    if len(riv) < W * H:
        return {"ok": False, "msg": "rivers.bmp 数据长度不足"}
    river_val = set(state.map_var("RIVER_KIND_IDX").values())
    dist = {}
    river_px = []
    for i, v in enumerate(riv[:W * H]):
        dist[v] = dist.get(v, 0) + 1
        if v in river_val:
            river_px.append(i)
    in_sea = 0
    if land is not None:
        in_sea = sum(1 for i in river_px if not land[i])
    # 连通块：只走河道像素，4 邻接
    seen = bytearray(W * H)
    blocks = []
    rs = set(river_px)
    for i in river_px:
        if seen[i]:
            continue
        stack = [i]
        seen[i] = 1
        cnt = 0
        touches_sea = False
        touches_edge = False
        while stack:
            j = stack.pop()
            cnt += 1
            x, y = j % W, j // W
            if x == 0 or y == 0 or x == W - 1 or y == H - 1:
                touches_edge = True
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if not (0 <= nx < W and 0 <= ny < H):
                    continue
                k = ny * W + nx
                if k in rs and not seen[k]:
                    seen[k] = 1
                    stack.append(k)
                elif land is not None and land[k] == 0:
                    touches_sea = True
        blocks.append({"pixels": cnt, "sea": touches_sea, "edge": touches_edge})
    blocks.sort(key=lambda b: -b["pixels"])
    dead = [b for b in blocks if not b["sea"] and not b["edge"]]
    msgs = []
    msgs.append("河道像素 %d 个，分成 %d 段" % (len(river_px), len(blocks)))
    if in_sea:
        msgs.append("有 %d 个河道像素落在海里（河画到海上了）" % in_sea)
    if dead:
        msgs.append("%d 段河没有连到海也没有连到地图边缘（会变成断头河）" % len(dead))
    if not in_sea and not dead and river_px:
        msgs.append("没有落海、没有断头，看起来是通的")
    if not river_px:
        msgs.append("整张图还没有河")
    return {"ok": True, "width": W, "height": H,
            "dist": {str(k): v for k, v in sorted(dist.items(), key=lambda x: -x[1])[:8]},
            "river_pixels": len(river_px), "in_sea": in_sea,
            "blocks": len(blocks), "dead": len(dead),
            "largest": blocks[0]["pixels"] if blocks else 0,
            "msg": "；".join(msgs), "lines": msgs}

def river_preview(root=None):
    """生成一张叠加用的 PNG：河道上色，其余透明。返回路径。"""
    root = _map_pick(root)
    layers = mod_layers(root)
    rbmp, _rb = _layers_find("map/rivers.bmp", layers)
    if not rbmp:
        return None
    outc = os.path.join(state.map_var("MAP_CACHE_DIR"), "river_preview.png")
    try:
        mt = int(os.path.getmtime(rbmp))
    except Exception:
        mt = 0
    stamp = os.path.join(state.map_var("MAP_CACHE_DIR"), "river_preview.stamp")
    try:
        if os.path.exists(outc) and os.path.exists(stamp):
            if io.open(stamp, encoding="utf-8").read().strip() == "%s|%s" % (rbmp, mt):
                return outc
    except Exception:
        pass
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(rbmp) as im:
            idx = im.convert("P") if im.mode != "P" else im.copy()
            idx.load()
        pal = idx.getpalette() or []
        W, H = idx.size
        data = idx.tobytes()
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        px = out.load()
        cmap = {3: (0, 210, 255, 230), 6: (40, 120, 255, 230),
                4: (130, 220, 255, 220), 11: (0, 70, 200, 240)}
        for y in range(H):
            base = y * W
            for x in range(W):
                v = data[base + x]
                c = cmap.get(v)
                if c:
                    px[x, y] = c
        os.makedirs(state.map_var("MAP_CACHE_DIR"), exist_ok=True)
        out.save(outc)
        io.open(stamp, "w", encoding="utf-8", newline="\n").write("%s|%s" % (rbmp, mt))
        return outc
    except Exception:
        return None

def _build_rivers_png(root, w, h, dirp):
    """把 rivers.bmp 转成 RGBA 叠层：背景索引透明，河流保留原色。

    rivers.bmp 是调色板图，背景用 254/255，其余索引才是河。"""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    rp, _ = _layers_find("map/rivers.bmp", mod_layers(root))
    if not rp:
        return 0
    try:
        with Image.open(rp) as im:
            if im.size != (w, h):
                return 0
            pal = im.getpalette() or []
            src = im.convert("P")
            raw = src.tobytes()
            # 找出背景索引（出现最多的两个，通常是 254/255）
            from collections import Counter
            cnt = Counter(raw)
            bg = set([idx for idx, _c in cnt.most_common(2)])
            out = bytearray(w * h * 4)
            for i, v in enumerate(raw):
                o = i * 4
                if v in bg:
                    continue
                r = pal[v * 3] if len(pal) > v * 3 else 80
                g = pal[v * 3 + 1] if len(pal) > v * 3 + 1 else 120
                b = pal[v * 3 + 2] if len(pal) > v * 3 + 2 else 200
                out[o] = r
                out[o + 1] = g
                out[o + 2] = b
                out[o + 3] = 220
            img = Image.frombytes("RGBA", (w, h), bytes(out))
            img.save(os.path.join(dirp, "rivers.png"))
            return len(cnt) - len(bg)
    except Exception as e:
        print("  河流图层失败:", e)
        return 0

def _tag_fallback_color(tag):
    """没有定义颜色的 tag（mod 里州引用了不存在的国家）按 tag 哈希生成稳定色。

    比直接落到中性灰好：至少能看出边界和政治区划，
    不会让整片大陆看起来像数据缺失。"""
    import hashlib
    # 预定义调色板：20 种区分度足够的颜色，按哈希取模。
    # 用 HSV 现算会在某些色相区间退化成相近的 RGB（红区都变成 R=191），
    # 调色板能保证任意两个 tag 落在视觉上不同的色块。
    palette = (
        (230, 90, 90), (90, 160, 230), (110, 200, 120), (240, 190, 90),
        (180, 120, 220), (90, 200, 200), (230, 140, 200), (150, 190, 90),
        (200, 110, 80), (120, 140, 220), (200, 200, 100), (140, 100, 180),
        (100, 180, 160), (220, 160, 120), (160, 200, 200), (200, 130, 130),
        (130, 170, 220), (180, 200, 120), (220, 170, 200), (140, 160, 120),
    )
    h = int(hashlib.md5(str(tag or '').encode('utf-8')).hexdigest()[:8], 16)
    return bytes(palette[h % len(palette)])

def _prov_type_map(root):
    """省号 → definition.csv 第 5 列（land / sea / lake 等）。

    政治图层要区分「海洋」和「无主陆地」：前者给海色，后者给中性灰，
    否则大片海洋会被画成深色，看起来像地图缺了一块。"""
    cache = getattr(_prov_type_map, "_cache", None)
    layers = mod_layers(root or None)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not csvp:
        return {}
    key = (os.path.abspath(csvp), int(os.path.getmtime(csvp)))
    if cache and cache[0] == key:
        return cache[1]
    out = {}
    try:
        with io.open(csvp, encoding="utf-8", errors="replace") as f:
            for line in f:
                p = line.strip().split(";")
                if len(p) >= 5 and p[0].isdigit():
                    out[int(p[0])] = (p[4] or "").strip().lower()
    except Exception:
        pass
    _prov_type_map._cache = (key, out)
    return out

def _terrain_colors(root):
    """从 common/terrain/*.txt 读各地形类别的游戏内配色 {name: (r,g,b)}。
    mod 定义了同名类别就覆盖原版；读不到就返回空字典。"""
    out = {}
    for base in reversed(mod_layers(root)):      # 原版 → ... → mod（后覆盖前）
        d = os.path.join(base or "", "common", "terrain")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8-sig",
                                              errors="replace").read())
            except Exception:
                continue
            m = re.search(r'(?m)^categories\s*=\s*\{', text)
            if not m:
                continue
            b = text.find("{", m.end() - 1)
            e = brace_match(text, b)
            if e <= b:
                continue
            body = text[b + 1:e - 1]
            # 只取一级子块：行首单个 tab 缩进的 name = {
            for cm in re.finditer(r'(?m)^\t([a-zA-Z_][\w]*)\s*=\s*\{', body):
                name = cm.group(1)
                cb = body.find("{", cm.end() - 1)
                ce = brace_match(body, cb)
                if ce <= cb:
                    continue
                sub = body[cb + 1:ce - 1]
                col = re.search(r'color\s*=\s*\{\s*(\d+)\s+(\d+)\s+(\d+)\s*\}', sub)
                if col:
                    out[name] = [int(col.group(1)), int(col.group(2)), int(col.group(3))]
    # 亮度归一化：游戏里地形色差异很大（marsh 76,96,35 与 plains 255,129,66 差 3 倍），
    # 直接铺到 2D 地图上会显得一半发黑。把陆地的最大分量抬到 210 左右，色相不变；
    # 海洋/湖泊保持原值（水本来就该深）。
    for name, c in list(out.items()):
        if name in ("ocean", "lakes", "unknown"):
            out[name] = tuple(c)
            continue
        mx = max(c) or 1
        target = 210
        if mx < target:
            f = target / float(mx)
            out[name] = tuple(min(255, int(v * f)) for v in c)
        else:
            out[name] = tuple(c)
    return out

def map_integrity(root=None, limit=200):
    """地图完整性检查：连通性、州/战略区连续、无效 ID、十字交叉、铁路断连、无主/超大省"""
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "还没有加载 mod"}
    dirp, _, base = _map_dir(root)
    if not dirp or not os.path.exists(os.path.join(dirp, "prov_id.png")):
        return {"ok": False, "msg": "请先构建图层（缺少 prov_id.png）"}
    t0 = time.time()
    ids, w, h, raw = _map_ids_from_cache(dirp)
    if not ids:
        return {"ok": False, "msg": "读取图层缓存失败"}
    n = w * h
    items = []

    def add(level, title, detail, provs=None):
        items.append({"level": level, "kind": "map", "title": title,
                      "detail": detail or "", "provinces": provs or []})

    # 省集合与像素数
    px = {}
    for i in range(n):
        pid = ids[i]
        if pid:
            px[pid] = px.get(pid, 0) + 1
    known = set(px)

    # 4-邻接 + 十字交叉
    adj = {}
    cross = 0
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            a = ids[i]
            if x + 1 < w:
                b = ids[i + 1]
                if a != b:
                    if a and b:
                        adj.setdefault(a, set()).add(b)
                        adj.setdefault(b, set()).add(a)
            if y + 1 < h:
                b = ids[i + w]
                if a != b:
                    if a and b:
                        adj.setdefault(a, set()).add(b)
                        adj.setdefault(b, set()).add(a)
                # 2x2 十字：左上==右下 且 右上==左下 且 两两不同
                if x + 1 < w:
                    c = ids[i + 1]
                    d = ids[i + w]
                    e = ids[i + w + 1]
                    if a == e and c == d and a != c and a and c:
                        cross += 1

    # 省份像素连通（BFS）
    seen = bytearray(n)
    comp = {}
    for i in range(n):
        if seen[i]:
            continue
        pid = ids[i]
        if not pid:
            seen[i] = 1
            continue
        stack = [i]
        seen[i] = 1
        cnt = 0
        while stack:
            cur = stack.pop()
            cnt += 1
            cy, cx = divmod(cur, w)
            for nb in (cur - 1 if cx > 0 else -1,
                       cur + 1 if cx + 1 < w else -1,
                       cur - w if cy > 0 else -1,
                       cur + w if cy + 1 < h else -1):
                if nb < 0 or seen[nb]:
                    continue
                if ids[nb] == pid:
                    seen[nb] = 1
                    stack.append(nb)
        comp[pid] = comp.get(pid, 0) + 1

    bad_comp = [(pid, c) for pid, c in comp.items() if c > 1]

    # 州 / 战略区归属
    prov2state = {}
    prov2state_one = {}
    for sid, st in state.states().items():
        try:
            sid_int = int(st.get("id") or sid)
        except Exception:
            continue
        for p in (st.get("provinces") or []):
            try:
                pid_i = int(p)
            except Exception:
                continue
            prov2state.setdefault(pid_i, []).append(sid_int)
            if pid_i not in prov2state_one:
                prov2state_one[pid_i] = sid_int
    prov2region, region_list = _strategic_regions(root)

    # 一省多州 / 无效 ID
    multi = [(pid, sids) for pid, sids in prov2state.items() if len(sids) > 1]
    dead_state = [pid for pid in prov2state if pid not in known]
    dead_region = [pid for pid in prov2region if pid not in known]

    def group_split(mapping, label):
        """按州/地区分组，用省邻接图判断每组是否连通"""
        groups = {}
        for pid, v in mapping.items():
            groups.setdefault(v, set()).add(pid)
        bad = []
        for gid, members in groups.items():
            members = set(m for m in members if m in known)
            if len(members) < 2:
                continue
            start = next(iter(members))
            stack = [start]
            visited = {start}
            while stack:
                cur = stack.pop()
                for nb in adj.get(cur, ()):
                    if nb in members and nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
            if len(visited) != len(members):
                bad.append((gid, len(members), len(visited)))
        return bad

    split_state = group_split(prov2state_one, "州")
    split_region = group_split(prov2region, "战略区")

    # 铁路
    rail_bad = 0
    rail_check = 0
    rp = None
    for b in (root, state.game()):
        cand = os.path.join(b or "", "map", "railways.txt")
        if os.path.exists(cand):
            rp = cand
            break
    if rp:
        try:
            text = strip_comments(io.open(rp, encoding="utf-8", errors="replace").read())
            for m in re.finditer(r'railway\s*=\s*\{([^{}]*)\}', text):
                body = m.group(1)
                pm = re.search(r'provinces\s*=\s*\{([^}]*)\}', body)
                if not pm:
                    continue
                chain = [int(x) for x in re.findall(r'\d+', pm.group(1))]
                for a, b2 in zip(chain, chain[1:]):
                    rail_check += 1
                    if b2 not in adj.get(a, set()):
                        rail_bad += 1
        except Exception:
            pass

    # 无主省 / 超大省
    no_state = [pid for pid in known if pid not in prov2state and px.get(pid, 0) > 0]
    big = sorted(((pid, c) for pid, c in px.items() if c > 2000), key=lambda x: -x[1])[:30]

    # 地图定义一致性（读缓存里的 meta）
    try:
        _mp = os.path.join(dirp, "meta.json")
        if os.path.exists(_mp):
            _m = json.loads(io.open(_mp, encoding="utf-8").read())
            _c = _m.get("consistency") or {}
            if _c.get("ghost"):
                add("warn", "definition.csv 里有 %d 个省在地图上没有像素" % _c["ghost"],
                    "例如省 " + ", ".join(str(x) for x in (_c.get("ghost_sample") or [])[:12]) +
                    "；可能是删省后没清 definition.csv", (_c.get("ghost_sample") or [])[:20])
            if _c.get("unset_pixels"):
                add("warn", "%.2f%% 的像素颜色在 definition.csv 里找不到（%d 像素）" %
                    (_c.get("unset_ratio", 0), _c["unset_pixels"]),
                    "这些像素会被当成无主地；通常是 bmp 与 csv 不同步，或父子 mod 的 csv/bmp 混用", [])
            if _c.get("dup_rgb"):
                add("error", "%d 组省在 definition.csv 里用了同一个 RGB" % _c["dup_rgb"],
                    "同色会让后定义的省永远不出现；例如 " + json.dumps(
                        (_c.get("dup_rgb_sample") or [])[:3], ensure_ascii=False)[:160], [])
    except Exception as _e:
        print("一致性检查读取失败:", _e)

    # 汇总条目
    if bad_comp:
        items.append({"level": "warn", "kind": "map",
                      "title": "%d 个省份由多块不相连的区域组成（岛屿/飞地或碎片）" % len(bad_comp),
                      "detail": "例如省 " + ", ".join("%d（%d 块）" % (p, c) for p, c in bad_comp[:8]),
                      "provinces": [p for p, c in bad_comp[:20]]})
    if multi:
        add("error", "%d 个省份同时属于多个州" % len(multi),
            "例如省 %s" % ", ".join("%d→州%s" % (p, s) for p, s in multi[:5]),
            [p for p, s in multi[:20]])
    if split_state:
        add("warn", "%d 个州在图上不连续（多为岛屿/飞地，需逐个人工确认）" % len(split_state),
            "例如州 " + ", ".join("%d（%d 省，最大连通 %d）" % g for g in split_state[:6]),
            [])
    if split_region:
        add("warn", "%d 个战略区不连续（多为跨海区域）" % len(split_region),
            "例如地区 " + ", ".join("%d（%d 省，最大连通 %d）" % g for g in split_region[:6]),
            [])
    if dead_state:
        add("error", "州里引用了 %d 个不存在的省" % len(dead_state),
            "例如 " + ", ".join(str(x) for x in dead_state[:10]), dead_state[:20])
    if dead_region:
        add("error", "战略区里引用了 %d 个不存在的省" % len(dead_region),
            "例如 " + ", ".join(str(x) for x in dead_region[:10]), dead_region[:20])
    if cross:
        add("warn", "%d 处十字交叉像素（2×2 对角线歧义）" % cross,
            "会在地图上产生斜角接缝，可用「检查」后手动修或跑修复", [])
    if rail_check and rail_bad:
        add("warn", "铁路有 %d 段两端省份不相邻（共检查 %d 段）" % (rail_bad, rail_check),
            "可能是拆分/删除省份后遗留", [])
    if no_state:
        add("info", "%d 块陆地省份不属于任何州" % len(no_state),
            "例如 " + ", ".join(str(x) for x in no_state[:10]), no_state[:20])
    if big:
        add("info", "%d 个省份面积超过 2000 像素（细化候选）" % len(big),
            "最大：" + ", ".join("%d（%d px）" % (p, c) for p, c in big[:6]), [p for p, c in big[:10]])

    counts = {"error": 0, "warn": 0, "info": 0}
    for it in items:
        counts[it["level"]] = counts.get(it["level"], 0) + 1
    return {"ok": True, "items": items[:limit], "stats": counts,
            "sizes": {"w": w, "h": h, "provinces": len(known)},
            "ms": int((time.time() - t0) * 1000), "source": base}

def map_asset(name, root=None):


    """返回缓存目录里的资产路径（白名单，防路径穿越）"""
    if name not in state.map_var("MAP_ASSETS"):
        return None
    root = _map_pick(root)
    dirp, _, _ = _map_dir(root) if root else (None, None, None)
    if not dirp:
        return None
    p = os.path.join(dirp, name)
    return p if os.path.exists(p) else None
