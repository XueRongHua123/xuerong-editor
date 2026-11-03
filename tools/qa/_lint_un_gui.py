# -*- coding: utf-8 -*-
"""联合国界面的契约检查：gui 元素名 / 脚本界面键 / 本地化键 三方对齐。

查五件事：
  1. scripted_gui 的 dynamic_lists 网格名，必须在 gui 里存在同名 gridboxtype
  2. scripted_gui 里 xxx_click 效果，必须对应 gui 里叫 xxx 的按钮
  3. gui 里的 text / pdx_tooltip 键，必须能在本地化或脚本文本里找到
  4. gui 里不许出现已知非法字段（文本框 color、按钮 size）
  5. gui 引用的 sprite 必须有定义

用法：python work/qa/_lint_un_gui.py [--base 包目录]
退出码非 0 即有失败项。
"""

import collections
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEFAULT_BASE = os.path.join(ROOT, 'mods', 'muvluvCNsub_xuerong')

GUI_DIR = 'interface'
SG_DIR = 'common/scripted_guis'
LOC_DIR = 'localisation'
SLOC_DIR = 'common/scripted_localisation'


def read(path):
    return io.open(path, encoding='utf-8-sig', errors='replace').read()


def blocks(text, header):
    """返回 header = { ... } 的 (起点, 终点) 列表。"""
    out = []
    for m in re.finditer(re.escape(header) + r'\s*=\s*\{', text):
        i = text.index('{', m.start())
        depth, j, instr = 0, i, False
        while j < len(text):
            ch = text[j]
            if ch == '"':
                instr = not instr
            elif not instr:
                if ch == '#':
                    nl = text.find('\n', j)
                    j = len(text) if nl < 0 else nl
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        out.append((i, j))
                        break
            j += 1
    return out


def inner(text, span):
    return text[span[0]:span[1] + 1]


def loc_keys(base):
    keys = set()
    for dp, _, fs in os.walk(os.path.join(base, LOC_DIR)):
        for f in fs:
            if not f.endswith('.yml'):
                continue
            for ln in read(os.path.join(dp, f)).split('\n'):
                m = re.match(r'\s*([A-Za-z0-9_.\-]+):\d*\s+"', ln)
                if m:
                    keys.add(m.group(1))
    return keys


def scripted_loc_names(base):
    names = set()
    d = os.path.join(base, SLOC_DIR)
    if os.path.isdir(d):
        for f in os.listdir(d):
            for m in re.finditer(r'name\s*=\s*([A-Za-z0-9_]+)', read(os.path.join(d, f))):
                names.add(m.group(1))
    return names


