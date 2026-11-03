# -*- coding: utf-8 -*-
"""把 dynamic_lists 的条目模板容器移到 guiTypes 顶层。

依据：原版 MTG_naval_treaty_scripted_gui.gui 里条目容器 depth=2（guiTypes 直接子级）；
我们的在 window 内（depth=3），游戏报 Undefined GUI_TYPE / Failed to create containerWindowType。

改法（三处，都用锚点定位，不依赖行号）：
  1. 新增 ENTRY_DEFS + add_entry()
  2. build_mem_page 里 mem_entry 那段改用 add_entry
  3. body 拼接：content 之后先闭合 window，再接 ENTRY_DEFS 与三个投票条目，最后闭合 guiTypes

幂等：检测到 ENTRY_DEFS 就退出。
"""
import io
import os
import sys

GEN = os.path.join(r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作', 'work', 'qa',
                   '_gen_un_window_gui.py')


def main():
    dry = '--dry-run' in sys.argv
    s = io.open(GEN, encoding='utf-8').read()
    if 'ENTRY_DEFS' in s:
        print('已改过，跳过')
        return 0

    # 1) 新列表与函数
    old = "def add(s):\n    content.append(s)\n"
    new = ("def add(s):\n    content.append(s)\n\n\n"
           "ENTRY_DEFS = []      # dynamic_lists 的条目模板容器，必须挂在 guiTypes 顶层\n\n\n"
           "def add_entry(s):\n    ENTRY_DEFS.append(s)\n")
    assert old in s, 'add() 定义未命中'
    s = s.replace(old, new, 1)

    # 2) mem_entry 整块改用 add_entry
    start_mark = '    # 条目容器（每个国家一份，作用域随条目切换）\n'
    end_mark = "    add('\\t}')\n    add('')\n\n\n# ------------------------------------------------------------------ 第四页：记录"
    i = s.index(start_mark)
    j = s.index(end_mark, i)
    block = s[i:j + len("    add('\\t}')\n    add('')")]
    if 'add_entry(' in block:
        print('该块已改过')
    else:
        n = block.count('    add(')
        s = s[:i] + block.replace('    add(', '    add_entry(') + s[i + len(block):]
        print('mem_entry 块内 %d 处 add → add_entry' % n)
        print('add-entry 块首改为：')
        print('   ' + s[i:i + 120].split('\n')[0])

    # 3) body 拼接
    old3 = "    body = '\\n'.join(gui) + '\\n'.join(content) + '''"
    new3 = ("    body = ('\\n'.join(gui) + '\\n'.join(content)\n"
            "            + '\\n\\t}\\n'                   # 先闭合 window\n"
            "            + '\\n'.join(ENTRY_DEFS) + '\\n'  # 条目模板挂到 guiTypes 顶层\n"
            "            + '''")
    assert old3 in s, 'body 拼接未命中'
    s = s.replace(old3, new3, 1)

    # 4) 结尾：原本最后一个 } 闭合 window，现在 window 已提前闭合 → 删掉它，并补右括号
    old4 = "\t}\n}\n}\n'''\n"
    new4 = "\t}\n}\n''' + '}\\n')\n"
    assert old4 in s, '结尾闭合未命中'
    s = s.replace(old4, new4, 1)

    print('四处改动全部命中')
    if dry:
        print('（--dry-run 未写盘）')
    else:
        io.open(GEN, 'w', encoding='utf-8', newline='').write(s)
        print('已写入')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
