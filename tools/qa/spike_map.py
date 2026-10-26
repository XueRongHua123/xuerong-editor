# -*- coding: utf-8 -*-
"""地图层 1 技术验证：读 provinces.bmp / definition.csv 的耗时与内存，测三条渲染路径。

用法：python work/qa/spike_map.py [mod_root]
"""
import io
import os
import sys
import time

MOD = sys.argv[1] if len(sys.argv) > 1 else r"D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\muvluvCN_1.19"
GAME = r"E:\SteamLibrary\steamapps\common\Hearts of Iron IV"


def pick(rel):
    for base in (MOD, GAME):
        p = os.path.join(base, rel)
        if os.path.exists(p):
            return p, base
    return None, None


def main():
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    bmp, base = pick("map/provinces.bmp")
    csv, _ = pick("map/definition.csv")
    print("bmp:", bmp)
    print("csv:", csv)

    t0 = time.time()
    im = Image.open(bmp)
    w, h = im.size
    print("打开: %.2fs  mode=%s  size=%dx%d  像素=%.1fM" % (time.time() - t0, im.mode, w, h, w * h / 1e6))

    t1 = time.time()
    im.load()
    print("load(): %.2fs" % (time.time() - t1))

    t2 = time.time()
    colors = im.convert("RGB").getcolors(maxcolors=2000000)
    print("getcolors: %.2fs  唯一色数=%s" % (time.time() - t2, len(colors or [])))

    t3 = time.time()
    n = 0
    with io.open(csv, encoding="utf-8", errors="replace") as f:
        for line in f:
            n += 1
            if n == 1:
                print("csv 首行:", line.strip()[:80])
    print("definition.csv 行数=%d  读取 %.2fs" % (n, time.time() - t3))

    # 方案 A：tobytes + Python 循环统计（无 numpy 的代价估算，只跑 1/10 像素）
    t4 = time.time()
    raw = im.convert("RGB").tobytes()
    step = 10
    seen = {}
    total = len(raw) // 3
    for i in range(0, total // step):
        o = i * 3 * step
        key = raw[o] << 16 | raw[o + 1] << 8 | raw[o + 2]
        seen[key] = seen.get(key, 0) + 1
    dt = time.time() - t4
    print("bytes 抽样 %.1f%%: %.2fs  推算全量约 %.1fs" % (100.0 / step, dt, dt * step))

    # 方案 B：调色板替换（Pillow C 层）——先降采样再 quantize，测可行性
    t5 = time.time()
    small = im.convert("RGB").resize((w // 8, h // 8), Image.NEAREST)
    q = small.quantize(colors=256, method=Image.MEDIANCUT)
    print("降采样+quantize(256): %.2fs  小图色数=%s" % (time.time() - t5, len(q.getcolors() or [])))

    # 方案 C：边界图（差分）
    t6 = time.time()
    g = im.convert("L").resize((w // 4, h // 4), Image.NEAREST)
    from PIL import ImageFilter
    edge = g.filter(ImageFilter.FIND_EDGES)
    print("灰度+边缘(1/4): %.2fs  bbox=%s" % (time.time() - t6, edge.getbbox()))

    print("\n结论依据：")
    print("  全量字节循环 ≈ %.1fs（不含映射）" % (dt * step))
    print("  若用 numpy 向量化，同类统计通常 0.2-0.8s")


if __name__ == "__main__":
    main()
