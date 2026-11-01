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

    n_all = n + sea_n
    colors = core.unique_colors(n_all, seed)
    say("分配了 %d 个唯一颜色" % len(colors))

    # 陆省按质心纬度分洲（continent.txt 的 ID 顺序 = 这里的 1..7）
    conts = {}
    try:
        cen = mgx.centroids(labels)
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
    mgw.write_terrain(labels, thint, os.path.join(map_dir, "terrain.bmp"), _pal)
    if rmask is not None:
        rmask = rmask & (labels > 0)   # 河道不落在海里
    mgw.write_rivers(labels, rmask, os.path.join(map_dir, "rivers.bmp"),
                     os.path.join(template_map, "rivers.bmp") if template_map else None)
    _tarr = None
    if thint is not None:
        _tarr = np.full(labels.shape, 0, dtype=np.uint8)
        _tarr[labels == 0] = 15
        _land = labels > 0
        _tarr[_land & (thint == 1)] = 2
        _tarr[_land & (thint == 2)] = 11
        _tarr[_land & (thint == 3)] = 16
        _tarr[_land & (thint == 4)] = 3
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
            "msg": "已生成 %d 个省的地图（%dx%d）" % (n, size[0], size[1])}
