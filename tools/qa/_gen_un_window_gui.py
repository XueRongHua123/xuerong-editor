# -*- coding: utf-8 -*-
"""从议题注册表生成联合国会场窗口的三份文件。

产出：
  mods/<包>/interface/zz_mvlv119_un_window.gui
  mods/<包>/common/scripted_guis/zz_mvlv119_un_window.txt
  两份本地化里的「预算 XX」行（就地替换，不动其他键）

为什么生成：16 条议题各自的按钮、文字、显隐触发器、提交效果一一对应，
手写必然错位；加一条议题只要改 un_resolutions.json 再跑本脚本。

用法：python work/qa/_gen_un_window_gui.py [--dry]
"""

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BASE = os.path.join(ROOT, 'mods', 'muvluvCNsub_xuerong')
REG = os.path.join(HERE, 'un_resolutions.json')

W, H = 980, 680

# 板块：id -> (本地化键, 栏位, 该栏第几个板块)
SECTIONS = [
    ('security', 'mvlv_un_sec_security', 'left', 0),
    ('politics', 'mvlv_un_sec_politics', 'left', 1),
    ('economy', 'mvlv_un_sec_economy', 'right', 0),
    ('tech', 'mvlv_un_sec_tech', 'right', 1),
    ('seat', 'mvlv_un_sec_seat', 'right', 2),
]

COL_X = {'left': 24, 'right': 508}
ROW_W = 448
ROW_H = 28
ROW_STEP = 32
SEC_TOP = 232
SEC_HEAD = 24

content = []   # gui 片段
page_names = {0: [], 1: [], 2: [], 3: [], 4: []}


def add(s):
    content.append(s)


ENTRY_DEFS = []      # dynamic_lists 的条目模板容器，必须挂在 guiTypes 顶层


def add_entry(s):
    ENTRY_DEFS.append(s)


def indent(text, n=1):
    pad = '\t' * n
    return '\n'.join(pad + ln if ln.strip() else ln for ln in text.split('\n'))


def text_el(name, x, y, font, key, w, h, fmt='left', tip=None, trans=False, page=1):
    lines = [
        'instantTextBoxType = {',
        '\tname = "%s"' % name,
        '\tposition = { x = %d y = %d }' % (x, y),
        '\tfont = "%s"' % font,
        '\ttext = "%s"' % key,
    ]
    if tip:
        lines.append('\tpdx_tooltip = "%s"' % tip)
    lines += ['\tformat = %s' % fmt, '\tmaxWidth = %d' % w, '\tmaxHeight = %d' % h]
    if trans:
        lines.append('\talwaystransparent = yes')
    lines.append('}')
    add(indent('\n'.join(lines), 2))
    page_names[page].append(name)


def button_el(name, sprite, x, y, tip=None, page=1, quad=False, sound='click_default'):
    field = 'quadTextureSprite' if quad else 'spriteType'
    lines = [
        'buttonType = {',
        '\tname = "%s"' % name,
        '\t%s = "%s"' % (field, sprite),
    ]
    if tip:
        lines.append('\tpdx_tooltip = "%s"' % tip)
    lines += [
        '\tposition = { x = %d y = %d }' % (x, y),
        '\tOrientation = "UPPER_LEFT"',
        '\tclicksound = %s' % sound,
        '\toversound = ui_menu_over',
        '}',
    ]
    add(indent('\n'.join(lines), 2))
    page_names[page].append(name)


def icon_el(name, sprite, x, y, page=1):
    lines = [
        'iconType = {',
        '\tname = "%s"' % name,
        '\tspriteType = "%s"' % sprite,
        '\tposition = { x = %d y = %d }' % (x, y),
        '\tOrientation = "UPPER_LEFT"',
        '}',
    ]
    add(indent('\n'.join(lines), 2))
    page_names[page].append(name)


def grid_el(name, x, y, w, h, sw, sh, cols, page=1):
    """生成 grid。

    外面套一层 containerWindowType（<name>_wrap）：dynamic_lists 管理的 grid
    不响应 _visible 触发器（原版全库没有给 grid 配可见性的先例），
    所以可见性绑到外层容器，grid 自己保持原名给 dynamic_lists 用。
    """
    wrap = name + '_wrap'
    lines = [
        'containerWindowType = {',
        '	name = "%s"' % wrap,
        '	position = { x = %d y = %d }' % (x, y),
        '	size = { width = %d height = %d }' % (w, h),
        '',
        '	gridboxtype = {',
        '		name = "%s"' % name,
        '		position = { x = 0 y = 0 }',
        '		size = { width = %d height = %d }' % (w, h),
        '		slotsize = { width = %d height = %d }' % (sw, sh),
        '		max_slots_horizontal = %d' % cols,
        '		format = "UPPER_LEFT"',
        '	}',
        '}',
    ]
    add(indent('\n'.join(lines), 2))
    page_names[page].append(wrap)


def open_page(name):
    add('\tcontainerWindowType = {')
    add('\t\tname = "%s"' % name)
    add('\t\tposition = { x = 0 y = 0 }')
    add('\t\tsize = { width = %d height = %d }' % (W, H))
    add('')


def close_page():
    add('\t}')
    add('')


# ------------------------------------------------------------------ 抬头

def build_header():
    # 抬头元素常驻，不参与页签
    add('\ticonType = {')
    add('\t\tname = "un_win_emblem"')
    add('\t\tspriteType = "GFX_mvlv119_un_entry"')
    add('\t\tposition = { x = 22 y = 12 }')
    add('\t\tscale = 0.55')
    add('\t\tOrientation = "UPPER_LEFT"')
    add('\t}')
    add('')


