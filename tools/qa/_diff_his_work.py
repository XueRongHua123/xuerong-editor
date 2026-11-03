# -*- coding: utf-8 -*-
"""对比个人适配版的两个位置：workshop 原件 vs 工作副本。

_build_submod.py 默认从 _paths.HIS（workshop）拷源文件；
如果工作副本被改过，从哪个源拷结果就不一样，交接前必须说清。

只比 size + md5，输出差异清单（最多列 40 条）。
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _paths import HIS, HIS_WORK  # noqa: E402


def idx(base):
    d = {}
    for dp, _, fs in os.walk(base):
        for f in fs:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, base).replace(os.sep, '/')
            try:
                d[rel] = (os.path.getsize(p), hashlib.md5(open(p, 'rb').read()).hexdigest())
            except OSError:
                pass
    return d


def main():
    print('workshop 原件 = %s' % HIS)
    print('工作副本     = %s' % HIS_WORK)
    a, b = idx(HIS), idx(HIS_WORK)
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    diff = sorted(k for k in set(a) & set(b) if a[k][1] != b[k][1])
    print('\n原件 %d 个文件, 工作副本 %d 个文件' % (len(a), len(b)))
    print('只在原件  : %d' % len(only_a))
    print('只在工作副本: %d' % len(only_b))
    print('内容不同  : %d' % len(diff))
    for label, items in (('只在原件', only_a), ('只在工作副本', only_b), ('内容不同', diff)):
        if items:
            print('\n%s（前 40 条）:' % label)
            for k in items[:40]:
                print('  ' + k)
    if not (only_a or only_b or diff):
        print('\n两边完全一致：工作副本是原件的纯拷贝')
    return 0


if __name__ == '__main__':
    sys.exit(main())
