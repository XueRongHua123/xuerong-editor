# -*- coding: utf-8 -*-
"""地形 / 高程：terrain.txt 与 terrain.bmp 的读改、按省刷地形、heightmap 绘制。"""
import io
import os
import re

from xuerong import state
from xuerong.core.paths import _layers_find, mod_layers
from xuerong.core.text import _atomic_write, brace_match, strip_comments
from xuerong.model.history import snapshot
from xuerong.model.map.io import (_ensure_map_writable, _map_pair_compatible,
                                  _map_pick, _refine_load_ids, bmp_info,
                                  bmp_write_rect_8)


def _terrain_tex_map(root):
    """terrain.txt 的 terrain_N -> {color索引: (type, texture编号)}"""
    idx2type, idx2tex = {}, {}
    for base in reversed(mod_layers(root)):
        d = os.path.join(base or "", "common", "terrain")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                with io.open(os.path.join(d, fn), encoding="utf-8-sig", errors="replace") as _f:
                    text = strip_comments(_f.read())
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

def prov_terrain_set(pid, terrain, root=None, adopt=False):
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
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    csvp, _cbase, cerr = _ensure_map_writable("definition.csv", root=root, adopt=adopt)
    if not csvp:
        return cerr
    tbmp, tbase, terr = _ensure_map_writable("terrain.bmp", root=root, adopt=adopt)
    if not tbmp:
        return terr
    layers = mod_layers(root)
    if pbmp and not _map_pair_compatible(tbmp, tbase, pbmp, pbase, layers):
        return {"ok": False,
                "msg": "terrain.bmp 与 provinces.bmp 尺寸或层级不匹配（mod 换了地图没换地形图），改地形会错位"}

    t2i, idx2type = _terrain_type_to_index(root)
    if terrain not in t2i:
        return {"ok": False, "msg": "terrain.txt 里没有类型 %s（可选：%s）" % (
            terrain, "、".join(sorted(t2i.keys())[:8]))}
    new_idx = t2i[terrain]

    # 1) 改 definition.csv
    with io.open(csvp, encoding="utf-8", errors="replace") as _f:
        raw = _f.read()
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

def _terrain_common(root, terrain, adopt=False):
    """批量改地形的公共准备：找文件、校验可写、查索引、验兼容。
    返回 (csvp, tbmp, new_idx, ids, w, h, err_dict_or_str)"""
    root = _map_pick(root)
    layers = mod_layers(root)
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    csvp, _cbase, cerr = _ensure_map_writable("definition.csv", root=root, adopt=adopt)
    if not csvp:
        return None, None, None, None, 0, 0, cerr
    tbmp, tbase, terr = _ensure_map_writable("terrain.bmp", root=root, adopt=adopt)
    if not tbmp:
        return None, None, None, None, 0, 0, terr
    layers = mod_layers(root)
    if pbmp and not _map_pair_compatible(tbmp, tbase, pbmp, pbase, layers):
        return None, None, None, None, 0, 0, "terrain.bmp 与 provinces.bmp 尺寸或层级不匹配，改地形会错位"
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

    with io.open(csvp, encoding="utf-8", errors="replace") as _f:
        raw = _f.read()
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

def prov_terrain_batch(pids, terrain, root=None, adopt=False):
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

    csvp, tbmp, new_idx, ids, w, h, err = _terrain_common(root, terrain, adopt=adopt)
    if err:
        return err if isinstance(err, dict) else {"ok": False, "msg": err}

    # 找出真正要改的（已经是指定类型的跳过）
    with io.open(csvp, encoding="utf-8", errors="replace") as _f:
        raw = _f.read()
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

def prov_terrain_by_type(from_type, to_type, root=None, adopt=False):
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
    with io.open(csvp, encoding="utf-8", errors="replace") as _f:
        for ln in _f:
            p = ln.rstrip("\r\n").split(";")
            if len(p) >= 8 and p[0].isdigit() and p[6] == from_type:
                pids.append(int(p[0]))
    if not pids:
        return {"ok": False, "msg": "没有地形为 %s 的省" % from_type}
    r = prov_terrain_batch(pids, to_type, root, adopt=adopt)
    if r.get("ok"):
        r["msg"] = "把 %d 个 %s 改成了 %s · 需重建图层" % (
            r.get("changed", 0), from_type, to_type)
    return r

