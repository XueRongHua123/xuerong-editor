# -*- coding: utf-8 -*-
"""把 labels 数组写成完整的 HOI4 map/ 目录。"""
import io
import os
import shutil
import struct
import numpy as np
from PIL import Image

# HOI4 常用固定色
SEA = (0, 0, 0)          # 旧版留给海的占位色；现在海必须是真省，只当兜底
DEFAULT_TERRAIN_INDEX = 0

# continent.txt 的 ID 顺序 = 这里的顺序（1 起）。definition.csv 第 8 列引用它。
DEFAULT_CONTINENTS = ("europe", "north_america", "south_america",
                      "australia", "africa", "asia", "middle_east")


def _palette_bytes(src_path):
    """直接从 BMP 文件里抠 1024 字节调色板。

    原版这些图是 8 位、biClrUsed=0（没写颜色数）但文件里确实带 1024 字节调色板。
    Pillow 的 getpalette() 对这种头有时返回 None，一旦走了兜底灰阶调色板，
    引擎就报 Palette in rivers.bmp is probably not correct。
    """
    try:
        with io.open(src_path, "rb") as f:
            head = f.read(54)
            if len(head) < 54 or head[:2] != b"BM":
                return None
            bpp = int.from_bytes(head[28:30], "little")
            if bpp != 8:
                return None
            off = int.from_bytes(head[10:14], "little")
            n = off - 54
            if not (0 < n <= 1024):
                return None
            f.seek(54)
            data = f.read(n)
            if len(data) < n:
                return None
            return list(data)
    except Exception:
        return None


def _write_indexed_bmp(path, arr, template=None):
    """写 8 位 indexed BMP：头部与调色板整段照抄原版文件，只换尺寸和像素。

    原版各图调色板长度并不一样（rivers 1024 / terrain 1104 / cities 1020 /
    trees 1108 字节），biClrUsed 分别是 0 / 255 / 256。自己拼一份 256 色调色板
    必然对不上，引擎直接 MAP_ERROR: Palette in xxx.bmp is probably not correct。
    """
    h, w = arr.shape
    row = (w + 3) // 4 * 4
    pad = row - w
    a = arr.astype(np.uint8)
    parts = []
    for y in range(h - 1, -1, -1):          # BMP 自下而上
        parts.append(a[y].tobytes() + b"\x00" * pad)
    raw = b"".join(parts)

    head = None
    if template and os.path.isfile(template):
        t = io.open(template, "rb").read(8192)
        if t[:2] == b"BM":
            off = int.from_bytes(t[10:14], "little")
            if 54 <= off <= len(t):
                head = bytearray(t[:off])
    if head is None:
        # 没有模板：灰阶兜底（尺寸对、能读，但调色板未必被引擎接受）
        plt = b"".join(bytes((i, i, i, 0)) for i in range(256))
        head = bytearray(b"BM" + struct.pack("<IHHI", 0, 0, 0, 54 + len(plt)) +
                         struct.pack("<IiiHHIIiiII", 40, w, h, 1, 8, 0,
                                     len(raw), 2835, 2835, 0, 0) + plt)
    head[2:6] = struct.pack("<I", len(head) + len(raw))
    head[18:22] = struct.pack("<i", w)
    head[22:26] = struct.pack("<i", h)
    head[34:38] = struct.pack("<I", len(raw))
    f = io.open(path, "wb")
    try:
        f.write(bytes(head) + raw)
    finally:
        f.close()


def _ensure(d):
    os.makedirs(d, exist_ok=True)


def write_provinces(labels, colors, path):
    """labels: int32（1..n，海省也在里面）；colors[i-1] 是省 i 的 RGB。输出 24 位 bmp。

    HOI4 不认「没上色的像素」：provinces.bmp 里每个像素都必须落在
    definition.csv 声明过的颜色上。给海留 (0,0,0) 的旧做法会让引擎
    自己补一个 land 省（error.log: prov N has no continent），
    海就变成陆地，地图加载直接停住。
    """
    h, w = labels.shape
    n = int(labels.max())
    lut = np.zeros((n + 1, 3), dtype=np.uint8)
    for i in range(1, n + 1):
        c = colors[i - 1] if i - 1 < len(colors) else (1, 1, 1)
        lut[i] = (int(c[0]), int(c[1]), int(c[2]))
    rgb = lut[np.clip(labels, 0, n)]
    if (labels == 0).any():
        rgb[labels == 0] = SEA
    Image.fromarray(rgb.astype(np.uint8), "RGB").save(path)


