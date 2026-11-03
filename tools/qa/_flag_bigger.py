# -*- coding: utf-8 -*-
"""只放大国旗，不加底板（底板会在别处误渲染成深色块）。

改：
  1. entry 里国旗 iconType 加 scale = 1.3，position y 7 → 4
  2. slotsize 96×14 → 96×20
  3. grid 高 60 → 80
  4. 下方按钮/倒计时/页脚整体下移 20px
"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)
BT = chr(92) + 't'

lines = io.open(GEN, encoding='utf-8').read().split(NL)
out = []
added = False
for ln in lines:
    if ("entry.append('" + BT + "position = { x = 0 y = 7 }')" in ln) and not added:
        out.append("    entry.append('" + BT + "position = { x = 0 y = 4 }')")
        out.append("    entry.append('" + BT + "scale = 1.3')")
        added = True
        continue
    out.append(ln)
print('国旗 scale 插入:', added)

g = NL.join(out)
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
    else:
        print('未命中:', a[:50])
print('顺延 %d 处' % n)

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')
