# -*- coding: utf-8 -*-
"""补齐两个半成品 flag（2026-10-31 方案 A）。

1. `mvlv_un_refuse`（拒绝）
   在 `mvlv_un_tally` 里，本次投**反对或弃权**的成员国打上 flag。
   效果链：
     * 下次投票时 `core.txt` 的议题 4 分支读它 → 该成员 AI 票分 -20
     * 制裁决议通过时挑出有 flag 的成员 → 挂 mvlv_un_sanction_2（更重）+ 声誉 -5，然后清掉
   即「这次不服从，下次制裁时被点名」。

2. `mvlv_un_tribunal_target`（审判目标）
   在 `mvlv_un_res_tribunal` 开头自动选**声誉最低的成员国**当目标（两遍遍历，13 国开销可忽略），
   再走原有的挂修正 + 365 天政策 + 声誉 -10 + 清 flag。
   原来是「没有设置入口」，现在改成「自动点名」。

两处都插在目标位置，锚点断言，幂等。
"""
import io
import os
import sys

PKG = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\mods\muvluvCNsub_xuerong'
CORE = os.path.join(PKG, 'common', 'scripted_effects', 'zz_mvlv119_un_core.txt')
RES = os.path.join(PKG, 'common', 'scripted_effects', 'zz_mvlv119_un_resolutions.txt')

# ---------- 1) tally 里打 refuse ----------
TALLY_OLD = """	mvlv_un_refresh_lists = yes

	# 结果通知"""

TALLY_NEW = """	mvlv_un_refresh_lists = yes

	# 立场记账：本次投反对或弃权的成员国打上「拒绝」标记。
	# 下次开会议题 4（制裁）的 AI 票分会对它们 -20；制裁决议通过时点名加重。
	# flag 由制裁决议在使用后清除，因此跨会期保留一轮。
	every_country = {
		limit = {
			mvlv_un_is_member = yes
			OR = {
				check_variable = { mvlv_un_stance = 3 }
				check_variable = { mvlv_un_stance = 2 }
			}
		}
		set_country_flag = mvlv_un_refuse
	}

	# 结果通知"""

# ---------- 2) tribunal 里选目标 ----------
TRIB_OLD = """mvlv_un_res_tribunal = {
	every_country = {
		limit = { mvlv_un_is_member = yes has_country_flag = mvlv_un_tribunal_target }"""

TRIB_NEW = """mvlv_un_res_tribunal = {
	# 选目标：声誉最低的成员国（方案 A）。两遍遍历：先求最小值，再打到第一个等于它的成员身上。
	# 只在本决议执行时选，选完立刻被下面的分支消费掉并清 flag，不会残留。
	set_variable = { global.mvlv_un_tr_min = 999 }
	every_country = {
		limit = { mvlv_un_is_member = yes }
		if = {
			limit = { check_variable = { mvlv_un_reputation < global.mvlv_un_tr_min } }
			set_variable = { global.mvlv_un_tr_min = mvlv_un_reputation }
		}
	}
	every_country = {
		limit = {
			mvlv_un_is_member = yes
			check_variable = { mvlv_un_reputation = global.mvlv_un_tr_min }
		}
		if = {
			limit = {
				NOT = { any_country = { limit = { has_country_flag = mvlv_un_tribunal_target } } }
			}
			set_country_flag = mvlv_un_tribunal_target
		}
	}

	every_country = {
		limit = { mvlv_un_is_member = yes has_country_flag = mvlv_un_tribunal_target }"""

EDITS = [
    (CORE, TALLY_OLD, TALLY_NEW, 'tally 里打 refuse'),
    (RES, TRIB_OLD, TRIB_NEW, 'tribunal 里选目标'),
]


def main():
    dry = '--dry-run' in sys.argv
    for path, old, new, what in EDITS:
        if not os.path.exists(path):
            print('缺文件:', path)
            continue
        s = io.open(path, encoding='utf-8').read()
        if new in s:
            print('%-18s 已存在，跳过' % what)
            continue
        if old not in s:
            print('%-18s 锚点未命中：%r' % (what, old[:50]))
            continue
        print('%-18s 命中' % what)
        if not dry:
            io.open(path, 'w', encoding='utf-8', newline='').write(s.replace(old, new, 1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
