# -*- coding: utf-8 -*-
"""会场页三栏去掉格子，只留计数 + 指路。

原因：voting grid 的条目在本页面渲染异常（国旗、文字、底衬都不显示，只剩深色空框），
与成员页同一套 grid 配置、同样 dynamic_lists 绑定，差异只在所属页面，根因未查明。
不再试错，改为：三栏保留标题与计数（chip 正常），下方一行提示去成员页看具体立场。

同时删掉 scripted_gui 里三条 win_*_grid 的 dynamic_lists 绑定（grid 元素已不存在）。
"""
import ast
import io

PKG = 'mods/muvluvCNsub_xuerong'
GEN = 'work/qa/_gen_un_window_gui.py'
SG = PKG + '/common/scripted_guis/zz_mvlv119_un_window.txt'
NL = chr(10)
T = chr(9)

# ---- 1) 生成器：删三个 grid，加提示行 ----
g = io.open(GEN, encoding='utf-8').read()
old = "    for x, w, cols, tag in LANES:\n"
if "grid_el('mvlv_un_win_%s_grid'" in g:
    # 定位 grid_el 那一行并删除（在 LANES 循环内）
    lines = g.split(NL)
    lines = [l for l in lines if "grid_el('mvlv_un_win_%s_grid'" not in l]
    g = NL.join(lines)
    print('已删三栏 grid')

# 在 LANES 循环之后加提示行（找按钮循环前的位置）
anchor = "    # ---- 投票按钮：各自栏下方对齐 ----"
hint = ("    # 各国具体立场去成员页看：voting grid 在本页面渲染异常，暂不展示\n"
        "    text_el('un_win_vote_hint', 24, 442, 'hoi_16mbs', 'mvlv_un_vote_hint', 932, 20)\n\n")
if 'un_win_vote_hint' not in g and anchor in g:
    g = g.replace(anchor, hint + anchor, 1)
    print('已加指路提示行')

# 按钮上移到 grid 删除后的位置
pairs = [
 ("'GFX_mvlv119_un_btn_vote', bx, 538,", "'GFX_mvlv119_un_btn_vote', bx, 476,"),
 ("text_el('un_win_vote_%s_label' % tag, bx, 544,", "text_el('un_win_vote_%s_label' % tag, bx, 482,"),
 ("text_el('un_win_days', 24, 576,", "text_el('un_win_days', 24, 514,"),
 ("'GFX_mvlv119_un_btn_pass', 24, 594,", "'GFX_mvlv119_un_btn_pass', 24, 532,"),
 ("text_el('un_win_pass_vote_label', 24, 600,", "text_el('un_win_pass_vote_label', 24, 538,"),
 ("'GFX_mvlv119_un_btn_pass_grey', 24, 594,", "'GFX_mvlv119_un_btn_pass_grey', 24, 532,"),
 ("'GFX_mvlv119_un_btn_action', 236, 594,", "'GFX_mvlv119_un_btn_action', 236, 532,"),
 ("text_el('un_win_pay_label', 244, 597,", "text_el('un_win_pay_label', 244, 535,"),
 ("'GFX_mvlv119_un_btn_action', 236, 624,", "'GFX_mvlv119_un_btn_action', 236, 562,"),
 ("text_el('un_win_exit_label', 244, 627,", "text_el('un_win_exit_label', 244, 565,"),
 ("text_el('un_win_note', 484, 546,", "text_el('un_win_note', 484, 532,"),
]
n = 0
for a, b in pairs:
    if a in g:
        g = g.replace(a, b, 1)
        n += 1
print('顺延 %d 处' % n)

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('生成器语法 OK')

# ---- 2) scripted_gui：删三条 dynamic_lists ----
s = io.open(SG, encoding='utf-8').read()
for tag in ('yes', 'no', 'abs'):
    key = 'mvlv_un_win_%s_grid = {' % tag
    if key not in s:
        continue
    i = s.index(key)
    # 往前取行首，往后取到匹配的 }
    start = s.rfind(chr(10), 0, i) + 1
    depth = 0
    j = i
    while j < len(s):
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0:
                break
        j += 1
    end = s.find(chr(10), j) + 1
    s = s[:start] + s[end:]
    print('删除 dynamic_lists: win_%s_grid' % tag)
io.open(SG, 'w', encoding='utf-8', newline='').write(s)

# ---- 3) loc：提示文案 ----
ZH = PKG + '/localisation/simp_chinese/replace/zz_mvlv119_un_l_simp_chinese.yml'
EN = PKG + '/localisation/english/replace/zz_mvlv119_un_l_english.yml'
for p, val in ((ZH, '各国具体立场见「成员」页，点旗子可游说。'),
               (EN, 'See the Members page for individual stances.')):
    s = io.open(p, encoding='utf-8-sig').read()
    if ' mvlv_un_vote_hint:' in s:
        continue
    anchor2 = ' mvlv_un_window_days:'
    i = s.find(anchor2)
    if i < 0:
        print('loc 锚点未命中:', p.split('/')[-1])
        continue
    eol = s.find(chr(10), i)
    s = s[:eol] + chr(10) + ' mvlv_un_vote_hint:0 "%s"' % val + s[eol:]
    io.open(p, 'w', encoding='utf-8-sig', newline='').write(s)
    b = open(p, 'rb').read()
    bom = b.startswith(b'\xef\xbb\xbf')
    if bom:
        b = b[3:]
    t = b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    open(p, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + t)
    print('加 loc:', p.split('/')[-1])
