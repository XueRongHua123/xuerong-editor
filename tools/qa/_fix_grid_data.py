# -*- coding: utf-8 -*-
"""用「数组内容」控制 grid 显隐（前两个方案都无效的最终解）。

依据：`live_tally` 完全靠 `every_country` + stance 变量算票，四个数组
（members / yes_list / no_list / abs_list）只被 scripted_gui 的 grid 引用，
没有任何逻辑读取。清空数组 = grid 无内容 = 不显示。

改两处：
  1. core.txt 的 refresh_lists / refresh_members 按 tab 决定是否填充
  2. 生成器 tab click 里调用这两个 refresh（切页时重算）

tab 未设置时按第一页（会场）处理，与 agenda 的 `NOT = { tab > 1 }` 一致。
"""
import ast
import io

CORE = 'mods/muvluvCNsub_xuerong/common/scripted_effects/zz_mvlv119_un_core.txt'
GEN = 'work/qa/_gen_un_window_gui.py'

T = chr(9)
NL = chr(10)

s = io.open(CORE, encoding='utf-8').read()

# ---------- 1) refresh_lists 加 tab 门控 ----------
old_lists = (
    'mvlv_un_refresh_lists = {' + NL +
    T + 'clear_array = global.mvlv_un_yes_list' + NL +
    T + 'clear_array = global.mvlv_un_no_list' + NL +
    T + 'clear_array = global.mvlv_un_abs_list' + NL +
    T + 'every_country = {'
)
new_lists = (
    'mvlv_un_refresh_lists = {' + NL +
    T + 'clear_array = global.mvlv_un_yes_list' + NL +
    T + 'clear_array = global.mvlv_un_no_list' + NL +
    T + 'clear_array = global.mvlv_un_abs_list' + NL +
    T + '# 只在会场页填。dynamic_lists 的 grid 不认 _visible 触发器，' + NL +
    T + '# 也不受 properties 坐标影响，唯一可靠的办法是让它没内容。' + NL +
    T + 'if = { limit = { NOT = { check_variable = { mvlv_un_tab > 1 } } }' + NL +
    T + T + 'every_country = {'
)
assert old_lists in s, 'refresh_lists 锚点未命中'
s = s.replace(old_lists, new_lists, 1)

# 原来 every_country 的闭合要跟着多一层 if 的闭合：在 refresh_lists 末尾的
# `add_to_variable = { global.mvlv_un_ui_version = 1 }` 之前补一个 `}`
old_tail = (
    T + '}' + NL +
    T + 'add_to_variable = { global.mvlv_un_ui_version = 1 }' + NL +
    '}' + NL + NL + NL +
    '# 三栏分组'
)
new_tail = (
    T + '}' + NL +
    T + '}' + NL +          # 闭合新加的 if
    T + 'add_to_variable = { global.mvlv_un_ui_version = 1 }' + NL +
    '}' + NL + NL + NL +
    '# 三栏分组'
)
assert old_tail in s, 'refresh_lists 尾部未命中'
s = s.replace(old_tail, new_tail, 1)
print('refresh_lists 已加 tab 门控')

# ---------- 2) refresh_members 加 tab 门控 ----------
old_mem = (
    'mvlv_un_refresh_members = {' + NL +
    T + 'clear_array = global.mvlv_un_members' + NL +
    T + 'every_country = {' + NL +
    T + T + 'limit = { mvlv_un_is_member = yes }' + NL +
    T + T + 'add_to_array = { global.mvlv_un_members = THIS }' + NL +
    T + '}' + NL +
    T + 'add_to_variable = { global.mvlv_un_ui_version = 1 }' + NL +
    '}'
)
new_mem = (
    'mvlv_un_refresh_members = {' + NL +
    T + 'clear_array = global.mvlv_un_members' + NL +
    T + '# 只在成员页填，理由同 refresh_lists' + NL +
    T + 'if = { limit = { check_variable = { mvlv_un_tab = 3 } }' + NL +
    T + T + 'every_country = {' + NL +
    T + T + T + 'limit = { mvlv_un_is_member = yes }' + NL +
    T + T + T + 'add_to_array = { global.mvlv_un_members = THIS }' + NL +
    T + T + '}' + NL +
    T + '}' + NL +
    T + 'add_to_variable = { global.mvlv_un_ui_version = 1 }' + NL +
    '}'
)
assert old_mem in s, 'refresh_members 锚点未命中'
s = s.replace(old_mem, new_mem, 1)
print('refresh_members 已加 tab 门控')

io.open(CORE, 'w', encoding='utf-8', newline='').write(s)

# ---------- 3) tab click 里调用两个 refresh ----------
lines = io.open(GEN, encoding='utf-8').read().split(NL)
i_set = next(i for i, l in enumerate(lines)
             if 'set_variable = { mvlv_un_tab = %d }' in l)
add = [
    "        a('" + (chr(92) + 't') * 3 + "mvlv_un_refresh_lists = yes')",
    "        a('" + (chr(92) + 't') * 3 + "mvlv_un_refresh_members = yes')",
]
lines[i_set + 1:i_set + 1] = add
src = NL.join(lines)
ast.parse(src)
io.open(GEN, 'w', encoding='utf-8', newline='').write(src)
print('tab click 已加 refresh 调用，生成器语法 OK')
