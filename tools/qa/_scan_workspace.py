# -*- coding: utf-8 -*-
"""工作区文件分布统计：按目录层级、扩展名、修改时间分组，找出可归档的东西。

只读，不移动任何文件。
"""
import os
import collections
import time

ROOT = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作'

# 这些目录是活跃资产，不参与统计（会淹没输出）
SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.dsh-ops'}
# 大体积目录单独报，不逐文件统计
WEIGHT_DIRS = {'mods', 'work', 'xuerong-editor', 'cache', 'backups'}


def walk(root, maxdepth=None):
    base_depth = root.rstrip('\\/').count(os.sep)
    for dp, dns, fns in os.walk(root):
        depth = dp.count(os.sep) - base_depth
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        if maxdepth is not None and depth >= maxdepth:
            dns[:] = []
        for f in fns:
            yield np_join(dp, f)


def np_join(dp, f):
    return os.path.join(dp, f)


def main():
    print('=== 一级目录/文件 ===')
    entries = []
    for name in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, name)
        if name in SKIP_DIRS:
            continue
        if os.path.isdir(p):
            n = sum(1 for _ in walk(p))
            entries.append((name + '/', n, True))
        else:
            entries.append((name, 1, False))
    for name, n, isdir in entries:
        print('  %-34s %5d 文件 %s' % (name, n, '[dir]' if isdir else ''))

    print('\n=== 根目录下的文件（不递归）===')
    files = [f for f in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, f))]
    print('  共 %d 个' % len(files))
    for f in sorted(files):
        print('    %-46s %8d bytes' % (f, os.path.getsize(os.path.join(ROOT, f))))

    print('\n=== work/ 根目录：按扩展名分组 ===')
    wd = os.path.join(ROOT, 'work')
    if os.path.isdir(wd):
        files = [f for f in os.listdir(wd) if os.path.isfile(os.path.join(wd, f))]
        ext = collections.Counter(os.path.splitext(f)[1].lower() or '(无)' for f in files)
        print('  共 %d 个文件' % len(files))
        for e, n in ext.most_common():
            print('    %-10s %4d' % (e, n))

    print('\n=== work/ 下的子目录 ===')
    if os.path.isdir(wd):
        for name in sorted(os.listdir(wd)):
            p = os.path.join(wd, name)
            if os.path.isdir(p):
                n = sum(1 for _ in walk(p))
                mt = time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(p)))
                print('  %-28s %5d 文件   最后改动 %s' % (name + '/', n, mt))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
