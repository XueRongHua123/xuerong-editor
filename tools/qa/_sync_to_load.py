# -*- coding: utf-8 -*-
"""把工作副本同步到游戏加载点（只同步有差异的文件）。

工作流：
    mods/muvluvCNsub_xuerong   改动在这里做
    → 本脚本 → 游戏加载点（load_base() 解析出来的那份）

永远不覆盖 `descriptor.mod` 与外部 `.mod`：那两个由 _build_submod.py 生成，
且加载点那份可能带着启动器回写的 remote_file_id。

用法：
    python work/qa/_sync_to_load.py --dry-run
    python work/qa/_sync_to_load.py
"""
import hashlib
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _paths import OUT_WORK, load_base  # noqa: E402

SKIP = {'descriptor.mod', 'thumbnail.png'}   # 由构建脚本管，不在这里同步


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def main():
    dry = '--dry-run' in sys.argv
    dst_base = load_base()
    print('工作副本 = %s' % OUT_WORK)
    print('加载点   = %s' % dst_base)
    if not os.path.isdir(OUT_WORK):
        print('工作副本不存在，停。')
        return 1
    if not os.path.isdir(dst_base):
        print('加载点不存在，停。')
        return 1
    if os.path.normcase(OUT_WORK) == os.path.normcase(dst_base):
        print('两边是同一个目录，不需要同步。')
        return 0

    added = updated = 0
    for dp, _, fs in os.walk(OUT_WORK):
        for f in fs:
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, OUT_WORK)
            if os.path.basename(rel) in SKIP and rel.count(os.sep) == 0:
                continue
            dst = os.path.join(dst_base, rel)
            if not os.path.exists(dst):
                state = '新增'
                added += 1
            elif md5(src) != md5(dst):
                state = '更新'
                updated += 1
            else:
                continue
            print('  %s %s' % (state, rel))
            if not dry:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)

    # 加载点多出来的文件只报告，不删（可能是启动器或工坊带进来的）
    extra = []
    for dp, _, fs in os.walk(dst_base):
        for f in fs:
            dst = os.path.join(dp, f)
            rel = os.path.relpath(dst, dst_base)
            if not os.path.exists(os.path.join(OUT_WORK, rel)):
                extra.append(rel)
    if extra:
        print('\n加载点有 %d 个工作副本里没有的文件（不自动删）：' % len(extra))
        for r in extra[:20]:
            print('  ' + r)

    print('\n新增 %d, 更新 %d%s' % (added, updated, '（--dry-run 未写盘）' if dry else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
