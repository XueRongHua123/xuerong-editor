# -*- coding: utf-8 -*-
"""精确删除 4 个 slotbg_* background 块（4 行一组，逐字匹配）。"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)
T = chr(9)

s = io.open(GEN, encoding='utf-8').read()
total = 0
for tag in ('yes', 'no', 'abs', 'mem'):
    block = (T * 3 + 'background = {' + NL +
             T * 4 + 'name = "slotbg_%s"' % tag + NL +
             T * 4 + 'spriteType = "GFX_mvlv119_un_slot_bg' + ('' if tag != 'mem' else '_wide') + '"' + NL +
             T * 3 + '}' + NL)
    if block in s:
        s = s.replace(block, '', 1)
        total += 1
        print('删除 slotbg_%s' % tag)
    else:
        # 试 add_entry 写法（成员条目）
        block2 = ("    add_entry('" + chr(92) + 'tbackground = {\')' + NL +
                  "    add_entry('" + chr(92) + 't' + chr(92) + 'tname = "slotbg_%s"\')' % tag + NL +
                  "    add_entry('" + chr(92) + 't' + chr(92) + 'tspriteType = "GFX_mvlv119_un_slot_bg' + ('' if tag != 'mem' else '_wide') + '"' + '\')' + NL +
                  "    add_entry('" + chr(92) + 't}\')' + NL)
        if block2 in s:
            s = s.replace(block2, '', 1)
            total += 1
            print('删除 slotbg_%s（add_entry 形式）' % tag)
        else:
            print('未命中 slotbg_%s' % tag)

print('共删 %d' % total)
ast.parse(s)
io.open(GEN, 'w', encoding='utf-8', newline='').write(s)
print('语法 OK')
