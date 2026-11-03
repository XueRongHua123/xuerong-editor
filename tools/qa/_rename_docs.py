# -*- coding: utf-8 -*-
"""一次性补丁：把文档里的旧 mod 名换成新的。

旧：muvluvCN_plus_sub / "muvluvCN+sub 扩展"
新：muvluvCNsub_xuerong / "muvluvCNsub雪绒拓展"
"""
import io
import os
import re

FILES = [
    'work/HANDOVER_SUBMOD.md',
    'work/ANALYSIS_SUBMOD_SPLIT.md',
    'work/SESSION_STATE.md',
    'work/README.md',
]

OLD_DIR = 'muvluvCN_plus_sub'
NEW_DIR = 'muvluvCNsub_xuerong'
OLD_NAME = 'muvluvCN+sub 扩展'
NEW_NAME = 'muvluvCNsub雪绒拓展'

for path in FILES:
    if not os.path.exists(path):
        print('跳过（不存在）:', path)
        continue
    s = io.open(path, encoding='utf-8').read()
    n_dir = s.count(OLD_DIR)
    n_name = s.count(OLD_NAME)
    s = s.replace(OLD_DIR, NEW_DIR).replace(OLD_NAME, NEW_NAME)
    io.open(path, 'w', encoding='utf-8').write(s)
    print('%-34s 目录名 %d 处, 显示名 %d 处' % (os.path.basename(path), n_dir, n_name))

print()
print('=== 复查残留 ===')
for path in FILES:
    if not os.path.exists(path):
        continue
    s = io.open(path, encoding='utf-8').read()
    left = s.count(OLD_DIR) + s.count(OLD_NAME)
    print('%-34s %s' % (os.path.basename(path), '残留 %d' % left if left else '干净'))