def _invalidate_height_preview_cache():
    stamp = os.path.join(state.map_var("MAP_CACHE_DIR"), "height_preview.stamp")
    try:
        if os.path.exists(stamp):
            os.remove(stamp)
    except Exception:
        pass


def height_paint(points, height, brush=8, feather=True, root=None, adopt=False):
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
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    hbmp, hbase, herr = _ensure_map_writable("heightmap.bmp", root=root, adopt=adopt)
    if not hbmp:
        return herr
    layers = mod_layers(root)
    if pbmp and not _map_pair_compatible(hbmp, hbase, pbmp, pbase, layers):
        return {"ok": False, "msg": "heightmap.bmp 与 provinces.bmp 尺寸或层级不匹配，刷高程会错位"}

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
    _invalidate_height_preview_cache()
    msg = "刷了 %d 个像素，高度 %d%s" % (n, hv, "（羽化）" if feather else "")
    if herr and herr.get("adopted"):
        msg = (herr.get("adopt_msg") or "已单文件接管 map/heightmap.bmp") + "；" + msg
    out = {"ok": True, "painted": n, "to": hv, "msg": msg}
    if herr and herr.get("adopted"):
        out["adopted"] = True
    return out


def height_preview(root=None):
    """把 heightmap.bmp 转为高程伪彩色叠加 PNG，返回缓存路径。"""
    root = _map_pick(root)
    layers = mod_layers(root)
    hbmp, _ = _layers_find("map/heightmap.bmp", layers)
    if not hbmp:
        return None
    outc = os.path.join(state.map_var("MAP_CACHE_DIR"), "height_preview.png")
    try:
        mt = int(os.path.getmtime(hbmp))
        sz = int(os.path.getsize(hbmp))
    except Exception:
        mt, sz = 0, 0
    stamp = os.path.join(state.map_var("MAP_CACHE_DIR"), "height_preview.stamp")
    sig = "%s|%s|%s" % (hbmp, mt, sz)
    try:
        if os.path.exists(outc) and os.path.exists(stamp):
            with io.open(stamp, encoding="utf-8") as _f:
                if _f.read().strip() == sig:
                    return outc
    except Exception:
        pass
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(hbmp) as im:
            g = im.convert("L") if im.mode != "L" else im.copy()
            W, H = g.size
            raw = g.tobytes()
        try:
            import numpy as np
            lut = np.zeros((256, 4), dtype=np.uint8)
            for v in range(256):
                if v < 95:
                    # 海域：半透深蓝，突出海岸线
                    lut[v] = (20, 50, 120, 140)
                elif v < 130:
                    t = (v - 95) / 35.0
                    lut[v] = (int(50 + 120 * t), int(160 + 55 * t), int(70 - 20 * t), 195)
                elif v < 190:
                    t = (v - 130) / 60.0
                    lut[v] = (int(170 + 40 * t), int(215 - 95 * t), int(50 + 20 * t), 210)
                else:
                    t = (v - 190) / 65.0
                    lut[v] = (int(210 + 45 * t), int(120 + 130 * t), int(70 + 180 * t), 225)
            arr = np.frombuffer(raw, dtype=np.uint8, count=W * H)
            out = Image.fromarray(lut[arr].reshape((H, W, 4)), mode="RGBA")
        except Exception:
            out = g.convert("RGBA")
        os.makedirs(state.map_var("MAP_CACHE_DIR"), exist_ok=True)
        out.save(outc)
        with io.open(stamp, "w", encoding="utf-8", newline="\n") as _f:
            _f.write(sig)
        return outc
    except Exception:
        return None

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

def terrain_paint(points, terrain, brush=3, root=None, adopt=False):
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
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    tbmp, tbase, terr = _ensure_map_writable("terrain.bmp", root=root, adopt=adopt)
    if not tbmp:
        return terr
    layers = mod_layers(root)
    if pbmp and not _map_pair_compatible(tbmp, tbase, pbmp, pbase, layers):
        return {"ok": False, "msg": "terrain.bmp 与 provinces.bmp 尺寸或层级不匹配，刷地形会错位"}
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
    msg = "刷了 %d 个像素为 %s" % (n, terrain)
    if terr and terr.get("adopted"):
        msg = (terr.get("adopt_msg") or "已单文件接管 map/terrain.bmp") + "；" + msg
    out = {"ok": True, "painted": n, "to": terrain, "msg": msg}
    if terr and terr.get("adopted"):
        out["adopted"] = True
    return out
