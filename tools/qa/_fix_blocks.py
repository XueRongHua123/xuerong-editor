# -*- coding: utf-8 -*-
"""修三处：

1. 常任占位图 1×1 太小（引擎渲染成黑块）→ 重做成 32×32 全透明
2. 删掉 un_div_* 分割线（用了 add() 进 window 级，不是页面内，每页都显示且拉伸成块）
3. 金色：确认 GetUNMemberName 的调用链
"""
import io
import os
import re

from PIL import Image

PKG = 'mods/muvluvCNsub_xuerong'
GEN = 'work/qa/_gen_un_window_gui.py'
LOC = PKG + '/common/scripted_localisation/zz_mvlv119_un_loc.txt'
NL = chr(10)

# ---- 1) 32×32 透明占位 ----
png = os.path.join(PKG, 'gfx', 'interface', 'un', 'mvlv119_un_blank.png')
Image.new('RGBA', (32, 32), (0, 0, 0, 0)).save(png, 'PNG')
print('占位图重做为 32×32:', png)

# ---- 2) 删分割线 ----
g = io.open(GEN, encoding='utf-8').read()
before = g.count('un_div_')
g = re.sub(r'    # 模块分割线[^\n]*\n(?:    [^\n]*\n)*?        add\(indent[^\n]*\n', '', g)
# 兜底：把所有含 un_div_ 的行删掉
lines = [l for l in g.split(NL) if 'un_div_' not in l]
g = NL.join(lines)
after = g.count('un_div_')
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('分割线残留：%d → %d' % (before, after))

# ---- 3) 检查 GetUNMemberName ----
s = io.open(LOC, encoding='utf-8').read()
has = 'GetUNMemberName' in s
print('GetUNMemberName 存在:', has)
i = s.find('name = GetUNMemberName')
if i > 0:
    print(repr(s[i:i + 260]))
