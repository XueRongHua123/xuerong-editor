# -*- coding: utf-8 -*-
"""从 GeoJSON / 真实地图图片生成省图。

from_geojson      矢量行政区划（最准）
from_terrain_map  真实地图/卫星图（自动识别海陆 + Voronoi 切省 + 地形反推）
"""
import io
import json
import random
import numpy as np
from PIL import Image, ImageDraw

import mapgen_core as core


# ============ GeoJSON ============

def _iter_rings(geom):
    """把 Polygon / MultiPolygon 统一成 [(ring, is_outer)] 列表。"""
    t = (geom or {}).get("type")
    coords = (geom or {}).get("coordinates")
    out = []
    if t == "Polygon":
        for i, ring in enumerate(coords or []):
            out.append((ring, i == 0))
    elif t == "MultiPolygon":
        for poly in (coords or []):
            for i, ring in enumerate(poly or []):
                out.append((ring, i == 0))
    return out


def geojson_bbox(path):
    """扫一遍拿整体 bbox，返回 (minlon, minlat, maxlon, maxlat)。"""
    data = json.load(io.open(path, encoding="utf-8"))
    lo1 = lo2 = 1e9
    hi1 = hi2 = -1e9
    n = 0
    for f in (data.get("features") or []):
        for ring, _outer in _iter_rings(f.get("geometry")):
            for pt in ring:
                if len(pt) < 2:
                    continue
                x, y = float(pt[0]), float(pt[1])
                lo1 = min(lo1, x); hi1 = max(hi1, x)
                lo2 = min(lo2, y); hi2 = max(hi2, y)
                n += 1
    if n == 0:
        return None
    return (lo1, lo2, hi1, hi2)


def from_geojson(path, width=1400, height=520, bbox=None, min_size=200,
                 name_key="name", seed=42):
    """从 GeoJSON 生成省图。

    返回 (labels, land, names)：
      labels  int32，0 = 海，1..N = 省
      land    bool 掩码
      names   {label_id: 省名}
    """
    data = json.load(io.open(path, encoding="utf-8"))
    feats = [f for f in (data.get("features") or []) if f.get("geometry")]
    if not feats:
        return None, None, {}

    bb = bbox or geojson_bbox(path)
    if not bb:
        return None, None, {}
    lon1, lat1, lon2, lat2 = bb
    if lon2 <= lon1 or lat2 <= lat1:
        return None, None, {}

    def to_xy(lon, lat):
        x = (float(lon) - lon1) / (lon2 - lon1) * (width - 1)
        y = (lat2 - float(lat)) / (lat2 - lat1) * (height - 1)
        return (x, y)

    img = Image.new("RGB", (width, height), (0, 0, 0))
    dr = ImageDraw.Draw(img)
    colors = core.unique_colors(len(feats), seed)
    names = {}

    for idx, f in enumerate(feats, start=1):
        col = colors[idx - 1]
        props = f.get("properties") or {}
        nm = str(props.get(name_key) or props.get("NAME") or props.get("name")
                 or props.get("NAME_1") or ("PROV%d" % idx))
        names[idx] = nm
        # 先填所有外环，再用黑色挖洞
        rings = _iter_rings(f.get("geometry"))
        for ring, outer in rings:
            if not outer:
                continue
            pts = [to_xy(p[0], p[1]) for p in ring if len(p) >= 2]
            if len(pts) < 3:
                continue
            dr.polygon(pts, fill=col)
        for ring, outer in rings:
            if outer:
                continue
            pts = [to_xy(p[0], p[1]) for p in ring if len(p) >= 2]
            if len(pts) < 3:
                continue
            dr.polygon(pts, fill=(0, 0, 0))

    a = np.array(img)
    # 用颜色当 key 反查 label
    key = a[:, :, 0].astype(np.int32) * 65536 + a[:, :, 1].astype(np.int32) * 256 + a[:, :, 2].astype(np.int32)
    labels = np.zeros((height, width), dtype=np.int32)
    for idx, col in enumerate(colors, start=1):
        k = col[0] * 65536 + col[1] * 256 + col[2]
        labels[key == k] = idx
    # 去掉太小的块
    labels = core.filter_small(labels, min_size)
    # 重新编号并同步名字
    uniq = sorted(int(x) for x in np.unique(labels) if x > 0)
    remap = {old: i + 1 for i, old in enumerate(uniq)}
    lut = np.zeros(int(labels.max()) + 1, dtype=np.int32)
    for old, new in remap.items():
        lut[old] = new
    labels = lut[labels]
    new_names = {remap[o]: names[o] for o in uniq if o in names}
    return labels, labels > 0, new_names


# ============ 真实地图 / 卫星图 ============

