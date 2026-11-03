# -*- coding: utf-8 -*-
"""UI 迭代第一批：标题 / 初始秘书长 / 初始观察员。

1. 标题「联合国大会」→「安全保障理事会」（中英同步）
2. 初始秘书长由国联推举（sg = 1 改革派），不再是「席位空缺」
3. 初始观察员为非洲联合（AFR，observer = 1），不再是「无观察员」
4. 对应文案同步（中英各两份）
"""
import io

PKG = 'mods/muvluvCNsub_xuerong'
CORE = PKG + '/common/scripted_effects/zz_mvlv119_un_core.txt'
SG = PKG + '/common/scripted_effects/zz_mvlv119_un_sg.txt'
ZH = PKG + '/localisation/simp_chinese/replace/zz_mvlv119_un_l_simp_chinese.yml'
EN = PKG + '/localisation/english/replace/zz_mvlv119_un_l_english.yml'

T = chr(9)
NL = chr(10)

# ---------- 1) 标题 ----------
edits_loc = [
    (ZH, 'mvlv_un_panel_title:0 "§L联合国大会§!"',
     'mvlv_un_panel_title:0 "§L安全保障理事会§!"'),
    (EN, 'mvlv_un_panel_title:0 "§LUnited Nations General Assembly§!"',
     'mvlv_un_panel_title:0 "§LUnited Nations Security Council§!"'),
    # 观察员文案
    (ZH, 'mvlv_un_window_observer_yes:0 "COSEAN 已入席，大会 +1 票。"',
     'mvlv_un_window_observer_yes:0 "非洲联合作为观察员入席，理事会 +1 票。"'),
    (EN, 'mvlv_un_window_observer_yes:0 "COSEAN is seated. The Assembly gains one vote."',
     'mvlv_un_window_observer_yes:0 "The African Union sits as observer. The Council gains one vote."'),
    # 秘书长显示名带上推举方
    (ZH, 'mvlv_un_sg_short_reform:0 "改革派"',
     'mvlv_un_sg_short_reform:0 "国联推举 · 改革派"'),
    (EN, 'mvlv_un_sg_short_reform:0 "Reformist"',
     'mvlv_un_sg_short_reform:0 "UN-backed Reformist"'),
]

for path, old, new in edits_loc:
    s = io.open(path, encoding='utf-8-sig').read()
    if new in s:
        print('已有，跳过:', new.split(':0')[0])
        continue
    if old not in s:
        print('未命中:', old[:50])
        continue
    io.open(path, 'w', encoding='utf-8-sig', newline='').write(s.replace(old, new, 1))
    print('已改:', new.split(':0')[0])

# ---------- 2) 初始观察员 ----------
s = io.open(CORE, encoding='utf-8').read()
old_obs = T + T + 'set_variable = { global.mvlv_un_observer = 0 }'
new_obs = (T + T + '# 开局即有观察员：非洲联合（AFR）入席，理事会 +1 票' + NL +
           T + T + 'set_variable = { global.mvlv_un_observer = 1 }')
if new_obs in s:
    print('观察员初值已是 1，跳过')
elif old_obs in s:
    s = s.replace(old_obs, new_obs, 1)
    io.open(CORE, 'w', encoding='utf-8', newline='').write(s)
    print('已改初始观察员 = 1（AFR）')
else:
    print('观察员初值锚点未命中')

# ---------- 3) 初始秘书长 ----------
s = io.open(SG, encoding='utf-8').read()
old_sg = T + T + 'set_variable = { global.mvlv_un_sg = 0 }'
new_sg = (T + T + '# 开局由国联（UNI）推举改革派秘书长，不再空缺' + NL +
          T + T + 'set_variable = { global.mvlv_un_sg = 1 }' + NL +
          T + T + 'set_variable = { global.mvlv_un_sg_tag = 1 }')
if new_sg in s:
    print('秘书长初值已改，跳过')
elif old_sg in s:
    s = s.replace(old_sg, new_sg, 1)
    io.open(SG, 'w', encoding='utf-8', newline='').write(s)
    print('已改初始秘书长 = 1（国联推举）')
else:
    print('秘书长初值锚点未命中')
