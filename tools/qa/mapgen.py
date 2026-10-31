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

HOI4_MAP = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV\map'


def _detect_size(labels):
    h, w = labels.shape
    return w, h


def generate(source="procedural", out_dir=None, width=1200, height=440,
             n_provinces=180, min_size=300, seed=11, src_path=None,
             sea_level=0.42, template_map=HOI4_MAP, log=None):
    """生成完整 map/ 目录。

    source:
      procedural  程序化（分形噪声大陆）
      lineart     黑白线稿
      mask        海陆掩码
      image       任意图片按色块
    """
    out = []
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
    else:
        return {"ok": False, "msg": "未知来源：%s" % source, "log": out}

    n = int(labels.max())
    say("得到 %d 个省，陆地 %d 像素" % (n, int(land.sum())))
    if n == 0:
        return {"ok": False, "msg": "没有识别出任何省", "log": out}

    colors = core.unique_colors(n, seed)
    say("分配了 %d 个唯一颜色" % len(colors))

    map_dir = os.path.join(out_dir, "map")
    os.makedirs(map_dir, exist_ok=True)

    say("写 provinces.bmp…")
    mgw.write_provinces(labels, colors, os.path.join(map_dir, "provinces.bmp"))
    say("写 definition.csv…")
    mgw.write_definition_csv(labels, colors, os.path.join(map_dir, "definition.csv"))
    say("写 heightmap.bmp…")
    mgw.write_heightmap(land, os.path.join(map_dir, "heightmap.bmp"))
    say("写 world_normal.bmp…")
    try:
        mgw.write_world_normal(os.path.join(map_dir, "heightmap.bmp"),
                               os.path.join(map_dir, "world_normal.bmp"))
    except Exception as e:
        say("  法线图失败（可忽略）：%s" % str(e)[:60])
    say("写 terrain.bmp / rivers / cities / trees…")
    size = _detect_size(labels)
    mgw.write_blank_indexed(size, os.path.join(map_dir, "terrain.bmp"))
    mgw.write_blank_indexed(size, os.path.join(map_dir, "rivers.bmp"))
    mgw.write_blank_indexed(size, os.path.join(map_dir, "cities.bmp"))
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
    say("生成战略区…")
    r = mgw.write_strategic_regions(map_dir, labels)
    say("  %d 个战略区" % r)
    say("生成补给区…")
    s = mgw.write_supply_areas(map_dir, labels)
    say("  %d 个补给区" % s)

    meta = {"source": source, "width": size[0], "height": size[1],
            "provinces": n, "seed": seed,
            "land_pixels": int(land.sum())}
    io.open(os.path.join(out_dir, "mapgen.json"), "w", encoding="utf-8",
            newline="").write(json.dumps(meta, ensure_ascii=False, indent=1))
    say("完成：%d 个省，%dx%d" % (n, size[0], size[1]))
    return {"ok": True, "province_count": n, "width": size[0],
            "height": size[1], "map_dir": map_dir, "log": out,
            "msg": "已生成 %d 个省的地图（%dx%d）" % (n, size[0], size[1])}
