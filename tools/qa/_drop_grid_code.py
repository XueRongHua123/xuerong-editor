# -*- coding: utf-8 -*-
"""删生成器里三条 win_*_grid 的 dynamic_lists 生成代码（用简单子串匹配）。"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)

lines = io.open(GEN, encoding='utf-8').read().split(NL)
out = []
removed = 0
i = 0
while i < len(lines):
    ln = lines[i]
    if ('win_yes_grid' in ln) or ('win_no_grid' in ln) or ('win_abs_grid' in ln):
        depth = ln.count('{') - ln.count('}')
        j = i
        while depth > 0 and j + 1 < len(lines):
            j += 1
            depth += lines[j].count('{') - lines[j].count('}')
        print('删除 L%d: %s' % (i + 1, ln.strip()[:60]))
        i = j + 1
        removed += 1
        continue
    out.append(ln)
    i += 1

g = NL.join(out)
ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('共删 %d 处，语法 OK' % removed)
