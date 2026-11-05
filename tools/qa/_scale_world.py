"""把一个 map/ 目录整体按整数倍放大/缩小。

只动像素和坐标，不动省号、不动 definition.csv、不动战略区/补给区。

用法:
    python qa/_scale_world.py <map_dir> <out_dir> --up 2
    python qa/_scale_world.py <map_dir> <out_dir> --down 2

注意（坑都在这）：
  · 8 位索引图（P 模式）必须保留调色板 —— convert('RGB') 会毁掉 terrain/rivers/cities
    的索引语义（那三张图靠索引值表达地形/海陆/城市）。
  · 必须用 NEAREST。BILINEAR 会把省界糊成渐变，provinces.bmp 就没有明确边界了。
  · 坐标表只放大 x / z（水平面），高度列不动 —— 高度是"离地多少米"，跟画布无关。
  · 行尾保持原样：这些表是 LF，统一写 CRLF 会让游戏读不到。
"""
import io
import os
import shutil
import sys


def _pil():
    from PIL import Image
    return Image


# 需要跟着画布一起缩放的位图。world_normal 是半分辨率，同样按倍数缩放。
BMPS = ("provinces.bmp", "terrain.bmp", "rivers.bmp", "cities.bmp",
        "heightmap.bmp", "trees.bmp", "world_normal.bmp")

# 分号表里的坐标列（0-based）。y 是高度，不缩放。
COORD_COLS = {
    "unitstacks.txt": (2, 4),        # 省号;type;x;y;z;rot;scale
    "buildings.txt": (2, 4),         # 省号;类型;x;y;z;rot;?
    "weatherpositions.txt": (1, 3),  # 省号;x;y;z;small|large
}


def scale_bmp(path, num, den):
    Image = _pil()
    im = Image.open(path)
    im.load()
    w, h = im.size
    nw, nh = max(1, w * num // den), max(1, h * num // den)
    pal = im.getpalette()
    im2 = im.resize((nw, nh), Image.NEAREST)
    if im.mode == "P":
        # 必须重新挂上调色板；resize 之后调色板可能丢
        if pal:
            im2.putpalette(pal)
        im2 = im2.convert("P") if im2.mode != "P" else im2
    # 先写内存再覆盖：P 模式 BMP 直接 save 到原路径会抛
    # OSError [Errno 22]（cp 过来的文件可能还带只读属性）
    buf = io.BytesIO()
    im2.save(buf, format="BMP")
    data = buf.getvalue()
    # **必须先关了源文件的读句柄**：PIL 是懒加载，`Image.open` 之后文件一直开着，
    # Windows 上这时再去 open(..., "wb") 同名文件直接 Errno 22 Invalid argument。
    im.close()
    try:
        os.chmod(path, 0o666)
    except Exception:
        pass
    with open(path, "wb") as f:
        f.write(data)
    return (w, h), (nw, nh), im.mode


def scale_coords(path, num, den):
    raw = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    nl = "\r\n" if "\r\n" in raw else "\n"
    cols = COORD_COLS[os.path.basename(path)]
    out, changed = [], 0
    for ln in raw.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            out.append(ln)
            continue
        p = ln.split(";")
        for c in cols:
            if c < len(p):
                try:
                    v = float(p[c])
                except ValueError:
                    continue
                p[c] = "%.2f" % (v * num / den)
                changed += 1
        out.append(";".join(p))
    body = nl.join(out)
    if not body.endswith(nl):
        body += nl
    io.open(path, "w", encoding="utf-8", newline="").write(body)
    return changed


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    num = den = 1
    if "--up" in sys.argv:
        num = int(sys.argv[sys.argv.index("--up") + 1])
    elif "--down" in sys.argv:
        den = int(sys.argv[sys.argv.index("--down") + 1])
    else:
        print("要给 --up N 或 --down N")
        return 2
    if os.path.abspath(src) == os.path.abspath(dst):
        print("输出目录不能和源目录相同")
        return 2

    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    print("缩放 %s ×%d/%d → %s" % (src, num, den, dst))
    for fn in BMPS:
        p = os.path.join(dst, fn)
        if not os.path.isfile(p):
            print("  %-20s 缺失，跳过" % fn)
            continue
        before, after, mode = scale_bmp(p, num, den)
        print("  %-20s %-4s %dx%d → %dx%d" % (fn, mode, before[0], before[1], after[0], after[1]))

    for fn in COORD_COLS:
        p = os.path.join(dst, fn)
        if not os.path.isfile(p):
            print("  %-20s 缺失，跳过" % fn)
            continue
        n = scale_coords(p, num, den)
        print("  %-20s 坐标改了 %d 个" % (fn, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
