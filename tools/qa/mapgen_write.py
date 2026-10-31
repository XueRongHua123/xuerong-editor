# -*- coding: utf-8 -*-
"""把 labels 数组写成完整的 HOI4 map/ 目录。"""
import io
import os
import shutil
import numpy as np
from PIL import Image

# HOI4 常用固定色
SEA = (0, 0, 0)          # 省图里的海（会被 definition.csv 标成 sea）
DEFAULT_TERRAIN_INDEX = 0


def _ensure(d):
    os.makedirs(d, exist_ok=True)


def write_provinces(labels, colors, path):
    """labels: int32 (0=海)；colors: 每省 RGB 列表。输出 24 位 bmp。"""
    h, w = labels.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    # 海 = SEA
    rgb[:, :] = SEA
    n = int(labels.max())
    for i in range(1, n + 1):
        c = colors[i - 1] if i - 1 < len(colors) else (1, 1, 1)
        rgb[labels == i] = c
    Image.fromarray(rgb, "RGB").save(path)


def write_definition_csv(labels, colors, path, name_prefix="PROV", names=None):
    """每省一行：id;r;g;b;land;terrain;continent;name

    names 给了就用真实省名（GeoJSON 来源）。
    """
    n = int(labels.max())
    names = names or {}
    lines = ["0;0;0;0;sea;ocean;0;"]
    for i in range(1, n + 1):
        c = colors[i - 1] if i - 1 < len(colors) else (1, 1, 1)
        nm = str(names.get(i) or (name_prefix + str(i))).replace(";", ",")
        lines.append("%d;%d;%d;%d;land;plains;0;%s" % (
            i, c[0], c[1], c[2], nm))
    io.open(path, "w", encoding="utf-8", newline="").write("\n".join(lines) + "\n")

# 原版 terrain.bmp 的常用索引（实测自 HoI4 1.19 的调色板）
TERRAIN_PLAINS = 0     # (86,124,27) 绿
TERRAIN_FOREST = 1     # (0,86,6)    深绿
TERRAIN_HILLS = 2      # (112,74,31) 褐
TERRAIN_DESERT = 3     # (206,169,99) 沙
TERRAIN_GRASS = 4      # (6,200,11)  亮绿
TERRAIN_MOUNTAIN = 11  # (92,83,76)  灰
TERRAIN_SEA = 15       # (8,31,130)  深蓝
TERRAIN_SNOW = 16      # (255,255,255) 白


def write_terrain(labels, thint, path, palette_from=None):
    """按地形提示写 terrain.bmp。

    labels  省图（0 = 海）
    thint   地形提示（0 plains / 1 hills / 2 mountain / 3 snow / 4 desert），
            可为 None
    palette_from  从哪个文件借调色板（一般是原版 terrain.bmp）
    """
    h, w = labels.shape
    arr = np.full((h, w), TERRAIN_PLAINS, dtype=np.uint8)
    # 海
    arr[labels == 0] = TERRAIN_SEA
    if thint is not None and thint.shape == labels.shape:
        land = labels > 0
        arr[land & (thint == 1)] = TERRAIN_HILLS
        arr[land & (thint == 2)] = TERRAIN_MOUNTAIN
        arr[land & (thint == 3)] = TERRAIN_SNOW
        arr[land & (thint == 4)] = TERRAIN_DESERT
    img = Image.fromarray(arr, "L").convert("P")
    pal = None
    if palette_from and os.path.isfile(palette_from):
        try:
            pal = Image.open(palette_from).getpalette()
        except Exception:
            pal = None
    if not pal:
        # 兜底：造一个够用的调色板
        pal = [0] * (256 * 3)
        pal[TERRAIN_PLAINS*3:TERRAIN_PLAINS*3+3] = [86, 124, 27]
        pal[TERRAIN_FOREST*3:TERRAIN_FOREST*3+3] = [0, 86, 6]
        pal[TERRAIN_HILLS*3:TERRAIN_HILLS*3+3] = [112, 74, 31]
        pal[TERRAIN_DESERT*3:TERRAIN_DESERT*3+3] = [206, 169, 99]
        pal[TERRAIN_GRASS*3:TERRAIN_GRASS*3+3] = [6, 200, 11]
        pal[TERRAIN_MOUNTAIN*3:TERRAIN_MOUNTAIN*3+3] = [92, 83, 76]
        pal[TERRAIN_SEA*3:TERRAIN_SEA*3+3] = [8, 31, 130]
        pal[TERRAIN_SNOW*3:TERRAIN_SNOW*3+3] = [255, 255, 255]
    img.putpalette(pal)
    img.save(path)


