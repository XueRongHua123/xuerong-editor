# -*- coding: utf-8 -*-
"""解析生成的 UN 窗口 .gui，找出位置重叠的文本元素。

重叠是截图里最明显的问题（"休会期间"压着"表决结果"、"核使用授权"压着"动用不预算"）。
本脚本只读，输出：每个元素的 name / 类型 / 坐标 / 文本框尺寸，以及 y 坐标相同的组。
"""
import collections
import io
import os
import re
import sys

PKG = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\mods\muvluvCNsub_xuerong'
GUI = os.path.join(PKG, 'interface', 'zz_mvlv119_un_window.gui')


def main():
    t = io.open(GUI, encoding='utf-8-sig', errors='replace').read()
    # 抓 name / position / 尺寸，按出现顺序
    items = []
    for m in re.finditer(r'(\w+Type)\s*=\s*\{(.*?)\n\t{2,3}\}', t, re.S):
        kind, body = m.group(1), m.group(2)
        nm = re.search(r'name\s*=\s*"([^"]+)"', body)
        pos = re.search(r'position\s*=\s*\{\s*x\s*=\s*(-?\d+)\s*y\s*=\s*(-?\d+)', body)
        size = re.search(r'size\s*=\s*\{\s*width\s*=\s*(-?\d+)\s*height\s*=\s*(-?\d+)', body)
        if not nm:
            continue
        items.append({
            'kind': kind,
            'name': nm.group(1),
            'pos': (int(pos.group(1)), int(pos.group(2))) if pos else None,
            'size': (int(size.group(1)), int(size.group(2))) if size else None,
        })

    print('共解析 %d 个带 name 的元素' % len(items))

    # 1) 同 y 同 x 的完全重叠
    by_xy = collections.defaultdict(list)
    for it in items:
        if it['pos']:
            by_xy[it['pos']].append(it)
    dup = {k: v for k, v in by_xy.items() if len(v) > 1}
    print('\n=== 坐标完全相同的元素（%d 组）===' % len(dup))
    for (x, y), group in sorted(dup.items()):
        print('  (%d,%d): %s' % (x, y, ', '.join('%s[%s]' % (g['name'], g['kind']) for g in group)))

    # 2) 同 x 区间、y 相邻但可能压线的文本
    print('\n=== 文本元素按 y 排序（x, y, 高度, name）===')
    texts = [it for it in items if it['kind'] == 'instantTextBoxType' and it['pos']]
    for it in sorted(texts, key=lambda i: (i['pos'][1], i['pos'][0])):
        h = it['size'][1] if it['size'] else '?'
        print('  y=%-5d x=%-5d h=%-4s %s' % (it['pos'][1], it['pos'][0], h, it['name']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
