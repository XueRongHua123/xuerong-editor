# -*- coding: utf-8 -*-
"""基座更新监测：给 CHG 的 23 个覆盖文件记一份基座 md5 基线。

背景：本 submod 覆盖了基座（muvluvCN + muvluvCNsub）的 23 个文件（整文件替换）。
基座一更新，这些文件的上游版本可能就变了，而本 submod 的副本会盖住上游新版，
导致内容冲突。本脚本在基座更新后跑一遍，输出「上游改了哪些、我这份还差什么」。

用法：
    python work/qa/_monitor_base.py --save    # 把当前基座这 23 个文件的 md5 存为基线
    python work/qa/_monitor_base.py           # 对比当前基座 vs 基线，输出改动清单

基线文件：work/qa/base_md5.json（开发期文件，不进包）
"""
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _paths import CHG, CN, SUB, check_roots  # noqa: E402

BASELINE = os.path.join(HERE, 'base_md5.json')


def md5_of(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def find_in_base(rel):
    """在 SUB 优先、CN 兜底里找 CHG 文件。返回 (路径, md5) 或 (None, None)。"""
    for root in (SUB, CN):
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            return p, md5_of(p)
    return None, None


def scan():
    out = {}
    for rel in CHG:
        _, h = find_in_base(rel)
        out[rel] = h          # None 表示基座里找不到
    return out


def main():
    if not check_roots():
        return 1

    if '--save' in sys.argv:
        data = scan()
        io.open(BASELINE, 'w', encoding='utf-8').write(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        print('基线已保存 ->', BASELINE)
        print('共 %d 个覆盖文件，%d 个在基座里找到' % (
            len(data), sum(1 for v in data.values() if v)))
        missing = [k for k, v in data.items() if v is None]
        if missing:
            print('基座里找不到（注意）：')
            for k in missing:
                print('  -', k)
        return 0

    if not os.path.exists(BASELINE):
        print('还没有基线，先跑 --save 记一份')
        return 1

    base = json.load(io.open(BASELINE, encoding='utf-8'))
    now = scan()

    changed, added, removed = [], [], []
    for rel, h in now.items():
        old = base.get(rel)
        if old is None and h is not None:
            added.append(rel)
        elif old is not None and h is None:
            removed.append(rel)
        elif old != h:
            changed.append(rel)

    print('覆盖文件 %d 个，上游改动 %d，新增 %d，移除 %d' % (
        len(now), len(changed), len(added), len(removed)))
    for rel in changed:
        print('  [改]', rel)
    for rel in added:
        print('  [增]', rel)
    for rel in removed:
        print('  [删]', rel)
    if not (changed or added or removed):
        print('  上游无改动，本 submod 覆盖的 23 个文件仍然安全。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
