# -*- coding: utf-8 -*-
"""生成工作副本的 .mod 描述文件（path 指向工作区 mods/ 下的副本）。

用法：python work/qa/_make_work_mods.py
幂等：重复跑只是重写 path 行。

来源模板：
    muvluvCN_personal        <- Paradox mod/ugc_3823420258.mod    （工坊 3823420258）
    muvluvCNsub_xuerong      <- Paradox mod/muvluvCNsub_xuerong.mod（工坊 3823420258 的 submod）
"""
import io
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

MOD = r'C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV\mod'
WORK = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\mods'

# (源 .mod, 工作副本目录名)
PAIRS = [
    ('ugc_3823420258.mod', 'muvluvCN_personal'),
    ('muvluvCNsub_xuerong.mod', 'muvluvCNsub_xuerong'),
]


def rewrite(src, dst, new_path):
    s = io.open(src, encoding='utf-8', errors='replace', newline='').read()
    out = []
    for line in s.splitlines():
        if line.strip().startswith('path='):
            out.append('path="%s"' % new_path)
        else:
            out.append(line)
    if not any(l.strip().startswith('path=') for l in out):
        out.append('path="%s"' % new_path)
    io.open(dst, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    return len(out)


def main():
    ok = True
    for src_name, work_dir in PAIRS:
        src = os.path.join(MOD, src_name)
        if not os.path.exists(src):
            print('[缺] 模板不存在: %s' % src)
            ok = False
            continue
        target_dir = os.path.join(WORK, work_dir)
        if not os.path.isdir(target_dir):
            print('[缺] 工作副本不存在: %s' % target_dir)
            ok = False
            continue
        dst = os.path.join(WORK, work_dir + '.mod')
        n = rewrite(src, dst, target_dir.replace(os.sep, '/'))
        print('[写出] %s（%d 行）  path -> %s' % (dst, n, target_dir))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
