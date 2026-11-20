# -*- coding: utf-8 -*-
"""河流：rivers.bmp 的绘制、撤销、统计与预览，以及给渲染用的河流底图。"""
import io
import os

from xuerong import state
from xuerong.core.paths import _layers_find, is_under_game, mod_layers
from xuerong.model.history import snapshot
from xuerong.model.map.io import _map_pick, bmp_info


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
