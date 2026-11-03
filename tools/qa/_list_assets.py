# -*- coding: utf-8 -*-
"""列出各方 .asset 文件，用来判断 HOI4 是否按「文件名」还是「扩展名」扫描。

结论用途：如果同一个目录下存在多个不同名的 .asset（不是只有 music.asset），
说明扫描规则是扩展名，可以给本 submod 新建独立 .asset 而不覆盖基座。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _paths import CN, GAME, HIS, OUT, SUB  # noqa: E402


def main():
    for name, base in (('HIS 适配版', HIS), ('CN', CN), ('SUB', SUB),
                       ('OUT 本包', OUT), ('GAME 原版', GAME)):
        hits = []
        for dp, _, fs in os.walk(base):
            for f in fs:
                if f.lower().endswith('.asset'):
                    hits.append(os.path.relpath(os.path.join(dp, f), base)
                                .replace('\\', '/'))
        print('=== %s: %d 个 .asset ===' % (name, len(hits)))
        # 按目录聚合，看同一目录下有没有多个不同名
        bydir = {}
        for h in hits:
            bydir.setdefault(os.path.dirname(h), []).append(os.path.basename(h))
        for d in sorted(bydir):
            names = sorted(set(bydir[d]))
            if len(names) > 1:
                print('  [多文件] %-40s %s' % (d or '(根)', ', '.join(names)))
            else:
                print('  [单文件] %-40s %s' % (d or '(根)', names[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
