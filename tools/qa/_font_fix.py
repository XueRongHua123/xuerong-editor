# -*- coding: utf-8 -*-
"""投票栏文字模式修根因：`hoi_12mbs` 字体不存在。

原版字体只有 hoi_16mbs / hoi_18mbs / hoi_18 / hoi_20b 等，没有 12mbs。
字体名不存在 → 整段文字渲染成 `?????`。成员页用 hoi_16mbs 才正常。

改：
  1. font hoi_12mbs → hoi_16mbs
  2. slotsize 96×24 → 100×24，maxWidth 88 → 92
  3. 三栏宽度重分配（16px 字更宽）：赞成 200(2列) / 反对 500(5列) / 弃权 256(2列)
  4. 恢复底衬（透明化的两个图改回浅色，精确尺寸 100×24 / 450×30）
"""
import ast
import io
import os

from PIL import Image

PKG = 'mods/muvluvCNsub_xuerong'
DIR = os.path.join(PKG, 'gfx', 'interface', 'un')
GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)
T = chr(9)

# 1) 底衬图恢复成浅色（100×24 / 450×30）
Image.new('RGBA', (100, 24), (170, 190, 205, 255)).save(os.path.join(DIR, 'mvlv119_un_slot_bg.png'), 'PNG')
Image.new('RGBA', (450, 30), (170, 190, 205, 255)).save(os.path.join(DIR, 'mvlv119_un_slot_bg_wide.png'), 'PNG')
print('底衬图恢复浅色 100×24 / 450×30')

g = io.open(GEN, encoding='utf-8').read()

# 2) 字体
n1 = g.count('hoi_12mbs')
g = g.replace('hoi_12mbs', 'hoi_16mbs')
print('hoi_12mbs → hoi_16mbs：%d 处' % n1)

# 3) 三栏宽度
old = "    LANES = ((24, 200, 2, 'yes'), (236, 400, 4, 'no'), (648, 308, 3, 'abs'))"
new = "    LANES = ((24, 200, 2, 'yes'), (236, 500, 5, 'no'), (748, 208, 2, 'abs'))"
if old in g:
    g = g.replace(old, new, 1)
    print('三栏宽度 200/500/208')
else:
    print('LANES 未命中')

# 4) slotsize 与文字宽度
g = g.replace("grid_el('mvlv_un_win_%s_grid' % tag, x, 410, w, 72, 96, 24, cols)",
              "grid_el('mvlv_un_win_%s_grid' % tag, x, 410, w, 72, 100, 24, cols)", 1)
g = g.replace("'maxWidth = 88'", "'maxWidth = 92'")
g = g.replace("maxWidth = 88", "maxWidth = 92")
print('slotsize 100×24，maxWidth 92')

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')
