# -*- coding: utf-8 -*-
"""投票栏条目：国旗 + 文字 → 只留国名文字。

理由：`GFX_flag_small` 是配深色 UI 设计的低对比贴图，垫底衬也救不回来（已试两轮）。
成员页的 `[This.GetName]` 能正常显示，证明 entry 里文字可行。
之前投票栏报 ????? 是因为 `maxWidth = 62` 装不下 4-6 字国名，被裁出乱码。

改：
  1. 删除 entry 里的国旗 iconType 和 background 底衬
  2. 换成 instantTextBox：text = "mvlv_un_mem_name"（已验证的 key），hoi_12mbs，maxWidth 92
  3. entry size 88×20 → 96×20（对齐槽位宽）
"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)
T = chr(9)
BT = chr(92) + 't'

g = io.open(GEN, encoding='utf-8').read()

# 三个投票条目：整块替换容器体
for tag in ('yes', 'no', 'abs'):
    old = (BT + T + 'containerWindowType = {' + NL +
           BT + T + T + 'name = "mvlv_un_win_entry_%s"' % tag + NL +
           BT + T + T + 'position = { x = 0 y = 0 }' + NL +
           BT + T + T + 'size = { width = 88 height = 20 }' + NL +
           BT + T + T + 'background = {' + NL)
    new = (BT + T + 'containerWindowType = {' + NL +
           BT + T + T + 'name = "mvlv_un_win_entry_%s"' % tag + NL +
           BT + T + T + 'position = { x = 0 y = 0 }' + NL +
           BT + T + T + 'size = { width = 96 height = 20 }' + NL +
           BT + T + T + 'background = {' + NL)
    if old in g:
        g = g.replace(old, new, 1)
        print('entry_%s size 88 → 96' % tag)

# 把每个 entry 里的 iconType(flag) 换成 instantTextBox
import re
# 匹配 iconType 块（flag）
old_icon = (BT + T + T + 'iconType = {' + NL +
            BT + T + T + T + 'name = "mvlv_un_win_flag_%s"' + NL +
            BT + T + T + T + 'quadTextureSprite = "GFX_flag_small"' + NL +
            BT + T + T + T + 'position = { x = 0 y = 0 }' + NL +
            BT + T + T + T + 'Orientation = "UPPER_LEFT"' + NL +
            BT + T + T + '}' + NL)
new_text = (BT + T + T + 'instantTextBoxType = {' + NL +
            BT + T + T + T + 'name = "mvlv_un_win_name_%s"' + NL +
            BT + T + T + T + 'position = { x = 4 y = 4 }' + NL +
            BT + T + T + T + 'font = "hoi_12mbs"' + NL +
            BT + T + T + T + 'text = "mvlv_un_mem_name"' + NL +
            BT + T + T + T + 'format = left' + NL +
            BT + T + T + T + 'maxWidth = 88' + NL +
            BT + T + T + T + 'maxHeight = 16' + NL +
            BT + T + T + T + 'alwaystransparent = yes' + NL +
            BT + T + T + '}' + NL)
cnt = 0
for tag in ('yes', 'no', 'abs'):
    o = old_icon % tag
    if o in g:
        g = g.replace(o, new_text % tag, 1)
        cnt += 1
        print('entry_%s 国旗 → 国名文字' % tag)
print('替换 %d 个' % cnt)

# properties 里去掉 flag 绑定（元素已删）
for tag in ('yes', 'no', 'abs'):
    line = "    a('" + BT * 3 + 'mvlv_un_win_flag_%s = { image = "[This.GetFlag]" }\')' % tag
    if line in g:
        g = g.replace(line + NL, '', 1)
        print('properties 去掉 win_flag_%s' % tag)

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')
