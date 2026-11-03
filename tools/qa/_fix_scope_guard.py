# -*- coding: utf-8 -*-
"""修正：页签判断被错写进 every_country 的 limit（国家作用域）。

上一版把 `check_variable = { mvlv_un_tab = 3 }` 放进了 every_country 的 limit，
而 mvlv_un_tab 只有玩家国家有 → 遍历时只有玩家自己被选中，
导致成员页只显示 1 个国家、会场三栏也只统计到 1 票。

正确做法：把页签判断提到 every_country 外面，用 if 包住整个遍历。
"""
import ast
import io
import re

CORE = 'mods/muvluvCNsub_xuerong/common/scripted_effects/zz_mvlv119_un_core.txt'
GEN = 'work/qa/_gen_un_window_gui.py'
T = chr(9)
NL = chr(10)

s = io.open(CORE, encoding='utf-8').read()


def extract_block(text, name):
    """取出 `name = { ... }` 的完整块（含花括号，按层数配对）。"""
    start = text.index(name + ' = {')
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise ValueError('块未闭合: ' + name)


# ---------------- refresh_lists ----------------
blk = extract_block(s, 'mvlv_un_refresh_lists')
new_blk = (
    'mvlv_un_refresh_lists = {' + NL +
    T + 'clear_array = global.mvlv_un_yes_list' + NL +
    T + 'clear_array = global.mvlv_un_no_list' + NL +
    T + 'clear_array = global.mvlv_un_abs_list' + NL +
    T + '# 只在会场页填三栏。页签判断必须放在 every_country 外面 ——' + NL +
    T + '# 放 limit 里会变成「逐个国家检查它自己的 tab 变量」，只有玩家会命中。' + NL +
    T + 'if = {' + NL +
    T + T + 'limit = { NOT = { check_variable = { mvlv_un_tab > 1 } } }' + NL +
    T + T + 'every_country = {' + NL +
    T + T + T + 'limit = { mvlv_un_is_member = yes }' + NL +
    T + T + T + 'if = { limit = { check_variable = { mvlv_un_stance = 1 } }' + NL +
    T + T + T + T + 'add_to_array = { global.mvlv_un_yes_list = THIS }' + NL +
    T + T + T + '}' + NL +
    T + T + T + 'else_if = { limit = { check_variable = { mvlv_un_stance = 3 } }' + NL +
    T + T + T + T + 'add_to_array = { global.mvlv_un_no_list = THIS }' + NL +
    T + T + T + '}' + NL +
    T + T + T + 'else = {' + NL +
    T + T + T + T + 'add_to_array = { global.mvlv_un_abs_list = THIS }' + NL +
    T + T + T + '}' + NL +
    T + T + '}' + NL +
    T + '}' + NL +
    T + 'add_to_variable = { global.mvlv_un_ui_version = 1 }' + NL +
    '}'
)
s = s.replace(blk, new_blk, 1)
print('refresh_lists 已重写（if 包住遍历）')

# ---------------- refresh_members ----------------
blk2 = extract_block(s, 'mvlv_un_refresh_members')
new_blk2 = (
    'mvlv_un_refresh_members = {' + NL +
    T + 'clear_array = global.mvlv_un_members' + NL +
    T + '# 只在成员页填，理由同 refresh_lists' + NL +
    T + 'if = {' + NL +
    T + T + 'limit = { check_variable = { mvlv_un_tab = 3 } }' + NL +
    T + T + 'every_country = {' + NL +
    T + T + T + 'limit = { mvlv_un_is_member = yes }' + NL +
    T + T + T + 'add_to_array = { global.mvlv_un_members = THIS }' + NL +
    T + T + '}' + NL +
    T + '}' + NL +
    T + 'add_to_variable = { global.mvlv_un_ui_version = 1 }' + NL +
    '}'
)
s = s.replace(blk2, new_blk2, 1)
print('refresh_members 已重写')

io.open(CORE, 'w', encoding='utf-8', newline='').write(s)
print('core.txt 已写入')
