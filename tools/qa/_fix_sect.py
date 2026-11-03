# -*- coding: utf-8 -*-
"""把 loc 里误写的字面 \\u00a7 换成真正的 § 字符。

坑：ops_bash 的 heredoc 会把 \\ 吃成 \，所以之前 ``'\\\\u00a7'`` 到 Python 手里变成了 `§`，
匹配不上文件里的字面反斜杠。这里用 chr(92) 拼反斜杠，避开所有转义。
"""
import io

BS = chr(92)
SEC = chr(0xA7)
LITERAL = BS + 'u00a7'          # 文件里真实的六个字符

for p in ('mods/muvluvCNsub_xuerong/localisation/simp_chinese/replace/'
          'zz_mvlv119_un_l_simp_chinese.yml',
          'mods/muvluvCNsub_xuerong/localisation/english/replace/'
          'zz_mvlv119_un_l_english.yml'):
    s = io.open(p, encoding='utf-8-sig').read()
    n = s.count(LITERAL)
    if n:
        s = s.replace(LITERAL, SEC)
    io.open(p, 'w', encoding='utf-8-sig', newline='').write(s)
    b = open(p, 'rb').read()
    bom = b.startswith(b'\xef\xbb\xbf')
    if bom:
        b = b[3:]
    t = b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    open(p, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + t)
    print('%-40s 替换 %d 处' % (p.split('/')[-1], n))

# 核对
for p in ('mods/muvluvCNsub_xuerong/localisation/simp_chinese/replace/'
          'zz_mvlv119_un_l_simp_chinese.yml',):
    for ln in io.open(p, encoding='utf-8-sig'):
        if 'mvlv_un_mem_name_perm' in ln:
            print('结果:', repr(ln.strip()))
