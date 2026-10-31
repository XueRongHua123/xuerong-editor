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

HOI4_MAP = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV\map'


def _detect_size(labels):
    h, w = labels.shape
    return w, h


def generate(source="procedural", out_dir=None, width=1200, height=440,
             n_provinces=180, min_size=300, seed=11, src_path=None,
             sea_level=0.42, template_map=HOI4_MAP, log=None,
             balance=True, min_province_px=800,
             n_regions=None, n_supply=None, bbox=None, rivers_path=None):
    """生成完整 map/ 目录。

    source:
      procedural  程序化（分形噪声大陆）
      lineart     黑白线稿
      mask        海陆掩码
      image       任意图片按色块
    """
    out = []
    gnames = {}
    thint = None
    rmask = None
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

    colors = core.unique_colors(n, seed)
    say("分配了 %d 个唯一颜色" % len(colors))

    map_dir = os.path.join(out_dir, "map")
    os.makedirs(map_dir, exist_ok=True)

    say("写 provinces.bmp…")
    mgw.write_provinces(labels, colors, os.path.join(map_dir, "provinces.bmp"))
    say("写 definition.csv…")
    mgw.write_definition_csv(labels, colors, os.path.join(map_dir, "definition.csv"),
                             names=gnames)
    say("写 heightmap.bmp…")
    mgw.write_heightmap(land, os.path.join(map_dir, "heightmap.bmp"))
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
                     os.path.join(template_map, "cities.bmp") if template_map else None)
    mgw.write_blank_indexed(size, os.path.join(map_dir, "trees.bmp"))
    say("写 default.map / continent.txt…")
    mgw.write_default_map(os.path.join(map_dir, "default.map"), n)
    mgw.write_continent_txt(os.path.join(map_dir, "continent.txt"), 1)

    if template_map and os.path.isdir(template_map):
        say("从原版复制模板文件…")
        copied = mgw.copy_template_dir(template_map, map_dir)
        say("  复制了 %s" % ", ".join(copied))
    else:
        say("  没找到原版 map 目录，跳过模板复制")

    say("写空文件…")
    mgw.write_empty_texts(map_dir)
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
    sup = mgw.write_supply_areas(map_dir, labels, gs)
    say("  %d 个补给区" % sup)

    meta = {"source": source, "width": size[0], "height": size[1],
            "provinces": n, "seed": seed,
            "land_pixels": int(land.sum())}
    io.open(os.path.join(out_dir, "mapgen.json"), "w", encoding="utf-8",
            newline="").write(json.dumps(meta, ensure_ascii=False, indent=1))
    say("完成：%d 个省，%dx%d" % (n, size[0], size[1]))
    return {"ok": True, "province_count": n, "width": size[0],
            "height": size[1], "map_dir": map_dir, "log": out,
            "msg": "已生成 %d 个省的地图（%dx%d）" % (n, size[0], size[1])}
