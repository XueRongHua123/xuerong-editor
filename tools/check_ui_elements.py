# -*- coding: utf-8 -*-
"""打包前检查：页面 JS 里 getElementById 引用的元素必须都在 HTML 中定义。
用法：python work/check_ui_elements.py
退出码非 0 表示存在缺失元素，禁止打包。
"""
import io, re, sys, os

WORK = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(WORK, "focus_editor_index.html")

s = io.open(HTML, encoding="utf-8").read()
ids = set(re.findall(r'id="([^"]+)"', s))
refs = set(re.findall(r"getElementById\('([^']+)'\)", s))
missing = sorted(refs - ids)

print("id 数:", len(ids), " 引用数:", len(refs))
if missing:
    print("缺失元素:", missing)
    sys.exit(1)
print("OK: 所有 getElementById 引用都存在")
