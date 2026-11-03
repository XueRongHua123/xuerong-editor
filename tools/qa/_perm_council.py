# -*- coding: utf-8 -*-
"""常任理事国重划 + UI 标识。

新常任：JAP（日本帝国）、SOV（苏维埃联盟）、EUR（欧洲联盟）、OSE（澳大利亚）、CHI（统一中华战线）
其余全部为普通会员国（原来的 USA、GEU 降级）。

UI 标识：成员页国名前加 ★。做法是给 `mvlv_un_mem_name` 加一层 scripted loc，
常任走 `_perm` 分支（★ 前缀），否则走原键。gui 里的 text 指向新键。
"""
import ast
import io

PKG = 'mods/muvluvCNsub_xuerong'
RULES = PKG + '/common/scripted_triggers/zz_mvlv119_un_rules.txt'
LOC = PKG + '/common/scripted_localisation/zz_mvlv119_un_loc.txt'
GEN = 'work/qa/_gen_un_window_gui.py'
ZH = PKG + '/localisation/simp_chinese/replace/zz_mvlv119_un_l_simp_chinese.yml'
EN = PKG + '/localisation/english/replace/zz_mvlv119_un_l_english.yml'
T = chr(9)
NL = chr(10)

# ---------- 1) 常任名单 ----------
s = io.open(RULES, encoding='utf-8').read()
old = """mvlv_un_is_permanent = {
	OR = {
		tag = USA
		tag = SOV
		tag = CHI
		tag = JAP
		tag = EUR
		tag = GEU
	}
}"""
new = """mvlv_un_is_permanent = {
	# 五个常任理事国（2026-10-31 重划）：日本帝国 / 苏维埃联盟 / 欧洲联盟 / 澳大利亚 / 统一中华战线
	# 安理会表决中任一人反对即构成否决
	OR = {
		tag = JAP
		tag = SOV
		tag = EUR
		tag = OSE
		tag = CHI
	}
}"""
assert old in s, 'is_permanent 未命中'
io.open(RULES, 'w', encoding='utf-8', newline='').write(s.replace(old, new, 1))
print('常任名单已重划（JAP/SOV/EUR/OSE/CHI）')

# ---------- 2) scripted loc：常任加 ★ ----------
s = io.open(LOC, encoding='utf-8').read()
if 'GetUNMemberName' in s:
    print('成员名 scripted loc 已存在，跳过')
else:
    block = (NL +
             'defined_text = {' + NL +
             T + '# 成员页国名：常任理事国加 ★ 前缀，其余原样' + NL +
             T + 'name = GetUNMemberName' + NL +
             T + 'text = {' + NL +
             T + T + 'trigger = { mvlv_un_is_permanent = yes }' + NL +
             T + T + 'localization_key = mvlv_un_mem_name_perm' + NL +
             T + '}' + NL +
             T + 'text = {' + NL +
             T + T + 'localization_key = mvlv_un_mem_name' + NL +
             T + '}' + NL +
             '}' + NL)
    s = s.rstrip() + NL + block
    io.open(LOC, 'w', encoding='utf-8', newline='').write(s)
    print('已加 GetUNMemberName')

# ---------- 3) loc 键 ----------
for path, pairs in (
    (ZH, [('mvlv_un_mem_name_perm:0', 'mvlv_un_mem_name_perm:0 "★ [This.GetName]"')]),
    (EN, [('mvlv_un_mem_name_perm:0', 'mvlv_un_mem_name_perm:0 "★ [This.GetName]"')]),
):
    s = io.open(path, encoding='utf-8-sig').read()
    key = 'mvlv_un_mem_name_perm:0'
    if key in s:
        print('已有', key, '跳过')
        continue
    # 插在 mvlv_un_mem_name 之后
    anchor = ' mvlv_un_mem_name:0'
    idx = s.find(anchor)
    if idx < 0:
        print('锚点未命中:', path)
        continue
    eol = s.find(chr(10), idx)
    ins = chr(10) + ' mvlv_un_mem_name_perm:0 "★ [This.GetName]"'
    s = s[:eol] + ins + s[eol:]
    io.open(path, 'w', encoding='utf-8-sig', newline='').write(s)
    print('已加 loc 键:', path.split('/')[-1])

# ---------- 4) gui 的成员名指向 scripted loc ----------
s = io.open(GEN, encoding='utf-8').read()
old_g = "'mvlv_un_mem_name', 196, 18"
new_g = "'GetUNMemberName', 196, 18"
if old_g in s:
    s = s.replace(old_g, new_g, 1)
    ast.parse(s)
    io.open(GEN, 'w', encoding='utf-8', newline='').write(s)
    print('生成器：成员名改指 GetUNMemberName')
else:
    print('生成器成员名锚点未命中')
