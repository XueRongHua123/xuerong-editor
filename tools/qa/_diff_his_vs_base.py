# -*- coding: utf-8 -*-
"""全量比对：适配版 vs (CN+CNsub) 基座，找出所有「真正自己写的」文件。

与早期分析的差别：早期只扫 *.txt/*.yml/*.gfx/*.gui/*.csv 五种扩展名，
漏掉了 .asset（music.asset 就在这里，导致开局音乐失效）、.mesh/.anim/.fnt/.shader 等。
本脚本不限定扩展名，全部扫。

判定：基座没这个文件 = NEW；有但内容不同 = CHG（size 不同直接判不同，相同才算 md5）

用法：
    python work/qa/_diff_his_vs_base.py            # 全量差异清单
    python work/qa/_diff_his_vs_base.py --missing   # 只列「差异文件里还没进本包的」
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _paths import CN, HIS, OUT, SUB, check_roots, p  # noqa: E402

# 纯资源目录：这些是替换原版素材用的，不随包（随包会让 submod 变成几百 MB）
RES_EXT = {'.dds', '.png', '.tga', '.jpg', '.jpeg', '.jfif', '.bmp',
           '.ogg', '.wav', '.mesh', '.anim', '.dae', '.fnt', '.shader'}


def md5_of(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def index(base):
    d = {}
    for dp, _, fs in os.walk(base):
        for f in fs:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, base).replace('\\', '/')
            try:
                d[rel] = os.path.getsize(full)
            except OSError:
                pass
    return d


def main():
    only_missing = '--missing' in sys.argv
    if not check_roots():
        return 1

    print('建基座索引（CN + CNsub）…')
    base = index(CN)
    for k, v in index(SUB).items():
        base[k] = v          # CNsub 覆盖同名
    print('  基座 %d 个文件' % len(base))

    print('扫适配版 …')
    his = index(HIS)
    print('  适配版 %d 个文件' % len(his))

    new, chg, res_new, res_chg = [], [], [], []
    for rel, size in sorted(his.items()):
        ext = os.path.splitext(rel)[1].lower()
        is_res = ext in RES_EXT
        if rel not in base:
            (res_new if is_res else new).append(rel)
            continue
        if base[rel] == size:
            a = p(HIS, rel)
            b1, b2 = p(CN, rel), p(SUB, rel)
            same = False
            for b in (b2, b1):
                if os.path.exists(b) and os.path.getsize(b) == size \
                        and md5_of(b) == md5_of(a):
                    same = True
                    break
            if same:
                continue
        (res_chg if is_res else chg).append(rel)

    print('\n=== 非资源文件（真正自己写的逻辑/配置）===')
    print('  新增 %d 个，改动 %d 个' % (len(new), len(chg)))

    def inpack(rel):
        return os.path.exists(p(OUT, rel))

    groups = [('新增', new), ('改动', chg)]
    for name, items in groups:
        print('\n--- %s %d 个 ---' % (name, len(items)))
        miss = [r for r in items if not inpack(r)]
        for r in items:
            mark = '  ' if inpack(r) else '缺'
            if only_missing and inpack(r):
                continue
            print('  [%s] %s' % (mark, r))
        print('  小计：包里已有 %d，**还没进包 %d**' % (len(items) - len(miss), len(miss)))

    print('\n=== 资源文件（图片/音频/模型，一般替换原版用，不随包）===')
    print('  新增 %d 个，改动 %d 个' % (len(res_new), len(res_chg)))
    for name, items in (('资源新增', res_new), ('资源改动', res_chg)):
        if not items:
            continue
        print('  %s 前 20 个：' % name)
        for r in items[:20]:
            print('    %s' % r)

    miss_all = [r for r in new + chg if not inpack(r)]
    print('\n=== 结论 ===')
    if miss_all:
        print('  %d 个非资源文件还没进本包：' % len(miss_all))
        for r in miss_all:
            print('    %s' % r)
    else:
        print('  非资源文件已全部进包')
    return 0


if __name__ == '__main__':
    sys.exit(main())
