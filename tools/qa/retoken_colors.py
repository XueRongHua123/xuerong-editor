# -*- coding: utf-8 -*-
"""v0.52：把 CSS 里遗留的雪夜硬编码色替换成设计令牌（跳过 :root 与 theme-paper 定义块）。
用法：python work/qa/retoken_colors.py [--dry]
"""
import io, os, re, sys, collections

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'focus_editor_index.html')

MAP = {
    # 最深底 -> --input
    '#0f1315': 'var(--input)', '#0f1210': 'var(--input)', '#101416': 'var(--input)',
    '#141719': 'var(--input)', '#16191b': 'var(--input)', '#171b19': 'var(--input)',
    '#181c1a': 'var(--input)', '#1a1e20': 'var(--input)', '#0f141a': 'var(--input)',
    '#171a18': 'var(--on-accent)', '#1a1d1c': 'var(--on-accent)',
    # 面板底
    '#1b2124': 'var(--panel)', '#1b2225': 'var(--panel)', '#1c2226': 'var(--panel)',
    '#1d2427': 'var(--panel)', '#1f2629': 'var(--panel)', '#202623': 'var(--panel)',
    '#252a27': 'var(--panel)', '#23261f': 'var(--panel)',
    # 次面板 / hover
    '#232a2d': 'var(--panel2)', '#232a2c': 'var(--panel2)', '#20262a': 'var(--panel2)',
    '#202a34': 'var(--panel2)', '#273033': 'var(--panel2)', '#28333a': 'var(--panel2)',
    '#2a2f2a': 'var(--panel2)', '#2a3135': 'var(--panel2)', '#2b3133': 'var(--panel2)',
    '#2b3336': 'var(--panel2)', '#2b3437': 'var(--panel2)', '#2e3a46': 'var(--panel2)',
    '#2a2c22': 'var(--panel2)', '#1e2426': 'var(--panel2)',
    '#2a3133': 'var(--panel2)', '#284057': 'var(--panel2)',
    # 边框
    '#2b3234': 'var(--line)', '#2f3a3c': 'var(--line)', '#33414f': 'var(--line)',
    '#3a4346': 'var(--line)', '#35403f': 'var(--line)', '#3a3524': 'var(--line)',
    '#556165': 'var(--line2)', '#4f6b60': 'var(--line2)', '#566a6f': 'var(--line2)',
    '#4a5659': 'var(--line2)',
    # 正文
    '#cfc7b6': 'var(--text)', '#c9c3b7': 'var(--text)', '#d9d3c7': 'var(--text)',
    '#e7d9b8': 'var(--text)', '#e8e2d4': 'var(--text)', '#e6dfd0': 'var(--text)',
    '#f0e6cf': 'var(--text)', '#bdb6a8': 'var(--text)', '#d6cfc2': 'var(--text)',
    '#e2dccd': 'var(--text)', '#f0e8d6': 'var(--text)', '#dbe7f2': 'var(--text)',
    '#a9c4da': 'var(--text)', '#cfe0d8': 'var(--text)', '#a9b3ae': 'var(--text)',
    '#f1ecd9': 'var(--text)',
    # 次要文字
    '#9a9384': 'var(--muted)', '#8b8378': 'var(--muted)', '#a3b0ae': 'var(--muted)',
    '#9fb0c0': 'var(--muted)', '#6f8a90': 'var(--muted)', '#7f95a8': 'var(--muted)',
    '#7d93a6': 'var(--muted)', '#938c7e': 'var(--muted)',
    # 金色强调
    '#c2ae82': 'var(--accent)', '#d8b878': 'var(--accent)', '#ffd479': 'var(--accent)',
    '#e0c894': 'var(--accent)', '#f0d9a6': 'var(--accent)', '#8a7a45': 'var(--accent)',
    '#5a4f2e': 'var(--accent)', '#e0a36a': 'var(--accent)', '#d99a5b': 'var(--accent)',
    # 绿系
    '#8fa06a': 'var(--accent-2)', '#6f9770': 'var(--accent-2)', '#9fbfb4': 'var(--accent-2)',
    '#55684a': 'var(--accent-2)', '#647a55': 'var(--accent-2)',
    # 语义色
    '#ff9a9a': 'var(--warn)', '#8fd18f': 'var(--ok)',
}

s = io.open(P, encoding='utf-8').read()
a, b = s.index('<style>'), s.index('</style>')
css = s[a:b]
prot = [(m.start(), m.end()) for m in re.finditer(r':root\{[^}]*\}|body\.theme-paper\{[^}]*\}', css)]

def protected(i):
    return any(x <= i < y for x, y in prot)

hits = collections.Counter()
kept = collections.Counter()
parts = []
last = 0
for m in re.finditer(r'#[0-9a-fA-F]{6}\b', css):
    hexv = m.group(0).lower()
    if protected(m.start()):
        continue
    if hexv in MAP:
        parts.append(css[last:m.start()])
        parts.append(MAP[hexv])
        last = m.end()
        hits[hexv] += 1
    else:
        kept[hexv] += 1
parts.append(css[last:])
newcss = ''.join(parts)
new = s[:a] + newcss + s[b:]

print('替换', sum(hits.values()), '处 /', len(hits), '种颜色')
for k, v in hits.most_common(12):
    print('  %s -> %-16s %d' % (k, MAP[k], v))
print('未映射保留', sum(kept.values()), '处:', ', '.join('%s(%d)' % (k, v) for k, v in kept.most_common()))

if '--dry' not in sys.argv:
    io.open(P, 'w', encoding='utf-8', newline='').write(new)
    io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'qa', 'reports', 'retoken.log'),
            'w', encoding='utf-8').write(str(hits) + '\n' + str(kept))
    print('written', P, 'css chars', len(css), '->', len(newcss))