def header_texts():
    # 直接用 text_el 但归到 page 0（常驻），page_names 里不放
    def h(name, x, y, font, key, w, hh, fmt='left', tip=None):
        lines = [
            'instantTextBoxType = {',
            '\tname = "%s"' % name,
            '\tposition = { x = %d y = %d }' % (x, y),
            '\tfont = "%s"' % font,
            '\ttext = "%s"' % key,
        ]
        if tip:
            lines.append('\tpdx_tooltip = "%s"' % tip)
        lines += ['\tformat = %s' % fmt, '\tmaxWidth = %d' % w, '\tmaxHeight = %d' % hh, '}']
        add(indent('\n'.join(lines)))

    h('un_win_title', 88, 6, 'hoi_20b', 'mvlv_un_panel_title', 430, 26)
    h('un_win_session', 88, 34, 'hoi_16mbs', 'mvlv_un_panel_session_text', 320, 18)
    h('un_win_seats', 88, 54, 'hoi_16mbs', 'mvlv_un_panel_seats_text', 320, 18, tip='mvlv_un_tt_seats')
    h('un_win_legitimacy', 690, 16, 'hoi_16mbs', 'mvlv_un_panel_legitimacy_text', 220, 18,
      fmt='right', tip='mvlv_un_tt_legitimacy')
    h('un_win_budget', 690, 36, 'hoi_16mbs', 'mvlv_un_panel_budget_text', 220, 18,
      fmt='right', tip='mvlv_un_tt_budget')

    add('\tbuttonType = {')
    add('\t\tname = "mvlv_un_close"')
    add('\t\tquadTextureSprite = "GFX_close_button_small"')
    add('\t\tposition = { x = 946 y = 14 }')
    add('\t\tbuttonFont = "hoi_16mbs"')
    add('\t\tOrientation = "UPPER_LEFT"')
    add('\t\tclicksound = click_close')
    add('\t\toversound = ui_menu_over')
    add('\t\tshortcut = "ESCAPE"')
    add('\t\tpdx_tooltip = "mvlv_un_window_close_tt"')
    add('\t}')
    add('')


def build_tabs():
    tabs = [
        ('mvlv_un_tab_agenda', 'mvlv_un_tab_label_agenda', 1),
        ('mvlv_un_tab_res', 'mvlv_un_tab_label_res', 2),
        ('mvlv_un_tab_mem', 'mvlv_un_tab_label_mem', 3),
        ('mvlv_un_tab_log', 'mvlv_un_tab_label_log', 4),
    ]
    for i, (btn, label, page) in enumerate(tabs):
        x = 24 + i * 156
        button_el(btn, 'GFX_mvlv119_un_btn_tab', x, 78, tip='mvlv_un_tt_tab', page=0)
        text_el('un_tab_label_%d' % page, x, 82, 'hoi_18mbs', label, 148, 22,
                fmt='center', trans=True, page=0)
        icon_el('un_tab_on_%d' % page, 'GFX_mvlv119_un_tab_on', x, 106, page=page)


# ------------------------------------------------------------------ 第一页：会场

