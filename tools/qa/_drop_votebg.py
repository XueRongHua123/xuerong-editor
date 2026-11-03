# -*- coding: utf-8 -*-
"""撤掉 grid_wrap 的 background（它会在不该出现的地方渲染成深色块）。

保留：国旗 scale 1.3、slotsize 96×20、grid 高 80。
亮度问题改用「把窗口底色换来对比」之外的简单办法：只放大国旗，不加底板。
"""
import ast
import io
import re

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)
BT = chr(92) + 't'

lines = io.open(GEN, encoding='utf-8').read().split(NL)
out = []
skip = 0
for ln in lines:
    if 'background = {' in ln and 'GFX_mvlv119_un_vote_bg' not in ln:
        if skip:
            skip -= 1
            out.append(ln)
            continue
    # 只删 grid_wrap 里那组三行
    if "background = {'," in ln and 'vote_bg' not in ln:
        # 检查后三行是不是 bg 定义
        idx = lines.index(ln)
        seg = NL.join(lines[idx:idx + 4])
        if 'GFX_mvlv119_un_vote_bg' in seg:
            out.append('# [removed] grid_wrap 底板（会误渲染成深色块）')
            skip = 3
            continue
    if skip and ln.strip().startswith(("'spriteType = \"GFX_mvlv119_un_vote_bg\"'", "'}'", "'name = \"bg\"'")):
        skip -= 1
        continue
    out.append(ln)

g = NL.join(out)
n = g.count('GFX_mvlv119_un_vote_bg')
ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('生成器里 vote_bg 残留:', n)
print('语法 OK')