def main():
    base = DEFAULT_BASE
    if '--base' in sys.argv:
        base = sys.argv[sys.argv.index('--base') + 1]

    gui_files = [f for f in os.listdir(os.path.join(base, GUI_DIR))
                 if f.startswith('zz_mvlv119_un') and f.endswith('.gui')]
    gui_text = '\n'.join(read(os.path.join(base, GUI_DIR, f)) for f in gui_files)
    sg_files = [f for f in os.listdir(os.path.join(base, SG_DIR))
                if f.startswith('zz_mvlv119_un')]
    sg_text = '\n'.join(read(os.path.join(base, SG_DIR, f)) for f in sg_files)

    names = set(re.findall(r'name\s*=\s*"([^"]+)"', gui_text))
    buttons = set()
    for span in blocks(gui_text, 'buttonType'):
        m = re.search(r'name\s*=\s*"([^"]+)"', inner(gui_text, span))
        if m:
            buttons.add(m.group(1))
    grids = set()
    for span in blocks(gui_text, 'gridboxtype'):
        m = re.search(r'name\s*=\s*"([^"]+)"', inner(gui_text, span))
        if m:
            grids.add(m.group(1))

    problems = []

    # 1) 动态列表网格
    for span in blocks(sg_text, 'dynamic_lists'):
        body = inner(sg_text, span)
        for m in re.finditer(r'([A-Za-z0-9_]+)\s*=\s*\{', body):
            grid = m.group(1)
            if grid not in grids:
                problems.append('动态列表网格 %s 在 gui 里没有同名 gridboxtype' % grid)

    # 2) 按钮回调
    for m in re.finditer(r'([A-Za-z0-9_]+)_click\s*=\s*\{', sg_text):
        btn = m.group(1)
        if btn not in buttons:
            problems.append('脚本界面效果 %s_click 找不到名为 %s 的按钮' % (btn, btn))

    # 3) 文本键
    keys = loc_keys(base) | scripted_loc_names(base)
    for m in re.finditer(r'(?:text|pdx_tooltip)\s*=\s*"([^"]+)"', gui_text):
        k = m.group(1)
        if k.startswith('GFX_') or k.isdigit():
            continue
        if k not in keys:
            problems.append('gui 引用的文本键 %s 在本地化/脚本文本里都不存在' % k)

    # 4) 非法字段
    if re.search(r'(?m)^\s*color\s*=\s*\{', gui_text):
        problems.append('gui 里出现 color = {（文本框不支持，改用 §颜色码）')
    for span in blocks(gui_text, 'buttonType'):
        if re.search(r'(?m)^\s*size\s*=\s*\{', inner(gui_text, span)):
            problems.append('buttonType 里出现 size（按钮尺寸由素材决定，写了会解析失败）')
    if re.search(r'check_variable\s*=\s*\{[^}]*>=', sg_text):
        problems.append('scripted_gui 里 check_variable 用了 >=（只支持 > < =，用 compare 长写法）')
    if re.search(r'(?m)^\s*\w+_click_enabled\s*=\s*\{', sg_text):
        problems.append('scripted_gui 里出现 xxx_click_enabled 触发器（引擎不认，会拖垮 effects）')

    # 5) sprite 定义：本包优先，其次在基座与原版里找
    gfx_text = '\n'.join(read(os.path.join(base, GUI_DIR, f))
                          for f in os.listdir(os.path.join(base, GUI_DIR)) if f.endswith('.gfx'))
    defined = set(re.findall(r'name\s*=\s*"?([A-Za-z0-9_]+)"?', gfx_text))
    extra_roots = [
        r'E:/SteamLibrary/steamapps/common/Hearts of Iron IV/interface',
        r'E:/SteamLibrary/steamapps/workshop/content/394360/2800380626/interface',
        r'E:/SteamLibrary/steamapps/workshop/content/394360/2989050816/interface',
    ]
    outside = set()
    for d in extra_roots:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith('.gfx'):
                outside |= set(re.findall(r'name\s*=\s*"?([A-Za-z0-9_]+)"?',
                                          read(os.path.join(d, f))))
    for m in re.finditer(r'spriteType\s*=\s*"([^"]+)"', gui_text):
        s = m.group(1)
        if s not in defined and s not in outside:
            problems.append('gui 引用的 sprite %s 在本包与三个基座根里都没有定义' % s)

    # 6) 显隐触发器：目标元素必须存在（页签切换的契约）
    vis_triggers = [m.group(1) for m in re.finditer(
        r'(?m)^\s*([A-Za-z0-9_]+)_visible\s*=\s*\{', sg_text)]
    missing_vis = [v for v in vis_triggers if v not in names]
    if missing_vis:
        problems.append('显隐触发器目标不存在于 gui：%s' % ', '.join(missing_vis[:8]))

    # 7) 元素名不得重复（重名会导致静默顶替）
    dup = [k for k, c in collections.Counter(names).items() if c > 1]
    if dup:
        problems.append('gui 元素重名：%s' % ', '.join(dup[:8]))

    print('gui 文件 %d，脚本界面文件 %d' % (len(gui_files), len(sg_files)))
    print('按钮 %d，网格 %d，显隐触发器 %d，本地化键 %d'
          % (len(buttons), len(grids), len(vis_triggers), len(keys)))

    if problems:
        print('\n=== 发现 %d 个问题 ===' % len(problems))
        for p in problems:
            print('  [!]', p)
        print('\n结论: FAIL')
        return 1

    print('\n结论: PASS（网格/按钮/文本/sprite 全部对齐）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
