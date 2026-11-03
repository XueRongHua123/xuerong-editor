# -*- coding: utf-8 -*-
"""解析 .gui 的花括号嵌套，打印容器层级树。

用途：确认某个 containerWindowType 到底挂在 window 下还是 page 容器下 ——
`country_scope_entry_container` 要求条目容器是 window 的直接子级，挂错层就创建失败
（游戏报 Undefined GUI_TYPE / Failed to create containerWindowType）。
"""
import io
import os
import re
import sys

GUI = os.path.join(
    r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\mods\muvluvCNsub_xuerong',
    'interface', 'zz_mvlv119_un_window.gui')

WATCH = ('mvlv_un_mem_entry', 'mvlv_un_win_entry_yes', 'mvlv_un_mem_grid',
         'mvlv_un_win_yes_grid', 'un_page_mem', 'un_page_agenda', 'mvlv_un_window')


def main():
    t = io.open(GUI, encoding='utf-8-sig', errors='replace').read()
    lines = t.split('\n')
    stack = []      # [(kind, name_or_None, depth)]
    hits = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        # 形如 xxxType = {  或者  name = "foo"
        m = re.match(r'(\w+)\s*=\s*\{', stripped)
        if m and m.group(1).endswith(('Type', 'type')) or re.match(r'gridboxtype\s*=', stripped, re.I):
            kind = m.group(1) if m else 'gridboxtype'
            stack.append([kind, None, i])
        nm = re.match(r'name\s*=\s*"([^"]+)"', stripped)
        if nm and stack:
            stack[-1][1] = nm.group(1)
            if nm.group(1) in WATCH:
                path = ' > '.join('%s[%s]' % (s[1] or '?', s[0]) for s in stack)
                hits.append((i, nm.group(1), len(stack), path))
        # 闭合
        opens = line.count('{')
        closes = line.count('}')
        if stripped.endswith('}') and not opens:
            if stack:
                stack.pop()
        elif closes and stack and not opens:
            for _ in range(closes):
                if stack:
                    stack.pop()

    print('=== 关注元素所在层级（深度 1 = window 的直接子级）===')
    for line_no, name, depth, path in hits:
        print('\nL%-5d %s  depth=%d' % (line_no, name, depth))
        print('   ' + path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
