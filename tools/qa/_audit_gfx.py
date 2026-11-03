# -*- coding: utf-8 -*-
"""gfx 图片全量审计：submod 的 gfx 定义引用，逐个查五个根是否存在。

五个根：OUT(本 submod) / CN / SUB / HIS(个人适配版) / GAME(原版)
同时列出「适配版 gfx 目录里有、submod 里没有」的文件，用来发现拆分漏拷。

用法：
    python work/qa/_audit_gfx.py            # 报告
    python work/qa/_audit_gfx.py --copy     # 把漏拷且引用到的图片补进 submod
"""
import hashlib
import io
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _paths import OUT, CN, SUB, HIS, GAME, p, walk_files  # noqa: E402


def gfx_refs(base):
    """扫 base 下 .gfx/.gui 的 texturefile 引用。"""
    refs = set()
    for dp, _, fs in os.walk(base):
        for f in fs:
            if not f.endswith(('.gfx', '.gui')):
                continue
            t = io.open(os.path.join(dp, f), encoding='utf-8-sig',
                        errors='replace').read()
            for m in re.finditer(r'texturefile\s*=\s*"([^"]+)"', t, re.I):
                refs.add(m.group(1).replace('\\', '/'))
    return refs


def md5_of(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def list_gfx(base):
    d = {}
    g = os.path.join(base, 'gfx')
    if not os.path.isdir(g):
        return d
    for dp, _, fs in os.walk(g):
        for f in fs:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, base).replace('\\', '/')
            d[rel] = md5_of(full)
    return d


def main():
    copy = '--copy' in sys.argv
    roots = [('OUT', OUT), ('CN', CN), ('SUB', SUB), ('HIS', HIS), ('GAME', GAME)]

    print('=== A. gfx 定义引用 x 五根存在性 ===')
    refs = gfx_refs(OUT)
    print('  定义引用 %d 个' % len(refs))
    notpacked, nowhere = [], []
    for r in sorted(refs):
        where = [k for k, v in roots if os.path.exists(p(v, r))]
        if 'OUT' in where:
            continue
        if where:
            notpacked.append((r, where))
        else:
            nowhere.append(r)
    for r, where in notpacked:
        print('  未随包但上层有: %-58s %s' % (r, '+'.join(where)))
    for r in nowhere:
        print('  五根都没有:     %s' % r)
    print('  小计: 未随包 %d, 真缺 %d' % (len(notpacked), len(nowhere)))

    print('\n=== B. 适配版 gfx vs submod gfx（只列被引用过的）===')
    h, o = list_gfx(HIS), list_gfx(OUT)
    only_his = sorted(k for k in h if k not in o)
    refset = set(refs)
    need = [k for k in only_his
            if k in refset
            and not os.path.exists(p(CN, k))
            and not os.path.exists(p(SUB, k))
            and not os.path.exists(p(GAME, k))]
    keep_base = [k for k in only_his
                 if k in refset
                 and (os.path.exists(p(CN, k)) or os.path.exists(p(SUB, k))
                      or os.path.exists(p(GAME, k)))]
    print('  适配版 %d 个, submod %d 个, 适配版独有 %d 个'
          % (len(h), len(o), len(only_his)))
    print('  被引用且只有适配版有 → 必须随包: %d 个' % len(need))
    for k in need:
        print('    %-58s %s' % (k, h[k][:8]))
    if keep_base:
        print('  被引用但基座/原版也有 → 不随包（随包会锁死上游更新）: %d 个'
              % len(keep_base))
        for k in keep_base:
            where = [n for n, v in (('CN', CN), ('SUB', SUB), ('GAME', GAME))
                     if os.path.exists(p(v, k))]
            print('    %-58s %s' % (k, '+'.join(where)))

    print('\n=== C. submod 里有、适配版没有（自己新增的图）===')
    for k in sorted(k for k in o if k not in h):
        print('    %-58s %s' % (k, o[k][:8]))

    if copy and need:
        print('\n=== 补拷 ===')
        for k in need:
            src = p(HIS, k)
            dst = p(OUT, k)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            print('  + %s (%d bytes)' % (k, os.path.getsize(dst)))
    elif need:
        print('\n（加 --copy 补拷上面标了“必须补”的文件）')


if __name__ == '__main__':
    main()
