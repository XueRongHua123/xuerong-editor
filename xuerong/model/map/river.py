# -*- coding: utf-8 -*-
"""河流：rivers.bmp 的绘制、撤销、统计与预览，以及给渲染用的河流底图。"""
import io
import os

from xuerong import state
from xuerong.core.paths import _layers_find, mod_layers
from xuerong.model.map.io import (_ensure_map_writable, _map_pair_compatible,
                                  _map_pick, bmp_info)

_CTRL_IDXS = (0, 1, 2)
_RIVER_CHANNEL_IDXS = tuple(range(3, 12))
_RIVER_ALL_IDXS = tuple(range(0, 12))

# HOI4 rivers.bmp 标准可视色表（0=绿源头 1=红汇入 2=黄分流 3..11=由浅入深蓝）
_RIVER_RGBA_MAP = {
    0: (0, 255, 0, 255),
    1: (255, 0, 0, 255),
    2: (255, 252, 0, 255),
    3: (0, 225, 255, 235),
    4: (0, 200, 255, 230),
    5: (0, 150, 255, 230),
    6: (40, 120, 255, 235),
    7: (0, 60, 255, 235),
    8: (0, 0, 225, 235),
    9: (0, 0, 200, 235),
    10: (0, 0, 150, 240),
    11: (0, 70, 200, 245),
}


def _invalidate_river_preview_cache():
    """写盘或撤销后使河流叠加预览缓存失效。"""
    stamp = os.path.join(state.map_var("MAP_CACHE_DIR"), "river_preview.stamp")
    try:
        if os.path.exists(stamp):
            os.remove(stamp)
    except Exception:
        pass


def _def_rgb_kind():
    """definition.csv 的 RGB → land/sea。擦除或统计时区分陆地与海域。"""
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
        with io.open(csvp, encoding="utf-8-sig", errors="replace") as _f:
            for ln in _f:
                p = ln.strip().split(";")
                if len(p) >= 5:
                    try:
                        m[(int(p[1]), int(p[2]), int(p[3]))] = p[4].strip().lower()
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


