# -*- coding: utf-8 -*-
"""地图生成统一入口。

generate(source, out_dir, ...) → 在 out_dir 下生成完整 map/ 目录
"""
import io
import os
import json
import numpy as np
from PIL import Image

import mapgen_core as core
import mapgen_write as mgw
import mapgen_extra as mgx
import mapgen_sources as mgs
import mapgen_scaffold as mgsc

HOI4_MAP = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV\map'


def _detect_size(labels):
    h, w = labels.shape
    return w, h


def _align256(v):
    """向上取整到 256 的倍数。

    HOI4 要求 provinces.bmp 等地图位图的宽高都必须是 256 的倍数，
    不是整数倍时游戏在加载期直接崩，且 error.log 里只留 shader 报错，
    看不出是尺寸问题。
    """
    v = int(v)
    return ((v + 255) // 256) * 256


def _clean_tiny_sea(labels, n_land, sea_n, sea_ids, say=None, min_px=32):
    """把面积 < min_px 的海省并掉，再把海省 id 连续重编号。

    两轮：
      1. 有海邻居 → 并进邻接面积最大的海省
      2. 没有海邻居（被陆地包死的 1 像素小湖）→ 并进邻接的陆省，这个像素算陆地

    第 2 步会让极少数像素从海变陆（实测几十个像素 / 52 万），换来的是
    definition.csv 里不再有「1 像素的省」这种退化数据。
    """
    def _nb_ids(mask):
        out = []
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            out.append(np.roll(labels, (dy, dx), axis=(0, 1))[mask])
        return np.concatenate(out) if out else None

    lo, hi = n_land + 1, n_land + sea_n
    for _ in range(6):
        counts = np.bincount(labels.ravel(), minlength=hi + 1)
        small = [i for i in range(lo, hi + 1) if 0 < counts[i] < min_px]
        if not small:
            break
        moved = 0
        for sid in small:
            m = labels == sid
            if not m.any():
                continue
            v = _nb_ids(m)
            if v is None:
                continue
            v = v[v != sid]
            # 先找海邻居，再退到陆省
            sea_nb = v[(v > n_land) & (v <= hi)]
            land_nb = v[(v >= 1) & (v <= n_land)]
            pick = None
            if sea_nb.size:
                pick = int(np.bincount(sea_nb).argmax())
            elif land_nb.size:
                pick = int(np.bincount(land_nb).argmax())
            if pick is None:
                continue
            labels[m] = pick
            moved += 1
        if not moved:
            break

    # 海省 id 连续重编号（不能留空洞：definition.csv 按 1..max 写，空洞会变成 0 像素省）
    present = [i for i in range(lo, hi + 1) if (labels == i).any()]
    remap = {}
    for new, old in enumerate(present, start=n_land + 1):
        remap[old] = new
    if len(present) != sea_n or any(k != v for k, v in remap.items()):
        buf = labels.copy()
        for old, new in remap.items():
            if old != new:
                buf[labels == old] = new
        labels = buf
    sea_n = len(present)
    sea_ids = set(range(n_land + 1, n_land + sea_n + 1))
    if say:
        say("  海省收尾：并掉小省并重编号 → %d 个海省" % sea_n)
    return labels, sea_n, sea_ids


def generate(source="procedural", out_dir=None, width=1024, height=512,
             n_provinces=180, min_size=300, seed=11, src_path=None,
             sea_level=0.42, template_map=HOI4_MAP, log=None,
             balance=True, min_province_px=800,
             n_regions=None, n_supply=None, bbox=None, rivers_path=None,
             cities_path=None, city_radius=4,
             scaffold=False, mod_name="雪绒地图测试", mod_tag="ZZZ",
             per_state=8):
    """生成完整 map/ 目录。

    source:
      procedural  程序化（分形噪声大陆）
      lineart     黑白线稿
      mask        海陆掩码
      image       任意图片按色块
    """
    out = []
    # 尺寸强制对齐 256，避免调用方传了非倍数导致加载期崩
    width = _align256(width)
    height = _align256(height)
    gnames = {}
    thint = None
    rmask = None
    cmask = None
    def say(t):
        out.append(t)
        if log:
            log(t)

    if not out_dir:
        return {"ok": False, "msg": "没给输出目录", "log": out}

    if source == "procedural":
        say("生成程序化大陆 %dx%d，%d 个省…" % (width, height, n_provinces))
        labels, land = core.procedural(width, height, n_provinces, seed, sea_level)
    elif source == "lineart":
        if not src_path or not os.path.isfile(src_path):
            return {"ok": False, "msg": "线稿文件不存在", "log": out}
        say("读线稿 %s…" % os.path.basename(src_path))
        labels, land = core.from_lineart(src_path, min_size)
    elif source == "mask":
        if not src_path or not os.path.isfile(src_path):
            return {"ok": False, "msg": "掩码文件不存在", "log": out}
        say("读海陆掩码 %s…" % os.path.basename(src_path))
        labels, land = core.from_mask(src_path, n_provinces, min_size, seed)
    elif source == "image":
        if not src_path or not os.path.isfile(src_path):
            return {"ok": False, "msg": "图片文件不存在", "log": out}
        say("按色块切省 %s…" % os.path.basename(src_path))
        labels, land = core.from_image(src_path, min_size)
    elif source == "geojson":
        if not src_path or not os.path.isfile(src_path):
            return {"ok": False, "msg": "GeoJSON 文件不存在", "log": out}
        say("读矢量行政区划 %s…" % os.path.basename(src_path))
        bb = None
        if bbox and len(bbox) == 4:
            bb = tuple(float(x) for x in bbox)
        if not bb:
            # 先算行政区划的 bbox，后面河流要用同一个，否则河道和陆地对不上
            bb = mgs.geojson_bbox(src_path)
        labels, land, gnames = mgs.from_geojson(
            src_path, max(200, int(width)), max(100, int(height)),
            bb, min_size, seed=seed)
        if labels is None:
            return {"ok": False, "msg": "GeoJSON 解析失败或为空", "log": out}
        say("  得到 %d 个省（真实行政区划）" % int(labels.max()))
        if rivers_path and os.path.isfile(rivers_path):
            say("读河流线 %s…" % os.path.basename(rivers_path))
            hh, ww = labels.shape
            rmask = mgs.rivers_from_geojson(rivers_path, ww, hh, bb)
            if rmask is not None:
                say("  河道 %d 像素" % int(rmask.sum()))
            else:
                say("  河流文件没解析出线段，跳过")
        if cities_path and os.path.isfile(cities_path):
            say("读城市点 %s…" % os.path.basename(cities_path))
            hh2, ww2 = labels.shape
            cmask = mgs.cities_from_geojson(cities_path, ww2, hh2, bb,
                                            int(city_radius))
            if cmask is not None:
                say("  城市区域 %d 像素" % int((cmask > 0).sum()))
            else:
                say("  城市文件没解析出点，跳过")
    elif source == "terrain_map":
        if not src_path or not os.path.isfile(src_path):
            return {"ok": False, "msg": "地图图片不存在", "log": out}
        say("识别真实地图 %s…" % os.path.basename(src_path))
        labels, land, thint, rmask = mgs.from_terrain_map(
            src_path, max(200, int(width)), max(100, int(height)),
            n_provinces, min_size, seed)
        say("  得到 %d 个省，地形与河流已识别" % int(labels.max()))
    else:
        return {"ok": False, "msg": "未知来源：%s" % source, "log": out}

    n = int(labels.max())
    say("得到 %d 个省，陆地 %d 像素" % (n, int(land.sum())))
    if n == 0:
        return {"ok": False, "msg": "没有识别出任何省", "log": out}

    if balance:
        say("均衡省大小（下限 %d 像素）…" % min_province_px)
        before = n
        labels = mgx.balance_sizes(labels, min_province_px)
        n = int(labels.max())
        land = labels > 0
        say("  %d → %d 个省" % (before, n))

    # 海也要成省：not-land 切连通块，id 接在陆省后面（n+1 .. n+sea_n）
    say("切分海省…")
    sea_ids = set()
    sea_n = 0
    try:
        import mapgen_sea as mgsea
        sea_arr, sea_n = mgsea.split_sea(land)
        if sea_n:
            labels = np.where(land, labels, sea_arr + n)
            sea_ids = set(range(n + 1, n + sea_n + 1))
            say("  %d 个海省（id %d..%d）" % (sea_n, n + 1, n + sea_n))
        else:
            say("  没有海，跳过")
    except Exception as e:
        say("  海省切分失败：%s" % str(e)[:80])

    # 收尾：把still很小的海省并掉，并连续重编号
    # （split_sea 内部已经吸收过一轮，这里补「被陆地包死的 1 像素小湖」——
    #   它们没有海邻居，只能并进周围的陆省。实测 167 个海省里有 57 个 ≤8 像素，
    #   其中 10 个只有 1 像素；退化省在地图初始化时要算邻接和海军寻路。）
    if sea_n:
        labels, sea_n, sea_ids = _clean_tiny_sea(labels, n, sea_n, sea_ids, say)

    n_all = n + sea_n
    colors = core.unique_colors(n_all, seed)
    say("分配了 %d 个唯一颜色" % len(colors))

    # 陆省按质心纬度分洲（continent.txt 的 ID 顺序 = 这里的 1..7）
    # 质心另有两个用途：unitstacks / buildings / weatherpositions 三张坐标表都要它，
    # 所以这里无条件算一次（早前只在分洲的 try 里算，失败就没有）。
    try:
        cen = mgx.centroids(labels)
        cen = {int(k): (round(float(v[0]), 2), round(float(v[1]), 2))
               for k, v in cen.items() if int(k) > 0}
        say("  质心 %d 个省" % len(cen))
    except Exception as e:
        cen = {}
        say("  质心计算失败：%s" % str(e)[:60])
    conts = {}
    try:
        for pid in range(1, n + 1):
            y = cen.get(pid, (0.0, 0.0))[1]
            band = int(y / max(1.0, float(labels.shape[0])) * 7) + 1
            conts[pid] = min(7, max(1, band))
    except Exception as e:
        say("  分洲失败，全归 1 号洲：%s" % str(e)[:60])

    map_dir = os.path.join(out_dir, "map")
    os.makedirs(map_dir, exist_ok=True)

    say("写 provinces.bmp…")
    mgw.write_provinces(labels, colors, os.path.join(map_dir, "provinces.bmp"))
    say("写 definition.csv…")
    mgw.write_definition_csv(labels, colors, os.path.join(map_dir, "definition.csv"),
                             names=gnames, continents=conts, sea_ids=sea_ids)
    say("写 heightmap.bmp…")
    mgw.write_heightmap(
        land, os.path.join(map_dir, "heightmap.bmp"),
        palette_from=os.path.join(template_map, "heightmap.bmp") if template_map else None)
    say("写 world_normal.bmp…")
    try:
        mgw.write_world_normal(os.path.join(map_dir, "heightmap.bmp"),
                               os.path.join(map_dir, "world_normal.bmp"))
    except Exception as e:
        say("  法线图失败（可忽略）：%s" % str(e)[:60])
    say("写 terrain.bmp（按地形提示）…")
    size = _detect_size(labels)
    _pal = os.path.join(template_map, "terrain.bmp") if template_map else None
    mgw.write_terrain(labels, thint, os.path.join(map_dir, "terrain.bmp"), _pal,
                      sea_mask=(~land))
    if rmask is not None:
        rmask = rmask & (labels > 0)   # 河道不落在海里
    mgw.write_rivers(labels, rmask, os.path.join(map_dir, "rivers.bmp"),
                     os.path.join(template_map, "rivers.bmp") if template_map else None,
                     sea_mask=(~land))
    _tarr = None
    if thint is not None:
        _tarr = np.full(labels.shape, 0, dtype=np.uint8)
        _tarr[~land] = 15
        _tarr[land & (thint == 1)] = 2
        _tarr[land & (thint == 2)] = 11
        _tarr[land & (thint == 3)] = 16
        _tarr[land & (thint == 4)] = 3
    mgw.write_cities(labels, _tarr, os.path.join(map_dir, "cities.bmp"),
                     os.path.join(template_map, "cities.bmp") if template_map else None,
                     city_mask=cmask)
    mgw.write_blank_indexed(
        size, os.path.join(map_dir, "trees.bmp"),
        palette_from=os.path.join(template_map, "trees.bmp") if template_map else None)
    say("写 default.map / continent.txt…")
    mgw.write_default_map(os.path.join(map_dir, "default.map"), n)
    mgw.write_continent_txt(os.path.join(map_dir, "continent.txt"))

    if template_map and os.path.isdir(template_map):
        say("从原版复制模板文件…")
        copied = mgw.copy_template_dir(template_map, map_dir)
        say("  复制了 %s" % ", ".join(copied))
    else:
        say("  没找到原版 map 目录，跳过模板复制")

    say("写空文件…")
    mgw.write_empty_texts(map_dir, size=size)
    # 三张坐标表必须按自己的图重写（原版坐标是 5632×2048 空间，在我们 1024×512
    # 的图上每一个点都越界）。州号要等建完州才有，所以 buildings 这一步先不写，
    # 由 scaffold / world_create 拿着真实州表再补。
    try:
        mp = mgw.write_map_positions(map_dir, cen, size=size)
        say("  坐标表：unitstacks %d 行 / weather %d 行"
            % (mp["unitstacks"], mp["weather"]))
    except Exception as e:
        say("  坐标表失败：%s" % str(e)[:60])
    say("按地理位置聚类…")
    try:
        nreg = int(n_regions) if n_regions else max(1, (n + 59) // 60)
        gr = mgx.group_provinces_by_location(labels, nreg, seed)
        nsup = int(n_supply) if n_supply else max(1, (n + 119) // 120)
        gs = mgx.group_provinces_by_location(labels, nsup, seed + 1)
        say("  %d 个地理组（战略区）、%d 个（补给区）" % (len(gr), len(gs)))
    except Exception as e:
        say("  聚类失败，退回顺序切分：%s" % str(e)[:60])
        gr = gs = None
    say("生成战略区…")
    r = mgw.write_strategic_regions(map_dir, labels, gr)
    say("  %d 个战略区" % r)
    say("生成补给区…")
    if scaffold:
        # 州还没建，写不出正确的州号；等 scaffold 建完州会用
        # write_supply_graph 按真实州号重写补给区和 supply_nodes.txt
        say("  跳过（交给 scaffold 按真实州号重写）")
        sup = 0
    else:
        sup = mgw.write_supply_areas(map_dir, labels, gs)
        say("  %d 个补给区（省号占位，仅供地图预览）" % sup)

    meta = {"source": source, "width": size[0], "height": size[1],
            "provinces": n, "seed": seed,
            "land_pixels": int(land.sum())}
    io.open(os.path.join(out_dir, "mapgen.json"), "w", encoding="utf-8",
            newline="").write(json.dumps(meta, ensure_ascii=False, indent=1))
    if scaffold:
        say("补齐 mod 骨架（descriptor / states / 国家 / 本地化）…")
        try:
            sc = mgsc.build(out_dir, labels, mod_name, mod_tag, int(per_state),
                            sea_ids=sea_ids)
            if sc.get("ok"):
                for m in sc["made"]:
                    say("  " + m)
            else:
                say("  骨架失败：" + (sc.get("msg") or ""))
        except Exception as e:
            say("  骨架失败：%s" % str(e)[:80])

    say("完成：%d 个省，%dx%d" % (n, size[0], size[1]))
    return {"ok": True, "province_count": n, "width": size[0],
            "height": size[1], "map_dir": map_dir, "log": out,
            "centroids": cen,
            "msg": "已生成 %d 个省的地图（%dx%d）" % (n, size[0], size[1])}