def _neighbor_any(mask):
    """4 邻域：这个像素周围有没有 mask 为 True 的点。"""
    h, w = mask.shape
    out = np.zeros_like(mask)
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def write_definition_csv(labels, colors, path, name_prefix="PROV", names=None,
                         continents=None, sea_ids=None,
                         n_continents=len(DEFAULT_CONTINENTS)):
    """写 definition.csv。列序按原版实测：

        省id ; R ; G ; B ; 类型 ; 是否沿海 ; 地形 ; 大洲id

    三条硬约束（哪条违反，游戏都在加载期停住，日志里只有一句
    prov N has no continent，看不出是这里）：

      1. 行尾必须 CRLF。LF 会让每行的 continent 列读不到。
      2. 陆省的大洲必须是 1..n_continents，不能是 0。
      3. 海省写成 sea + ocean + 大洲 0；一个 sea 省都没有的话，
         海像素会被引擎补成 land 省。

    continents / sea_ids 都可以不给：不给就全算 1 号洲、没有海省。
    """
    n = int(labels.max())
    names = names or {}
    conts = continents or {}
    seas = set(sea_ids or ())
    sea_mask = np.isin(labels, list(seas)) if seas else np.zeros(labels.shape, bool)
    land_mask = (labels > 0) & ~sea_mask
    coastal = set(int(v) for v in np.unique(
        labels[_neighbor_any(sea_mask) & land_mask]))
    coastal |= set(int(v) for v in np.unique(
        labels[_neighbor_any(land_mask) & sea_mask]))

    lines = ["0;0;0;0;land;false;unknown;0"]
    for i in range(1, n + 1):
        c = colors[i - 1] if i - 1 < len(colors) else (1, 1, 1)
        is_sea = i in seas
        typ = "sea" if is_sea else "land"
        coast = "true" if i in coastal else "false"
        terrain = "ocean" if is_sea else "plains"
        if is_sea:
            cont = 0
        else:
            cont = int(conts.get(i, 1))
            cont = min(n_continents, max(1, cont))
        lines.append("%d;%d;%d;%d;%s;%s;%s;%d" % (
            i, int(c[0]), int(c[1]), int(c[2]), typ, coast, terrain, cont))
    body = "\r\n".join(lines) + "\r\n"
    io.open(path, "w", encoding="utf-8", newline="").write(body)
    # 省名另存一份，供本地化或地图工具用
    if names:
        try:
            import json as _j
            np_ = os.path.join(os.path.dirname(path) or ".", "province_names.json")
            io.open(np_, "w", encoding="utf-8").write(
                _j.dumps({str(k): v for k, v in names.items()}, ensure_ascii=False))
        except Exception:
            pass

# 原版 terrain.bmp 的常用索引（实测自 HoI4 1.19 的调色板）
TERRAIN_PLAINS = 0     # (86,124,27) 绿
TERRAIN_FOREST = 1     # (0,86,6)    深绿
TERRAIN_HILLS = 2      # (112,74,31) 褐
TERRAIN_DESERT = 3     # (206,169,99) 沙
TERRAIN_GRASS = 4      # (6,200,11)  亮绿
TERRAIN_MOUNTAIN = 11  # (92,83,76)  灰
TERRAIN_SEA = 15       # (8,31,130)  深蓝
TERRAIN_SNOW = 16      # (255,255,255) 白


# rivers.bmp 的常用索引（实测自 HoI4 1.19）
RIVER_LAND = 254      # (122,122,122) 陆地
RIVER_SEA = 255       # (255,255,255) 海
RIVER_MAIN = 3        # (0,225,255)   主流（青）
RIVER_TRIB = 6        # (0,100,255)   支流（蓝）
RIVER_SMALL = 4       # (0,200,255)   小溪
RIVER_DEEP = 11       # (0,0,100)     深河


def write_rivers(labels, rivers, path, palette_from=None):
    """写 rivers.bmp。

    labels  省图（0 = 海）
    rivers  bool 数组，True = 河（可为 None 表示无河）
    """
    h, w = labels.shape
    arr = np.full((h, w), RIVER_LAND, dtype=np.uint8)
    arr[labels == 0] = RIVER_SEA
    if rivers is not None and rivers.shape == labels.shape:
        arr[rivers] = RIVER_MAIN
    pal = _palette_bytes(palette_from) if palette_from else None
    if not pal:
        pal = [0] * (256 * 3)
        pal[RIVER_LAND*3:RIVER_LAND*3+3] = [122, 122, 122]
        pal[RIVER_SEA*3:RIVER_SEA*3+3] = [255, 255, 255]
        pal[RIVER_MAIN*3:RIVER_MAIN*3+3] = [0, 225, 255]
        pal[RIVER_TRIB*3:RIVER_TRIB*3+3] = [0, 100, 255]
        pal[RIVER_SMALL*3:RIVER_SMALL*3+3] = [0, 200, 255]
        pal[RIVER_DEEP*3:RIVER_DEEP*3+3] = [0, 0, 100]
    _write_indexed_bmp(path, arr, palette_from)


