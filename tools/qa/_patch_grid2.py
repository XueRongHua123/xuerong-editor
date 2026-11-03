# -*- coding: utf-8 -*-
"""给 grid_el 套一层容器：dynamic_lists 的 grid 不响应 _visible 触发器。

依据：原版 common/scripted_guis 全库没有 *grid_visible 的写法；
MTG 的 dynamic_lists 只给 label 配可见性。本 mod 实测 mem_grid / voting grid
在四个页面都显示，而外层 page 容器能正常隐藏。

本脚本内用 chr() 拼制表符与反斜杠，避免多层转义。
"""
import ast
import io

P = 'work/qa/_gen_un_window_gui.py'
lines = io.open(P, encoding='utf-8').read().split(chr(10))

start = next(i for i, l in enumerate(lines) if l.startswith('def grid_el('))
end = next(i for i in range(start + 1, start + 40)
           if lines[i].strip() == 'page_names[page].append(name)')
print('替换 L%d-L%d' % (start + 1, end + 1))

T = chr(9)
B = chr(92)
Q = "'"
D = '"'


def q(s):
    return Q + s + Q


new = [
    'def grid_el(name, x, y, w, h, sw, sh, cols, page=1):',
    '    """生成 grid。',
    '',
    '    外面套一层 containerWindowType（<name>_wrap）：dynamic_lists 管理的 grid',
    '    不响应 _visible 触发器（原版全库没有给 grid 配可见性的先例），',
    '    所以可见性绑到外层容器，grid 自己保持原名给 dynamic_lists 用。',
    '    """',
    "    wrap = name + '_wrap'",
    '    lines = [',
    '        ' + q('containerWindowType = {') + ',',
    '        ' + q(T + 'name = ' + D + '%s' + D) + ' % wrap,',
    '        ' + q(T + 'position = { x = %d y = %d }') + ' % (x, y),',
    '        ' + q(T + 'size = { width = %d height = %d }') + ' % (w, h),',
    "        '',",
    '        ' + q(T + 'gridboxtype = {') + ',',
    '        ' + q(T + T + 'name = ' + D + '%s' + D) + ' % name,',
    '        ' + q(T + T + 'position = { x = 0 y = 0 }') + ',',
    '        ' + q(T + T + 'size = { width = %d height = %d }') + ' % (w, h),',
    '        ' + q(T + T + 'slotsize = { width = %d height = %d }') + ' % (sw, sh),',
    '        ' + q(T + T + 'max_slots_horizontal = %d') + ' % cols,',
    '        ' + q(T + T + 'format = ' + D + 'UPPER_LEFT' + D) + ',',
    '        ' + q(T + '}') + ',',
    '        ' + q('}') + ',',
    '    ]',
    '    add(indent(' + q(B + 'n') + '.join(lines), 2))',
    '    page_names[page].append(wrap)',
]

lines[start:end + 1] = new
io.open(P, 'w', encoding='utf-8', newline='').write(chr(10).join(lines))
print('已替换')
ast.parse(io.open(P, encoding='utf-8').read())
print('语法 OK')
