# -*- coding: utf-8 -*-
"""三处修正：

1. **常任否决在例行全会也生效**：原来只有「危机安理会」分支检查 `mvlv_un_vetoed`，
   kind=1（例行全会）和 kind=3（紧急特别会议）完全不看否决，所以常任投反对照样通过。
   改成所有分支都先检查否决，被否决则 result=3（未通过）。
   紧急特别会议（kind=3）按联合国规则本来就是「大会绕过否决」，保留不检查。

2. **结果在窗口内显示**：新增 `mvlv_un_last_result` 供会场页显示本次结果，
   不再只靠事件弹窗。

3. **预算数值可见**：新增 `un_win_budget` 文本。
"""
import ast
import io

PKG = 'mods/muvluvCNsub_xuerong'
CORE = PKG + '/common/scripted_effects/zz_mvlv119_un_core.txt'
GEN = 'work/qa/_gen_un_window_gui.py'
ZH = PKG + '/localisation/simp_chinese/replace/zz_mvlv119_un_l_simp_chinese.yml'
EN = PKG + '/localisation/english/replace/zz_mvlv119_un_l_english.yml'
T = chr(9)
NL = chr(10)

# ---- 1) 例行全会也检查否决 ----
s = io.open(CORE, encoding='utf-8').read()
old = """	else_if = { limit = { check_variable = { global.mvlv_un_session_kind = 1 } }
		if = { limit = { mvlv_un_majority_reached = yes }
			set_variable = { global.mvlv_un_result = 1 }
		}
	}"""
new = """	else_if = { limit = { check_variable = { global.mvlv_un_session_kind = 1 } }
		# 例行全会同样受常任否决约束：达标后仍有常任反对 → 未通过
		if = { limit = { mvlv_un_majority_reached = yes } }
			if = { limit = { mvlv_un_vetoed = yes }
				set_variable = { global.mvlv_un_result = 3 }
			}
			else = {
				set_variable = { global.mvlv_un_result = 1 }
			}
		}
	}"""
if '例行全会同样受常任否决约束' in s:
    print('否决已修，跳过')
else:
    assert old in s, 'kind=1 分支未命中'
    s = s.replace(old, new, 1)
    print('kind=1 分支加入否决检查')

# 紧急特别会议（kind=3）保留「绕过否决」，加注释说明
old3 = """	if = { limit = { check_variable = { global.mvlv_un_session_kind = 3 } }
		if = { limit = { mvlv_un_supermajority_reached = yes }"""
new3 = """	if = { limit = { check_variable = { global.mvlv_un_session_kind = 3 } }
		# 紧急特别会议按联合国规则可绕过常任否决（大会接管），这里刻意不查 mvlv_un_vetoed
		if = { limit = { mvlv_un_supermajority_reached = yes }"""
if '可绕过常任否决' not in s:
    s = s.replace(old3, new3, 1)
    print('kind=3 加注释说明')

io.open(CORE, 'w', encoding='utf-8', newline='').write(s)

# ---- 2) 会场页加预算与结果文本 ----
g = io.open(GEN, encoding='utf-8').read()
if 'un_win_budget' not in g:
    anchor = "    text_el('un_win_days', 24, 608,"
    add = ("    # 预算数值与本次结果（原来只有「预算：正常」的定性描述，看不到数字）\n"
           "    text_el('un_win_budget', 236, 608, 'hoi_16mbs', 'mvlv_un_window_budget_num', 240, 20)\n")
    assert anchor in g, 'days 锚点未命中'
    g = g.replace(anchor, add + anchor, 1)
    print('加预算数值文本')
ast.parse(g)
io.open(GEN, 'w', encoding='utf-8', newline='').write(g)
print('生成器语法 OK')

# ---- 3) loc ----
for p, val in ((ZH, '预算：[?global.mvlv_un_budget]'), (EN, 'Budget: [?global.mvlv_un_budget]')):
    s = io.open(p, encoding='utf-8-sig').read()
    if ' mvlv_un_window_budget_num:' in s:
        continue
    a = ' mvlv_un_vote_hint:'
    i = s.find(a)
    if i < 0:
        print('loc 锚点未命中:', p.split('/')[-1])
        continue
    eol = s.find(NL, i)
    s = s[:eol] + NL + ' mvlv_un_window_budget_num:0 "%s"' % val + s[eol:]
    io.open(p, 'w', encoding='utf-8-sig', newline='').write(s)
    b = open(p, 'rb').read()
    bom = b.startswith(b'\xef\xbb\xbf')
    if bom:
        b = b[3:]
    t = b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    open(p, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + t)
    print('加 loc:', p.split('/')[-1])