# cities.bmp 的语义（对比原版数据量推断）：
#   15 = 无城市（占 9.6M 像素，和地形图的海同色）
#   0 / 1 / 2 = 有城市，分别对应 cities.txt 里三组建筑的 color_index
CITY_NONE = 15
CITY_FOREIGN = 0


def write_cities(labels, terrain_idx, path, palette_from=None, city_mask=None,
                 city_index=CITY_FOREIGN):
    """写 cities.bmp。

    原版这张图不是「城市点」，而是「城市区域」：每个像素代表一块建筑，
    索引值对应 map/cities.txt 里各 city_group 的 color_index。

    city_mask 给了就用它标城市；没给就退回地形副本（旧行为）。
    """
    h, w = labels.shape
    if city_mask is not None and city_mask.shape == labels.shape:
        arr = np.full((h, w), CITY_NONE, dtype=np.uint8)
        arr[(city_mask > 0) & (labels > 0)] = city_index
    elif terrain_idx is not None and terrain_idx.shape == labels.shape:
        arr = terrain_idx.astype(np.uint8).copy()
    else:
        arr = np.full((h, w), TERRAIN_PLAINS, dtype=np.uint8)
        arr[labels == 0] = TERRAIN_SEA
    pal = _palette_bytes(palette_from) if palette_from else None
    if not pal:
        pal = [0] * (256 * 3)
        pal[TERRAIN_PLAINS*3:TERRAIN_PLAINS*3+3] = [86, 124, 27]
        pal[TERRAIN_SEA*3:TERRAIN_SEA*3+3] = [8, 31, 130]
        pal[TERRAIN_HILLS*3:TERRAIN_HILLS*3+3] = [112, 74, 31]
        pal[TERRAIN_FOREST*3:TERRAIN_FOREST*3+3] = [0, 86, 6]
        pal[CITY_NONE*3:CITY_NONE*3+3] = [8, 31, 130]
        pal[CITY_FOREIGN*3:CITY_FOREIGN*3+3] = [86, 124, 27]
    _write_indexed_bmp(path, arr, palette_from)


def _load_palette(palette_from):
    """兼容旧调用：优先按字节读，读不到再退回 Pillow。"""
    if not palette_from or not os.path.isfile(palette_from):
        return None
    b = _palette_bytes(palette_from)
    if b:
        return b
    try:
        return Image.open(palette_from).getpalette()
    except Exception:
        return None


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
    pal = _palette_bytes(palette_from) if palette_from else None
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
    _write_indexed_bmp(path, arr, palette_from)


def write_heightmap(land, path, base=110, noise=18, seed=5,
                   palette_from=None):
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
    _write_indexed_bmp(path, hh.astype(np.uint8), palette_from)


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


def write_blank_indexed(size, out_path, fill=0, palette_from=None):
    """写一张全 fill 的 8 位 bmp（trees.bmp 用），调色板按原版抄。"""
    w, h = size
    arr = np.full((h, w), fill, dtype=np.uint8)
    pal = _palette_bytes(palette_from) if palette_from else None
    _write_indexed_bmp(out_path, arr, palette_from)


def write_continent_txt(path, names=None):
    """continent.txt 是纯列表，不是键值块。

    正确：continents = { europe north_america ... }   （ID 按出现顺序 1 起）
    错误：continents = { europe = { 1 } }             （只剩 1 个名字，
           definition.csv 里的 2..7 全部越界）

    返回写了几个洲。
    """
    names = list(names or DEFAULT_CONTINENTS)
    body = "continents = {\r\n" + "".join("\t%s\r\n" % x for x in names) + "}\r\n"
    io.open(path, "w", encoding="utf-8", newline="").write(body)
    return len(names)


