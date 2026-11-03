# -*- coding: utf-8 -*-
"""给 _paths.py 增加工作副本常量（2026-10-30 目录重组）。

只追加常量，不改 HIS/OUT 的现有语义：
    HIS / OUT 仍然是游戏加载点（workshop 与 MODDIR 下那份）
    *_WORK 是日常改动的工作副本（工作区 mods/ 下）

用法：python work/qa/_patch_paths_work.py [--dry-run]
"""
import io
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

P = 'work/qa/_paths.py'

EDITS = [
    # 1) 默认值表加 WORK_MODS
    (
        "    'GAME': r'E:\\SteamLibrary\\steamapps\\common\\Hearts of Iron IV',\n}",
        "    'GAME': r'E:\\SteamLibrary\\steamapps\\common\\Hearts of Iron IV',\n"
        "    'WORK_MODS': r'D:\\大肥鱼工作区\\HOI4 MUVLUVsub mod 制作\\mods',\n}",
    ),
    # 2) 环境变量表
    (
        "    'GAME': 'MVL_GAME',\n}",
        "    'GAME': 'MVL_GAME',\n    'WORK_MODS': 'MVL_WORK_MODS',\n}",
    ),
    # 3) 解析赋值
    (
        "GAME = os.environ.get(_ENV['GAME']) or _DEF['GAME']\n",
        "GAME = os.environ.get(_ENV['GAME']) or _DEF['GAME']\n"
        "WORK_MODS = os.environ.get(_ENV['WORK_MODS']) or _DEF['WORK_MODS']\n",
    ),
    # 4) 工作副本路径（放在 OUT 定义之后，因为要用 NAME）
    (
        "OUT = os.environ.get(_ENV['OUT']) or os.path.join(MODDIR, NAME)\n",
        "OUT = os.environ.get(_ENV['OUT']) or os.path.join(MODDIR, NAME)\n"
        "\n"
        "# 工作副本：日常改动在这里做。游戏加载读的是 OUT（MODDIR 下那份）和 workshop，\n"
        "# 两者不自动同步——改完工作副本要同步回 OUT 才能进游戏，见 work/README.md。\n"
        "HIS_WORK = os.path.join(WORK_MODS, 'muvluvCN_personal')\n"
        "OUT_WORK = os.path.join(WORK_MODS, NAME)\n",
    ),
    # 5) 自检列表加上工作副本
    (
        "    for name, path in (('OUT', OUT), ('CN', CN), ('SUB', SUB),\n"
        "                       ('HIS', HIS), ('GAME', GAME)):",
        "    for name, path in (('OUT', OUT), ('CN', CN), ('SUB', SUB),\n"
        "                       ('HIS', HIS), ('GAME', GAME),\n"
        "                       ('HIS_WORK', HIS_WORK), ('OUT_WORK', OUT_WORK)):",
    ),
]


def main():
    dry = '--dry-run' in sys.argv
    s = io.open(P, encoding='utf-8', newline='').read()
    original = s
    for old, new in EDITS:
        if old not in s:
            print('[未命中] %r' % old[:50])
            return 2
        if new in s:
            print('[已存在] %r' % old[:40])
            continue
        s = s.replace(old, new, 1)
    if s == original:
        print('无需改动')
        return 0
    if dry:
        print('[dry] 将修改 %s（%d 字节 -> %d 字节）' % (P, len(original), len(s)))
        return 0
    io.open(P, 'w', encoding='utf-8', newline='').write(s)
    print('[改写] %s（%d 字节 -> %d 字节）' % (P, len(original), len(s)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
