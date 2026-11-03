# -*- coding: utf-8 -*-
"""投票三栏提亮 第二版（行级定位，避免拼接格式不匹配）。

1. 底板图 96×80 (32,56,76) + 注册 sprite
2. grid_wrap 加 background
3. 国旗 iconType 加 scale 1.3，position y 7→4
4. slotsize 14→20、grid 高 60→80、按钮与页脚顺延
"""
import ast
import io
import os

from PIL import Image

PKG = 'mods/muvluvCNsub_xuerong'
DIR = os.path.join(PKG, 'gfx', 'interface', 'un')
GFXF = PKG + '/interface/zz_mvlv119_un_assets.gfx'
GEN = 'work/qa/_gen_un_window_gui.py'
T = chr(9)
NL = chr(10)
BT = chr(92) + 't'

# ---- 1) 底板图 + gfx ----
png = os.path.join(DIR, 'mvlv119_un_vote_bg.png')
Image.new('RGBA', (96, 80), (32, 56, 76, 255)).save(png, 'PNG')
print('底板图:', os.path.basename(png))

s = io.open(GFXF, encoding='utf-8-sig').read()
if 'GFX_mvlv119_un_vote_bg' not in s:
    block = (T + 'spriteType = {' + NL + T + T + 'name = "GFX_mvlv119_un_vote_bg"' + NL +
             T + T + 'texturefile = "gfx/interface/un/mvlv119_un_vote_bg.png"' + NL + T + '}' + NL)
    i = s.rstrip().rfind('}')
    io.open(GFXF, 'w', encoding='utf-8', newline='').write(s[:i] + block + s[i:])
    print('已注册底板 sprite')

# ---- 2~4) 生成器行级改 ----
lines = io.open(GEN, encoding='utf-8').read().split(NL)
out = []
done = {'bg': False, 'flag': False}
i = 0
while i < len(lines):
    ln = lines[i]
    # grid_wrap：在 size 行后插 background
    if "name = \"%s\"' % wrap" in ln and not done['bg']:
        out.append(ln)
        # 后面三行是 position / size / ''
        for k in range(1, 4):
            out.append(lines[i + k])
        out.append("        '" + BT + "background = {',")
        out.append("        '" + BT * 2 + "name = \"bg\"',")
        out.append("        '" + BT * 2 + "spriteType = \"GFX_mvlv119_un_vote_bg\"',")
        out.append("        '" + BT + "}',")
        i += 4
        done['bg'] = True
        print('grid_wrap 加底板')
        continue
    # 国旗：position 行后插 scale
    if "entry.append('" + BT + "position = { x = 0 y = 7 }')" in ln and not done['flag']:
        out.append("    entry.append('" + BT + "position = { x = 0 y = 4 }')")
        out.append("    entry.append('" + BT + "scale = 1.3')")
        i += 1
        done['flag'] = True
        print('国旗 scale 1.3')
        continue
    out.append(ln)
    i += 1

g = NL.join(out)

# ---- 尺寸与坐标顺延 ----
pairs = [
 ("grid_el('mvlv_un_win_%s_grid' % tag, x, 410, w, 60, 96, 14, cols)",
  "grid_el('mvlv_un_win_%s_grid' % tag, x, 410, w, 80, 96, 20, cols)"),
 ("'GFX_mvlv119_un_btn_vote', bx, 478,", "'GFX_mvlv119_un_btn_vote', bx, 498,"),
 ("text_el('un_win_vote_%s_label' % tag, bx, 484,", "text_el('un_win_vote_%s_label' % tag, bx, 504,"),
 ("text_el('un_win_days', 24, 516,", "text_el('un_win_days', 24, 536,"),
 ("'GFX_mvlv119_un_btn_pass', 24, 534,", "'GFX_mvlv119_un_btn_pass', 24, 554,"),
 ("text_el('un_win_pass_vote_label', 24, 540,", "text_el('un_win_pass_vote_label', 24, 560,"),
 ("'GFX_mvlv119_un_btn_pass_grey', 24, 534,", "'GFX_mvlv119_un_btn_pass_grey', 24, 554,"),
 ("'GFX_mvlv119_un_btn_action', 236, 534,", "'GFX_mvlv119_un_btn_action', 236, 554,"),
 ("text_el('un_win_pay_label', 244, 537,", "text_el('un_win_pay_label', 244, 557,"),
 ("'GFX_mvlv119_un_btn_action', 236, 564,", "'GFX_mvlv119_un_btn_action', 236, 584,"),
 ("text_el('un_win_exit_label', 244, 567,", "text_el('un_win_exit_label', 244, 587,"),
 ("text_el('un_win_note', 484, 534,", "text_el('un_win_note', 484, 554,"),
]
n = 0
for a, b in pairs:
    if a in g:
        g = g.replace(a, b, 1)
        n += 1
print('顺延 %d 处' % n)

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('生成器语法 OK')
