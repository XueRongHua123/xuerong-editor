# -*- coding: utf-8 -*-
"""删掉所有 slotbg_* 的 background 块（文字模式下不需要底衬，浅底配白字更糊）。"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)
lines = io.open(GEN, encoding='utf-8').read().split(NL)

out = []
i = 0
removed = 0
while i < len(lines):
    if 'slotbg_' in lines[i]:
        # 往上找到 background = { 开头（可能在 out 里）
        start = len(out) - 1
        while start >= 0 and 'background' not in out[start]:
            start -= 1
        # 往下找到闭合 }
        j = i
        while j < len(lines) and lines[j].strip() != '}':
            j += 1
        if start >= 0:
            del out[start:]
            removed += 1
            i = j + 1
            continue
    out.append(lines[i])
    i += 1

g = NL.join(out)
ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('删除底衬块 %d 处，语法 OK' % removed)
