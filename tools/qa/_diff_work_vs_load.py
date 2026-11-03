# -*- coding: utf-8 -*-
"""对比 submod 工作副本与游戏加载点是否一致。

两处路径：
  工作副本  mods/muvluvCNsub_xuerong        （维护在这里）
  加载点    Documents/.../mod/muvluvCNsub_xuerong （游戏读这里，上传也从这里）

结论用途：交接时说明「以哪份为准」，以及同步了多少差异。
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _paths import OUT, OUT_WORK, load_base  # noqa: E402


def idx(base):
    d = {}
    for dp, _, fs in os.walk(base):
        for f in fs:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, base).replace(os.sep, '/')
            d[rel] = hashlib.md5(open(p, 'rb').read()).hexdigest()
    return d


def main():
    target = load_base()
    print('工作副本 = %s' % OUT_WORK)
    print('加载点   = %s%s' % (target, '' if target != OUT else '（本地 .mod，非工坊）'))
    a, b = idx(OUT_WORK), idx(target)
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    print('\n工作副本 %d 个文件, 加载点 %d 个文件' % (len(a), len(b)))
    print('只在工作副本: %s' % (only_a or '无'))
    print('只在加载点  : %s' % (only_b or '无'))
    print('内容不同    : %s' % (diff or '无'))
    if not (only_a or only_b or diff):
        print('\n两边完全一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
