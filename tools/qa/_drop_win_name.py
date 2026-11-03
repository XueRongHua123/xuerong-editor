# -*- coding: utf-8 -*-
"""投票三栏的条目去掉国名文本，只留国旗 + 点击区（对齐原版 MTG 做法）。

原因：entry 里的 instantTextBox 用 loc key `mvlv_un_flag_name`（值 [This.GetName]），
在 dynamic_lists 克隆出来的条目里求值失败，显示成一串 ?????。
原版 MTG 的投票条目只画国旗，名字放 pdx_tooltip。

改生成器：删掉三个 win_entry 块里的 instantTextBoxType（win_name_yes/no/abs），
国旗的 tooltip 加一句"点旗游说"。
"""
import ast
import io
import re

GEN = 'work/qa/_gen_un_window_gui.py'
lines = io.open(GEN, encoding='utf-8').read().split(chr(10))
NL = chr(10)

# 定位三个 win_name 文本块（生成器里是字符串列表元素，形如
#   '\t\t\t\tname = "mvlv_un_win_name_yes"' 等）
# 块结构：instantTextBoxType = { name = ... position = ... font = ... text = "mvlv_un_flag_name" ... }
out = []
i = 0
removed = 0
while i < len(lines):
    ln = lines[i]
    if 'win_name_yes' in ln or 'win_name_no' in ln or 'win_name_abs' in ln:
        # 往回找 instantTextBoxType 开头，往前找到对应的 '}' 结束
        start = len(out) - 1
        while start >= 0 and "instantTextBoxType" not in out[start]:
            start -= 1
        # 往前找该块的结束行（缩进相同的 '}' ）
        j = i
        while j < len(lines) and lines[j].strip() != '}':
            j += 1
        if start >= 0:
            del out[start:]
            removed += 1
            print('删除 %s 的文本块（L%d-L%d）' % (ln.strip()[:40], start + 1, j + 1))
        i = j + 1
        continue
    out.append(ln)
    i += 1

src = NL.join(out)
ast.parse(src)
io.open(GEN, 'w', encoding='utf-8', newline='').write(src)
print('已删除 %d 个文本块，生成器语法 OK' % removed)
