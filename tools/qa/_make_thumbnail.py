# -*- coding: utf-8 -*-
"""生成创意工坊缩略图：直接用 muvluvCNsub 的封面，在 "sub" 右边加一行白字。

不重绘底图，只在基座封面上贴「雪绒拓展」，保持和 muvluvCNsub 同一套视觉。

位置和字号都是量出来的，不是猜的：
  * 先在底图里找红色像素（"sub" 那几个字），取它的右边界和底部基线
  * 白字的基线对齐 "sub" 基线，左边留 SUB_GAP 像素
  * 字号按 "sub" 的字符高度换算，避免手调

底图换成别的封面时，脚本仍然按红色像素定位；找不到红字就回退到右上角。

用法：
    python work/qa/_make_thumbnail.py
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _paths import OUT, SUB, p  # noqa: E402

SRC = p(SUB, 'thumbnail.png')          # muvluvCNsub 那套封面
FONT = r'C:\Windows\Fonts\msyhbd.ttc'  # 微软雅黑粗体
TEXT = '雪绒拓展'
SUB_GAP = 14                           # 白字与 "sub" 的水平间距
STROKE = 1                             # 白字描边宽度，压住青绿背景


def find_red_box(im):
    """找底图里的红色文字区域，返回 (x0, y0, x1, y1)；找不到返回 None。"""
    px = im.load()
    w, h = im.size
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            if r > 120 and r > g * 1.8 and r > b * 1.8:
                xs.append(x)
                ys.append(y)
    if len(xs) < 50:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def main():
    if not os.path.exists(SRC):
        print('底图不存在:', SRC)
        return 1

    im = Image.open(SRC).convert('RGB')
    w, h = im.size

    box = find_red_box(im)
    if box:
        x0, y0, x1, y1 = box
        size = max(24, int((y1 - y0 + 1) * 1.12))
        tx, baseline = x1 + SUB_GAP, y1
        print('  红字范围 x %d-%d, y %d-%d -> 字号 %d，白字起点 (%d, %d)'
              % (x0, x1, y0, y1, size, tx, baseline))
    else:
        size = max(24, int(h * 0.09))
        tx, baseline = w - int(size * len(TEXT) * 0.95) - 20, h - 24
        print('  没找到红字，回退到右下角：字号 %d，起点 (%d, %d)'
              % (size, tx, baseline))

    # 放不下就缩字号，别让字跑出画布
    while tx + size * len(TEXT) > w - 8 and size > 16:
        size -= 2
    font = ImageFont.truetype(FONT, size)

    d = ImageDraw.Draw(im)
    d.text((tx, baseline), TEXT, font=font, anchor='ls',
           fill=(255, 255, 255),
           stroke_width=STROKE, stroke_fill=(18, 24, 30))

    dst = p(OUT, 'thumbnail.png')
    im.save(dst, 'PNG', optimize=True)
    print('  已生成 %s' % dst)
    print('  %dx%d, %d bytes' % (w, h, os.path.getsize(dst)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
