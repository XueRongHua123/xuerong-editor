# -*- coding: utf-8 -*-
"""会场页重排（精确到窗口 680 高）。

  信息行   216-258
  议程     266-330
  三栏 chip 338-358
  立场列表  366-548  （182px = 7 行 × 26）
  投票按钮  556-584
  提示      588
  倒计时    600
  通过投票  618-646 / 缴纳核责任金 618 / 退出温哥华协议 646
  说明      x=484 y=618
"""
import ast
import io

PKG = 'mods/muvluvCNsub_xuerong'
GEN = 'work/qa/_gen_un_window_gui.py'
SG = PKG + '/common/scripted_guis/zz_mvlv119_un_window.txt'
NL = chr(10)
T = chr(9)

g = io.open(GEN, encoding='utf-8').read()

pairs = [
 # 议程压缩
 ("text_el('un_win_agenda', 24, 296,", "text_el('un_win_agenda', 24, 266,"),
 ("text_el('un_win_agenda_name', 24, 314,", "text_el('un_win_agenda_name', 24, 284,"),
 ("text_el('un_win_agenda_desc', 24, 338,", "text_el('un_win_agenda_desc', 24, 306,"),
 ("text_el('un_win_effect', 676, 338,", "text_el('un_win_effect', 676, 306,"),
 # chip
 ("icon_el('un_win_%s_chip' % tag, chip, x, 386)", "icon_el('un_win_%s_chip' % tag, chip, x, 338)"),
 ("text_el('un_win_%s_label' % tag, x + 8, 387,", "text_el('un_win_%s_label' % tag, x + 8, 339,"),
 # 列表 grid
 ("grid_el('mvlv_un_vote_list_grid', 24, 410, 932, 210, 466, 30, 2)",
  "grid_el('mvlv_un_vote_list_grid', 24, 366, 932, 182, 466, 26, 2)"),
 # 提示
 ("text_el('un_win_vote_hint', 24, 442,", "text_el('un_win_vote_hint', 24, 552,"),
 # 按钮
 ("'GFX_mvlv119_un_btn_vote', bx, 476,", "'GFX_mvlv119_un_btn_vote', bx, 574,"),
 ("text_el('un_win_vote_%s_label' % tag, bx, 482,", "text_el('un_win_vote_%s_label' % tag, bx, 580,"),
 ("text_el('un_win_days', 24, 514,", "text_el('un_win_days', 24, 608,"),
 ("'GFX_mvlv119_un_btn_pass', 24, 532,", "'GFX_mvlv119_un_btn_pass', 24, 626,"),
 ("text_el('un_win_pass_vote_label', 24, 538,", "text_el('un_win_pass_vote_label', 24, 632,"),
 ("'GFX_mvlv119_un_btn_pass_grey', 24, 532,", "'GFX_mvlv119_un_btn_pass_grey', 24, 626,"),
 ("'GFX_mvlv119_un_btn_action', 236, 532,", "'GFX_mvlv119_un_btn_action', 236, 626,"),
 ("text_el('un_win_pay_label', 244, 535,", "text_el('un_win_pay_label', 244, 629,"),
 ("'GFX_mvlv119_un_btn_action', 236, 562,", "'GFX_mvlv119_un_btn_action', 236, 654,"),
 ("text_el('un_win_exit_label', 244, 565,", "text_el('un_win_exit_label', 244, 657,"),
 ("text_el('un_win_note', 484, 532,", "text_el('un_win_note', 484, 626,"),
]
n = 0
for a, b in pairs:
    if a in g:
        g = g.replace(a, b, 1)
        n += 1
    else:
        print('未命中:', a[:48])
print('调整 %d 处' % n)

ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')
