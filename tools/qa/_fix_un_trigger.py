# -*- coding: utf-8 -*-
"""修 UN 规则表里的非法 trigger：is_at_war -> has_war

依据：
  * HOI4 documentation/triggers_documentation.md 里 0 次 is_at_war
  * 原版脚本 544 次 has_war=，0 次 is_at_war=
  * 游戏 logs/error.log: Unknown trigger-type: is_at_war, near line: 89

后果：10 个 allow 恒为 false，对应决议永远不出现在会议议程里。

改前备份到 work/_archive/patches_un/。
"""
import io
import os
import shutil
import sys

ROOT = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作'
REL = 'common/scripted_triggers/zz_mvlv119_un_rules.txt'
TARGETS = [
    os.path.join(ROOT, 'mods', 'muvluvCNsub_xuerong'),
    os.path.join(r'C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV\mod', 'muvluvCNsub_xuerong'),
]
BAK = os.path.join(ROOT, 'work', '_archive', 'patches_un')


def main():
    dry = '--dry-run' in sys.argv
    os.makedirs(BAK, exist_ok=True)
    for base in TARGETS:
        path = os.path.join(base, REL.replace('/', os.sep))
        if not os.path.exists(path):
            print('跳过（不存在）:', path)
            continue
        t = io.open(path, encoding='utf-8-sig').read()
        n = t.count('is_at_war')
        print('\n%s\n  命中 is_at_war %d 处' % (path, n))
        if n == 0:
            continue
        if dry:
            for line in t.split('\n'):
                if 'is_at_war' in line:
                    print('   >', line.strip())
            continue
        tag = 'workcopy' if 'mods' in base else 'loadpoint'
        bak = os.path.join(BAK, 'zz_mvlv119_un_rules.%s.bak' % tag)
        shutil.copy2(path, bak)
        print('  备份 ->', bak)
        t2 = t.replace('is_at_war = yes', 'has_war = yes')
        io.open(path, 'w', encoding='utf-8', newline='').write(t2)
        print('  已替换 %d 处' % n)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
