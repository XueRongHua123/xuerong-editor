# -*- coding: utf-8 -*-
"""把实拍照片处理成联合国面板的横幅（双色调，接 HUD 的蓝）。

源图：work/assets/un_hq_flags.jpg（纽约联合国总部，旗帜与秘书处大楼）
产出：gfx/interface/un/mvlv119_un_hall.png  502x110
      含左侧压暗（放标题）、底部渐隐（接到面板底）、扫描线

处理链固定在这里，换图只换源文件重跑，不改代码。
"""

import os

from PIL import Image, ImageEnhance, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'work', 'assets', 'un_hq_flags.jpg')
OUT = os.path.join(ROOT, 'mods', 'muvluvCNsub_xuerong', 'gfx', 'interface', 'un',
                   'mvlv119_un_hall.png')

W, H = 502, 110
CROP = (0, 62, 800, 237)         # 讲台与大会堂中段，比例 800:175 = 4.57:1，正好贴 502x110


def ramp(v):
    """灰度 0-1 映射到 深海军蓝 -> 青白。"""
    r = 6 + 150 * (v ** 1.9)
    g = 18 + 205 * (v ** 1.35)
    b = 38 + 225 * (v ** 1.05)
    return int(min(255, r)), int(min(255, g)), int(min(255, b))


def main():
    im = Image.open(SRC).convert('RGB').crop(CROP)
    im = im.resize((W, H), Image.LANCZOS)
    gray = ImageOps.autocontrast(im.convert('L'), cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.25)

    out = Image.new('RGBA', (W, H))
    px = out.load()
    gp = gray.load()
    for y in range(H):
        fade = 1.0
        if y > 82:
            fade = max(0.0, (H - 1 - y) / 27.0)
        scan = 0.94 if y % 3 == 0 else 1.0
        for x in range(W):
            scrim = 0.40 + 0.60 * (x / 240.0) if x < 240 else 1.0
            r, g, b = ramp(gp[x, y] / 255.0)
            k = scrim * scan
            px[x, y] = (int(r * k), int(g * k), int(b * k), int(255 * fade))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT)
    print('%s  %dx%d  %d KB' % (os.path.basename(OUT), W, H, os.path.getsize(OUT) // 1024))


if __name__ == '__main__':
    main()
