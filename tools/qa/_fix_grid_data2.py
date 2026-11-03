# -*- coding: utf-8 -*-
"""用数组内容控制 grid 显隐：给 refresh_* 的 every_country limit 加页签条件。

比插 if 块更简单：不改结构，只在 limit 里多一行。
数组只被 scripted_gui 的 grid 引用，无逻辑依赖（live_tally 靠 stance 变量算票）。
"""
import ast
import io

CORE = 'mods/muvluvCNsub_xuerong/common/scripted_effects/zz_mvlv119_un_core.txt'
GEN = 'work/qa/_gen_un_window_gui.py'
T = chr(9)
NL = chr(10)

s = io.open(CORE, encoding='utf-8').read()

# ---- refresh_lists：三栏只在会场页填 ----
old1 = (T + T + 'limit = { mvlv_un_is_member = yes }' + NL +
        T + T + 'if = { limit = { check_variable = { mvlv_un_stance = 1 } }')
new1 = (T + T + 'limit = {' + NL +
        T + T + T + 'mvlv_un_is_member = yes' + NL +
        T + T + T + '# grid 不认 _visible，靠不填数组来控制显示（只在会场页）' + NL +
        T + T + T + 'NOT = { check_variable = { mvlv_un_tab > 1 } }' + NL +
        T + T + '}' + NL +
        T + T + 'if = { limit = { check_variable = { mvlv_un_stance = 1 } }')
assert old1 in s, 'refresh_lists limit 未命中'
s = s.replace(old1, new1, 1)
print('refresh_lists 已加页签条件')

# ---- refresh_members：只在成员页填 ----
old2 = (T + T + 'limit = { mvlv_un_is_member = yes }' + NL +
        T + T + 'add_to_array = { global.mvlv_un_members = THIS }')
new2 = (T + T + 'limit = {' + NL +
        T + T + T + 'mvlv_un_is_member = yes' + NL +
        T + T + T + '# 只在成员页填，理由同 refresh_lists' + NL +
        T + T + T + 'check_variable = { mvlv_un_tab = 3 }' + NL +
        T + T + '}' + NL +
        T + T + 'add_to_array = { global.mvlv_un_members = THIS }')
assert old2 in s, 'refresh_members limit 未命中'
s = s.replace(old2, new2, 1)
print('refresh_members 已加页签条件')

io.open(CORE, 'w', encoding='utf-8', newline='').write(s)

# ---- tab click 里调两个 refresh ----
lines = io.open(GEN, encoding='utf-8').read().split(NL)
i_set = next(i for i, l in enumerate(lines)
             if 'set_variable = { mvlv_un_tab = %d }' in l)
BT = chr(92) + 't'
add = [
    "        a('" + BT * 3 + "mvlv_un_refresh_lists = yes')",
    "        a('" + BT * 3 + "mvlv_un_refresh_members = yes')",
]
lines[i_set + 1:i_set + 1] = add
src = NL.join(lines)
ast.parse(src)
io.open(GEN, 'w', encoding='utf-8', newline='').write(src)
print('tab click 已加 refresh，生成器语法 OK')
