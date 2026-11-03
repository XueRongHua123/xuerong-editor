# -*- coding: utf-8 -*-
"""会场页三栏 UI 调整：

1. grid 高度 88 → 112（7 行 × 16px，13 国排得下；slotsize 20 → 16 更紧凑）
2. 按钮/倒计时/通过投票整体下移，给三栏腾地方
3. 三栏只在「有进行中的表决」时填充 —— 否则没开会时 13 个成员默认弃权，
   旗子全堆在弃权栏下面，看起来像「国旗属于弃权」
"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
CORE = 'mods/muvluvCNsub_xuerong/common/scripted_effects/zz_mvlv119_un_core.txt'
T = chr(9)
NL = chr(10)

s = io.open(GEN, encoding='utf-8').read()

# ---- 1) grid 尺寸 ----
old_grid = (
    "    grid_el('mvlv_un_win_yes_grid', 322, 324, 190, 88, 92, 20, 2)" + NL +
    "    grid_el('mvlv_un_win_no_grid', 534, 324, 190, 88, 92, 20, 2)" + NL +
    "    grid_el('mvlv_un_win_abs_grid', 746, 324, 190, 88, 92, 20, 2)"
)
new_grid = (
    "    # 每行 2 枚，7 行放得下 13 国；slotsize 压到 16 高，省出按钮的位置" + NL +
    "    grid_el('mvlv_un_win_yes_grid', 322, 324, 190, 112, 92, 16, 2)" + NL +
    "    grid_el('mvlv_un_win_no_grid', 534, 324, 190, 112, 92, 16, 2)" + NL +
    "    grid_el('mvlv_un_win_abs_grid', 746, 324, 190, 112, 92, 16, 2)"
)
assert old_grid in s, 'grid 行未命中'
s = s.replace(old_grid, new_grid, 1)

# ---- 2) 按钮与倒计时下移 ----
pairs = [
    ("button_el('mvlv_un_vote_%s' % tag, 'GFX_mvlv119_un_btn_vote', x, 424,",
     "button_el('mvlv_un_vote_%s' % tag, 'GFX_mvlv119_un_btn_vote', x, 446,"),
    ("text_el('un_win_vote_%s_label' % tag, x, 430,",
     "text_el('un_win_vote_%s_label' % tag, x, 452,"),
    ("text_el('un_win_days', 320, 460,",
     "text_el('un_win_days', 320, 482,"),
    ("button_el('mvlv_un_pass_vote', 'GFX_mvlv119_un_btn_pass', 320, 486,",
     "button_el('mvlv_un_pass_vote', 'GFX_mvlv119_un_btn_pass', 320, 508,"),
    ("text_el('un_win_pass_vote_label', 320, 492,",
     "text_el('un_win_pass_vote_label', 320, 514,"),
    ("button_el('mvlv_un_pass_vote_grey', 'GFX_mvlv119_un_btn_pass_grey', 320, 486,",
     "button_el('mvlv_un_pass_vote_grey', 'GFX_mvlv119_un_btn_pass_grey', 320, 508,"),
]
for old, new in pairs:
    if old not in s:
        print('未命中:', old[:50])
        continue
    s = s.replace(old, new, 1)

ast.parse(s)
io.open(GEN, 'w', encoding='utf-8', newline='').write(s)
print('生成器坐标已调整，语法 OK')

# ---- 3) 只有表决中才填三栏 ----
c = io.open(CORE, encoding='utf-8').read()
old_cond = (T + T + 'limit = { NOT = { check_variable = { mvlv_un_tab > 1 } } }')
new_cond = (T + T + 'limit = {' + NL +
            T + T + T + 'NOT = { check_variable = { mvlv_un_tab > 1 } }' + NL +
            T + T + T + '# 只在本会期有进行中的表决时填三栏；没开会时全员默认弃权，' + NL +
            T + T + T + '# 旗子会全堆在弃权栏下面，看起来像国旗属于弃权。' + NL +
            T + T + T + 'check_variable = { global.mvlv_un_pending = 1 }' + NL +
            T + T + '}')
assert old_cond in c, 'refresh_lists 条件未命中'
c = c.replace(old_cond, new_cond, 1)
io.open(CORE, 'w', encoding='utf-8', newline='').write(c)
print('refresh_lists 已加「表决中」条件')
