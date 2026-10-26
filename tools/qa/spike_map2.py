# -*- coding: utf-8 -*-
"""地图层 1 技术验证 - 第二阶段：生成图层 PNG，测耗时与体积（无 numpy，纯 Pillow）。

用法：python work/qa/spike_map2.py [mod_root] [out_dir]
"""
import io
import os
import sys
import time

MOD = sys.argv[1] if len(sys.argv) > 1 else r"D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\muvluvCN_1.19"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots", "spike_map")
GAME = r"E:\SteamLibrary\steamapps\common\Hearts of Iron IV"


def pick(rel):
    for base in (MOD, GAME):
        p = os.path.join(base, rel)
        if os.path.exists(p):
            return p
    return None


def main():
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    os.makedirs(OUT, exist_ok=True)

    t_all = time.time()
    bmp = pick("map/provinces.bmp")
    csv = pick("map/definition.csv")

    # 1) definition.csv：颜色 -> 省 id / 类型
    t0 = time.time()
    color2prov = {}
    with io.open(csv, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) < 5:
                continue
            try:
                pid = int(parts[0])
                rgb = (int(parts[1]), int(parts[2]), int(parts[3]))
            except Exception:
                continue
            color2prov[rgb] = pid
    print("definition.csv 解析: %.2fs  省数=%d" % (time.time() - t0, len(color2prov)))

    # 2) 读图 + 取字节
    t1 = time.time()
    im = Image.open(bmp).convert("RGB")
    w, h = im.size
    raw = im.tobytes()
    print("读取: %.2fs  %dx%d  %.1f MB" % (time.time() - t1, w, h, len(raw) / 1e6))

    # 3) 逐像素映射两件事：省 id 图 + 省色块
    t2 = time.time()
    n = w * h
    provbuf = bytearray(n)          # 省 id 低 8 位索引？（id 可能 >255）改用 int 数组
    ids = [0] * n
    lookup = color2prov
    miss = 0
    for i in range(n):
        o = i * 3
        key = (raw[o], raw[o + 1], raw[o + 2])
        pid = lookup.get(key)
        if pid is None:
            miss += 1
            pid = 0
        ids[i] = pid
    print("像素映射: %.2fs  未命中色=%d" % (time.time() - t2, miss))

    # 4) 生成省色块（每个省一个稳定色）
    t3 = time.time()
    colors = {}
    buf = bytearray(n * 3)
    for i in range(n):
        pid = ids[i]
        c = colors.get(pid)
        if c is None:
            hsh = (pid * 2654435761) & 0xFFFFFF
            r = 40 + ((hsh >> 16) & 0xFF) * 170 // 255
            g = 40 + ((hsh >> 8) & 0xFF) * 170 // 255
            b = 40 + (hsh & 0xFF) * 170 // 255
            c = bytes((r, g, b))
            colors[pid] = c
        o = i * 3
        buf[o] = c[0]
        buf[o + 1] = c[1]
        buf[o + 2] = c[2]
    prov_img = Image.frombytes("RGB", (w, h), bytes(buf))
    p1 = os.path.join(OUT, "layer_province.png")
    prov_img.save(p1, optimize=False)
    print("省色块: %.2fs  -> %.1f MB" % (time.time() - t3, os.path.getsize(p1) / 1e6))

    # 5) 省界：左右/上下不同 id 处标白（1px）
    t4 = time.time()
    edgebuf = bytearray(n * 3)
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            pid = ids[i]
            edge = False
            if x + 1 < w and ids[i + 1] != pid:
                edge = True
            elif y + 1 < h and ids[i + w] != pid:
                edge = True
            if edge:
                o = i * 3
                edgebuf[o] = 255
                edgebuf[o + 1] = 255
                edgebuf[o + 2] = 255
    edge_img = Image.frombytes("RGB", (w, h), bytes(edgebuf))
    p2 = os.path.join(OUT, "layer_edges.png")
    edge_img.save(p2)
    print("省界: %.2fs  -> %.1f MB" % (time.time() - t4, os.path.getsize(p2) / 1e6))

    # 6) 缩略底图（给快速预览用）
    t5 = time.time()
    thumb = im.resize((w // 4, h // 4), Image.BILINEAR)
    p3 = os.path.join(OUT, "base_quarter.png")
    thumb.save(p3)
    print("缩略底图: %.2fs  -> %.1f MB (%dx%d)" % (time.time() - t5, os.path.getsize(p3) / 1e6, w // 4, h // 4))

    print("\n总计: %.1fs" % (time.time() - t_all))
    print("产物目录:", OUT)


if __name__ == "__main__":
    main()
