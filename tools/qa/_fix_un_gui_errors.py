# -*- coding: utf-8 -*-
"""修 UN 窗口的两处检查 ERROR（改生成器，不手改产物）：

1. GFX001：窗口左上角 emblem 引用 `GFX_goal_EasyUNI_un_logo`，这个 sprite 从来没注册过。
   改用已注册的 `GFX_mvlv119_un_entry`（顶栏入口那张 UN 徽记，44×44，同款视觉）。
2. GUI002：`scripted_gui` 缺 `context_type`。基座与本包的 dust_topbar 都写了
   `context_type = player_context`，这两个窗口补上同一个。

`zz_mvlv119_un_window.txt` 是 _gen_un_window_gui.py 生成的，所以改生成器；
`zz_mvlv119_un_entry.txt` 是手写文件，直接改。

改完必须重跑生成器，再用 diff 确认只动了预期的地方。
"""
import io
import os
import re
import sys

GEN = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work\qa\_gen_un_window_gui.py'
PKG = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\mods\muvlcnsub_xuerong'  # 占位，下面覆盖
PKG = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\mods\muvluvCNsub_xuerong'
ENTRY = os.path.join(PKG, 'common', 'scripted_guis', 'zz_mvlv119_un_entry.txt')

EDITS = [
    # 生成器：emblem sprite
    (GEN,
     'add(\'\\t\\tspriteType = "GFX_goal_EasyUNI_un_logo"\')',
     'add(\'\\t\\tspriteType = "GFX_mvlv119_un_entry"\')'),
    # 生成器：scripted_gui 补 context_type
    (GEN,
     "a('\\tmvlv_un_window = {')\n    a('\\t\\tparent_window_token = top_bar')",
     "a('\\tmvlv_un_window = {')\n    a('\\t\\tcontext_type = player_context')\n    a('\\t\\tparent_window_token = top_bar')"),
    # 手写文件：un_entry 补 context_type
    (ENTRY,
     "\tmvlv_un_entry = {\n\t\tparent_window_token = top_bar",
     "\tmvlv_un_entry = {\n\t\tcontext_type = player_context\n\t\tparent_window_token = top_bar"),
]


def main():
    dry = '--dry-run' in sys.argv
    for path, old, new in EDITS:
        if not os.path.exists(path):
            print('缺文件:', path)
            continue
        t = io.open(path, encoding='utf-8').read()
        if old not in t:
            print('未命中: %s\n  想找: %r' % (os.path.basename(path), old[:70]))
            continue
        print('%-24s 命中，%s' % (os.path.basename(path), 'dry-run 不写' if dry else '已改'))
        if not dry:
            io.open(path, 'w', encoding='utf-8', newline='').write(t.replace(old, new, 1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
