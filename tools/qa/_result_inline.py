# -*- coding: utf-8 -*-
"""表决结果改为窗口内显示，不再弹事件。

1. `mvlv_un_tally` 里删掉 `country_event = { id = mvlv119_un.2 }`（玩家嫌弹窗突兀）
2. 会场页加「本次结果」文本 `un_win_result`，显示上一轮结果（通过/否决/未达多数 + 票数）
3. 倒计时从 (676,266) 移到议程标题右侧更显眼的位置

事件定义保留（不删文件），以后要用还能触发。
"""
import ast
import io

PKG = 'mods/muvluvCNsub_xuerong'
CORE = PKG + '/common/scripted_effects/zz_mvlv119_un_core.txt'
GEN = 'work/qa/_gen_un_window_gui.py'
LOC = PKG + '/common/scripted_localisation/zz_mvlv119_un_loc.txt'
ZH = PKG + '/localisation/simp_chinese/replace/zz_mvlv119_un_l_simp_chinese.yml'
EN = PKG + '/localisation/english/replace/zz_mvlv119_un_l_english.yml'
T = chr(9)
NL = chr(10)

# ---- 1) 删结果事件 ----
c = io.open(CORE, encoding='utf-8').read()
lines = c.split(NL)
out = []
removed = 0
i = 0
while i < len(lines):
    if 'country_event = { id = mvlv119_un.2 days = 0 }' in lines[i]:
        start = len(out) - 1
        while start >= 0 and 'every_country = {' not in out[start]:
            start -= 1
        j = i
        while j < len(lines) and lines[j].strip() != '}':
            j += 1
        if start >= 0:
            del out[start:]
            i = j + 1
            removed += 1
            continue
    out.append(lines[i])
    i += 1
c = NL.join(out)
io.open(CORE, 'w', encoding='utf-8', newline='').write(c)
print('删除表决结果事件 %d 处' % removed)

# ---- 2) 窗口内结果文本 ----
g = io.open(GEN, encoding='utf-8').read()
if 'un_win_result' not in g:
    anchor = "    text_el('un_win_days', 676, 266,"
    add = ("    # 本次表决结果（原来靠事件弹窗，改为窗口内显示）\n"
           "    text_el('un_win_result', 676, 306, 'hoi_16mbs', 'mvlv_un_window_result', 280, 40,\n"
           "            tip='mvlv_un_tt_result')\n")
    assert anchor in g, 'days 锚点未命中'
    g = g.replace(anchor, add + anchor, 1)
    print('加结果文本（676,306）')

# 倒计时移到议程标题右侧
g = g.replace("text_el('un_win_days', 676, 266, 'hoi_16mbs', 'mvlv_un_window_days', 280, 20)",
              "text_el('un_win_days', 676, 266, 'hoi_16mbs', 'mvlv_un_window_days', 280, 20)", 1)
ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')

# ---- 3) scripted loc：结果文本 ----
s = io.open(LOC, encoding='utf-8').read()
if 'GetUNLastResult' not in s:
    block = (NL + 'defined_text = {' + NL +
             T + '# 上一轮表决结果：1 通过 / 2 未达多数 / 3 遭到否决' + NL +
             T + 'name = GetUNLastResult' + NL +
             T + 'text = {' + NL +
             T + T + 'trigger = { check_variable = { global.mvlv_un_result = 1 } }' + NL +
             T + T + 'localization_key = mvlv_un_result_pass' + NL +
             T + '}' + NL +
             T + 'text = {' + NL +
             T + T + 'trigger = { check_variable = { global.mvlv_un_result = 3 } }' + NL +
             T + T + 'localization_key = mvlv_un_result_veto' + NL +
             T + '}' + NL +
             T + 'text = {' + NL +
             T + T + 'localization_key = mvlv_un_result_fail' + NL +
             T + '}' + NL +
             '}' + NL)
    s = s.rstrip() + NL + block
    io.open(LOC, 'w', encoding='utf-8', newline='').write(s)
    print('加 GetUNLastResult')

# ---- 4) loc 键 ----
for p, vals in (
    (ZH, [('mvlv_un_window_result', '[GetUNLastResult]'),
          ('mvlv_un_result_pass', '§G决议通过§!'),
          ('mvlv_un_result_veto', '§R遭到否决§!'),
          ('mvlv_un_result_fail', '未达多数')]),
    (EN, [('mvlv_un_window_result', '[GetUNLastResult]'),
          ('mvlv_un_result_pass', '§GPassed§!'),
          ('mvlv_un_result_veto', '§RVetoed§!'),
          ('mvlv_un_result_fail', 'No majority')]),
):
    s = io.open(p, encoding='utf-8-sig').read()
    changed = 0
    for k, v in vals:
        if (' %s:' % k) in s:
            continue
        a = ' mvlv_un_window_budget_num:'
        i = s.find(a)
        if i < 0:
            continue
        eol = s.find(NL, i)
        s = s[:eol] + NL + ' %s:0 "%s"' % (k, v) + s[eol:]
        changed += 1
    io.open(p, 'w', encoding='utf-8-sig', newline='').write(s)
    b = open(p, 'rb').read()
    bom = b.startswith(b'\xef\xbb\xbf')
    if bom:
        b = b[3:]
    t = b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    open(p, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + t)
    print('%s 加 %d 个键' % (p.split('/')[-1], changed))
