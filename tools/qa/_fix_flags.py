# -*- coding: utf-8 -*-
"""投票栏修国旗可见性 + 列数重排。

问题：
  1. 槽高 20，国旗 scale 1.3 后高约 18、从 y=4 开始 → 底部超出被裁，看不到旗
  2. 反对栏 11 国用 2 列要 6 行（144px），grid 只有 80 高，大部分挤不进去

改：
  * 槽高 20 → 24，国旗 y 4 → 2（18 高，居中不裁）
  * 三栏宽度重分配：赞成 200(2列) / 反对 400(4列) / 弃权 308(3列)
    11 国 ÷ 4 列 = 3 行 × 24 = 72px，放得下
  * grid 高 80 → 72，下方按钮/页脚重新对齐
"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)
BT = chr(92) + 't'

g = io.open(GEN, encoding='utf-8').read()

# 1) 国旗位置
g = g.replace("entry.append('" + BT + "position = { x = 0 y = 4 }')",
              "entry.append('" + BT + "position = { x = 0 y = 2 }')", 1)
print('国旗 y 4 → 2')

# 2) 三栏宽度与列数
old_lanes = "    LANES = ((24, 200, 2, 'yes'), (236, 200, 2, 'no'), (448, 508, 5, 'abs'))"
new_lanes = ("    # 反对通常最多（11 国），给 4 列；弃权次之 3 列；赞成为了 2 列\n"
             "    LANES = ((24, 200, 2, 'yes'), (236, 400, 4, 'no'), (648, 308, 3, 'abs'))")
assert old_lanes in g, 'LANES 未命中'
g = g.replace(old_lanes, new_lanes, 1)
print('三栏宽度 200/400/308，列数 2/4/3')

# chip 图按宽度选：200 用 _200，400/308 用 _508（拉伸一点可接受）
g = g.replace("chip = 'GFX_mvlv119_un_chip_%d' % (508 if w > 200 else 200)",
              "chip = 'GFX_mvlv119_un_chip_%d' % (200 if w <= 200 else 508)", 1)

# 3) slotsize 与 grid 高
g = g.replace("grid_el('mvlv_un_win_%s_grid' % tag, x, 410, w, 80, 96, 20, cols)",
              "grid_el('mvlv_un_win_%s_grid' % tag, x, 410, w, 72, 96, 24, cols)", 1)

# 4) 下方元素对齐：按钮 498→490，其余顺延
pairs = [
 ("'GFX_mvlv119_un_btn_vote', bx, 498,", "'GFX_mvlv119_un_btn_vote', bx, 490,"),
 ("text_el('un_win_vote_%s_label' % tag, bx, 504,", "text_el('un_win_vote_%s_label' % tag, bx, 496,"),
 ("text_el('un_win_days', 24, 536,", "text_el('un_win_days', 24, 528,"),
 ("'GFX_mvlv119_un_btn_pass', 24, 554,", "'GFX_mvlv119_un_btn_pass', 24, 546,"),
 ("text_el('un_win_pass_vote_label', 24, 560,", "text_el('un_win_pass_vote_label', 24, 552,"),
 ("'GFX_mvlv119_un_btn_pass_grey', 24, 554,", "'GFX_mvlv119_un_btn_pass_grey', 24, 546,"),
 ("'GFX_mvlv119_un_btn_action', 236, 554,", "'GFX_mvlv119_un_btn_action', 236, 546,"),
 ("text_el('un_win_pay_label', 244, 557,", "text_el('un_win_pay_label', 244, 549,"),
 ("'GFX_mvlv119_un_btn_action', 236, 584,", "'GFX_mvlv119_un_btn_action', 236, 576,"),
 ("text_el('un_win_exit_label', 244, 587,", "text_el('un_win_exit_label', 244, 579,"),
 ("text_el('un_win_note', 484, 554,", "text_el('un_win_note', 484, 546,"),
]
n = 0
for a, b in pairs:
    if a in g:
        g = g.replace(a, b, 1)
        n += 1
    else:
        print('未命中:', a[:48])
print('顺延 %d 处' % n)

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')
