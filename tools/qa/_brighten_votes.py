# -*- coding: utf-8 -*-
"""投票三栏提亮：给每个 grid 加稍亮的底板，并把国旗放大 1.3 倍。

现状：grid 直接铺在窗口底色（20,34,46）上，国旗 16px 很暗，看不清。
做法：
  1. 生成一张 (32,56,76) 的底板图 96×80，注册 sprite
  2. grid_wrap 加 background 用它
  3. entry 的国旗 iconType 加 scale 1.3
  4. slotsize 96×14 → 96×20，grid 高 60 → 80，按钮与页脚顺延
"""
import io
import os

from PIL import Image

PKG = 'mods/muvluvCNsub_xuerong'
DIR = os.path.join(PKG, 'gfx', 'interface', 'un')
GFXF = PKG + '/interface/zz_mvlv119_un_assets.gfx'
GEN = 'work/qa/_gen_un_window_gui.py'
T = chr(9)
NL = chr(10)
BS = chr(92)

# ---- 1) 底板图 ----
png = os.path.join(DIR, 'mvlv119_un_vote_bg.png')
Image.new('RGBA', (96, 80), (32, 56, 76, 255)).save(png, 'PNG')
print('底板图:', png, '(96x80, RGBA 32,56,76)')

s = io.open(GFXF, encoding='utf-8-sig').read()
if 'GFX_mvlv119_un_vote_bg' not in s:
    block = (T + 'spriteType = {' + NL +
             T + T + 'name = "GFX_mvlv119_un_vote_bg"' + NL +
             T + T + 'texturefile = "gfx/interface/un/mvlv119_un_vote_bg.png"' + NL +
             T + '}' + NL)
    i = s.rstrip().rfind('}')
    io.open(GFXF, 'w', encoding='utf-8', newline='').write(s[:i] + block + s[i:])
    print('已注册 GFX_mvlv119_un_vote_bg')
else:
    print('底板 sprite 已存在')

# ---- 2) grid_wrap 加 background + 尺寸调整 ----
g = io.open(GEN, encoding='utf-8').read()

old = ("""        'containerWindowType = {',""" + NL +
       """        '""" + T + """name = "%s"' % wrap,""" + NL +
       """        '""" + T + """position = { x = %d y = %d }' % (x, y),""" + NL +
       """        '""" + T + """size = { width = %d height = %d }' % (w, h),""" + NL +
       """        '',""" + NL)
new = ("""        'containerWindowType = {',""" + NL +
       """        '""" + T + """name = "%s"' % wrap,""" + NL +
       """        '""" + T + """position = { x = %d y = %d }' % (x, y),""" + NL +
       """        '""" + T + """size = { width = %d height = %d }' % (w, h),""" + NL +
       """        '""" + T + """background = {',""" + NL +
       """        '""" + T + T + """name = "bg"',""" + NL +
       """        '""" + T + T + """spriteType = "GFX_mvlv119_un_vote_bg"',""" + NL +
       """        '""" + T + """}',""" + NL +
       """        '',""" + NL)
if 'GFX_mvlv119_un_vote_bg' not in g:
    assert old in g, 'grid_wrap 锚点未命中'
    g = g.replace(old, new, 1)
    print('grid_wrap 已加底板')
else:
    print('底板已绑')

# ---- 3) 国旗放大 ----
old_flag = ("""    entry.append('iconType = {')""" + NL +
            """    entry.append('""" + T + """name = "mvlv_un_mem_flag"')""" + NL +
            """    entry.append('""" + T + """quadTextureSprite = "GFX_flag_small"')""" + NL +
            """    entry.append('""" + T + """position = { x = 0 y = 7 }')""" + NL)
new_flag = ("""    entry.append('iconType = {')""" + NL +
            """    entry.append('""" + T + """name = "mvlv_un_mem_flag"')""" + NL +
            """    entry.append('""" + T + """quadTextureSprite = "GFX_flag_small"')""" + NL +
            """    entry.append('""" + T + """position = { x = 0 y = 4 }')""" + NL +
            """    entry.append('""" + T + """scale = 1.3')""" + NL)
if 'scale = 1.3' not in g:
    assert old_flag in g, 'flag 锚点未命中'
    g = g.replace(old_flag, new_flag, 1)
    print('国旗放大 1.3 倍')
else:
    print('国旗已放大')

# ---- 4) slotsize / 高度 / 按钮顺延 ----
pairs = [
 ("grid_el('mvlv_un_win_%s_grid' % tag, x, 410, w, 60, 96, 14, cols)",
  "grid_el('mvlv_un_win_%s_grid' % tag, x, 410, w, 80, 96, 20, cols)"),
 ("button_el('mvlv_un_vote_%s' % tag, 'GFX_mvlv119_un_btn_vote', bx, 478,",
  "button_el('mvlv_un_vote_%s' % tag, 'GFX_mvlv119_un_btn_vote', bx, 498,"),
 ("text_el('un_win_vote_%s_label' % tag, bx, 484,", "text_el('un_win_vote_%s_label' % tag, bx, 504,"),
 ("text_el('un_win_days', 24, 516,", "text_el('un_win_days', 24, 536,"),
 ("button_el('mvlv_un_pass_vote', 'GFX_mvlv119_un_btn_pass', 24, 534,",
  "button_el('mvlv_un_pass_vote', 'GFX_mvlv119_un_btn_pass', 24, 554,"),
 ("text_el('un_win_pass_vote_label', 24, 540,", "text_el('un_win_pass_vote_label', 24, 560,"),
 ("button_el('mvlv_un_pass_vote_grey', 'GFX_mvlv119_un_btn_pass_grey', 24, 534,",
  "button_el('mvlv_un_pass_vote_grey', 'GFX_mvlv119_un_btn_pass_grey', 24, 554,"),
 ("button_el('mvlv_un_pay', 'GFX_mvlv119_un_btn_action', 236, 534,",
  "button_el('mvlv_un_pay', 'GFX_mvlv119_un_btn_action', 236, 554,"),
 ("text_el('un_win_pay_label', 244, 537,", "text_el('un_win_pay_label', 244, 557,"),
 ("button_el('mvlv_un_exit', 'GFX_mvlv119_un_btn_action', 236, 564,",
  "button_el('mvlv_un_exit', 'GFX_mvlv119_un_btn_action', 236, 584,"),
 ("text_el('un_win_exit_label', 244, 567,", "text_el('un_win_exit_label', 244, 587,"),
 ("text_el('un_win_note', 484, 534,", "text_el('un_win_note', 484, 554,"),
]
n = 0
for old_p, new_p in pairs:
    if old_p in g:
        g = g.replace(old_p, new_p, 1)
        n += 1
    else:
        print('未命中:', old_p[:52])
print('顺延 %d 处坐标' % n)

import ast
ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('生成器语法 OK')
