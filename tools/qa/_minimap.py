# -*- coding: utf-8 -*-
"""造一个极简 map/：省 0（引擎占位）+ 省 1，256x256。

目的不是能玩，是确认「最小可加载的地图」长什么样。
每放大一步（省数、尺寸、文件种类）就测一次，崩了就知道是哪一步的问题。
"""
import io
import os
import struct
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work\tmp\_mini\map'
GAME = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV'
GMAP = os.path.join(GAME, 'map')

W = H = 256


def w_bmp24(path, w, h, pixel_fn):
    """写 24 位 BMP。行按 4 字节对齐。"""
    row = (w * 3 + 3) // 4 * 4
    data = bytearray()
    for y in range(h - 1, -1, -1):          # BMP 自下而上
        line = bytearray()
        for x in range(w):
            r, g, b = pixel_fn(x, y)
            line += bytes((b, g, r))
        line += b'\x00' * (row - len(line))
        data += line
    hdr = b'BM' + struct.pack('<IHHI', 54 + len(data), 0, 0, 54)
    dib = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0, len(data), 2835, 2835, 0, 0)
    io.open(path, 'wb', buffering=0).write(hdr + dib + bytes(data))


def w_bmp8(path, w, h, v=0):
    """写 8 位灰度「假 indexed」BMP。

    8 位图像需要调色板。这里写 256 级灰阶调色板，像素全填 v，
    够让引擎读到正确尺寸。
    """
    row = (w + 3) // 4 * 4
    pal = bytearray()
    for i in range(256):
        pal += bytes((i, i, i, 0))
    data = bytearray()
    for _y in range(h):
        data += bytes([v]) * w
        data += b'\x00' * (row - w)
    off = 54 + len(pal)
    hdr = b'BM' + struct.pack('<IHHI', off + len(data), 0, 0, off)
    dib = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 8, 0, len(data), 2835, 2835, 256, 0)
    io.open(path, 'wb', buffering=0).write(hdr + dib + bytes(pal) + bytes(data))


def main():
    os.makedirs(OUT, exist_ok=True)
    _w = lambda n, t: io.open(os.path.join(OUT, n), 'w',
                              encoding='utf-8', newline='').write(t)

    # provinces.bmp：左半省 1（红），右半黑（海）
    w_bmp24(os.path.join(OUT, 'provinces.bmp'), W, H,
            lambda x, y: (200, 30, 30) if x < W // 2 else (0, 0, 0))

    # definition.csv：省0 + 省1
    _w('definition.csv',
       '0;0;0;0;land;false;unknown;0\n'
       '1;200;30;30;land;false;plains;0\n')

    # 其余位图
    w_bmp8(os.path.join(OUT, 'heightmap.bmp'), W, H, 128)
    w_bmp8(os.path.join(OUT, 'terrain.bmp'), W, H, 0)
    w_bmp8(os.path.join(OUT, 'rivers.bmp'), W, H, 254)
    w_bmp8(os.path.join(OUT, 'cities.bmp'), W, H, 15)
    w_bmp8(os.path.join(OUT, 'trees.bmp'), W, H, 0)
    # world_normal 是半分辨率 24 位
    w_bmp24(os.path.join(OUT, 'world_normal.bmp'), W // 2, H // 2,
            lambda x, y: (128, 128, 255))

    # 文本类：尽量照原版最小结构
    _w('default.map',
       'definitions = "definition.csv"\n'
       'provinces = "provinces.bmp"\n'
       'positions = "positions.txt"\n'
       'terrain = "terrain.bmp"\n'
       'rivers = "rivers.bmp"\n'
       'heightmap = "heightmap.bmp"\n'
       'tree_definition = "trees.bmp"\n'
       'continent = "continent.txt"\n'
       'adjacency_rules = "adjacency_rules.txt"\n'
       'adjacencies = "adjacencies.csv"\n'
       'ambient_object = "ambient_object.txt"\n'
       'seasons = "seasons.txt"\n\n'
       'tree = { 3 4 7 10 }\n')
    _w('continent.txt', 'continents = {\n\teurope = { 1 }\n}\n')
    # 空但存在的文件
    for n in ('adjacencies.csv', 'positions.txt', 'cities.txt', 'buildings.txt',
              'supply_nodes.txt', 'railways.txt', 'unitstacks.txt',
              'weatherpositions.txt', 'ambient_object.txt'):
        _w(n, '')
    # 从原版抄不依赖省号的
    for n in ('adjacency_rules.txt', 'seasons.txt', 'colors.txt'):
        src = os.path.join(GMAP, n)
        if os.path.isfile(src):
            io.open(os.path.join(OUT, n), 'wb').write(io.open(src, 'rb').read())

    # 一个战略区
    os.makedirs(os.path.join(OUT, 'strategicregions'), exist_ok=True)
    io.open(os.path.join(OUT, 'strategicregions', '1-mini.txt'), 'w',
            encoding='utf-8', newline='').write(
        'strategic_region={\n'
        '\tid=1\n'
        '\tname="STRATEGICREGION_1"\n'
        '\tprovinces={\n\t\t1\n\t}\n'
        '\tweather={\n\t\tperiod={\n'
        '\t\t\tbetween={ 0.0 30.0 }\n'
        '\t\t\ttemperature={ -6.0 12.0 }\n'
        '\t\t\tno_phenomenon=0.500\n'
        '\t\t\train_light=1.000\n'
        '\t\t\train_heavy=0.150\n'
        '\t\t\tsnow=0.200\n'
        '\t\t\tblizzard=0.000\n'
        '\t\t\tarctic_water=0.000\n'
        '\t\t\tmud=0.300\n'
        '\t\t\tsandstorm=0.000\n'
        '\t\t\tmin_snow_level=0.000\n'
        '\t\t}\n\t}\n}\n')

    # 一个补给区
    os.makedirs(os.path.join(OUT, 'supplyareas'), exist_ok=True)
    io.open(os.path.join(OUT, 'supplyareas', '1-mini.txt'), 'w',
            encoding='utf-8', newline='').write(
        'supply_area={\n\tid=1\n\tname="SUPPLYAREA_1"\n\tvalue=10\n'
        '\tstates={\n\t\t1\n\t}\n}\n')

    # terrain 目录从原版抄（纯定义，不含省号）
    src_t = os.path.join(GMAP, 'terrain')
    dst_t = os.path.join(OUT, 'terrain')
    if os.path.isdir(src_t):
        os.makedirs(dst_t, exist_ok=True)
        import shutil
        for fn in os.listdir(src_t):
            shutil.copyfile(os.path.join(src_t, fn), os.path.join(dst_t, fn))

    n = sum(len(fs) for _r, _d, fs in os.walk(OUT))
    print('已生成 %d 个文件 → %s' % (n, OUT))
    print('省数: 1（省0 是引擎占位）')
    print('尺寸: %dx%d' % (W, H))


if __name__ == '__main__':
    main()
