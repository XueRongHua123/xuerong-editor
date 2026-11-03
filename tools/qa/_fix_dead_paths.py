# -*- coding: utf-8 -*-
"""把 qa 脚本里指向已删除的 work/muvluvCN_1.19 的路径改到工作副本。

2026-10-30：work/muvluvCN_1.19 已删除，模组改为在 work 之外的 mods/ 目录维护。
本脚本只改默认值/源路径，不改脚本逻辑。

用法：python work/qa/_fix_dead_paths.py [--dry-run]
"""
import io
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

OLD = r'muvluvCN_1.19'
NEW = r'mods\muvluvCN_personal'
OLD_JS = OLD.replace('\\', '\\\\')
NEW_JS = NEW.replace('\\', '\\\\')

# (文件, 是否 JS 双反斜杠写法)
TARGETS = [
    ('work/qa/probe_country_reload.mjs', True),
    ('work/qa/spike_map.py', False),
    ('work/qa/spike_map2.py', False),
    ('work/qa/test_v094_paint.py', False),
    ('work/qa/test_v095_e2e.py', False),
]


def main():
    dry = '--dry-run' in sys.argv
    total = 0
    for rel, is_js in TARGETS:
        try:
            s = io.open(rel, encoding='utf-8', errors='replace', newline='').read()
        except OSError as e:
            print('[跳过] %s: %s' % (rel, e))
            continue
        old, new = (OLD_JS, NEW_JS) if is_js else (OLD, NEW)
        n = s.count(old)
        if not n:
            print('[无命中] %s' % rel)
            continue
        out = s.replace(old, new)
        if dry:
            print('[dry] %s  替换 %d 处' % (rel, n))
        else:
            io.open(rel, 'w', encoding='utf-8', newline='').write(out)
            print('[改写] %s  替换 %d 处' % (rel, n))
        total += n
    print('合计 %d 处' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
