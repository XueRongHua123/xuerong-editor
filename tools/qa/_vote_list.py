# -*- coding: utf-8 -*-
"""会场页腾出空间给「各国立场」列表（复用成员页同款条目）。

窗口只有 680 高，要塞下 13 国列表就得压缩上半部分：
  信息行 216-258（原 216-286）
  议程   266-330（原 296-378）
  三栏 chip 338-358（原 386-406）
  列表   366-576（210px，2 列 × 466×30，13 国 7 行）
  按钮   584 / 倒计时 622 / 通过投票 640 / 页脚 640
"""
import ast
import io

PKG = 'mods/muvluvCNsub_xuerong'
GEN = 'work/qa/_gen_un_window_gui.py'
SG = PKG + '/common/scripted_guis/zz_mvlv119_un_window.txt'
NL = chr(10)
T = chr(9)

g = io.open(GEN, encoding='utf-8').read()

# ---- 上半部分压缩 ----
pairs = [
 # 信息行
 ("text_el('un_win_sg_desc', 24, 258,", "text_el('un_win_sg_desc', 24, 252,"),
 ("text_el('un_win_obs_text', 336, 234,", "text_el('un_win_obs_text', 336, 234,"),
 # 议程
 ("text_el('un_win_agenda', 24, 296,", "text_el('un_win_agenda', 24, 266,"),
 ("text_el('un_win_agenda_name', 24, 314,", "text_el('un_win_agenda_name', 24, 284,"),
 ("text_el('un_win_agenda_desc', 24, 338,", "text_el('un_win_agenda_desc', 24, 306,"),
 ("text_el('un_win_effect', 676, 338,", "text_el('un_win_effect', 676, 306,"),
 # chip
 ("icon_el('un_win_%s_chip' % tag, chip, x, 386)", "icon_el('un_win_%s_chip' % tag, chip, x, 338)"),
 ("text_el('un_win_%s_label' % tag, x + 8, 387,", "text_el('un_win_%s_label' % tag, x + 8, 339,"),
 # 提示行放到列表下方
 ("text_el('un_win_vote_hint', 24, 442,", "text_el('un_win_vote_hint', 24, 578,"),
 # 按钮
 ("'GFX_mvlv119_un_btn_vote', bx, 476,", "'GFX_mvlv119_un_btn_vote', bx, 598,"),
 ("text_el('un_win_vote_%s_label' % tag, bx, 482,", "text_el('un_win_vote_%s_label' % tag, bx, 604,"),
 ("text_el('un_win_days', 24, 514,", "text_el('un_win_days', 24, 636,"),
 ("'GFX_mvlv119_un_btn_pass', 24, 532,", "'GFX_mvlv119_un_btn_pass', 24, 654,"),
 ("text_el('un_win_pass_vote_label', 24, 538,", "text_el('un_win_pass_vote_label', 24, 660,"),
 ("'GFX_mvlv119_un_btn_pass_grey', 24, 532,", "'GFX_mvlv119_un_btn_pass_grey', 24, 654,"),
 ("'GFX_mvlv119_un_btn_action', 236, 532,", "'GFX_mvlv119_un_btn_action', 236, 654,"),
 ("text_el('un_win_pay_label', 244, 535,", "text_el('un_win_pay_label', 244, 657,"),
 ("'GFX_mvlv119_un_btn_action', 236, 562,", "'GFX_mvlv119_un_btn_action', 236, 684,"),
 ("text_el('un_win_exit_label', 244, 565,", "text_el('un_win_exit_label', 244, 687,"),
 ("text_el('un_win_note', 484, 532,", "text_el('un_win_note', 484, 654,"),
]
n = 0
for a, b in pairs:
    if a in g:
        g = g.replace(a, b, 1)
        n += 1
    else:
        print('未命中:', a[:50])
print('调整 %d 处' % n)

# ---- 列表 grid ----
anchor = "    # 各国具体立场去成员页看：voting grid 在本页面渲染异常，暂不展示"
block = ("    # 各国立场：复用成员页同款条目（450×30 那套在成员页渲染正常，投票栏 100×24 的不行）\n"
         "    grid_el('mvlv_un_vote_list_grid', 24, 366, 932, 210, 466, 30, 2)\n")
if 'mvlv_un_vote_list_grid' not in g:
    assert anchor in g, '锚点未命中'
    g = g.replace(anchor, block, 1)
    print('加列表 grid（366-576，2 列 466×30）')

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')

# ---- 绑定 dynamic_lists ----
s = io.open(SG, encoding='utf-8').read()
if 'mvlv_un_vote_list_grid' not in s:
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
    end = s.find(NL, j) + 1
    ins = (T * 3 + 'mvlv_un_vote_list_grid = {' + NL +
           T * 4 + 'array = global.mvlv_un_members' + NL +
           T * 4 + 'change_scope = yes' + NL +
           T * 4 + 'country_scope_entry_container = "mvlv_un_mem_entry"' + NL +
           T * 3 + '}' + NL)
    s = s[:end] + ins + s[end:]
    io.open(SG, 'w', encoding='utf-8', newline='').write(s)
    print('已绑定（复用 mvlv_un_mem_entry）')