def write_heightmap(land, path, base=110, noise=18, seed=5):
    """海 = 0，陆 = base ± noise。8 位灰度 bmp。"""
    rng = np.random.default_rng(seed)
    h, w = land.shape
    hh = np.zeros((h, w), dtype=np.float32)
    hh[land] = base
    n = rng.normal(0, noise, (h, w)).astype(np.float32)
    # 平滑一下，避免噪点太碎
    k = 5
    for _ in range(2):
        n = (np.roll(n, 1, 0) + np.roll(n, -1, 0) + np.roll(n, 1, 1) + np.roll(n, -1, 1) + n) / 5.0
    hh = np.where(land, np.clip(hh + n, 1, 255), 0)
    Image.fromarray(hh.astype(np.uint8), "L").save(path)


def write_world_normal(heightmap_path, out_path):
    """由高度图算法线图（半分辨率 24 位）。"""
    a = np.array(Image.open(heightmap_path).convert("L"), dtype=np.float32) / 255.0
    gy, gx = np.gradient(a)
    nx = -gx * 8.0
    ny = -gy * 8.0
    nz = np.ones_like(a)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-9
    nx, ny, nz = nx / ln, ny / ln, nz / ln
    rgb = np.stack([(nx * 0.5 + 0.5) * 255, (ny * 0.5 + 0.5) * 255, (nz * 0.5 + 0.5) * 255], axis=2)
    img = Image.fromarray(rgb.clip(0, 255).astype(np.uint8), "RGB")
    img = img.resize((img.width // 2, img.height // 2), Image.BILINEAR)
    img.save(out_path)


def write_blank_indexed(size, out_path, fill=0):
    """写一张全 fill 的 8 位 bmp。"""
    w, h = size
    Image.fromarray(np.full((h, w), fill, dtype=np.uint8), "L").convert("P").save(out_path)


def write_continent_txt(path, n_continents=1):
    lines = []
    for i in range(n_continents):
        lines.append("continent_%d = {" % i)
        lines.append("\tprovinces = {")
        lines.append("\t\t# 手工补或让生成器填")
        lines.append("\t}")
        lines.append("}")
    io.open(path, "w", encoding="utf-8", newline="").write("\n".join(lines) + "\n")


DEFAULT_MAP = """max_provinces = %d
sea_starts = { 0 }
only_used_for_random = { }
"""


def write_default_map(path, n_provinces):
    io.open(path, "w", encoding="utf-8", newline="").write(
        DEFAULT_MAP % max(1, n_provinces + 1))


def copy_template_dir(src_root, out_root):
    """从原版/模板复制那些不需要改的文件。"""
    copied = []
    for rel in ("terrain",):
        s = os.path.join(src_root, rel)
        d = os.path.join(out_root, rel)
        if os.path.isdir(s):
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
            shutil.copytree(s, d)
            copied.append(rel)
    for rel in ("adjacencies.csv", "adjacency_rules.txt", "colors.txt",
                "seasons.txt", "ambient_object.txt", "weatherpositions.txt"):
        s = os.path.join(src_root, rel)
        d = os.path.join(out_root, rel)
        if os.path.isfile(s):
            shutil.copyfile(s, d)
            copied.append(rel)
    return copied


def write_empty_texts(out_root):
    """写那些可以留空的文件。"""
    written = []
    for rel, content in (
        ("railways.txt", ""),
        ("buildings.txt", ""),
        ("cities.txt", ""),
        ("supply_nodes.txt", ""),
        ("positions.txt", ""),
        ("unitstacks.txt", ""),
    ):
        p = os.path.join(out_root, rel)
        if not os.path.exists(p):
            io.open(p, "w", encoding="utf-8", newline="").write(content)
            written.append(rel)
    return written


def write_strategic_regions(out_root, labels, groups=None, per_region=60):
    """写战略区。groups 给了就按地理聚类分组，否则按 id 顺序切。"""
    d = os.path.join(out_root, "strategicregions")
    _ensure(d)
    n = int(labels.max())
    if n == 0:
        return 0
    made = 0
    rid = 1
    if groups:
        order = sorted(groups.keys())
        for g in order:
            pids = sorted(groups[g])
            if not pids:
                continue
            body = ("strategic_region={\n\tid=%d\n\tname=\"REGION_%d\"\n"
                    "\tprovinces={\n%s\n\t}\n\tweather={\n\t\tperiod={\n"
                    "\t\t\ttemperature={\n\t\t\t\tmin=0\n\t\t\t\tmax=0\n\t\t\t}\n"
                    "\t\t}\n\t}\n}\n") % (
                rid, rid, "".join("\t\t%d\n" % x for x in pids))
            io.open(os.path.join(d, "%d-region.txt" % rid), "w", encoding="utf-8",
                    newline="").write(body)
            made += 1
            rid += 1
        return made
    for start in range(1, n + 1, per_region):
        end = min(n, start + per_region - 1)
        pids = list(range(start, end + 1))
        body = ("strategic_region={\n\tid=%d\n\tname=\"REGION_%d\"\n"
                "\tprovinces={\n%s\n\t}\n\tweather={\n\t\tperiod={\n"
                "\t\t\ttemperature={\n\t\t\t\tmin=0\n\t\t\t\tmax=0\n\t\t\t}\n"
                "\t\t}\n\t}\n}\n") % (
            rid, rid, "".join("\t\t%d\n" % x for x in pids))
        io.open(os.path.join(d, "%d-region.txt" % rid), "w", encoding="utf-8",
                newline="").write(body)
        made += 1
        rid += 1
    return made


def write_supply_areas(out_root, labels, groups=None, per_area=120):
    """写补给区。groups 给了就按地理聚类分组。"""
    d = os.path.join(out_root, "supplyareas")
    _ensure(d)
    n = int(labels.max())
    if n == 0:
        return 0
    made = 0
    sid = 1
    if groups:
        for g in sorted(groups.keys()):
            pids = sorted(groups[g])
            if not pids:
                continue
            body = ("supply_area={\n\tid=%d\n\tname=\"SUPPLYAREA_%d\"\n\tvalue=10\n"
                    "\tstates={\n%s\n\t}\n}\n") % (
                sid, sid, "".join("\t\t%d\n" % x for x in pids))
            io.open(os.path.join(d, "%d-SupplyArea.txt" % sid), "w", encoding="utf-8",
                    newline="").write(body)
            made += 1
            sid += 1
        return made
    for start in range(1, n + 1, per_area):
        end = min(n, start + per_area - 1)
        states = list(range(start, end + 1))
        body = ("supply_area={\n\tid=%d\n\tname=\"SUPPLYAREA_%d\"\n\tvalue=10\n"
                "\tstates={\n%s\n\t}\n}\n") % (
            sid, sid, "".join("\t\t%d\n" % x for x in states))
        io.open(os.path.join(d, "%d-SupplyArea.txt" % sid), "w", encoding="utf-8",
                newline="").write(body)
        made += 1
        sid += 1
    return made
