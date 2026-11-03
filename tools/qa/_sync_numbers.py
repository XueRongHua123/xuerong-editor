# -*- coding: utf-8 -*-
"""一次性补丁：把 HANDOVER_SUBMOD.md 里受改名和加封面影响的数字/说法同步。

75 个文件（74 + thumbnail.png），2.25 MB（其中 1.44 MB 是创意工坊封面）。
"""
import io

P = 'work/HANDOVER_SUBMOD.md'
s = io.open(P, encoding='utf-8').read()

pairs = [
    # 第二章表格
    ('| **本 submod** | 未上传 | **0.84 MB** | **0** | `muvluvCN` + `muvluvCNsub` |',
     '| **本 submod**（`muvluvCNsub雪绒拓展`） | 未上传 | **2.25 MB** | **0** | `muvluvCN` + `muvluvCNsub` |'),
    # 拆分结论
    ('**结论：真正属于自己写的只有 59 个文本 + 14 个图片 = 73 个文件**\n（再加自动生成的 `descriptor.mod`，目录里共 74 个）。',
     '**结论：真正属于自己写的只有 59 个文本 + 14 个图片 = 73 个文件**\n（再加自动生成的 `descriptor.mod` 和创意工坊封面 `thumbnail.png`，目录里共 75 个）。'),
    # 安装位置树
    ('└── muvluvCNsub_xuerong\\             ← 内容（74 个文件）',
     '└── muvluvCNsub_xuerong\\             ← 内容（75 个文件）'),
    ('    ├── music/_songs.txt\n    └── credit.txt',
     '    ├── music/_songs.txt\n    ├── thumbnail.png                ← 创意工坊封面 1024×1024\n    └── credit.txt'),
    # 第五章验证表
    ('| 文件完整性 | 74 个文件，0 缺失 |',
     '| 文件完整性 | 75 个文件，0 缺失 |'),
    ('| 总体积 | 0.84 MB |',
     '| 总体积 | 2.25 MB（其中 1.44 MB 是创意工坊封面） |'),
    # 十一章复验结论
    ('文件 74 个，0.84 MB\n花括号        全部配平',
     '文件 75 个，2.25 MB\n花括号        全部配平'),
]

hit = 0
for a, b in pairs:
    if a not in s:
        print('未命中: %r' % a[:60])
        continue
    s = s.replace(a, b, 1)
    hit += 1

io.open(P, 'w', encoding='utf-8').write(s)
print('命中 %d/%d' % (hit, len(pairs)))
print('残留 「74 个」:', s.count('74 个'))
print('残留 「0.84 MB」:', s.count('0.84 MB'))
