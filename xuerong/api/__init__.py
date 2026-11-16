# -*- coding: utf-8 -*-
"""HTTP 层：路由表 + 按域拆的 handler。随便 import 下层。

这里**必须** import 两个 routes_*：路由表靠装饰器在 import 时注册，
不 import 就一张空表。`xuerong/__init__.py` 那条「包初始化不 import 子模块」
只针对 model/core（为了 `import xuerong.state` 不拖整条链），不适用于这里——
`xuerong.api` 只有门面在 import，拖不动别的东西。
"""
from xuerong.api import routes_get, routes_post  # noqa: F401  触发路由注册
