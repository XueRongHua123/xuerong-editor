# -*- coding: utf-8 -*-
"""会场页改用「成员页同款条目」显示各国立场。

依据：成员页 450×30 的条目能正常渲染国旗+国名，投票栏 100×24 的条目不能。
差异在条目尺寸/复杂度，不在 grid 位置。所以会场页直接复用 450×30 的条目：
  grid 932 宽、2 列、条目 466×30（略宽于成员页的 452）
  13 国 ÷ 2 列 = 7 行 × 30 = 210px，落在 y=410 ~ 620，窗口内放得下
数据用 mvlv_un_members（所有成员国 + 各自立场，已在成员页验证可用）。
"""
import ast
import io

PKG = 'mods/muvluvCNsub_xuerong'
GEN = 'work/qa/_gen_un_window_gui.py'
SG = PKG + '/common/scripted_guis/zz_mvlv119_un_window.txt'
NL = chr(10)
T = chr(9)
BT = chr(92) + 't'

# ---- 1) 生成器：在会场页加成员列表 grid ----
g = io.open(GEN, encoding='utf-8').read()

anchor = "    # 各国具体立场去成员页看：voting grid 在本页面渲染异常，暂不展示"
new_block = ("    # 各国立场：复用成员页同款条目（450×30 那套在成员页渲染正常，投票栏 100×24 的不行）\n"
             "    grid_el('mvlv_un_vote_list_grid', 24, 410, 932, 210, 466, 30, 2)\n\n")
if 'mvlv_un_vote_list_grid' not in g:
    assert anchor in g, '会场页锚点未命中'
    g = g.replace(anchor, new_block, 1)
    print('会场页加成员列表 grid（932×210，个 466×30，2 列）')

# 提示行下移到列表下方
g = g.replace("text_el('un_win_vote_hint', 24, 442,", "text_el('un_win_vote_hint', 24, 626,", 1)

# 按钮区下移（列表到 620）
pairs = [
 ("'GFX_mvlv119_un_btn_vote', bx, 476,", "'GFX_mvlv119_un_btn_vote', bx, 750,"),
 ("text_el('un_win_vote_%s_label' % tag, bx, 482,", "text_el('un_win_vote_%s_label' % tag, bx, 756,"),
 ("text_el('un_win_days', 24, 514,", "text_el('un_win_days', 24, 700,"),
 ("'GFX_mvlv119_un_btn_pass', 24, 532,", "'GFX_mvlv119_un_btn_pass', 24, 700,"),
 ("text_el('un_win_pass_vote_label', 24, 538,", "text_el('un_win_pass_vote_label', 24, 706,"),
 ("'GFX_mvlv119_un_btn_pass_grey', 24, 532,", "'GFX_mvlv119_un_btn_pass_grey', 24, 700,"),
 ("'GFX_mvlv119_un_btn_action', 236, 532,", "'GFX_mvlv119_un_btn_action', 236, 700,"),
 ("text_el('un_win_pay_label', 244, 535,", "text_el('un_win_pay_label', 244, 703,"),
 ("'GFX_mvlv119_un_btn_action', 236, 562,", "'GFX_mvlv119_un_btn_action', 236, 730,"),
 ("text_el('un_win_exit_label', 244, 565,", "text_el('un_win_exit_label', 244, 733,"),
 ("text_el('un_win_note', 484, 532,", "text_el('un_win_note', 484, 700,"),
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

# ---- 2) scripted_gui：绑定新 grid ----
s = io.open(SG, encoding='utf-8').read()
if 'mvlv_un_vote_list_grid' not in s:
    # 找到 dynamic_lists 块，在 mem_grid 后面插
    key = 'mvlv_un_mem_grid = {'
    i = s.index(key)
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
    ins = (T * 3 + 'mvlv_un_vote_list_grid = {' + NL +
           T * 4 + 'array = global.mvlv_un_members' + NL +
           T * 4 + 'change_scope = yes' + NL +
           T * 4 + 'country_scope_entry_container = "mvlv_un_mem_entry"' + NL +
           T * 3 + '}' + NL)
    s = s[:end] + ins + s[end:]
    io.open(SG, 'w', encoding='utf-8', newline='').write(s)
    print('已绑定 mvlv_un_vote_list_grid（复用 mvlv_un_mem_entry）')