def river_paint(points, kind="main", brush=1, erase=False, new_stroke=False, root=None, adopt=False):
    """在地图上画河流（直接写 rivers.bmp 的索引）。

    points: [[x,y], ...] 地图像素坐标（和 /api/map_asset 的图同一坐标系）
    kind:   main / stream / tributary / deep / source / flow_in / split
    brush:  笔刷半径 1-5（控制点 source/flow_in/split 强制单点）
    erase:  True = 擦回陆地/海洋
    new_stroke: 一次拖拽的第一帧，用来把整笔合成一个撤销单元
    adopt:  True = 若 rivers.bmp 在只读/父层，先单文件接管到可写顶层再写
    """
    if not points:
        return {"ok": False, "msg": "没有落点"}
    try:
        brush = max(1, min(5, int(brush or 1)))
    except Exception:
        brush = 1
    kind = (kind or "main").strip()
    kind_idx = state.map_var("RIVER_KIND_IDX") or {}
    if not erase and kind not in kind_idx:
        return {"ok": False, "msg": "河型只能是 " + " / ".join(k for k, _l, _i in state.map_var("RIVER_KINDS"))}

    root = _map_pick(root)
    layers = mod_layers(root)
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    if not pbmp:
        return {"ok": False, "msg": "找不到 map/provinces.bmp"}
    rbmp, rbase, werr = _ensure_map_writable("rivers.bmp", root=root, adopt=adopt)
    if not rbmp:
        return werr
    layers = mod_layers(root)
    if not _map_pair_compatible(rbmp, rbase, pbmp, pbase, layers):
        return {"ok": False, "msg": "rivers.bmp 与 provinces.bmp 尺寸或层级不匹配，画上去会错位"}

    info = bmp_info(rbmp)
    if not info or info.get("bpp") != 8:
        return {"ok": False, "msg": "rivers.bmp 不是 8 位索引图，无法按像素画"}
    W, H = info["w"], info["h"]
    off0, rowb = info["offset"], info["row"]
    top_down = bool(info.get("top_down"))
    new_idx = kind_idx.get(kind, 3)
    is_ctrl = (not erase) and (new_idx in _CTRL_IDXS)
    eff_brush = 1 if is_ctrl else brush

    seq = []
    for pt in points:
        try:
            seq.append((int(pt[0]), int(pt[1])))
        except Exception:
            continue
    if not seq:
        return {"ok": False, "msg": "坐标不合法"}

    if is_ctrl:
        pts = [seq[-1]]
    else:
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
        for dy in range(-eff_brush + 1, eff_brush):
            for dx in range(-eff_brush + 1, eff_brush):
                if eff_brush > 1 and dx * dx + dy * dy > (eff_brush - 1) * (eff_brush - 1) + 1:
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
    undo = state.map_var("_RIVER_UNDO")[-1]

    from contextlib import nullcontext
    rgb2kind = _def_rgb_kind() if erase else {}
    pinfo = bmp_info(pbmp) if erase else None
    n = 0
    with (open(pbmp, "rb") if erase else nullcontext()) as pb, open(rbmp, "r+b") as f:
        for (x, y) in hit:
            fy = y if top_down else (H - 1 - y)
            f.seek(off0 + fy * rowb + x)
            old_b = f.read(1)
            old = old_b[0] if old_b else 0
            if erase:
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
            if (x, y) not in undo["px"]:
                undo["px"][(x, y)] = old
            f.seek(off0 + fy * rowb + x)
            f.write(bytes((new,)))
            n += 1

    if n:
        _invalidate_river_preview_cache()
    label = dict((k, l) for k, l, _i in state.map_var("RIVER_KINDS")).get(kind, kind)
    msg = ("擦掉 %d 个像素" % n) if erase else ("画了 %d 个像素（%s）" % (n, label))
    if werr and werr.get("adopted"):
        msg = (werr.get("adopt_msg") or "已单文件接管 map/rivers.bmp") + "；" + msg
    out = {"ok": True, "painted": n, "to": ("擦除" if erase else kind), "msg": msg}
    if werr and werr.get("adopted"):
        out["adopted"] = True
    return out


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
    _invalidate_river_preview_cache()
    return {"ok": True, "restored": len(item["px"]),
            "msg": "撤销了上一笔（%d 个像素）" % len(item["px"])}


