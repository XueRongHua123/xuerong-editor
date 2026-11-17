# -*- coding: utf-8 -*-
"""POST 路由的注册汇总（P4：151 条按域拆进 handlers/ 之后，这里只剩兼容层）。

函数实体在 xuerong/api/handlers/ 下按业务域分文件。本模块保留的原因：
focus_editor.py 与 tests/routes_smoke.py 都用 `xuerong.api.routes_post` 这个路径，
且 do_POST 调用 routes_post.dispatch(...)。
"""
from xuerong.api.router import dispatch_post as dispatch
from xuerong.api import handlers  # noqa: F401  触发 7 个域的 @post 注册

__all__ = ["dispatch"]
