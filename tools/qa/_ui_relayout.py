# -*- coding: utf-8 -*-
"""会场页布局重做（一次改到位）。

新版分区（窗口 980×680，内容区 x 24-956）：
  信息行 216-286   秘书长 | 观察员 | 上期表决，三块并排各 300 宽
  议程区 296-348   本轮议程 + 效果，通栏
  三栏   356-440   chip（22）+ grid（60）
                   赞成 24-224 / 反对 236-436 / 弃权 448-956（不等宽）
                   赞成反对 2 列，弃权 5 列（13 国 3 行放得下）
  按钮   448-476   各自栏下方对齐
  倒计时 486
  通过投票 504-532
  页脚   560-640
"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)

src = io.open(GEN, encoding='utf-8').read()

start = src.index('def build_agenda_page():')
end = src.index('def build_res_page(')

new_fn = '''def build_agenda_page():
    open_page('un_page_agenda')

    # ---- 信息行：三块并排（各 300 宽），省下垂直空间给三栏 ----
    text_el('un_win_sg_label', 24, 216, 'hoi_16mbs', 'mvlv_un_window_sg_label', 288, 18)
    text_el('un_win_sg_name', 24, 234, 'hoi_18mbs', 'mvlv_un_window_sg_text', 288, 22,
            tip='mvlv_un_tt_sg')
    text_el('un_win_sg_desc', 24, 258, 'hoi_16mbs', 'mvlv_un_window_sg_desc_text', 288, 40)

    text_el('un_win_obs_label', 336, 216, 'hoi_16mbs', 'mvlv_un_window_observer_label', 288, 18)
    text_el('un_win_obs_text', 336, 234, 'hoi_16mbs', 'mvlv_un_window_observer_text', 288, 44,
            tip='mvlv_un_tt_observer')

    text_el('un_win_last_label', 648, 216, 'hoi_16mbs', 'mvlv_un_window_last_label', 288, 18)
    text_el('un_win_last_text', 648, 234, 'hoi_16mbs', 'mvlv_un_window_last_text', 288, 44)

    # ---- 议程区：通栏 ----
    text_el('un_win_agenda', 24, 296, 'hoi_16mbs', 'mvlv_un_panel_agenda', 932, 18)
    text_el('un_win_agenda_name', 24, 314, 'hoi_18mbs', 'mvlv_un_panel_agenda_text', 932, 22)
    text_el('un_win_effect', 24, 338, 'hoi_16mbs', 'mvlv_un_window_effect_text', 932, 18)

    # ---- 三栏：不等宽（赞成/反对是少数，弃权是常态）----
    LANES = ((24, 200, 2, 'yes'), (236, 200, 2, 'no'), (448, 508, 5, 'abs'))
    for x, w, cols, tag in LANES:
        icon_el('un_win_%s_chip' % tag, 'GFX_mvlv119_un_chip', x, 356)
        text_el('un_win_%s_label' % tag, x + 8, 357, 'hoi_16mbs',
                'mvlv_un_panel_%s_text' % tag, min(w - 12, 200), 18)
        grid_el('mvlv_un_win_%s_grid' % tag, x, 380, w, 60, 96, 14, cols)

    # ---- 投票按钮：各自栏下方对齐 ----
    for x, w, _cols, tag in LANES:
        label = 'mvlv_un_window_vote_%s' % tag
        button_el('mvlv_un_vote_%s' % tag, 'GFX_mvlv119_un_btn_vote', x, 448,
                  tip='mvlv_un_tt_vote')
        text_el('un_win_vote_%s_label' % tag, x, 454, 'hoi_16mbs', label, w, 20,
                fmt='center', trans=True)

    # ---- 倒计时 / 通过投票 ----
    text_el('un_win_days', 24, 486, 'hoi_16mbs', 'mvlv_un_window_days', 932, 20)

    button_el('mvlv_un_pass_vote', 'GFX_mvlv119_un_btn_pass', 24, 504,
              tip='mvlv_un_pass_vote_tt')
    text_el('un_win_pass_vote_label', 24, 510, 'hoi_16mbs', 'mvlv_un_window_pass_vote',
            200, 20, fmt='center', trans=True)
    button_el('mvlv_un_pass_vote_grey', 'GFX_mvlv119_un_btn_pass_grey', 24, 504,
              tip='mvlv_un_pass_vote_grey_tt')

    # ---- 页脚：两枚动作按钮 + 说明 ----
    button_el('mvlv_un_pay', 'GFX_mvlv119_un_btn_action', 236, 504,
              tip='mvlv_un_pay_reparation_desc')
    text_el('un_win_pay_label', 244, 507, 'hoi_16mbs', 'mvlv_un_pay_reparation', 236, 18,
            trans=True)
    button_el('mvlv_un_exit', 'GFX_mvlv119_un_btn_action', 236, 534,
              tip='mvlv_un_exit_vancouver_desc')
    text_el('un_win_exit_label', 244, 537, 'hoi_16mbs', 'mvlv_un_exit_vancouver', 236, 18,
            trans=True)

    text_el('un_win_note', 484, 504, 'hoi_16mbs', 'mvlv_un_window_note', 472, 100)


'''

out = src[:start] + new_fn + src[end:]
ast.parse(out)
io.open(GEN, 'w', encoding='utf-8', newline='').write(out)
print('build_agenda_page 已重写，语法 OK')
