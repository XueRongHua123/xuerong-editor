# -*- coding: utf-8 -*-
"""去掉「会期召开」事件的弹窗，改为窗口内提示。

事件 mvlv119_un.1 在两处开会 effect 里弹给玩家（例行全会 + 危机会议），
玩家反馈「提示太突兀」。改成静默开会，状态靠窗口里的倒计时行显示。

保留 on_actions 里危机升级那一处（重要转折，需要玩家知道）。
同时把倒计时行移到议程区右侧（原来在 y=608 按钮下方，容易被挤掉）。
"""
import ast
import io

PKG = 'mods/muvluvCNsub_xuerong'
CORE = PKG + '/common/scripted_effects/zz_mvlv119_un_core.txt'
GEN = 'work/qa/_gen_un_window_gui.py'
NL = chr(10)

# ---- 1) 删两处开会事件 ----
s = io.open(CORE, encoding='utf-8').read()
block = ("	every_country = {'" + NL +
         "		limit = { mvlv_un_is_member = yes is_ai = no }'" + NL +
         "		country_event = { id = mvlv119_un.1 days = 0 }'" + NL +
         "	}'" + NL)
# 上面构造多引号，改用简单行过滤
lines = s.split(NL)
out = []
removed = 0
i = 0
while i < len(lines):
    if 'country_event = { id = mvlv119_un.1 days = 0 }' in lines[i]:
        # 往上找 every_country = { 起头，往下找闭合 }
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
s = NL.join(out)
io.open(CORE, 'w', encoding='utf-8', newline='').write(s)
print('删除开会事件 %d 处（保留危机升级那处）' % removed)

# ---- 2) 倒计时移到议程区右侧 ----
g = io.open(GEN, encoding='utf-8').read()
moved = 0
for old, new in (
        ("text_el('un_win_days', 24, 608,", "text_el('un_win_days', 676, 266,"),
        ("text_el('un_win_budget', 236, 608,", "text_el('un_win_budget', 676, 286,"),
):
    if old in g:
        g = g.replace(old, new, 1)
        moved += 1
print('倒计时/预算移到议程区右侧：%d 处' % moved)
ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('语法 OK')
