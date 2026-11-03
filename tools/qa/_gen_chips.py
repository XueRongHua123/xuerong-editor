# -*- coding: utf-8 -*-
"""按栏宽生成三张 chip 图（200/200/508），避免拉伸变形。

原 chip.png 是 150×20：左侧一条亮边 + 纯深蓝底。拉伸会让亮边变粗，
所以按目标宽度重新拼：左侧 2px 亮边原样保留，其余用底色填满。
"""
import io
import os

from PIL import Image

DIR = r'mods\muvluvCNsub_xuerong\gfx\interface\un'
SRC = os.path.join(DIR, 'mvlv119_un_chip.png')
GFXF = r'mods\muvluvCNsub_xuerong\interface\zz_mvlv119_un_assets.gfx'
T = chr(9)
NL = chr(10)

src = Image.open(SRC).convert('RGBA')
w, h = src.size
print('源图 %dx%d' % (w, h))

# 取左亮边（前 2px）和中等高度的底色
edge = src.crop((0, 0, 2, h))
mid_y = h // 2
bg = src.getpixel((w // 2, mid_y))
print('底色 RGBA =', bg)

made = []
for target in (200, 508):
    if target == w:
        continue
    im = Image.new('RGBA', (target, h), bg)
    im.paste(edge, (0, 0))
    # 顶部/底部若有高光行，复制一条
    im.paste(src.crop((0, 0, target, 1)), (0, 0))
    name = 'mvlv119_un_chip_%d.png' % target
    im.save(os.path.join(DIR, name), 'PNG')
    made.append(target)
    print('生成', name, im.size)

# 注册 gfx
s = io.open(GFXF, encoding='utf-8-sig').read()
add = ''
for target in made:
    key = 'GFX_mvlv119_un_chip_%d' % target
    if key in s:
        continue
    add += (T + 'spriteType = {' + NL +
            T + T + 'name = "%s"' % key + NL +
            T + T + 'texturefile = "gfx/interface/un/mvlv119_un_chip_%d.png"' % target + NL +
            T + '}' + NL)
if add:
    i = s.rstrip().rfind('}')
    s = s[:i] + add + s[i:]
    io.open(GFXF, 'w', encoding='utf-8', newline='').write(s)
    print('已注册:', ', '.join('GFX_mvlv119_un_chip_%d' % t for t in made))
else:
    print('gfx 已注册，跳过')
