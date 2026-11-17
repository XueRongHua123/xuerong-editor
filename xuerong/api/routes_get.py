# -*- coding: utf-8 -*-
"""GET 路由的注册汇总（P5：实体已搬进 handlers/）。

实体按域拆进 xuerong/api/handlers/：map_h / content_h / system_h /
state_country_h / focus_h / ai_h / misc_h。本文件只剩两件事：

1. 把 `dispatch_get` 以旧名字 `dispatch` 暴露出去——focus_editor.py:8577 与
   tests/routes_smoke.py 都走 `routes_get.dispatch(...)` 这个路径。
2. import `handlers`，让各域的 `@get` / `@prefix` 装饰器真的执行一遍。

前缀的注册顺序由 handlers/__init__.py 末尾显式排序保证，不依赖 import 次序。
"""
from xuerong.api.router import dispatch_get as dispatch
from xuerong.api import handlers  # noqa: F401  触发七个域的 @get / @prefix 注册

__all__ = ["dispatch"]
