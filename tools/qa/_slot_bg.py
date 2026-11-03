# -*- coding: utf-8 -*-
"""给投票/成员条目加深色底衬（解决国旗看不清）。

原因：`GFX_flag_small` 是彩色国旗贴图，铺在窗口深蓝底（20,34,46）上对比度极低。
做法：在**条目容器内部**加 background（不是 window 级，避免上次那种错位），
铺一张浅蓝灰底（170,190,205），国旗就浮出来了。

每个容器的 background 用唯一名字（上次四处都用 "bg"，怀疑是错位根源）。
"""
import ast
import io
import os

from PIL import Image

PKG = 'mods/muvluvCNsub_xuerong'
DIR = os.path.join(PKG, 'gfx', 'interface', 'un')
GFXF = PKG + '/interface/zz_mvlv119_un_assets.gfx'
GEN = 'work/qa/_gen_un_window_gui.py'
T = chr(9)
NL = chr(10)
BT = chr(92) + 't'

# ---- 1) 浅底图 ----
png = os.path.join(DIR, 'mvlv119_un_slot_bg.png')
Image.new('RGBA', (32, 32), (170, 190, 205, 255)).save(png, 'PNG')
print('底衬图:', os.path.basename(png), '(170,190,205)')

s = io.open(GFXF, encoding='utf-8-sig').read()
if 'GFX_mvlv119_un_slot_bg' not in s:
    block = (T + 'spriteType = {' + NL + T + T + 'name = "GFX_mvlv119_un_slot_bg"' + NL +
             T + T + 'texturefile = "gfx/interface/un/mvlv119_un_slot_bg.png"' + NL + T + '}' + NL)
    i = s.rstrip().rfind('}')
    io.open(GFXF, 'w', encoding='utf-8', newline='').write(s[:i] + block + s[i:])
    print('已注册 GFX_mvlv119_un_slot_bg')

lines = io.open(GEN, encoding='utf-8').read().split(NL)
out = []
injected = 0
i = 0
while i < len(lines):
    ln = lines[i]
    # 三个投票条目：在 size 行之后插 background
    if ('name = "mvlv_un_win_entry_yes"' in ln or
            'name = "mvlv_un_win_entry_no"' in ln or
            'name = "mvlv_un_win_entry_abs"' in ln):
        tag = ln.split('entry_')[1].split('"')[0]
        out.append(ln)
        # 后面依次是 position / size / 空行
        for k in range(1, 4):
            out.append(lines[i + k])
        out.append('')
        out.append(BT + T + T + T + 'background = {')
        out.append(BT + T + T + T + T + 'name = "slotbg_%s"' % tag)
        out.append(BT + T + T + T + T + 'spriteType = "GFX_mvlv119_un_slot_bg"')
        out.append(BT + T + T + T + '}')
        i += 4
        injected += 1
        print('投票条目 %s 加底衬' % tag)
        continue
    out.append(ln)
    i += 1

g = NL.join(out)

# 成员条目：容器里 size 之后（那一块是 add_entry 系列）
old_mem = "    add_entry('" + BT + "size = { width = 450 height = 30 }')" + NL + "    add_entry('')"
new_mem = ("    add_entry('" + BT + "size = { width = 450 height = 30 }')" + NL +
           "    add_entry('')" + NL +
           "    add_entry('" + BT + "background = {')" + NL +
           "    add_entry('" + BT + T + "name = \"slotbg_mem\"')" + NL +
           "    add_entry('" + BT + T + "spriteType = \"GFX_mvlv119_un_slot_bg\"')" + NL +
           "    add_entry('" + BT + "}')")
if 'slotbg_mem' not in g and old_mem in g:
    g = g.replace(old_mem, new_mem, 1)
    print('成员条目加底衬')

print('投票条目注入 %d 个' % injected)
ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')
