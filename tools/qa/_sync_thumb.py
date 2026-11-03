# -*- coding: utf-8 -*-
"""封面改版后的数字同步：2.25 MB/1024×1024 → 1.04 MB/512×512。

封面从「AI 底图 + 大标题」换成「muvluvCNsub 原封面 + sub 右边白字」，
体积从 1.44 MB 降到 206 KB，尺寸退回基座的 512×512。
"""
import io

FILES = ['work/HANDOVER_SUBMOD.md', 'work/UPLOAD_WORKSHOP.md', 'work/SESSION_STATE.md']

PAIRS = [
    ('| 封面 | `thumbnail.png`，1024×1024 |',
     '| 封面 | `thumbnail.png`，512×512（muvluvCNsub 原封面 + `sub` 右边加白字） |'),
    ('**2.25 MB**', '**1.04 MB**'),
    ('| 总体积 | 2.25 MB（其中 1.44 MB 是创意工坊封面） |',
     '| 总体积 | 1.04 MB（其中 206 KB 是创意工坊封面） |'),
    ('文件 75 个，2.25 MB', '文件 75 个，1.04 MB'),
    ('| 4 | 新增 `thumbnail.png`（1024×1024，1.44 MB） | 体积 0.84 → **2.25 MB** | `work/qa/_make_thumbnail.py` 生成 |',
     '| 4 | 新增 `thumbnail.png`（512×512，206 KB） | 体积 0.84 → **1.04 MB** | `work/qa/_make_thumbnail.py` 生成：基座原封面 + `sub` 右边白字「雪绒拓展」 |'),
    ('| `thumbnail.png` | 正方形，≥256×256 | 1024×1024，1.44 MB |',
     '| `thumbnail.png` | 正方形，≥256×256 | 512×512，206 KB |'),
    ('| 1024×1024，1.44 MB',
     '| 512×512，206 KB'),
    ('75 个文件 / 2.25 MB（封面占 1.44 MB）',
     '75 个文件 / 1.04 MB（封面占 206 KB）'),
]

for path in FILES:
    s = io.open(path, encoding='utf-8').read()
    n = 0
    for a, b in PAIRS:
        if a in s:
            s = s.replace(a, b)
            n += 1
    io.open(path, 'w', encoding='utf-8').write(s)
    print('%-24s 命中 %d 组' % (path.split('/')[-1], n))

print()
for path in FILES:
    s = io.open(path, encoding='utf-8').read()
    left = [t for t in ('2.25 MB', '1.44 MB', '1024×1024', '1024x1024') if t in s]
    print('%-24s %s' % (path.split('/')[-1], '残留 ' + str(left) if left else '干净'))
