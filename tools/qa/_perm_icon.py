# -*- coding: utf-8 -*-
"""常任理事国：用国家精神图标替代金色★（成员页每行）。

做法：
  1. 生成 1×1 透明 png 并注册 `GFX_mvlv119_un_blank`（非常任的占位）
  2. 成员条目里在国名前加一个 iconType（`mvlv_un_mem_perm`）
  3. properties 里用 `image = "[GetUNPermIcon]"` 绑定（原版有先例：
     `image = "[GetPropagandaCenterSlotAge]"`）
  4. scripted loc `GetUNPermIcon`：常任返回 `GFX_idea_mvlv_parmanent`，否则 blank
  5. 国名 loc 去掉 ★，名字右移让出图标位
  6. 删掉上一轮错放到会场页的图例图标
"""
import ast
import io
import os

from PIL import Image

PKG = 'mods/muvluvCNsub_xuerong'
GEN = 'work/qa/_gen_un_window_gui.py'
LOC = PKG + '/common/scripted_localisation/zz_mvlv119_un_loc.txt'
GFXF = PKG + '/interface/zz_mvlv119_un_assets.gfx'
ZH = PKG + '/localisation/simp_chinese/replace/zz_mvlv119_un_l_simp_chinese.yml'
EN = PKG + '/localisation/english/replace/zz_mvlv119_un_l_english.yml'
T = chr(9)
NL = chr(10)

# ---------- 1) 透明占位图 + gfx ----------
png_dir = os.path.join(PKG, 'gfx', 'interface', 'un')
png = os.path.join(png_dir, 'mvlv119_un_blank.png')
os.makedirs(png_dir, exist_ok=True)
Image.new('RGBA', (1, 1), (0, 0, 0, 0)).save(png, 'PNG')
print('已生成透明占位图:', png)

s = io.open(GFXF, encoding='utf-8-sig').read()
if 'GFX_mvlv119_un_blank' not in s:
    block = (T + 'spriteType = {' + NL +
             T + T + 'name = "GFX_mvlv119_un_blank"' + NL +
             T + T + 'texturefile = "gfx/interface/un/mvlv119_un_blank.png"' + NL +
             T + '}' + NL)
    i = s.rstrip().rfind('}')
    s = s[:i] + block + s[i:]
    io.open(GFXF, 'w', encoding='utf-8', newline='').write(s)
    print('已注册 GFX_mvlv119_un_blank')
else:
    print('blank sprite 已存在')

# ---------- 2) 生成器：删图例、条目加图标、名字右移 ----------
g = io.open(GEN, encoding='utf-8').read()

# 删掉上一轮错放的图例图标（它默认 page=1 落到了会场页）
import re
g = re.sub(r"\n    # 常任理事国图例：沿用国家精神「常任理事国」的图标\n    icon_el\('un_win_mem_perm_icon'[^\n]*\n", "\n", g)
g = g.replace("text_el('un_win_mem_hint', 52, 224,", "text_el('un_win_mem_hint', 24, 224,", 1)
print('已删图例图标，说明文字复位')

# 条目内：国名前加图标，名字右移
old_name = """		instantTextBoxType = {
			name = "mvlv_un_mem_name"
			position = { x = 32 y = 7 }"""
new_name = """		iconType = {
			name = "mvlv_un_mem_perm"
			spriteType = "GFX_mvlv119_un_blank"
			position = { x = 32 y = 6 }
			Orientation = "UPPER_LEFT"
		}

		instantTextBoxType = {
			name = "mvlv_un_mem_name"
			position = { x = 56 y = 7 }"""
if 'mvlv_un_mem_perm"' not in g:
    assert old_name in g, 'mem_name 锚点未命中'
    g = g.replace(old_name, new_name, 1)
    # 名字宽度收窄，给图标让位
    g = g.replace("'GetUNMemberName', 196, 18", "'mvlv_un_mem_name', 172, 18")
    g = g.replace("'mvlv_un_mem_name', 196, 18", "'mvlv_un_mem_name', 172, 18")
    print('条目已加图标位，名字右移 24px')
else:
    print('条目图标已存在')

# properties 增加绑定
old_prop = "    a('" + T + T + T + "mvlv_un_mem_flag = { image = \"[This.GetFlag]\" }')"
new_prop = (old_prop + NL +
            "    a('" + T + T + T + "mvlv_un_mem_perm = { image = \"[GetUNPermIcon]\" }')")
if 'GetUNPermIcon' not in g:
    assert old_prop in g, 'properties 锚点未命中'
    g = g.replace(old_prop, new_prop, 1)
    print('properties 已绑定 GetUNPermIcon')

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('生成器语法 OK')

# ---------- 3) scripted loc ----------
s = io.open(LOC, encoding='utf-8').read()
if 'GetUNPermIcon' not in s:
    block = (NL + 'defined_text = {' + NL +
             T + '# 常任理事国标记：常任返回国家精神图标，其余返回 1×1 透明占位' + NL +
             T + 'name = GetUNPermIcon' + NL +
             T + 'text = {' + NL +
             T + T + 'trigger = { mvlv_un_is_permanent = yes }' + NL +
             T + T + 'localization_key = mvlv_un_perm_icon_on' + NL +
             T + '}' + NL +
             T + 'text = {' + NL +
             T + T + 'localization_key = mvlv_un_perm_icon_off' + NL +
             T + '}' + NL +
             '}' + NL)
    s = s.rstrip() + NL + block
    io.open(LOC, 'w', encoding='utf-8', newline='').write(s)
    print('已加 GetUNPermIcon')

# ---------- 4) loc：图标键 + 去掉 ★ ----------
for p in (ZH, EN):
    s = io.open(p, encoding='utf-8-sig').read()
    s = s.replace(' mvlv_un_mem_name_perm:0 "★ [This.GetName]"',
                  ' mvlv_un_perm_icon_on:0 "GFX_idea_mvlv_parmanent"', 1)
    if 'mvlv_un_perm_icon_off' not in s:
        i = s.find(' mvlv_un_perm_icon_on:0')
        eol = s.find(chr(10), i)
        s = s[:eol] + chr(10) + ' mvlv_un_perm_icon_off:0 "GFX_mvlv119_un_blank"' + s[eol:]
    io.open(p, 'w', encoding='utf-8-sig', newline='').write(s)
    b = open(p, 'rb').read()
    bom = b.startswith(b'\xef\xbb\xbf')
    if bom:
        b = b[3:]
    t = b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    open(p, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + t)
    print('loc 已更新:', p.split('/')[-1])
