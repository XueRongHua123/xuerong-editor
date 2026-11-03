# -*- coding: utf-8 -*-
"""一次性补丁：把 _build_submod.py 的 DESC 换成新的（用 DISPLAY_NAME + picture + tags）。

按位置切片替换，不对字符串里的转义形式做假设。
跑完自查：DESC 里应出现 DISPLAY_NAME、picture、Gameplay。
"""
import io
import re

P = 'work/qa/_build_submod.py'
s = io.open(P, encoding='utf-8').read()

start = s.index("DESC = '''")
end = s.index('def md5_of', start)
old = s[start:end]

new = '''DESC = ''' + "'''" + '''name="%s"
version="%s"
tags={
[TAB]"Alternative History"
[TAB]"Gameplay"
[TAB]"Sound"
}
picture="thumbnail.png"
supported_version="1.19.*"
dependencies={
[TAB]"muvluvCN"
[TAB]"muvluvCNsub"
}
''' + "'''" + ''' % (DISPLAY_NAME, VERSION)


'''.replace('[TAB]', '\\t')

s = s[:start] + new + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)

print('替换前 %d 字符，替换后 %d 字符' % (len(old), len(new)))
chk = io.open(P, encoding='utf-8').read()
for token in ('DISPLAY_NAME, VERSION', 'picture="thumbnail.png"', '"Gameplay"', '"Sound"'):
    print('  %-28s %s' % (token, 'OK' if token in chk else '缺'))
print()
print(re.search(r"DESC = .*?VERSION\)", chk, re.S).group(0))
