# -*- coding: utf-8 -*-
"""grid 显隐改走 properties 坐标（dynamic_lists 的 grid 不认 _visible）。

改三处：
  1. 生成器 properties 段：4 个 grid_wrap 的 x 绑全局变量
  2. 生成器 tab click：按当前页设 4 个全局变量（不在本页的推到 -9999）
  3. core.txt：初始化函数 mvlv_un_init_grid_x

本脚本用 chr() 拼制表符/反斜杠，匹配用 in 而非 ==，避免格式与转义问题。
"""
import ast
import io

GEN = 'work/qa/_gen_un_window_gui.py'
CORE = 'mods/muvluvCNsub_xuerong/common/scripted_effects/zz_mvlv119_un_core.txt'

T = chr(9)
B = chr(92)
Q = chr(39)
NL = chr(10)

GRIDS = (('yes', 322), ('no', 534), ('abs', 746), ('mem', 24))
OFF = -9999


def line_a(indent_n, text):
    """构造生成器里的一行：a('<tabs><text>')  → 返回源码行。"""
    tabs = B + 't' * 1 if False else (B + 't') * indent_n
    return '    a(' + Q + tabs + text + Q + ')'


# ---------------- 1) properties 段 ----------------
lines = io.open(GEN, encoding='utf-8').read().split(NL)
i_mem_flag = next(i for i, l in enumerate(lines) if 'mvlv_un_mem_flag = { image' in l)
print('properties 锚点 L%d' % (i_mem_flag + 1))

props = []
for name, _x in GRIDS:
    props.append(line_a(3, 'mvlv_un_%s_grid_wrap = { x = global.mvlv_un_gx_%s }'
                        % ('win_' + name if name != 'mem' else 'mem', name)))
lines[i_mem_flag + 1:i_mem_flag + 1] = props
print('插入 properties %d 条' % len(props))

# ---------------- 2) tab click 里设坐标 ----------------
i_tab = next(i for i, l in enumerate(lines) if 'mvlv_un_tab_%s_click' in l)
i_set = next(i for i in range(i_tab, i_tab + 6)
             if 'set_variable = { mvlv_un_tab = %d }' in lines[i])
print('tab click 锚点 L%d' % (i_set + 1))

block = [
    '        _keep = (("yes", "no", "abs") if p == 1 else (("mem",) if p == 3 else ()))',
    '        for _v, _x in (("yes", 322), ("no", 534), ("abs", 746), ("mem", 24)):',
    "            a('" + (B + 't') * 3 + "set_variable = { global.mvlv_un_gx_%s = %d }' % (_v, _x if _v in _keep else -9999))",
]
lines[i_set + 1:i_set + 1] = block
print('插入 tab click 坐标设置 %d 行' % len(block))

src = NL.join(lines)
ast.parse(src)
io.open(GEN, 'w', encoding='utf-8', newline='').write(src)
print('生成器已改，语法 OK')

# ---------------- 3) core.txt 初始化 ----------------
s = io.open(CORE, encoding='utf-8').read()
if 'mvlv_un_init_grid_x' in s:
    print('core.txt 已有初始化，跳过')
else:
    anchor = 'mvlv_un_refresh_lists = {'
    assert anchor in s, 'core 锚点未命中'
    init = (
        'mvlv_un_init_grid_x = {' + NL +
        T + '# grid 显隐靠坐标：第一页（会场）显示投票三栏，其余推到屏幕外。' + NL +
        T + '# dynamic_lists 的 grid 不认 _visible 触发器，只能用坐标绕。' + NL +
        T + 'set_variable = { global.mvlv_un_gx_yes = 322 }' + NL +
        T + 'set_variable = { global.mvlv_un_gx_no = 534 }' + NL +
        T + 'set_variable = { global.mvlv_un_gx_abs = 746 }' + NL +
        T + 'set_variable = { global.mvlv_un_gx_mem = -9999 }' + NL +
        '}' + NL + NL
    )
    s = s.replace(anchor, init + anchor, 1)
    io.open(CORE, 'w', encoding='utf-8', newline='').write(s)
    print('core.txt 已加 mvlv_un_init_grid_x')