# default.map 是文件映射表，不是参数表。
# max_provinces / sea_starts 属于 definition.csv 的语义，写在这里游戏会报
# "Unexpected token: max_provinces" 并整张地图加载失败。
DEFAULT_MAP = """definitions = "definition.csv"
provinces = "provinces.bmp"
positions = "positions.txt"
terrain = "terrain.bmp"
rivers = "rivers.bmp"
heightmap = "heightmap.bmp"
tree_definition = "trees.bmp"
continent = "continent.txt"
adjacency_rules = "adjacency_rules.txt"
adjacencies = "adjacencies.csv"
ambient_object = "ambient_object.txt"
seasons = "seasons.txt"

tree = { 3 4 7 10 }
"""


def write_default_map(path, n_provinces=0):
    """写 default.map。n_provinces 参数保留兼容，实际不再写进这个文件。"""
    io.open(path, "w", encoding="utf-8", newline="").write(DEFAULT_MAP)


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
    # adjacencies.csv / adjacency_rules.txt / weatherpositions.txt 全按省号或战略区号
    # 引用原版数据，照抄会在新地图上报 "Province is invalid or added twice"。
    # 这三个不复制，由 write_empty_texts 生成空壳。
    for rel in ("colors.txt", "seasons.txt", "ambient_object.txt"):
        s = os.path.join(src_root, rel)
        d = os.path.join(out_root, rel)
        if os.path.isfile(s):
            shutil.copyfile(s, d)
            copied.append(rel)
    return copied


ADJ_HEADER = ("From;To;Type;Through;start_x;start_y;stop_x;stop_y;"
              "adjacency_rule_name;Comment\n")


def write_empty_texts(out_root, size=(1024, 512)):
    """写那些必须存在、但内容可以最简的文件。

    adjacencies.csv 只留表头：原版那些行按省号连海陆，换地图后省号全废。
    weatherpositions.txt 不能是空文件 —— 引擎要求至少各有一条 small / large，
    否则加载期崩；坐标放在地图中心附近就行。
    """
    w, h = size
    wp = ("1;%.2f;10.00;%.2f;small\n"
          "1;%.2f;10.00;%.2f;large\n") % (w / 2.0, h / 2.0, w / 2.0, h / 2.0)
    written = []
    for rel, content in (
        ("railways.txt", ""),
        ("buildings.txt", ""),
        ("cities.txt", ""),
        ("supply_nodes.txt", ""),
        ("positions.txt", ""),
        ("unitstacks.txt", ""),
        ("adjacencies.csv", ADJ_HEADER),
        ("adjacency_rules.txt", ""),
        ("weatherpositions.txt", wp),
    ):
        p = os.path.join(out_root, rel)
        if not os.path.exists(p):
            io.open(p, "w", encoding="utf-8", newline="").write(content)
            written.append(rel)
    return written


WEATHER_TEMPLATE = (
    "\tweather={\n"
    "\t\tperiod={\n"
    "\t\t\tbetween={ 0.0 30.0 }\n"
    "\t\t\ttemperature={ -6.0 12.0 }\n"
    "\t\t\tno_phenomenon=0.500\n"
    "\t\t\train_light=1.000\n"
    "\t\t\train_heavy=0.150\n"
    "\t\t\tsnow=0.200\n"
    "\t\t\tblizzard=0.000\n"
    "\t\t\tarctic_water=0.000\n"
    "\t\t\tmud=0.300\n"
    "\t\t\tsandstorm=0.000\n"
    "\t\t\tmin_snow_level=0.000\n"
    "\t\t}\n"
    "\t}\n"
)


def _region_body(rid, pids):
    """一个战略区的完整文本。

    weather 段必须按原版格式写：period 里要有 between（时间段）、
    temperature 是内联的 { 最小 最大 }，后面跟各天气概率。
    写成块形式（temperature={min=..max=..}）或漏掉 between，
    游戏会在地图加载阶段直接退出，error.log 里看不出原因。
    """
    return ("strategic_region={\n"
            "\tid=%d\n"
            "\tname=\"STRATEGICREGION_%d\"\n"
            "\tprovinces={\n%s\t}\n"
            "%s"
            "}\n") % (rid, rid, "".join("\t\t%d\n" % x for x in pids), WEATHER_TEMPLATE)


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
            body = _region_body(rid, pids)
            io.open(os.path.join(d, "%d-region.txt" % rid), "w", encoding="utf-8",
                    newline="").write(body)
            made += 1
            rid += 1
        return made
    for start in range(1, n + 1, per_region):
        end = min(n, start + per_region - 1)
        pids = list(range(start, end + 1))
        body = _region_body(rid, pids)
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
