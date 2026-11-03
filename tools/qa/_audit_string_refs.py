# -*- coding: utf-8 -*-
"""归档前第二道审计：字符串引用（subprocess 调用、图片路径、文档提及）。

import 审计只覆盖 `import x`，脚本被 subprocess/os.system 调用，或者图片被 .py/.md
用路径引用的，import 审计看不到。这里补上。
"""
import io
import os
import re

ROOT = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作'
WD = os.path.join(ROOT, 'work')

# 要归档的候选：work/ 根目录的 .py 与图片
cands_py = [f for f in os.listdir(WD)
            if f.endswith('.py') and f not in
            ('verify_mod.py', 'focus_editor.py', 'editor_i18n.py', 'balance.py')]
cands_img = [f for f in os.listdir(WD)
             if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]

print('候选脚本 %d 个, 候选图片 %d 个' % (len(cands_py), len(cands_img)))


def read_all(base, exts):
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if d not in ('.git', '__pycache__', 'node_modules')]
        for f in fns:
            if f.lower().endswith(exts):
                p = os.path.join(dp, f)
                try:
                    yield p, io.open(p, encoding='utf-8', errors='replace').read()
                except OSError:
                    continue


# 扫的范围：qa/、tools/、packaging/、xuerong-editor/ 的 .py、.mjs、.md、.json
SCAN = [os.path.join(WD, 'qa'), os.path.join(WD, 'tools'),
        os.path.join(WD, 'packaging'), os.path.join(ROOT, 'xuerong-editor')]
hits_py = {}
hits_img = {}
for base in SCAN:
    if not os.path.isdir(base):
        continue
    for p, t in read_all(base, ('.py', '.mjs', '.js', '.md', '.json', '.ps1')):
        rel = os.path.relpath(p, ROOT)
        if rel.startswith('xuerong-editor\\node_modules'):
            continue
        for name in cands_py:
            if name in t:
                hits_py.setdefault(name, set()).add(rel)
        for name in cands_img:
            if name in t:
                hits_img.setdefault(name, set()).add(rel)

print('\n=== 被脚本/文档/配置提到过的候选脚本（不能盲归档）===')
if hits_py:
    for k, v in sorted(hits_py.items()):
        print('  %-34s <- %s' % (k, ', '.join(sorted(v)[:3])))
else:
    print('  无')

print('\n=== 被引用过的候选图片（不能盲归档）===')
if hits_img:
    for k, v in sorted(hits_img.items()):
        print('  %-34s <- %s' % (k, ', '.join(sorted(v)[:3])))
else:
    print('  无')
