# -*- coding: utf-8 -*-
"""按域拆的 handler：misc / focus / state / country / tech / idea ...

每个 handler 只做「取参数 → 调 model → 返回 dict」，不写 HTTP 细节。
P4 搬 POST（151 条），P5 搬 GET（56 条精确 + 6 条前缀）。
"""
from xuerong.api.handlers import (  # noqa: F401  触发七个域的 @post / @get 注册
    focus_h, state_country_h, map_h, content_h, world_mod_h, ai_h, system_h, misc_h)

# 六条前缀路由（/index、/help、/api/data、/icons/、/web/、/mascot/）分在 misc_h /
# system_h / map_h 三个文件里，光靠 import 次序凑不出 dispatch_get 需要的命中顺序。
# 这里按目标顺序原地排一次：dispatch_get 只看 GET_PREFIXES 的列表顺序，排完就
# 与模块 import 顺序无关，后面谁往哪个文件加前缀都不影响既有命中。
from xuerong.api.router import GET_PREFIXES as _GET_PREFIXES

_PREFIX_ORDER = ("/index", "/help", "/api/data", "/icons/", "/web/", "/mascot/")
_GET_PREFIXES.sort(
    key=lambda kv: (_PREFIX_ORDER.index(kv[0]) if kv[0] in _PREFIX_ORDER
                    else len(_PREFIX_ORDER)))
