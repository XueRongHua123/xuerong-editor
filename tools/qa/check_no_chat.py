# -*- coding: utf-8 -*-
"""清理发布说明里的对话指代，改成客观描述。"""
import io
import os
import re

DIRS = ['qa', '../xuerong-editor/tools/qa']

# 把「你/我」指向对话的句子改成客观说法
RULES = [
    (r'### 关于你说的「([^」]+)」', r'### 关于「\1」'),
    (r'关于你说的「([^」]+)」', r'关于「\1」的反馈'),
    (r'你截图里是', '截图显示'),
    (r'你截图里看到的', '截图里看到的'),
    (r'你截图里', '截图里'),
    (r'你问的', ''),
    (r'你那张图的', '截图里的'),
    (r'你说的', ''),
    (r'都是你截图里遇到的', '都是截图反馈里出现的'),
    (r'我判断', '判断'),
    (r'我建议', '建议'),
    (r'你说的「放大后还是很糊」', '「放大后仍然模糊」'),
]

# 只要出现这些，就说明还带对话痕迹
BAD = re.compile(r'你说的|你截图|你问的|你那张|我们的对话|我跟你说|你反馈')


def main():
    changed = []
    still_bad = []
    for d in DIRS:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.md'):
                continue
            p = os.path.join(d, fn)
            s = io.open(p, encoding='utf-8').read()
            o = s
            for pat, rep in RULES:
                s = re.sub(pat, rep, s)
            if s != o:
                io.open(p, 'w', encoding='utf-8', newline='').write(s)
                changed.append(os.path.relpath(p))
            if BAD.search(s):
                for m in BAD.finditer(s):
                    line = s[:m.start()].count('\n') + 1
                    still_bad.append('%s:%d %s' % (os.path.relpath(p), line,
                                                   s.splitlines()[line - 1][:70]))
    print('已改写 %d 个文件' % len(changed))
    for c in changed:
        print('  ', c)
    if still_bad:
        print('\n仍有对话痕迹：')
        for b in still_bad:
            print('  ', b)
    else:
        print('\n无残留')


if __name__ == '__main__':
    main()
