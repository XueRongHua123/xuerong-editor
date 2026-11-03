# -*- coding: utf-8 -*-
"""两处修正：

1. 新增的预算数值文本改名 `un_win_budget_num`（`un_win_budget` 已被标题栏的「预算：」占用）
2. 生成器里删掉 `mvlv_un_win_yes/no/abs_grid` 的三条 dynamic_lists 生成代码
   （grid 元素早已移除，但生成器每次重跑会把旧绑定写回去，导致 _lint_un_gui FAIL）
"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)

g = io.open(GEN, encoding='utf-8').read()

# 1) 预算元素改名
n1 = g.count("text_el('un_win_budget'")
g = g.replace("text_el('un_win_budget',", "text_el('un_win_budget_num',")
print('预算元素改名：%d 处' % n1)

# 2) 删三条 dynamic_lists 生成代码
lines = g.split(NL)
out = []
removed = 0
i = 0
while i < len(lines):
    ln = lines[i]
    if any("mvlv_un_win_%s_grid' % tag" % t in ln or '"mvlv_un_win_%s_grid"' % t in ln
           or "mvlv_un_win_%s_grid = {" % t in ln for t in ('yes', 'no', 'abs')):
        # 找到这个块的结尾（括号配对）
        depth = ln.count('{') - ln.count('}')
        j = i
        while depth > 0 and j + 1 < len(lines):
            j += 1
            depth += lines[j].count('{') - lines[j].count('}')
        i = j + 1
        removed += 1
        continue
    out.append(ln)
    i += 1
g = NL.join(out)
print('删 dynamic_lists 生成代码：%d 处' % removed)

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')
