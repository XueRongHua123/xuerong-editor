# -*- coding: utf-8 -*-
"""投票栏格子重叠 + 文字被裁。

1. grid 高 72 不够：弃权 9 国 2 列要 5 行（120px），溢出的格子压到按钮上
   → 三栏统一 grid 高 120，下方元素顺延
2. 文字被裁：maxHeight 16 装不下 16px 字（成员页是 18），且 y=4 偏下
   → maxHeight 20、y=2（照成员页的留白比例）
"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)
g = io.open(GEN, encoding='utf-8').read()

# 1) grid 高 72 → 120
g = g.replace("grid_el('mvlv_un_win_%s_grid' % tag, x, 410, w, 72, 100, 24, cols)",
              "grid_el('mvlv_un_win_%s_grid' % tag, x, 410, w, 120, 100, 24, cols)", 1)
print('grid 高 72 → 120')

# 2) 文字位置与高度
g = g.replace("ind + T + 'position = { x = 4 y = 4 }'", "ind + T + 'position = { x = 4 y = 2 }'")
g = g.replace("ind + T + 'maxHeight = 16'", "ind + T + 'maxHeight = 20'")
print('文字 y 4→2，maxHeight 16→20')

# 3) 下方元素顺延（grid 到 530）
pairs = [
 ("'GFX_mvlv119_un_btn_vote', bx, 490,", "'GFX_mvlv119_un_btn_vote', bx, 538,"),
 ("text_el('un_win_vote_%s_label' % tag, bx, 496,", "text_el('un_win_vote_%s_label' % tag, bx, 544,"),
 ("text_el('un_win_days', 24, 528,", "text_el('un_win_days', 24, 576,"),
 ("'GFX_mvlv119_un_btn_pass', 24, 546,", "'GFX_mvlv119_un_btn_pass', 24, 594,"),
 ("text_el('un_win_pass_vote_label', 24, 552,", "text_el('un_win_pass_vote_label', 24, 600,"),
 ("'GFX_mvlv119_un_btn_pass_grey', 24, 546,", "'GFX_mvlv119_un_btn_pass_grey', 24, 594,"),
 ("'GFX_mvlv119_un_btn_action', 236, 546,", "'GFX_mvlv119_un_btn_action', 236, 594,"),
 ("text_el('un_win_pay_label', 244, 549,", "text_el('un_win_pay_label', 244, 597,"),
 ("'GFX_mvlv119_un_btn_action', 236, 576,", "'GFX_mvlv119_un_btn_action', 236, 624,"),
 ("text_el('un_win_exit_label', 244, 579,", "text_el('un_win_exit_label', 244, 627,"),
]
n = 0
for a, b in pairs:
    if a in g:
        g = g.replace(a, b, 1)
        n += 1
    else:
        print('未命中:', a[:46])
print('顺延 %d 处' % n)

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')