def build_agenda_page():
    open_page('un_page_agenda')

    # ---- 信息行：三块并排（各 300 宽），省下垂直空间给三栏 ----
    text_el('un_win_sg_label', 24, 216, 'hoi_16mbs', 'mvlv_un_window_sg_label', 288, 18)
    text_el('un_win_sg_name', 24, 234, 'hoi_18mbs', 'mvlv_un_window_sg_text', 288, 22,
            tip='mvlv_un_tt_sg')
    text_el('un_win_sg_desc', 24, 252, 'hoi_16mbs', 'mvlv_un_window_sg_desc_text', 288, 40)

    text_el('un_win_obs_label', 336, 216, 'hoi_16mbs', 'mvlv_un_window_observer_label', 288, 18)
    text_el('un_win_obs_text', 336, 234, 'hoi_16mbs', 'mvlv_un_window_observer_text', 288, 44,
            tip='mvlv_un_tt_observer')

    text_el('un_win_last_label', 648, 216, 'hoi_16mbs', 'mvlv_un_window_last_label', 288, 18)
    text_el('un_win_last_text', 648, 234, 'hoi_16mbs', 'mvlv_un_window_last_text', 288, 44)

    # ---- 议程区：通栏 ----
    text_el('un_win_agenda', 24, 266, 'hoi_16mbs', 'mvlv_un_panel_agenda', 932, 18)
    text_el('un_win_agenda_name', 24, 284, 'hoi_18mbs', 'mvlv_un_panel_agenda_text', 932, 22)
    # 议题描述与效果同一行左右排：描述左（宽 640），效果右
    text_el('un_win_agenda_desc', 24, 306, 'hoi_16mbs', 'mvlv_un_panel_desc_text', 640, 40)
    text_el('un_win_effect', 676, 306, 'hoi_16mbs', 'mvlv_un_window_effect_text', 280, 40)


    # ---- 三栏：不等宽（赞成/反对是少数，弃权是常态）----
    # 反对通常最多（11 国），给 4 列；弃权次之 3 列；赞成为了 2 列
    LANES = ((24, 200, 2, 'yes'), (236, 500, 5, 'no'), (748, 208, 2, 'abs'))
    for x, w, cols, tag in LANES:
        # 按栏宽选 chip 图，避免拉伸变形（200 宽用 _200，508 宽用 _508）
        chip = 'GFX_mvlv119_un_chip_%d' % (200 if w <= 200 else 508)
        icon_el('un_win_%s_chip' % tag, chip, x, 338)
        text_el('un_win_%s_label' % tag, x + 8, 339, 'hoi_16mbs',
                'mvlv_un_panel_%s_text' % tag, min(w - 12, 200), 18)

    # 各国立场：复用成员页同款条目（450×30 那套在成员页渲染正常，投票栏 100×24 的不行）
    grid_el('mvlv_un_vote_list_grid', 24, 366, 932, 182, 466, 26, 2)

    text_el('un_win_vote_hint', 24, 552, 'hoi_16mbs', 'mvlv_un_vote_hint', 932, 20)

    # ---- 投票按钮：各自栏下方对齐 ----
    for x, w, _cols, tag in LANES:
        label = 'mvlv_un_window_vote_%s' % tag
        bx = x + max(0, (w - 196) // 2)   # 按钮图固定 196 宽，在栏内居中
        button_el('mvlv_un_vote_%s' % tag, 'GFX_mvlv119_un_btn_vote', bx, 574,
                  tip='mvlv_un_tt_vote')
        text_el('un_win_vote_%s_label' % tag, bx, 580, 'hoi_16mbs', label, 196, 20,
                fmt='center', trans=True)

    # ---- 倒计时 / 通过投票 ----
    # 本次表决结果（原来靠事件弹窗，改为窗口内显示）
    text_el('un_win_result', 676, 330, 'hoi_16mbs', 'mvlv_un_window_result', 280, 40,
            tip='mvlv_un_tt_result')
    text_el('un_win_days', 676, 266, 'hoi_16mbs', 'mvlv_un_window_days', 280, 20)
    # 预算数值（标题栏只有定性描述「预算：正常」，看不到具体数额）
    text_el('un_win_budget_num', 676, 286, 'hoi_16mbs', 'mvlv_un_window_budget_num', 280, 20)

    button_el('mvlv_un_pass_vote', 'GFX_mvlv119_un_btn_pass', 24, 626,
              tip='mvlv_un_pass_vote_tt')
    text_el('un_win_pass_vote_label', 24, 632, 'hoi_16mbs', 'mvlv_un_window_pass_vote',
            200, 20, fmt='center', trans=True)
    button_el('mvlv_un_pass_vote_grey', 'GFX_mvlv119_un_btn_pass_grey', 24, 626,
              tip='mvlv_un_pass_vote_grey_tt')

    # ---- 页脚：两枚动作按钮 + 说明 ----
    button_el('mvlv_un_pay', 'GFX_mvlv119_un_btn_action', 236, 626,
              tip='mvlv_un_pay_reparation_desc')
    text_el('un_win_pay_label', 244, 629, 'hoi_16mbs', 'mvlv_un_pay_reparation', 236, 18,
            trans=True)
    button_el('mvlv_un_exit', 'GFX_mvlv119_un_btn_action', 236, 654,
              tip='mvlv_un_exit_vancouver_desc')
    text_el('un_win_exit_label', 244, 657, 'hoi_16mbs', 'mvlv_un_exit_vancouver', 236, 18,
            trans=True)

    text_el('un_win_note', 484, 626, 'hoi_16mbs', 'mvlv_un_window_note', 472, 100)

    close_page()


def build_res_page(reg):
    open_page('un_page_res')
    text_el('un_win_res_title', 24, 202, 'hoi_18mbs', 'mvlv_un_res_page_title', 600, 22, page=2)
    text_el('un_win_res_sub', 508, 206, 'hoi_16mbs', 'mvlv_un_res_page_sub', 448, 18,
            fmt='right', page=2)

    by_sec = {}
    for item in reg['resolutions']:
        by_sec.setdefault(item.get('section', 'security'), []).append(item)

    col_y = {'left': SEC_TOP, 'right': SEC_TOP}
    for sec_id, sec_key, col, _ in SECTIONS:
        items = by_sec.get(sec_id, [])
        if not items:
            continue
        x = COL_X[col]
        y = col_y[col]
        text_el('un_win_sec_%s' % sec_id, x, y, 'hoi_16mbs', sec_key, ROW_W, 20, page=2)
        y += SEC_HEAD
        for item in items:
            rid = item['id']
            button_el('mvlv_un_res_%s_submit' % rid, 'GFX_mvlv119_un_btn_res', x, y,
                      tip='mvlv_un_res_%s_desc' % rid, page=2)
            text_el('un_win_res_%s_name' % rid, x + 14, y + 6, 'hoi_16mbs',
                    'mvlv_un_res_%s_name' % rid, 250, 18, trans=True, page=2)
            text_el('un_win_res_%s_cost' % rid, x + 264, y + 6, 'hoi_16mbs',
                    'mvlv_un_res_%s_status' % rid, 170, 18, fmt='right', trans=True, page=2)
            y += ROW_STEP
        col_y[col] = y + 12

    text_el('un_win_res_rules', 24, 524, 'hoi_16mbs', 'mvlv_un_res_rules', 448, 110, page=2)
    close_page()


# ------------------------------------------------------------------ 第三页：成员

def build_mem_page():
    open_page('un_page_mem')
    text_el('un_win_mem_title', 24, 202, 'hoi_18mbs', 'mvlv_un_mem_title', 500, 22, page=3)
    # 常任理事国图例：沿用国家精神「常任理事国」的图标
    text_el('un_win_mem_hint', 24, 224, 'hoi_16mbs', 'mvlv_un_mem_hint', 920, 18, page=3)
    grid_el('mvlv_un_mem_grid', 24, 268, 920, 238, 452, 34, 2, page=3)
    text_el('un_win_mem_legend', 24, 520, 'hoi_16mbs', 'mvlv_un_mem_legend', 920, 80, page=3)
    close_page()

    # 条目容器（每个国家一份，作用域随条目切换）
    add_entry('\tcontainerWindowType = {')
    add_entry('\t\tname = "mvlv_un_mem_entry"')
    add_entry('\t\tposition = { x = 0 y = 0 }')
    add_entry('\t\tsize = { width = 450 height = 30 }')
    add_entry('\tbackground = {')
    add_entry('\t	name = "slotbg_mem"')
    add_entry('\t	spriteType = "GFX_mvlv119_un_slot_bg_wide"')
    add_entry('\t}')
    add_entry('')
    entry = []
    entry.append('iconType = {')
    entry.append('\tname = "mvlv_un_mem_flag"')
    entry.append('\tquadTextureSprite = "GFX_flag_small"')
    entry.append('\tposition = { x = 0 y = 2 }')
    entry.append('\tscale = 1.3')
    entry.append('\tOrientation = "UPPER_LEFT"')
    entry.append('}')
    add_entry(indent('\n'.join(entry), 2))
    add_entry('')
    # 常任理事国标记：图标由 properties 绑 GetUNPermIcon（非常任返回透明占位）
    # 国家精神图标原图 60×68，缩到 0.42 才不压住国名（行高 30）
    perm = ['iconType = {', '	name = "mvlv_un_mem_perm"',
            '	spriteType = "GFX_mvlv119_un_blank"',
            '	position = { x = 30 y = 1 }',
            '	scale = 0.42',
            '	Orientation = "UPPER_LEFT"', '}']
    add_entry(indent('\n'.join(perm), 2))
    add_entry('')
    e_texts = [
        ('mvlv_un_mem_name', 56, 7, 'hoi_16mbs', 'mvlv_un_mem_name', 172, 18, 'left', None, True),
        ('mvlv_un_mem_stance', 234, 7, 'hoi_16mbs', 'mvlv_un_mem_stance', 76, 18, 'left', None, True),
        ('mvlv_un_mem_score', 314, 7, 'hoi_16mbs', 'mvlv_un_mem_score', 44, 18, 'right',
         'mvlv_un_tt_score', True),
        ('mvlv_un_mem_lobby_label', 360, 7, 'hoi_16mbs', 'mvlv_un_mem_lobby', 86, 18, 'center',
         None, True),
    ]
    for name, x, y, font, key, w, h, fmt, tip, trans in e_texts:
        lines = ['instantTextBoxType = {', '\tname = "%s"' % name,
                 '\tposition = { x = %d y = %d }' % (x, y), '\tfont = "%s"' % font,
                 '\ttext = "%s"' % key]
        if tip:
            lines.append('\tpdx_tooltip = "%s"' % tip)
        lines += ['\tformat = %s' % fmt, '\tmaxWidth = %d' % w, '\tmaxHeight = %d' % h]
        if trans:
            lines.append('\talwaystransparent = yes')
        lines.append('}')
        add_entry(indent('\n'.join(lines), 2))
        add_entry('')
    add_entry(indent('\n'.join([
        'buttonType = {',
        '\tname = "mvlv_un_mem_lobby"',
        '\tspriteType = "GFX_mvlv119_un_btn_lobby"',
        '\tposition = { x = 360 y = 5 }',
        '\tOrientation = "UPPER_LEFT"',
        '\tclicksound = click_default',
        '\toversound = ui_menu_over',
        '\tpdx_tooltip = "mvlv_un_tt_lobby"',
        '}']), 2))
    add_entry('\t}')
    add_entry('')


# ------------------------------------------------------------------ 第四页：记录

def build_log_page():
    open_page('un_page_log')
    text_el('un_win_log_title', 24, 202, 'hoi_18mbs', 'mvlv_un_log_title', 600, 22, page=4)
    text_el('un_win_log_hint', 24, 226, 'hoi_16mbs', 'mvlv_un_log_hint', 920, 18, page=4)
    for i in range(1, 6):
        y = 252 + (i - 1) * 34
        text_el('un_win_log%d_name' % i, 24, y, 'hoi_16mbs', 'mvlv_un_log%d_name' % i, 560, 20, page=4)
        text_el('un_win_log%d_result' % i, 600, y, 'hoi_16mbs', 'mvlv_un_log%d_result' % i, 340, 20,
                fmt='right', page=4)
    text_el('un_win_log_legend', 24, 460, 'hoi_16mbs', 'mvlv_un_log_legend', 920, 80, page=4)
    close_page()


# ------------------------------------------------------------------ 脚本界面

def build_scripted_gui(reg):
    pages = {1: 'agenda', 2: 'res', 3: 'mem', 4: 'log'}
    out = []
    a = out.append
    a('# =====================================================================')
    a('# mvlv119 联合国大会 | 模块: 会场窗口（页签版，生成文件）')
    a('# 生成: work/qa/_gen_un_window_gui.py —— 别手改，改注册表后重跑')
    a('# 说明: 三页靠 triggers 里的 <元素名>_visible 切换；页容器与每个子元素都挂，')
    a('#       容器级不生效时子元素各自隐藏，两种情况都不会叠页。')
    a('# =====================================================================')
    a('')
    a('scripted_gui = {')
    a('\tmvlv_un_window = {')
    a('\t\tcontext_type = player_context')
    a('\t\tparent_window_token = top_bar')
    a('\t\twindow_name = "mvlv_un_window"')
    a('\t\tdirty = global.mvlv_un_ui_version')
    a('\t\tvisible = { has_country_flag = mvlv_un_ui_open }')
    a('')
    a('\t\tdynamic_lists = {')
    for grid, arr, entry in (
            ('mvlv_un_mem_grid', 'global.mvlv_un_members', 'mvlv_un_mem_entry'),
    ):
        a('\t\t\t%s = {' % grid)
        a('\t\t\t\tarray = %s' % arr)
        a('\t\t\t\tchange_scope = yes')
        a('\t\t\t\tcountry_scope_entry_container = "%s"' % entry)
        a('\t\t\t}')
    a('\t\t}')
    a('')
    a('\t\tproperties = {')
    a('\t\t\tmvlv_un_mem_flag = { image = "[This.GetFlag]" }')
    a('\t\t\tmvlv_un_mem_perm = { image = "[GetUNPermIcon]" }')
    a('\t\t\tmvlv_un_mem_grid_wrap = { x = global.mvlv_un_gx_mem }')
    a('\t\t}')
    a('')
    a('\t\ttriggers = {')
    a('\t\t\t# 页签：每页一个容器 + 各子元素，双保险')
    a('\t\t\t# 第一页写成「不是后两页就是第一页」：旧档没有 mvlv_un_tab 时也有内容')
    for p in (1, 2, 3, 4):
        if p == 1:
            a('\t\t\tun_page_%s_visible = { NOT = { check_variable = { mvlv_un_tab > 1 } } }' % pages[p])
        else:
            a('\t\t\tun_page_%s_visible = { check_variable = { mvlv_un_tab = %d } }' % (pages[p], p))
    special_vis = {'mvlv_un_pass_vote', 'mvlv_un_pass_vote_grey', 'un_win_pass_vote_label'}
    for p in (1, 2, 3, 4):
        for name in page_names[p]:
            if name in special_vis:
                continue
            if p == 1:
                a('\t\t\t%s_visible = { NOT = { check_variable = { mvlv_un_tab > 1 } } }' % name)
            else:
                a('\t\t\t%s_visible = { check_variable = { mvlv_un_tab = %d } }' % (name, p))
    # 通过投票按钮：只在会期进行中显示，达标亮色 / 未达标灰
    a('\t\t\tmvlv_un_pass_vote_visible = {')
    a('\t\t\t\tNOT = { check_variable = { mvlv_un_tab > 1 } }')
    a('\t\t\t\tcheck_variable = { global.mvlv_un_pending = 1 }')
    a('\t\t\t\tmvlv_un_passable_now = yes')
    a('\t\t\t}')
    a('\t\t\tmvlv_un_pass_vote_grey_visible = {')
    a('\t\t\t\tNOT = { check_variable = { mvlv_un_tab > 1 } }')
    a('\t\t\t\tcheck_variable = { global.mvlv_un_pending = 1 }')
    a('\t\t\t\tNOT = { mvlv_un_passable_now = yes }')
    a('\t\t\t}')
    a('\t\t\tun_win_pass_vote_label_visible = {')
    a('\t\t\t\tNOT = { check_variable = { mvlv_un_tab > 1 } }')
    a('\t\t\t\tcheck_variable = { global.mvlv_un_pending = 1 }')
    a('\t\t\t}')
    a('\t\t}')
    a('')
    a('\t\teffects = {')
    a('\t\t\tmvlv_un_close_click = {')
    a('\t\t\t\tclr_country_flag = mvlv_un_ui_open')
    a('\t\t\t}')
    a('')
    for p, key in ((1, 'agenda'), (2, 'res'), (3, 'mem'), (4, 'log')):
        a('\t\t\tmvlv_un_tab_%s_click = {' % key)
        a('\t\t\t\tset_variable = { mvlv_un_tab = %d }' % p)
        a('\t\t\tmvlv_un_refresh_lists = yes')
        a('\t\t\tmvlv_un_refresh_members = yes')
        _keep = (("yes", "no", "abs") if p == 1 else (("mem",) if p == 3 else ()))
        for _v, _x in (("yes", 322), ("no", 534), ("abs", 746), ("mem", 24)):
            a('\t\t\tset_variable = { global.mvlv_un_gx_%s = %d }' % (_v, _x if _v in _keep else -9999))
        a('\t\t\t\tadd_to_variable = { global.mvlv_un_ui_version = 1 }')
        a('\t\t\t}')
    a('')
    a('\t\t\t# 投票：一周后揭晓，期间仍可游说')
    for tag, stance in (('yes', 1), ('no', 3), ('abs', 2)):
        a('\t\t\tmvlv_un_vote_%s_click = {' % tag)
        a('\t\t\t\tif = { limit = { check_variable = { global.mvlv_un_pending = 1 } }')
        a('\t\t\t\t\tset_variable = { mvlv_un_stance = %d }' % stance)
        a('\t\t\t\t\tset_variable = { mvlv_un_reason = 0 }')
        a('\t\t\t\t\tset_country_flag = mvlv_un_player_voted')
        a('\t\t\t\t\tmvlv_un_refresh_lists = yes')
        a('\t\t\t\t\tmvlv_un_live_tally = yes')
        a('\t\t\t\t}')
        a('\t\t\t}')
    a('')
    a('\t\t\t# 通过投票：票数达标即可提前结束表决，未达标按钮置灰不可点')
    a('\t\t\tmvlv_un_pass_vote_click = {')
    a('\t\t\t\tif = { limit = {')
    a('\t\t\t\t\tcheck_variable = { global.mvlv_un_pending = 1 }')
    a('\t\t\t\t\tmvlv_un_passable_now = yes')
    a('\t\t\t\t}')
    a('\t\t\t\t\tmvlv_un_tally = yes')
    a('\t\t\t\t}')
    a('\t\t\t}')
    a('')
    a('\t\t\t# 提交决议：40 政治点 + 该决议的预算，提交后跳到会场页')
    for i, item in enumerate(reg['resolutions'], 1):
        a('\t\t\tmvlv_un_res_%s_submit_click = {' % item['id'])
        a('\t\t\t\tif = { limit = {')
        a('\t\t\t\t\tcheck_variable = { global.mvlv_un_pending = 0 }')
        if item['cost'] > 0:
            a('\t\t\t\t\tcheck_variable = { global.mvlv_un_budget > %d }' % (item['cost'] - 1))
        a('\t\t\t\t\thas_political_power > 39')
        a('\t\t\t\t\tmvlv_un_allow_%s = yes' % item['id'])
        a('\t\t\t\t}')
        a('\t\t\t\t\tadd_political_power = -40')
        if item['cost'] > 0:
            a('\t\t\t\t\tsubtract_from_variable = { global.mvlv_un_budget = %d }' % item['cost'])
        a('\t\t\t\t\tset_variable = { var = global.mvlv_un_current value = %d }' % i)
        a('\t\t\t\t\tmvlv_un_begin_chosen = yes')
        a('\t\t\t\t\tset_variable = { mvlv_un_tab = 1 }')
        a('\t\t\t\t\tadd_to_variable = { global.mvlv_un_ui_version = 1 }')
        a('\t\t\t\t}')
        a('\t\t\t}')
    a('')
    a('\t\t\t# 缴纳核责任金')
    a('\t\t\tmvlv_un_pay_click = {')
    a('\t\t\t\tif = { limit = {')
    a('\t\t\t\t\thas_political_power > 149')
    a('\t\t\t\t\tOR = {')
    for n in (1, 2, 3):
        a('\t\t\t\t\t\thas_dynamic_modifier = { modifier = mvlv_un_sanction_%d }' % n)
    a('\t\t\t\t\t}')
    a('\t\t\t\t}')
    a('\t\t\t\t\tadd_political_power = -150')
    for n in (1, 2, 3):
        a('\t\t\t\t\tif = { limit = { has_dynamic_modifier = { modifier = mvlv_un_sanction_%d } }' % n)
        a('\t\t\t\t\t\tremove_dynamic_modifier = { modifier = mvlv_un_sanction_%d }' % n)
        a('\t\t\t\t\t}')
    a('\t\t\t\t\tset_variable = { mvlv_un_reputation = 45 }')
    a('\t\t\t\t\tadd_to_variable = { global.mvlv_un_legitimacy = 5 }')
    a('\t\t\t\t}')
    a('\t\t\t}')
    a('')
    a('\t\t\t# 退出温哥华协议')
    a('\t\t\tmvlv_un_exit_click = {')
    a('\t\t\t\tif = { limit = {')
    a('\t\t\t\t\tcheck_variable = { global.mvlv_un_legitimacy < 20 }')
    a('\t\t\t\t\tNOT = { has_country_flag = mvlv_un_exited }')
    a('\t\t\t\t}')
    a('\t\t\t\t\tset_country_flag = mvlv_un_exited')
    for mod in ('mvlv_un_authorized', 'mvlv_un_sanction_1', 'mvlv_un_sanction_2', 'mvlv_un_sanction_3'):
        a('\t\t\t\t\tif = { limit = { has_dynamic_modifier = { modifier = %s } }' % mod)
        a('\t\t\t\t\t\tremove_dynamic_modifier = { modifier = %s }' % mod)
        a('\t\t\t\t\t}')
    a('\t\t\t\t\tset_variable = { mvlv_un_license_days = 0 }')
    a('\t\t\t\t\tadd_political_power = -100')
    a('\t\t\t\t\tadd_stability = -0.1')
    a('\t\t\t\t}')
    a('\t\t\t}')
    a('')
    a('\t\t\t# 游说：点反对/弃权栏的旗子')
    a('\t\t\tmvlv_un_win_lobby_yes_click = {')
    a('\t\t\t\tif = { limit = { always = no }')
    a('\t\t\t\t\tadd_political_power = 1')
    a('\t\t\t\t}')
    a('\t\t\t}')
    for tag in ('no', 'abs'):
        a('\t\t\tmvlv_un_win_lobby_%s_click = {' % tag)
        a('\t\t\t\tif = { limit = {')
        a('\t\t\t\t\tcheck_variable = { global.mvlv_un_pending = 1 }')
        a('\t\t\t\t\tNOT = { check_variable = { global.mvlv_un_legitimacy < 1 } }')
        a('\t\t\t\t\tNOT = { has_country_flag = mvlv_un_lobbied }')
        a('\t\t\t\t}')
        a('\t\t\t\t\tset_country_flag = mvlv_un_lobbied')
        a('\t\t\t\t\tset_variable = { mvlv_un_stance = 1 }')
        a('\t\t\t\t\tset_variable = { mvlv_un_reason = 6 }')
        a('\t\t\t\t\tsubtract_from_variable = { global.mvlv_un_legitimacy = 1 }')
        a('\t\t\t\t\tmvlv_un_refresh_lists = yes')
        a('\t\t\t\t\tmvlv_un_live_tally = yes')
        a('\t\t\t\t}')
        a('\t\t\t}')
    a('')
    a('\t\t\t# 成员页：点某国行尾的游说按钮，作用域是该国')
    a('\t\t\tmvlv_un_mem_lobby_click = {')
    a('\t\t\t\tif = { limit = {')
    a('\t\t\t\t\tcheck_variable = { global.mvlv_un_pending = 1 }')
    a('\t\t\t\t\tNOT = { check_variable = { global.mvlv_un_legitimacy < 1 } }')
    a('\t\t\t\t\tNOT = { has_country_flag = mvlv_un_lobbied }')
    a('\t\t\t\t}')
    a('\t\t\t\t\tset_country_flag = mvlv_un_lobbied')
    a('\t\t\t\t\tset_variable = { mvlv_un_stance = 1 }')
    a('\t\t\t\t\tset_variable = { mvlv_un_reason = 6 }')
    a('\t\t\t\t\tsubtract_from_variable = { global.mvlv_un_legitimacy = 1 }')
    a('\t\t\t\t\tmvlv_un_refresh_lists = yes')
    a('\t\t\t\t}')
    a('\t\t\t}')
    a('\t\t}')
    a('\t}')
    a('}')
    return '\n'.join(out) + '\n'


# ------------------------------------------------------------------ 本地化

def merge_loc(path, rows):
    raw = open(path, 'rb').read().decode('utf-8-sig')
    lines = raw.replace('\r\n', '\n').split('\n')
    out, seen = [], set()
    for ln in lines:
        hit = None
        for k, v in rows:
            if ln.startswith(' %s:' % k):
                hit = (k, v)
                break
        if hit:
            out.append(' %s:0 "%s"' % hit)
            seen.add(hit[0])
        else:
            out.append(ln)
    add_rows = [' %s:0 "%s"' % (k, v) for k, v in rows if k not in seen]
    while out and out[-1] == '':
        out.pop()
    out += add_rows + ['']
    data = '\n'.join(out).replace('\n', '\r\n').encode('utf-8')
    open(path, 'wb').write(b'\xef\xbb\xbf' + data)
    return len(add_rows)


def build_hist_loc(reg):
    """生成 5 槽位历史的名字/结果脚本本地化块。"""
    names = [r['id'] for r in reg['resolutions']]
    lines = []
    for slot in range(1, 6):
        lines += ['defined_text = {', '\tname = GetUNHist%dName' % slot,
                  '\ttext = {',
                  '\t\ttrigger = { check_variable = { global.mvlv_un_h%d_res = 0 } }' % slot,
                  '\t\tlocalization_key = mvlv_un_res_none_name', '\t}']
        for i, rid in enumerate(names, 1):
            lines += ['\ttext = {',
                      '\t\ttrigger = { check_variable = { global.mvlv_un_h%d_res = %d } }' % (slot, i),
                      '\t\tlocalization_key = mvlv_un_res_%s_name' % rid, '\t}']
        lines += ['\ttext = {', '\t\tlocalization_key = mvlv_un_res_unknown_name', '\t}', '}', '']
        lines += ['defined_text = {', '\tname = GetUNHist%dResult' % slot,
                  '\ttext = {',
                  '\t\ttrigger = { check_variable = { global.mvlv_un_h%d_result = 1 } }' % slot,
                  '\t\tlocalization_key = mvlv_un_result_pass', '\t}',
                  '\ttext = {',
                  '\t\ttrigger = { check_variable = { global.mvlv_un_h%d_result = 2 } }' % slot,
                  '\t\tlocalization_key = mvlv_un_result_fail', '\t}',
                  '\ttext = {',
                  '\t\ttrigger = { check_variable = { global.mvlv_un_h%d_result = 3 } }' % slot,
                  '\t\tlocalization_key = mvlv_un_result_vetoed', '\t}',
                  '\ttext = {', '\t\tlocalization_key = mvlv_un_result_none', '\t}', '}', '']
    return '\n'.join(lines) + '\n'


def build_status_loc(reg):
    """生成 16 个 GetUNResStatus_<id> 脚本本地化块（写入独立片段文件）。"""
    lines = ['# =====================================================================',
             '# mvlv119 联合国大会 | 模块: 决议页状态（生成文件，别手改）',
             '# 生成: work/qa/_gen_un_window_gui.py',
             '# =====================================================================',
             '']
    for item in reg['resolutions']:
        rid = item['id']
        lines += ['defined_text = {', '\tname = GetUNResStatus_%s' % rid,
                  '\ttext = {',
                  '\t\ttrigger = { check_variable = { global.mvlv_un_pending = 1 } }',
                  '\t\tlocalization_key = mvlv_un_res_cond_pending', '\t}',
                  '\ttext = {',
                  '\t\ttrigger = { NOT = { mvlv_un_allow_%s = yes } }' % rid,
                  '\t\tlocalization_key = mvlv_un_res_cond_blocked', '\t}']
        if item['cost'] > 0:
            lines += ['\ttext = {',
                      '\t\ttrigger = { check_variable = { global.mvlv_un_budget > %d } }' % (item['cost'] - 1),
                      '\t\tlocalization_key = mvlv_un_res_%s_cost' % rid, '\t}',
                      '\ttext = {', '\t\tlocalization_key = mvlv_un_res_cond_budget', '\t}']
        else:
            lines += ['\ttext = {', '\t\tlocalization_key = mvlv_un_res_%s_cost' % rid, '\t}']
        lines += ['}', '']
    return '\n'.join(lines) + '\n'


def loc_rows(reg):
    zh, en = [], []
    for item in reg['resolutions']:
        cost = item['cost']
        rid = item['id']
        zh.append(('mvlv_un_res_%s_cost' % rid,
                   '预算 %d' % cost if cost else '不动用预算'))
        zh.append(('mvlv_un_res_%s_status' % rid, '[GetUNResStatus_%s]' % rid))
        en.append(('mvlv_un_res_%s_cost' % rid,
                   'Budget %d' % cost if cost else 'No budget'))
        en.append(('mvlv_un_res_%s_status' % rid, '[GetUNResStatus_%s]' % rid))
    for slot in range(1, 6):
        zh.append(('mvlv_un_log%d_name' % slot, '[GetUNHist%dName]' % slot))
        zh.append(('mvlv_un_log%d_result' % slot, '[GetUNHist%dResult]' % slot))
        en.append(('mvlv_un_log%d_name' % slot, '[GetUNHist%dName]' % slot))
        en.append(('mvlv_un_log%d_result' % slot, '[GetUNHist%dResult]' % slot))
    return zh, en


def main():
    dry = '--dry' in sys.argv
    reg = json.load(io.open(REG, encoding='utf-8'))

    for item in reg['resolutions']:
        if 'section' not in item:
            raise SystemExit('议题 %s 缺 section 字段' % item['id'])

    build_header()
    header_texts()
    build_tabs()
    build_agenda_page()
    build_res_page(reg)
    build_mem_page()
    build_log_page()

    gui = ['guiTypes = {', '', '\tcontainerWindowType = {',
           '\t\tname = "mvlv_un_window"',
           '\t\tposition = { x = 470 y = 40 }',
           '\t\tsize = { width = %d height = %d }' % (W, H),
           '\t\tclipping = no',
           '\t\tmoveable = yes',
           '\t\tclick_to_front = yes',
           '',
           '\t\tbackground = {',
           '\t\t\tname = "un_win_bg"',
           '\t\t\tspriteType = "GFX_mvlv119_un_window_bg"',
           '\t\t}',
           '']
    body = ('\n'.join(gui) + '\n'.join(content)
            + '\n\t}\n'                   # 先闭合 window
            + '\n'.join(ENTRY_DEFS) + '\n'  # 条目模板挂到 guiTypes 顶层
            + '''
	# ================= 国旗条目（旗 + 国名 + 透明点击区） =================
	containerWindowType = {
		name = "mvlv_un_win_entry_yes"
		position = { x = 0 y = 0 }
		size = { width = 100 height = 24 }
\t		background = {
\t			name = "slotbg_yes"
\t			spriteType = "GFX_mvlv119_un_slot_bg"
\t		}
		instantTextBoxType = {
			name = "mvlv_un_win_name_yes"
			position = { x = 4 y = 4 }
			font = "hoi_16mbs"
			text = "mvlv_un_mem_name"
			format = left
			maxWidth = 92
			maxHeight = 16
			alwaystransparent = yes
		}
		buttonType = {
			name = "mvlv_un_win_lobby_yes"
			spriteType = "GFX_mvlv119_un_btn_lobby"
			position = { x = 0 y = 0 }
			Orientation = "UPPER_LEFT"
			pdx_tooltip = "mvlv_un_panel_flag_yes_tt"
		}
	}

	containerWindowType = {
		name = "mvlv_un_win_entry_no"
		position = { x = 0 y = 0 }
		size = { width = 100 height = 24 }
\t		background = {
\t			name = "slotbg_no"
\t			spriteType = "GFX_mvlv119_un_slot_bg"
\t		}
		instantTextBoxType = {
			name = "mvlv_un_win_name_no"
			position = { x = 4 y = 4 }
			font = "hoi_16mbs"
			text = "mvlv_un_mem_name"
			format = left
			maxWidth = 92
			maxHeight = 16
			alwaystransparent = yes
		}
		buttonType = {
			name = "mvlv_un_win_lobby_no"
			spriteType = "GFX_mvlv119_un_btn_lobby"
			position = { x = 0 y = 0 }
			Orientation = "UPPER_LEFT"
			pdx_tooltip = "mvlv_un_panel_flag_no_tt"
		}
	}

	containerWindowType = {
		name = "mvlv_un_win_entry_abs"
		position = { x = 0 y = 0 }
		size = { width = 100 height = 24 }
\t		background = {
\t			name = "slotbg_abs"
\t			spriteType = "GFX_mvlv119_un_slot_bg"
\t		}
		instantTextBoxType = {
			name = "mvlv_un_win_name_abs"
			position = { x = 4 y = 4 }
			font = "hoi_16mbs"
			text = "mvlv_un_mem_name"
			format = left
			maxWidth = 92
			maxHeight = 16
			alwaystransparent = yes
		}
		buttonType = {
			name = "mvlv_un_win_lobby_abs"
			spriteType = "GFX_mvlv119_un_btn_lobby"
			position = { x = 0 y = 0 }
			Orientation = "UPPER_LEFT"
			pdx_tooltip = "mvlv_un_panel_flag_abs_tt"
		}
	}
''' + '}\n')

    sg = build_scripted_gui(reg)
    status_loc = build_status_loc(reg) + build_hist_loc(reg)
    zh, en = loc_rows(reg)

    print('gui %d 行，脚本界面 %d 行，预算键 %d 条' % (
        body.count('\n'), sg.count('\n'), len(zh)))
    print('页元素：议程 %d，决议 %d，成员 %d' % (
        len(page_names[1]), len(page_names[2]), len(page_names[3])))

    if dry:
        print('干跑，未写文件')
        return

    io.open(os.path.join(BASE, 'interface', 'zz_mvlv119_un_window.gui'),
            'w', encoding='utf-8', newline='\n').write(body)
    io.open(os.path.join(BASE, 'common', 'scripted_guis', 'zz_mvlv119_un_window.txt'),
            'w', encoding='utf-8', newline='\n').write(sg)
    io.open(os.path.join(BASE, 'common', 'scripted_localisation',
                        'zz_mvlv119_un_status_loc.txt'),
            'w', encoding='utf-8', newline='\n').write(status_loc)
    n1 = merge_loc(os.path.join(BASE, 'localisation', 'simp_chinese', 'replace',
                                'zz_mvlv119_un_l_simp_chinese.yml'), zh)
    n2 = merge_loc(os.path.join(BASE, 'localisation', 'english', 'replace',
                                'zz_mvlv119_un_l_english.yml'), en)
    print('已写入 gui / scripted_gui / status_loc；中文本地化新增 %d，英文新增 %d' % (n1, n2))


if __name__ == '__main__':
    main()
