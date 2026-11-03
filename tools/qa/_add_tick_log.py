# -*- coding: utf-8 -*-
"""加日志：验证倒计时到底走几天才结算。

在 on_daily 的递减处和 tally 入口各打一行 log（写入 logs/error.log），
跑一次会期后 grep MVLVUN 就能看到实际天数。

日志格式：
  MVLVUN tick days=N      每次每日递减后
  MVLVUN TALLY days=N     触发结算时
"""
import io

PKG = 'mods/muvluvCNsub_xuerong'
OA = PKG + '/common/on_actions/zz_mvlv119_un_sessions.txt'
CORE = PKG + '/common/scripted_effects/zz_mvlv119_un_core.txt'
T = chr(9)
NL = chr(10)

s = io.open(OA, encoding='utf-8').read()

# 1) 每日递减后打日志
old = (T * 4 + "if = { limit = { check_variable = { global.mvlv_un_pending = 1 } }" + NL +
       T * 5 + "subtract_from_variable = { global.mvlv_un_vote_days = 1 }" + NL)
new = (T * 4 + "if = { limit = { check_variable = { global.mvlv_un_pending = 1 } }" + NL +
       T * 5 + "subtract_from_variable = { global.mvlv_un_vote_days = 1 }" + NL +
       T * 5 + '# 调试：确认倒计时天数（跑完 grep MVLVUN logs/error.log）' + NL +
       T * 5 + 'log = "MVLVUN tick"' + NL)
if 'MVLVUN tick' not in s:
    assert old in s, 'on_daily 递减锚点未命中'
    s = s.replace(old, new, 1)
    print('on_daily 加日志')
else:
    print('on_daily 已有日志')
io.open(OA, 'w', encoding='utf-8', newline='').write(s)

# 2) tally 入口打日志
c = io.open(CORE, encoding='utf-8').read()
old2 = 'mvlv_un_tally = {' + NL + T + 'set_variable = { global.mvlv_un_pending = 0 }'
new2 = ('mvlv_un_tally = {' + NL +
        T + 'log = "MVLVUN TALLY"' + NL +
        T + 'set_variable = { global.mvlv_un_pending = 0 }')
if 'MVLVUN TALLY' not in c:
    assert old2 in c, 'tally 锚点未命中'
    c = c.replace(old2, new2, 1)
    print('tally 加日志')
else:
    print('tally 已有日志')
io.open(CORE, 'w', encoding='utf-8', newline='').write(c)