def water_thickness(water, cap=24):
    """每个水像素到最近非水像素的曼哈顿距离（迭代 BFS 近似）。

    海很宽，距离值大；河只有 1-3 像素宽，距离值 ≤ 2。
    """
    dist = np.where(water, cap, 0).astype(np.int32)
    for _ in range(cap):
        nb = np.minimum.reduce([
            np.roll(dist, 1, 0), np.roll(dist, -1, 0),
            np.roll(dist, 1, 1), np.roll(dist, -1, 1)]) + 1
        new = np.where(water, np.minimum(dist, nb), 0)
        if (new == dist).all():
            break
        dist = new
    return dist


def thin_water(water, max_width=2):
    """宽度 <= max_width 的水 = 河流。

    河流常和海洋连成一块（河口），形态学分离不了——膨胀会把紧贴的河吞掉。
    改用距离变换：细线的距离值小，大片水的距离值大。
    """
    if not water.any():
        return np.zeros_like(water)
    dist = water_thickness(water)
    return water & (dist <= max_width)


def from_terrain_map(path, width=None, height=None, n_provinces=None,
                     min_size=300, seed=9, water_blue=0.12):
    """从真实地图/卫星图生成。

    思路：
      1. 按 RGB 判海陆（蓝色占比高的算海）
      2. 陆地用 Voronoi 切省
      3. 顺便按颜色反推地形倾向（绿=平原、褐=丘陵/山地、白=雪）
    返回 (labels, land, terrain_hint)：
      terrain_hint 是 (h, w) uint8，0=plains 1=hills 2=mountain 3=snow 4=desert
    """
    im = Image.open(path).convert("RGB")
    if width and height:
        im = im.resize((width, height), Image.LANCZOS)
    a = np.array(im, dtype=np.float32)
    h, w = a.shape[:2]

    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)

    # 海：蓝通道明显高于红绿，且饱和度不太低
    is_blue = (b > r * 1.15) & (b > g * 1.05) & (sat > water_blue) & (mx > 30)
    # 深蓝（深海）
    deep = (b > 60) & (b > r * 1.5) & (b > g * 1.35)
    water = is_blue | deep
    land = ~water

    # 河流要在去噪前提取：去噪的邻居投票会把 1-3 像素宽的细线当噪点抹掉。
    # 河流常和海洋连成一块（河口），按连通块面积分不出来，用细线检测。
    try:
        rivers = thin_water(water, max_width=3)
    except Exception:
        rivers = np.zeros((h, w), dtype=bool)

    # 去掉陆地里零星的水点 / 去掉水里零星的陆点
    for _ in range(2):
        nb = (np.roll(land, 1, 0).astype(np.int8) + np.roll(land, -1, 0).astype(np.int8)
              + np.roll(land, 1, 1).astype(np.int8) + np.roll(land, -1, 1).astype(np.int8))
        land = np.where(nb >= 3, True, np.where(nb <= 1, False, land))
    water_final = ~land

    if n_provinces is None:
        n_provinces = max(1, int(land.sum() / 6000))

    # 在陆地上做 Voronoi
    ys, xs = np.nonzero(land)
    if len(ys) == 0:
        return np.zeros((h, w), dtype=np.int32), np.zeros((h, w), dtype=bool), np.zeros((h, w), dtype=np.uint8)
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(ys), size=min(n_provinces, len(ys)), replace=False)
    seeds = np.stack([ys[pick], xs[pick]], axis=1).astype(np.float32)
    labels = np.zeros((h, w), dtype=np.int32)
    block = 64
    for y0 in range(0, h, block):
        y1 = min(h, y0 + block)
        yy, xx = np.mgrid[y0:y1, 0:w]
        pts = np.stack([yy.ravel(), xx.ravel()], axis=1).astype(np.float32)
        d = ((pts[:, None, :] - seeds[None, :, :]) ** 2).sum(axis=2)
        lab = d.argmin(axis=1).astype(np.int32) + 1
        lab = lab.reshape(yy.shape)
        labels[y0:y1] = np.where(land[y0:y1], lab, 0)

    # 地形反推
    terrain = np.zeros((h, w), dtype=np.uint8)
    # 绿多 → plains；褐/黄多 → hills/mountain；白 → snow；黄橙 → desert
    greenish = (g > r * 1.05) & (g > b * 1.05) & land
    brownish = (r > g * 1.05) & (g > b) & land
    # 雪：三个通道都亮（阈值放宽到 185/175，190 太严会漏掉偏黄的雪）
    bright = (r >= 185) & (g >= 185) & (b >= 175) & land
    sandy = (r > 170) & (g > 140) & (b < 130) & land
    terrain[greenish] = 0
    terrain[brownish] = 1
    terrain[sandy] = 4
    terrain[bright] = 3
    # 非常暗的褐色 → 高山
    # 暗褐才算山地：褐色 (120,90,60) 的 mx=120，暗褐 (70,55,40) 的 mx=70
    dark_brown = brownish & (mx < 100)
    terrain[dark_brown] = 2

    labels = core.filter_small(labels, min_size)

    # 河流只留落在陆地上的部分
    rivers = rivers & (labels > 0)

    return labels, labels > 0, terrain, rivers
