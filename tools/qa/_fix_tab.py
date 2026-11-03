# -*- coding: utf-8 -*-
"""修 _patch_desc.py 留下的 [TAB] 占位：换成源码里的 \\t。"""
import io

P = 'work/qa/_build_submod.py'
s = io.open(P, encoding='utf-8').read()
n = s.count('[TAB]')
s = s.replace('[TAB]', '\\' + 't')
io.open(P, 'w', encoding='utf-8').write(s)
print('替换 %d 处 [TAB]' % n)

chk = io.open(P, encoding='utf-8').read()
print('残留 [TAB]:', chk.count('[TAB]'))
# 用 AST 确认还能编译
import ast
ast.parse(chk)
print('语法 OK')

# 真跑一遍模板，看生成结果
ns = {}
src = chk
exec(compile(ast.parse(src), P, 'exec'), ns)  # 会执行 main? 不会，__name__ 不是 __main__
print('---- 生成的 descriptor ----')
print(ns['DESC'])
