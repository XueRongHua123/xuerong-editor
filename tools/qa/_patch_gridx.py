# -*- coding: utf-8 -*-
"""用 properties 的 x 坐标控制 grid 显隐（dynamic_lists 的 grid 不认 _visible）。

思路：四个 grid 外面已有 `<name>_wrap` 容器。properties 里把它们的 x 绑到全局变量，
tab 切换时把不属于当前页的那组推到屏幕外（-9999）。
`dirty = global.mvlv_un_ui_version` 会在 tab 点击时 +1，触发重新应用 properties。

改两处：
  1. properties 段追加 4 条 x 绑定
  2. tab click 里设 4 个全局变量（每个 tab 一套）
另外在 core.txt 的初始化里给这 4 个变量默认值（第一页可见）。
"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
CORE = ('mods/muvluvCNsub_xuerong/common/scripted_effects/'
        'zz_mvlv119_un_core.txt')

T = chr(9)
B = chr(92)

# 原始 x 坐标（与 grid_el 调用处一致）
X_YES, X_NO, X_ABS, X_MEM = 322, 534, 746, 24
OFF = -9999

# ---------------- 1) 生成器：properties 追加 ----------------
lines = io.open(GEN, encoding='utf-8').read().split(chr(10))
i_prop = next(i for i, l in enumerate(lines)
              if l.strip() == 'a(' + chr(39) + T + T + 'properties = {' + chr(39) + ')')
# 找到 properties 段最后一条（mvlv_un_mem_flag）
i_last = next(i for i in range(i_prop, i_prop + 10)
              if 'mvlv_un_mem_flag' in lines[i])
add_props = [
    '    a(' + chr(39) + T + T + T + 'mvlv_un_win_yes_grid_wrap = { x = global.mvlv_un_gx_yes }' + chr(39) + ')',
    '    a(' + chr(39) + T + T + T + 'mvlv_un_win_no_grid_wrap = { x = global.mvlv_un_gx_no }' + chr(39) + ')',
    '    a(' + chr(39) + T + T + T + 'mvlv_un_win_abs_grid_wrap = { x = global.mvlv_un_gx_abs }' + chr(39) + ')',
    '    a(' + chr(39) + T + T + T + 'mvlv_un_mem_grid_wrap = { x = global.mvlv_un_gx_mem }' + chr(39) + ')',
]
lines[i_last + 1:i_last + 1] = add_props
print('properties 追加 %d 条' % len(add_props))

# ---------------- 2) 生成器：tab click 里设坐标 ----------------
i_tab = next(i for i, l in enumerate(lines) if 'mvlv_un_tab_%s_click' in l)
# 在该循环里，set_variable 之后插入 4 行
i_set = i_tab + 1
while 'set_variable = { mvlv_un_tab = %d }' not in lines[i_set]:
    i_set += 1
insert = []
for var, visible_x in (('yes', X_YES), ('no', X_NO), ('abs', X_ABS), ('mem', X_MEM)):
    cond = '%d' % visible_x if var == 'mem' else '%d' % OFF   # 占位，下面按页重写
insert = [
    "        # grid 显隐：本页要显示的 grid 放回原位，其余推到屏幕外",
    "        for _v, _x in (('yes', 322), ('no', 534), ('abs', 746), ('mem', 24)):",
    "            _keep = (('yes', 'no', 'abs') if p == 1 else ((('mem',) if p == 3 else ())))",
    "            a('" + T + T + T + "set_variable = { global.mvlv_un_gx_%s = %d }' % (_v, _x if _v in _keep else -9999))",
]
lines[i_set + 1:i_set + 1] = insert
print('tab click 插入坐标设置')

src = chr(10).join(lines)
ast.parse(src)
io.open(GEN, 'w', encoding='utf-8', newline='').write(src)
print('生成器已改，语法 OK')

# ---------------- 3) core.txt 初始化 ----------------
s = io.open(CORE, encoding='utf-8').read()
anchor = 'mvlv_un_refresh_lists = {'
assert anchor in s
init = (
    'mvlv_un_init_grid_x = {\n'
    '\t# grid 显隐靠坐标：第一页（会场）显示投票三栏，其余推到屏幕外。\n'
    '\t# dynamic_lists 的 grid 不认 _visible 触发器，只能用坐标绕。\n'
    '\tset_variable = { global.mvlv_un_gx_yes = %d }\n'
    '\tset_variable = { global.mvlv_un_gx_no = %d }\n'
    '\tset_variable = { global.mvlv_un_gx_abs = %d }\n'
    '\tset_variable = { global.mvlv_un_gx_mem = %d }\n'
    '}\n\n' % (X_YES, X_NO, X_ABS, OFF)
)
s = s.replace(anchor, init + anchor, 1)
io.open(CORE, 'w', encoding='utf-8', newline='').write(s)
print('core.txt 已加 mvlv_un_init_grid_x')