def _build_land_mask(pbmp, W, H, rgb2kind):
    """返回长度为 W*H 的陆地掩码（1=陆地, 0=海洋/湖泊/未知）。"""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(pbmp) as im2:
        raw = im2.convert("RGB").tobytes()
    try:
        import numpy as np
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((H * W, 3))
        codes = (arr[:, 0].astype(np.uint32) << 16) | (arr[:, 1].astype(np.uint32) << 8) | arr[:, 2].astype(np.uint32)
        land_codes = np.array(
            [(r << 16) | (g << 8) | b for (r, g, b), k in rgb2kind.items() if k == "land"],
            dtype=np.uint32,
        )
        if land_codes.size == 0:
            return bytearray(W * H)
        return np.isin(codes, land_codes).astype(np.uint8).tobytes()
    except Exception:
        land = bytearray(W * H)
        for i in range(0, min(len(raw), W * H * 3), 3):
            if rgb2kind.get((raw[i], raw[i + 1], raw[i + 2])) == "land":
                land[i // 3] = 1
        return land


def river_stats(root=None):
    """读 rivers.bmp + provinces.bmp，统计河道、源头/汇流控制点、2×2 粗块、落海与断头河。"""
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
            if im.mode not in ("P", "L"):
                im = im.convert("P")
            W, H = im.size
            riv = im.tobytes()
        land = _build_land_mask(pbmp, W, H, _def_rgb_kind()) if pbmp else None
    except Exception as e:
        return {"ok": False, "msg": "读图失败：%s" % str(e)[:80]}
    if len(riv) < W * H:
        return {"ok": False, "msg": "rivers.bmp 数据长度不足"}

    river_val = set(_RIVER_ALL_IDXS) | set((state.map_var("RIVER_KIND_IDX") or {}).values())
    ctrl_val = set(_CTRL_IDXS)
    dist = {}
    river_px = []
    sources = flow_ins = splits = 0
    thick_2x2 = 0

    try:
        import numpy as np
        arr = np.frombuffer(riv, dtype=np.uint8, count=W * H).reshape((H, W))
        uniq, cnts = np.unique(arr, return_counts=True)
        dist = {int(u): int(c) for u, c in zip(uniq, cnts)}
        sources = dist.get(0, 0)
        flow_ins = dist.get(1, 0)
        splits = dist.get(2, 0)
        rmask = arr <= 11
        extra_vals = [v for v in river_val if v > 11]
        if extra_vals:
            rmask = rmask | np.isin(arr, extra_vals)
        flat_r = rmask.ravel()
        river_px = np.flatnonzero(flat_r).tolist()
        if W > 1 and H > 1:
            thick_2x2 = int(np.count_nonzero(rmask[:-1, :-1] & rmask[1:, :-1] & rmask[:-1, 1:] & rmask[1:, 1:]))
        in_sea = 0
        if land is not None and river_px:
            larr = np.frombuffer(land, dtype=np.uint8, count=W * H)
            in_sea = int(np.count_nonzero(flat_r & (larr == 0)))
    except Exception:
        for i, v in enumerate(riv[:W * H]):
            dist[v] = dist.get(v, 0) + 1
            if v in river_val:
                river_px.append(i)
                if v == 0:
                    sources += 1
                elif v == 1:
                    flow_ins += 1
                elif v == 2:
                    splits += 1
        in_sea = sum(1 for i in river_px if not land[i]) if land is not None else 0
        rs_tmp = set(river_px)
        for i in river_px:
            x, y = i % W, i // W
            if x + 1 < W and y + 1 < H:
                if (i + 1) in rs_tmp and (i + W) in rs_tmp and (i + W + 1) in rs_tmp:
                    thick_2x2 += 1

    # 连通块：走所有河流像素（含控制索引 0/1/2），4 邻接
    seen = bytearray(W * H)
    blocks = []
    rs = set(river_px)
    for i in river_px:
        if seen[i]:
            continue
        stack = [i]
        seen[i] = 1
        cnt = 0
        has_ctrl = False
        touches_sea = False
        touches_edge = False
        while stack:
            j = stack.pop()
            cnt += 1
            if riv[j] in ctrl_val:
                has_ctrl = True
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
        blocks.append({"pixels": cnt, "sea": touches_sea, "edge": touches_edge, "has_ctrl": has_ctrl})

    blocks.sort(key=lambda b: -b["pixels"])
    dead = [b for b in blocks if not b["sea"] and not b["edge"]]
    no_src = [b for b in blocks if not b["has_ctrl"]]
    msgs = ["河道像素 %d 个，分成 %d 段（源头 %d / 汇入 %d / 分流 %d）"
            % (len(river_px), len(blocks), sources, flow_ins, splits)]
    if in_sea:
        msgs.append("有 %d 个河道像素落在海里（河画到海上了）" % in_sea)
    if dead:
        msgs.append("%d 段河没有连到海也没有连到地图边缘（会变成断头河）" % len(dead))
    if no_src:
        msgs.append("%d 段河缺少源头(绿 0)或汇入/分流(红 1/黄 2)起止像素" % len(no_src))
    if thick_2x2:
        msgs.append("存在 %d 处 2×2 粗块（HOI4 要求 1px 单像素河线）" % thick_2x2)
    if not in_sea and not dead and not no_src and not thick_2x2 and river_px:
        msgs.append("起止控制点与入海连通正常，符合 1px 单线规则")
    if not river_px:
        msgs.append("整张图还没有河")
    return {"ok": True, "width": W, "height": H,
            "dist": {str(k): v for k, v in sorted(dist.items(), key=lambda x: -x[1])[:12]},
            "river_pixels": len(river_px), "in_sea": in_sea,
            "blocks": len(blocks), "dead": len(dead),
            "no_source_blocks": len(no_src), "thick_2x2": thick_2x2,
            "sources": sources, "flow_ins": flow_ins, "splits": splits,
            "largest": blocks[0]["pixels"] if blocks else 0,
            "msg": "；".join(msgs), "lines": msgs}


def _indices_to_rgba_image(idx_bytes, W, H, cmap, bg_idxs=None, pal=None):
    """把 8 位索引字节转为透明底 RGBA Image，优先用 numpy 向量化查表。"""
    from PIL import Image
    try:
        import numpy as np
        lut = np.zeros((256, 4), dtype=np.uint8)
        for v in range(256):
            if bg_idxs is not None and v in bg_idxs:
                continue
            if v in cmap:
                lut[v] = cmap[v]
            elif pal and len(pal) > v * 3 + 2 and bg_idxs is not None:
                lut[v] = (pal[v * 3], pal[v * 3 + 1], pal[v * 3 + 2], 225)
        arr = np.frombuffer(idx_bytes, dtype=np.uint8, count=W * H)
        rgba = lut[arr].reshape((H, W, 4))
        return Image.fromarray(rgba, mode="RGBA")
    except Exception:
        out = bytearray(W * H * 4)
        for i, v in enumerate(idx_bytes[:W * H]):
            if bg_idxs is not None and v in bg_idxs:
                continue
            c = cmap.get(v)
            if c is None:
                if pal and len(pal) > v * 3 + 2 and bg_idxs is not None:
                    c = (pal[v * 3], pal[v * 3 + 1], pal[v * 3 + 2], 225)
                else:
                    continue
            o = i * 4
            out[o], out[o + 1], out[o + 2], out[o + 3] = c
        return Image.frombytes("RGBA", (W, H), bytes(out))


def river_preview(root=None):
    """生成一张叠加用的 PNG：河道与控制点(0/1/2)上色，其余透明。返回路径。"""
    root = _map_pick(root)
    layers = mod_layers(root)
    rbmp, _rb = _layers_find("map/rivers.bmp", layers)
    if not rbmp:
        return None
    outc = os.path.join(state.map_var("MAP_CACHE_DIR"), "river_preview.png")
    try:
        mt = int(os.path.getmtime(rbmp))
        sz = int(os.path.getsize(rbmp))
    except Exception:
        mt, sz = 0, 0
    stamp = os.path.join(state.map_var("MAP_CACHE_DIR"), "river_preview.stamp")
    sig = "%s|%s|%s" % (rbmp, mt, sz)
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
        with Image.open(rbmp) as im:
            idx = im.convert("P") if im.mode != "P" else im.copy()
            idx.load()
        W, H = idx.size
        out = _indices_to_rgba_image(idx.tobytes(), W, H, _RIVER_RGBA_MAP)
        os.makedirs(state.map_var("MAP_CACHE_DIR"), exist_ok=True)
        out.save(outc)
        with io.open(stamp, "w", encoding="utf-8", newline="\n") as _f:
            _f.write(sig)
        return outc
    except Exception:
        return None


def _build_rivers_png(root, w, h, dirp):
    """把 rivers.bmp 转成 RGBA 叠层：背景索引透明，河流保留标准色。"""
    from collections import Counter
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
            src = im.convert("P") if im.mode != "P" else im
            raw = src.tobytes()
            cnt = Counter(raw)
            bg = set(idx for idx, _c in cnt.most_common(2) if idx in (254, 255)) or {254, 255}
            img = _indices_to_rgba_image(raw, w, h, _RIVER_RGBA_MAP, bg_idxs=bg, pal=pal)
            img.save(os.path.join(dirp, "rivers.png"))
            return len([k for k in cnt if k not in bg])
    except Exception as e:
        print("  河流图层失败:", e)
        return 0
