# -*- coding: utf-8 -*-
"""三处修正：

1. 常任徽章 60×68 太大 → scale 0.42（约 25×29），位置 (32,2)，不压国名
2. 常任国名改金色：`mvlv_un_mem_name` 指向 `[GetUNMemberName]`，
   常任分支用 `§Y...§!`；`_perm` 的 ★ 去掉（图标已经替代）
3. 会场页加三条分割线（信息行 / 议程 / 三栏之间），用 background 拉伸 chip 当细线
"""
import ast
import io

PKG = 'mods/muvluvCNsub_xuerong'
GEN = 'work/qa/_gen_un_window_gui.py'
ZH = PKG + '/localisation/simp_chinese/replace/zz_mvlv119_un_l_simp_chinese.yml'
EN = PKG + '/localisation/english/replace/zz_mvlv119_un_l_english.yml'
T = chr(9)
NL = chr(10)
BS = chr(92)

g = io.open(GEN, encoding='utf-8').read()

# ---- 1) 徽章缩小 ----
old = """    perm = ['iconType = {', '""" + T + """name = "mvlv_un_mem_perm"',"""
if 'mvlv_un_mem_perm' in g and 'scale' not in g.split('mvlv_un_mem_perm')[1][:400]:
    old_block = ("""    perm = ['iconType = {', '""" + T + """name = "mvlv_un_mem_perm"',""" + NL +
                 """            '""" + T + """spriteType = "GFX_mvlv119_un_blank"',""" + NL +
                 """            '""" + T + """position = { x = 32 y = 6 }',""" + NL +
                 """            '""" + T + """Orientation = "UPPER_LEFT"', '}']""")
    new_block = ("""    # 国家精神图标原图 60×68，缩到 0.42 才不压住国名（行高 30）
    perm = ['iconType = {', '""" + T + """name = "mvlv_un_mem_perm"',""" + NL +
             """            '""" + T + """spriteType = "GFX_mvlv119_un_blank"',""" + NL +
             """            '""" + T + """position = { x = 30 y = 1 }',""" + NL +
             """            '""" + T + """scale = 0.42',""" + NL +
             """            '""" + T + """Orientation = "UPPER_LEFT"', '}']""")
    assert old_block in g, 'perm 块未命中'
    g = g.replace(old_block, new_block, 1)
    print('徽章已缩放到 0.42，位置 (30,1)')
else:
    print('徽章块状态未识别，跳过')

# ---- 3) 分割线 ----
div_fn = '''    # 模块分割线：用 chip 图当细条拉伸（background 会撑满容器）
    for i, y in enumerate((288, 350, 476)):
        lines_ = ['containerWindowType = {', '\\tname = "un_div_%d"' % (i + 1),
                  '\\tposition = { x = 24 y = %d }' % y,
                  '\\tsize = { width = 932 height = 2 }',
                  '\\tbackground = {', '\\t\\tname = "d"',
                  '\\t\\tspriteType = "GFX_mvlv119_un_chip"', '\\t}', '}']
        add(indent('\\n'.join(lines_), 2))
'''
if 'un_div_1' not in g:
    anchor = "    # ---- 三栏：不等宽（赞成/反对是少数，弃权是常态）----"
    assert anchor in g, '分割线插入锚点未命中'
    g = g.replace(anchor, div_fn + '\n' + anchor, 1)
    print('已插入三条分割线（y=288/350/476）')

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('生成器语法 OK')

# ---- 2) 金色国名 ----
for p in (ZH, EN):
    s = io.open(p, encoding='utf-8-sig').read()
    s = s.replace(' mvlv_un_mem_name:0 "[This.GetName]"',
                  ' mvlv_un_mem_name:0 "[GetUNMemberName]"', 1)
    s = s.replace(' mvlv_un_mem_name_perm:0 "★ [This.GetName]"',
                  ' mvlv_un_mem_name_perm:0 "\\u00a7Y[This.GetName]\\u00a7!"', 1)
    io.open(p, 'w', encoding='utf-8-sig', newline='').write(s)
    b = open(p, 'rb').read()
    bom = b.startswith(b'\xef\xbb\xbf')
    if bom:
        b = b[3:]
    t = b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    open(p, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + t)
    print('loc 已改:', p.split('/')[-1])
