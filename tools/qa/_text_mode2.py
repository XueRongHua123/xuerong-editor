# -*- coding: utf-8 -*-
"""投票栏改文字模式（行级扫描，不依赖转义形式）。

现状：entry 里是 iconType(国旗) + background(slotbg_X)，国旗在深色底上看不清。
目标：换成 instantTextBox 显示国名（成员页已验证 `mvlv_un_mem_name` 可用），
      删掉底衬和国旗，size 88×20 → 96×20。
"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)
T = chr(9)

lines = io.open(GEN, encoding='utf-8').read().split(NL)
out = []
i = 0
stats = {'size': 0, 'icon': 0, 'bg': 0}
cur_tag = None

while i < len(lines):
    ln = lines[i]
    m = ln.strip().startswith('name = "mvlv_un_win_entry_')
    if m:
        cur_tag = ln.strip().split('entry_')[1].split('"')[0]
    # size 88 → 96
    if cur_tag and 'size = { width = 88 height = 20 }' in ln:
        out.append(ln.replace('width = 88', 'width = 96'))
        stats['size'] += 1
        i += 1
        continue
    # 底衬块：background = { ... slotbg_X ... }
    if cur_tag and ln.strip() == 'background = {':
        j = i
        blk = []
        while j < len(lines):
            blk.append(lines[j])
            if lines[j].strip() == '}':
                break
            j += 1
        if any('slotbg_' in b for b in blk):
            i = j + 1
            stats['bg'] += 1
            continue
    # 国旗块：iconType = { ... mvlv_un_win_flag_X ... }
    if cur_tag and ln.strip() == 'iconType = {':
        j = i
        blk = []
        while j < len(lines):
            blk.append(lines[j])
            if lines[j].strip() == '}':
                break
            j += 1
        if any('mvlv_un_win_flag_' in b for b in blk):
            ind = ln[:len(ln) - len(ln.lstrip())]
            tag = cur_tag
            out.append(ind + 'instantTextBoxType = {')
            out.append(ind + T + 'name = "mvlv_un_win_name_%s"' % tag)
            out.append(ind + T + 'position = { x = 4 y = 4 }')
            out.append(ind + T + 'font = "hoi_12mbs"')
            out.append(ind + T + 'text = "mvlv_un_mem_name"')
            out.append(ind + T + 'format = left')
            out.append(ind + T + 'maxWidth = 88')
            out.append(ind + T + 'maxHeight = 16')
            out.append(ind + T + 'alwaystransparent = yes')
            out.append(ind + '}')
            i = j + 1
            stats['icon'] += 1
            continue
    out.append(ln)
    i += 1

g = NL.join(out)

# properties 去掉三个 flag 绑定（元素已删）
for tag in ('yes', 'no', 'abs'):
    for pat in ('mvlv_un_win_flag_%s = { image = "[This.GetFlag]" }' % tag,):
        g = NL.join([l for l in g.split(NL) if pat not in l])

print('size 改 %d，国旗→文字 %d，底衬删 %d' % (stats['size'], stats['icon'], stats['bg']))
ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')
