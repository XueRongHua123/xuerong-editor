# -*- coding: utf-8 -*-
"""通用性审计：找出代码里违反「不为单个 mod 写死」的地方。

检查项：
1. 硬编码 mod 名 / workshop id
2. 硬编码地图尺寸（5632 / 2048 / 3072 / 4096 / 13264 / 17325 等）
3. 硬编码特定 tag（H01-H20 / mvlv / BETA …）
4. 只扫 mod 层、没走 _layers_find 的路径拼接
"""
import io
import os
import re
import sys

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    os.path.join(WORK, 'focus_editor.py'),
    os.path.join(WORK, 'focus_editor_index.html'),
]

# 规则：(名称, 正则, 说明, 例外文件名/片段)
RULES = [
    ('硬编码 mod 名', re.compile(r'muvluvCN|muvluv\s*CN|京都燃烧|3004109283|2800380626|3823420258'),
     '代码里出现具体 mod 名或 workshop id', None),
    ('硬编码地图尺寸', re.compile(r'\b(5632|2048|3072|4096|13264|17325|5490|2034)\b'),
     '地图宽高/省数写死', ['MAP_ASSETS', 'w // 2', 'h // 2']),
    ('硬编码 tag', re.compile(r'\b(H0[0-9]|H1[0-9]|H20|D0[0-9]|D[1-7][0-9]|mvlv|BETA)\b'),
     '写死具体国家 tag', None),
    ('绕开 layers_find', re.compile(r'os\.path\.join\(\s*root\s*,\s*["\'](?:common|history|map|events|localisation)'),
     '只拼 mod 根目录，没走 _layers_find（原版文件读不到）', None),
]

SKIP_DIR = ('qa/', 'packaging/', 'cache/', 'tmp/', 'tools/')


def scan(path):
    hits = []
    if not os.path.exists(path):
        return hits
    rel = os.path.relpath(path, WORK).replace('\\', '/')
    lines = io.open(path, encoding='utf-8', errors='replace').read().splitlines()
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if not s or s.startswith('#') or s.startswith('//'):
            continue
        # 跳过注释尾部的说明
        for name, pat, why, excepts in RULES:
            m = pat.search(ln)
            if not m:
                continue
            if excepts and any(e in ln for e in excepts):
                continue
            hits.append((name, why, rel, i, s[:110], m.group(0)))
    return hits


def main():
    all_hits = []
    for f in FILES:
        all_hits.extend(scan(f))
    if not all_hits:
        print('没有发现硬编码')
        return 0
    # 按规则分组
    by = {}
    for h in all_hits:
        by.setdefault(h[0], []).append(h)
    print('发现 %d 处可疑硬编码，分 %d 类：\n' % (len(all_hits), len(by)))
    for name, lst in by.items():
        print('=' * 70)
        print('%s（%d 处）—— %s' % (name, len(lst), lst[0][1]))
        for _n, _w, rel, line, snippet, matched in lst[:12]:
            print('  %s:%d  [%s]' % (rel, line, matched))
            print('      %s' % snippet)
        if len(lst) > 12:
            print('  …还有 %d 处' % (len(lst) - 12))
        print()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
