# -*- coding: utf-8 -*-
"""归档前安全审计：被引用的文件不能动。

扫 work/ 与 xuerong-editor/ 全部 .py 的 import 语句，找出引用了 work/ 根目录模块的地方。
同时列出：谁 import 了谁、哪些文件被别的脚本当模块用。
"""
import io
import os
import re
import collections

ROOT = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作'
WD = os.path.join(ROOT, 'work')

IMPORT_RE = re.compile(
    r'^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))', re.M)


def py_files(base):
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if d not in ('.git', '__pycache__', 'node_modules')]
        for f in fns:
            if f.endswith('.py'):
                yield os.path.join(dp, f)


def main():
    top_mods = {os.path.splitext(f)[0]
                for f in os.listdir(WD) if f.endswith('.py')}
    print('work/ 根目录共 %d 个可 import 的模块' % len(top_mods))

    used = collections.defaultdict(list)     # 模块名 -> 引用它的文件
    for path in list(py_files(WD)) + list(py_files(os.path.join(ROOT, 'xuerong-editor'))):
        rel = os.path.relpath(path, ROOT)
        try:
            t = io.open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for m in IMPORT_RE.finditer(t):
            mod = (m.group(1) or m.group(2)).split('.')[0]
            if mod in top_mods and os.path.dirname(path) != WD:
                used[mod].append(rel)

    if used:
        print('\n=== 被其他目录 import 的根模块（不能移走）===')
        for mod, refs in sorted(used.items()):
            print('  %-24s <- %s' % (mod, ', '.join(sorted(set(refs))[:4])))
    else:
        print('\n没人 import 根目录的模块，全部可归档')

    # 反向：根目录脚本之间互相 import
    inner = collections.defaultdict(list)
    for f in os.listdir(WD):
        if not f.endswith('.py'):
            continue
        t = io.open(os.path.join(WD, f), encoding='utf-8', errors='replace').read()
        for m in IMPORT_RE.finditer(t):
            mod = (m.group(1) or m.group(2)).split('.')[0]
            if mod in top_mods and mod != os.path.splitext(f)[0]:
                inner[mod].append(f)
    if inner:
        print('\n=== 根目录脚本之间互相 import ===')
        for mod, refs in sorted(inner.items()):
            print('  %-24s <- %s' % (mod, ', '.join(sorted(set(refs))[:5])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
